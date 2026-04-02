# ─────────────────────────────────────────────
# config.py
# ─────────────────────────────────────────────

TARGET_SITES = [
    {
        "name": "위비티_웹IT",
        "label": "위비티",             # UI에 표시될 소스명
        "url": "https://www.wevity.com/?c=find&s=1&gub=1&cidx=20",
        "base_url": "https://www.wevity.com",
        "category": "웹/모바일/IT",
    },
    {
        "name": "위비티_게임SW",
        "label": "위비티",
        "url": "https://www.wevity.com/?c=find&s=1&gub=1&cidx=21",
        "base_url": "https://www.wevity.com",
        "category": "게임/소프트웨어",
    },
    {
        "name": "콘테스트코리아_IT",
        "label": "콘테스트코리아",
        "url": "https://www.contestkorea.com/sub/list.php?int_gbn=1&Txt_bcode=030310001",
        "base_url": "https://www.contestkorea.com",
        "category": "학문/과학/IT",
    },
]

DELAY_BETWEEN_PAGES = 2.5
DELAY_BETWEEN_SITES = 5.0
DELAY_JITTER        = 1.5

HEADLESS        = True
BROWSER_TIMEOUT = 30_000

OUTPUT_FILE = "contests.json"
