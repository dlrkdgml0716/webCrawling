# ─────────────────────────────────────────────
# src/robots_checker.py  — robots.txt 파싱 및 접근 허용 여부 확인
# ─────────────────────────────────────────────

from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from src.utils import get_logger

log = get_logger("robots")


class RobotsChecker:
    """
    사이트별 robots.txt 를 가져와 캐싱하고,
    특정 경로의 크롤링 허용 여부를 반환합니다.
    """

    USER_AGENT = "*"

    def __init__(self) -> None:
        self._cache: dict[str, RobotFileParser] = {}

    def _get_parser(self, base_url: str) -> RobotFileParser:
        """base_url 에 대한 RobotFileParser 를 반환 (캐시 우선)."""
        if base_url not in self._cache:
            robots_url = urljoin(base_url, "/robots.txt")
            log.info("robots.txt 로드: %s", robots_url)
            rp = RobotFileParser(robots_url)
            try:
                rp.read()
            except Exception as exc:
                log.warning("robots.txt 로드 실패 (%s): %s", robots_url, exc)
            self._cache[base_url] = rp
        return self._cache[base_url]

    def is_allowed(self, url: str) -> bool:
        """해당 URL 을 크롤해도 되는지 robots.txt 기준으로 확인합니다."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._get_parser(base_url)

        allowed = rp.can_fetch(self.USER_AGENT, url)
        if not allowed:
            log.warning("robots.txt 에 의해 차단됨: %s", url)
        return allowed

    def crawl_delay(self, base_url: str) -> float:
        """robots.txt 에 명시된 Crawl-delay 값을 반환합니다 (없으면 0.0)."""
        rp = self._get_parser(base_url)
        delay = rp.crawl_delay(self.USER_AGENT) or 0.0
        return float(delay)
