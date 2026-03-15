# ─────────────────────────────────────────────
# main.py  — 크롤러 진입점
# ─────────────────────────────────────────────

import asyncio

from config import DELAY_BETWEEN_SITES, DELAY_JITTER, OUTPUT_FILE, TARGET_SITES
from src.browser import create_browser
from src.scraper import ContestScraper
from src.storage import save_contests
from src.utils import get_logger, random_delay

log = get_logger("main")


async def run() -> None:
    all_contests: list[dict] = []

    pw, browser, context = await create_browser()

    try:
        scraper = ContestScraper(context)

        for i, site in enumerate(TARGET_SITES):
            log.info("=" * 50)
            log.info("사이트 %d/%d: %s", i + 1, len(TARGET_SITES), site["name"])
            log.info("=" * 50)

            contests = await scraper.scrape(site)
            all_contests.extend(contests)

            # 마지막 사이트가 아니면 사이트 간 딜레이
            if i < len(TARGET_SITES) - 1:
                await random_delay(DELAY_BETWEEN_SITES, DELAY_JITTER)

    finally:
        await browser.close()
        await pw.stop()

    save_contests(all_contests, OUTPUT_FILE)
    log.info("전체 수집 완료: %d 건", len(all_contests))


if __name__ == "__main__":
    asyncio.run(run())
