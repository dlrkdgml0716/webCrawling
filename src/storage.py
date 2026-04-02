# ─────────────────────────────────────────────
# src/storage.py  — 수집 데이터 JSON 저장
# ─────────────────────────────────────────────

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import get_logger

log = get_logger("storage")


def _deduplicate(contests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for c in contests:
        key = c["name"].strip()
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def save_contests(contests: list[dict[str, Any]], filepath: str = "contests.json") -> None:
    """
    대회 목록을 JSON 파일로 저장합니다.
    기존 파일이 있으면 덮어씁니다.

    저장 형식:
    {
        "crawled_at": "<ISO 8601 타임스탬프>",
        "total": <건수>,
        "contests": [ {...}, ... ]
    }
    """
    contests = _deduplicate(contests)
    output = {
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "total": len(contests),
        "contests": contests,
    }
    path = Path(filepath)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("저장 완료: %s (%d 건)", path.resolve(), len(contests))


def load_contests(filepath: str = "contests.json") -> list[dict[str, Any]]:
    """
    저장된 contests.json 을 불러옵니다.
    파일이 없으면 빈 리스트를 반환합니다.
    """
    path = Path(filepath)
    if not path.exists():
        log.warning("파일 없음: %s", filepath)
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("contests", [])
