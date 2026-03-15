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
    if site_name == "링커리어":
        return _parse_linkareer
    raise ValueError(f"등록된 파서가 없습니다: {site_name!r}")


# ── 위비티 파서 ────────────────────────────────────────────
#
# [확인된 사실]
# - IT 카테고리 URL: ?c=find&s=1&gub=1&cidx=20 (웹/모바일/IT)
#                   ?c=find&s=1&gub=1&cidx=21 (게임/소프트웨어)
# - 상세 페이지 링크 href에는 반드시 "gbn=view" 포함
#   예) ?c=find&s=1&gub=1&cidx=20&gbn=view&gp=1&ix=105706
# - 같은 ix에 썸네일 링크(텍스트 없음) + 제목 링크(텍스트 있음) 2개 존재
#   → ix 기준으로 그룹핑, 가장 긴 텍스트(제목)를 선택해야 함

_WEVITY_JS = r"""
() => {
    const results = [];
    // 공지사항(.top)은 건너뛰고 실제 리스트만 타겟팅
    const listItems = document.querySelectorAll('.list li:not(.top), .list tr:not(.top)');

    for (const item of listItems) {
        const titleLink = item.querySelector('a[href*="gbn=view"]');
        if (!titleLink) continue;

        // 링크 안의 'N(새글)' 아이콘 등 자식 태그의 텍스트를 빼고 순수 제목 텍스트만 추출
        const name = Array.from(titleLink.childNodes)
            .filter(node => node.nodeType === Node.TEXT_NODE)
            .map(node => node.textContent.trim())
            .join('')
            .replace(/\s+/g, ' ');

        if (name.length < 3 || /^\d+$/.test(name)) continue;

        const url = titleLink.href;
        const org = item.querySelector('.organ')?.textContent.trim() || '';
        const deadlineText = item.querySelector('.day, .time')?.textContent.trim() || '';

        const ddayMatch = item.textContent.match(/D[-–]\d+/i) || item.textContent.match(/오늘마감/);
        const dday = ddayMatch ? ddayMatch[0] : '';

        results.push({
            name: name,
            url: url,
            org: org,
            dday: dday,
            deadline: deadlineText
        });
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
    log.info("위비티 [%s]: %d 건 수집", site.get("category", ""), len(contests))
    return contests


# ── 링커리어 파서 ──────────────────────────────────────────
#
# [확인된 사실]
# - Next.js SPA, JS 실행 필요
# - 공모전 상세 URL: /activity/[숫자]
# - 채용공고도 같은 /activity/ 경로 사용
#
# [해결책]
# - /list/contest 페이지는 공모전 목록 페이지 → 메인 리스트 내 링크만 수집
# - 채용 관련 키워드("채용", "취업", "인턴", "신입", "경력", "공채")가
#   주변 텍스트에 있으면 제외
# - 공모전 관련 키워드("공모전", "대회", "공모", "해커톤", "경진")가
#   있으면 우선 포함

# 채용공고 판별 키워드
_JOB_KEYWORDS = {"채용", "취업", "인턴", "신입", "경력", "공채", "채용공고",
                  "모집공고", "recruit", "hiring", "job"}

_LINKAREER_JS = r"""
() => {
    // IT 공모전과 무관한 채용, 국비교육 등 필터링 강화
    const JOB_KW = ["채용", "취업", "인턴", "신입", "경력", "공채", "부트캠프", "국비", "교육", "수강생", "채용공고"];
    const results = [];
    const seen = new Set();

    const links = document.querySelectorAll('a[href^="/activity/"]');

    for (const a of links) {
        const href = a.getAttribute('href');
        if (seen.has(href)) continue;

        // innerText는 화면에 렌더링된 대로 줄바꿈을 유지해줘서 데이터를 쪼개기 좋아
        const cardText = a.innerText || '';
        if (cardText.length < 10) continue; // 데이터가 덜 로드된 카드는 패스

        // 채용 공고 필터링
        if (JOB_KW.some(kw => cardText.includes(kw))) continue;

        const lines = cardText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

        let org = '';
        let name = '';
        let dday = '';

        // D-day 추출
        const ddayMatch = cardText.match(/D[-–]\d+/i) || cardText.match(/오늘\s*마감/);
        if (ddayMatch) dday = ddayMatch[0];

        // 보통 카드 내에서 가장 긴 텍스트가 공모전 제목이야 (조회수, D-day 등 제외)
        let maxLen = 0;
        let titleIdx = -1;
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].match(/D[-–]\d+/i)) continue;
            if (lines[i].includes('조회') || lines[i].includes('댓글') || lines[i].includes('스크랩')) continue;

            if (lines[i].length > maxLen) {
                maxLen = lines[i].length;
                titleIdx = i;
            }
        }

        if (titleIdx !== -1) {
            name = lines[titleIdx].replace(/^\[.*?\]\s*/, ''); // [공모전] 같은 말머리 제거
            // 주최기관은 보통 제목 바로 윗줄에 있음
            if (titleIdx > 0 && lines[titleIdx - 1].length < 30) {
                org = lines[titleIdx - 1];
            }
        } else {
            name = lines[0] || '제목 없음';
        }

        seen.add(href);
        results.push({
            name: name,
            url: new URL(href, location.href).href,
            org: org,
            dday: dday,
            deadline: ''
        });
    }
    return results;
}
"""

async def _parse_linkareer(page: Page, site: dict) -> list[dict[str, Any]]:
    log.info("링커리어: SPA 렌더링 대기 중…")
    try:
        await page.wait_for_function(
            r"() => Array.from(document.querySelectorAll('a[href]'))"
            r".some(a => /^\/activity\/\d+/.test(a.getAttribute('href')))",
            timeout=25_000,
        )
    except Exception:
        log.warning("링커리어: 공모전 링크 미발견")
        return []

    # 충분히 렌더링될 때까지 추가 대기
    await page.wait_for_timeout(2_000)

    raw: list[dict] = await page.evaluate(_LINKAREER_JS)
    contests = []
    for item in raw:
        contests.append({
            "name":     item["name"],
            "org":      item.get("org", ""),
            "deadline": item.get("deadline", ""),
            "dday":     item.get("dday", ""),
            "url":      item["url"],
            "source":   site.get("label", "링커리어"),
            "category": site.get("category", "IT개발"),
        })
    log.info("링커리어: %d 건 수집 (채용공고 제외)", len(contests))
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
            log.warning("[%s] robots.txt 에 의해 스킵: %s", name, url)
            return []

        parsed      = urlparse(url)
        base        = f"{parsed.scheme}://{parsed.netloc}"
        crawl_delay = max(self.robots.crawl_delay(base), DELAY_BETWEEN_PAGES)

        log.info("[%s] 크롤링 시작: %s", name, url)
        page = await new_stealth_page(self.context)

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            parser  = _get_parser(name)
            results = await parser(page, site)   # site 전체를 넘겨 label·category 활용
        except Exception as exc:
            log.error("[%s] 크롤링 실패: %s", name, exc)
            results = []
        finally:
            await page.close()
            await random_delay(crawl_delay, DELAY_JITTER)

        return results
