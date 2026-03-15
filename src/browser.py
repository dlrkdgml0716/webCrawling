# ─────────────────────────────────────────────
# src/browser.py  — Playwright 브라우저 설정 (Stealth 모듈 제거)
# ─────────────────────────────────────────────

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config import HEADLESS, BROWSER_TIMEOUT
from src.utils import get_logger

log = get_logger("browser")

# 실제 크롬 브라우저처럼 보이기 위한 User-Agent
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def create_browser() -> tuple:
    pw = await async_playwright().start()
    browser: Browser = await pw.chromium.launch(
        headless=HEADLESS,
        args=[
            "--disable-blink-features=AutomationControlled", # 이게 핵심 스텔스 기능
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context: BrowserContext = await browser.new_context(
        user_agent=_USER_AGENT,
        viewport={"width": 1280, "height": 800},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        extra_http_headers={
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    context.set_default_timeout(BROWSER_TIMEOUT)
    log.info("브라우저 시작 완료 (headless=%s)", HEADLESS)
    return pw, browser, context


async def new_stealth_page(context: BrowserContext) -> Page:
    """
    기본 설정이 적용된 새 페이지를 반환합니다.
    """
    page: Page = await context.new_page()
    return page