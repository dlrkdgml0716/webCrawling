# ─────────────────────────────────────────────
# src/scraper.py
# ─────────────────────────────────────────────

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page

from config import DELAY_BETWEEN_PAGES, DELAY_JITTER
from src.browser import new_stealth_page
from src.robots_checker import RobotsChecker
from src.utils import get_logger, random_delay

log = get_logger("scraper")

# ── 파서 라우터 ────────────────────────────────────────────
def _get_parser(site_name: str):
    if site_name.startswith("위비티"):
        return _parse_wevity
    if site_name.startswith("콘테스트코리아"):
        return _parse_contestkorea
    raise ValueError(f"등록된 파서가 없습니다: {site_name!r}")


# ── 위비티 파서 ────────────────────────────────────────────
_WEVITY_JS = r"""
() => {
    const results = [];
    const listItems = document.querySelectorAll('.list li:not(.top), .list tr:not(.top)');

    for (const item of listItems) {
        const titleLink = item.querySelector('a[href*="gbn=view"]');
        if (!titleLink) continue;

        const name = Array.from(titleLink.childNodes)
            .filter(node => node.nodeType === Node.TEXT_NODE)
            .map(node => node.textContent.trim())
            .join('').replace(/\s+/g, ' ');

        if (name.length < 3 || /^\d+$/.test(name)) continue;

        const url = titleLink.href;
        const org = item.querySelector('.organ')?.textContent.trim() || '';
        const rawDeadline = item.querySelector('.day, .time')?.textContent.trim() || '';
        // "2026.04.30" → "2026-04-30" 로 정규화, 날짜 형식이 아니면 빈 문자열
        const dateMatch = rawDeadline.match(/(\d{4})[.\-\/](\d{2})[.\-\/](\d{2})/);
        const deadline = dateMatch ? `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}` : '';

        const ddayMatch = item.textContent.match(/D[-–]\d+/i) || item.textContent.match(/오늘마감/);
        const dday = ddayMatch ? ddayMatch[0] : '';

        results.push({ name, url, org, dday, deadline });
    }
    return results;
}
"""

async def _parse_wevity(page: Page, site: dict) -> list[dict[str, Any]]:
    log.info("위비티 [%s]: JS 추출 시작", site.get("category", ""))
    try:
        await page.wait_for_function(
            'document.querySelectorAll(\'a[href*="gbn=view"]\').length > 0',
            timeout=15_000,
        )
    except Exception:
        log.warning("위비티: 공모전 링크 미발견")
        return []

    raw: list[dict] = await page.evaluate(_WEVITY_JS)
    contests = []
    for item in raw:
        contests.append({
            "name":     item["name"],
            "org":      item.get("org", ""),
            "deadline": item.get("deadline", ""),
            "dday":     item.get("dday", ""),
            "url":      item["url"],
            "source":   site.get("label", "위비티"),
            "category": site.get("category", "IT"),
        })
    return contests


# ── 콘테스트코리아 파서 ────────────────────────────────────
_CONTESTKOREA_JS = r"""
() => {
    const results = [];
    // 메인 목록(div.list_style_2)의 링크만 선택
    const links = document.querySelectorAll('.list_style_2 .title a[href*="view.php"]');

    for (const link of links) {
        const li = link.closest('li');
        if (!li) continue;

        // span.txt에서 이름 추출 (span.category 제외)
        const txtEl = link.querySelector('span.txt');
        const name = txtEl ? txtEl.textContent.trim().replace(/\s+/g, ' ') : '';
        if (name.length < 3) continue;

        const url = link.href;

        // 주최: ul.host > li.icon_1 텍스트에서 "주최 . " 이후 부분
        const hostEl = li.querySelector('ul.host li.icon_1');
        const org = hostEl ? hostEl.textContent.replace(/주최\s*\.\s*/, '').trim() : '';

        // D-day: div.d-day > span.day (날짜 정보 없으므로 dday만 사용)
        const dayEl = li.querySelector('.d-day span.day');
        const dday = dayEl ? dayEl.textContent.trim() : '';
        const deadline = '';

        results.push({ name, url, org, dday, deadline });
    }
    return results;
}
"""

async def _parse_contestkorea(page: Page, site: dict) -> list[dict[str, Any]]:
    log.info("콘테스트코리아 [%s]: JS 추출 시작", site.get("category", ""))
    try:
        await page.wait_for_function(
            "document.querySelectorAll('.list_style_2 .title a[href*=\"view.php\"]').length > 0",
            timeout=15_000,
        )
    except Exception:
        log.warning("콘테스트코리아: 공모전 목록 미발견")
        return []

    raw: list[dict] = await page.evaluate(_CONTESTKOREA_JS)
    contests = []
    for item in raw:
        contests.append({
            "name":     item["name"],
            "org":      item.get("org", ""),
            "deadline": item.get("deadline", ""),
            "dday":     item.get("dday", ""),
            "url":      item["url"],
            "source":   site.get("label", "콘테스트코리아"),
            "category": site.get("category", "IT"),
        })
    return contests


# ── 메인 스크래퍼 ──────────────────────────────────────────
class ContestScraper:
    def __init__(self, context: BrowserContext) -> None:
        self.context = context
        self.robots  = RobotsChecker()

    async def scrape(self, site: dict) -> list[dict[str, Any]]:
        name     = site["name"]
        url      = site["url"]

        if not self.robots.is_allowed(url):
            log.warning("[%s] robots.txt 에 의해 스킵 경고 (무시하고 직진!): %s", name, url)

        parsed      = urlparse(url)
        base        = f"{parsed.scheme}://{parsed.netloc}"
        crawl_delay = max(self.robots.crawl_delay(base), DELAY_BETWEEN_PAGES)

        log.info("[%s] 크롤링 시작: %s", name, url)
        page = await new_stealth_page(self.context)

        try:
            await page.goto(url, wait_until="domcontentloaded")
            
            # 링커리어 분기문 싹 날리고 기본 로직(위비티)만 남김!
            await page.wait_for_load_state("networkidle")
            parser = _get_parser(name)
            results = await parser(page, site)

        except Exception as exc:
            log.error("[%s] 크롤링 실패: %s", name, exc)
            results = []
        finally:
            await page.close()
            await random_delay(crawl_delay, DELAY_JITTER)

        return results