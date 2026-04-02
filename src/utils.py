# ─────────────────────────────────────────────
# src/utils.py  — 공통 유틸리티 (딜레이, 로깅)
# ─────────────────────────────────────────────

import asyncio
import logging
import random
import sys


def get_logger(name: str) -> logging.Logger:
    """모든 모듈이 공유하는 포맷의 Logger를 반환합니다."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if hasattr(handler.stream, 'reconfigure'):
            handler.stream.reconfigure(encoding='utf-8')
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(name)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


async def random_delay(base: float, jitter: float = 1.0) -> None:
    """
    base 초 + 0 ~ jitter 초 사이의 랜덤 시간만큼 대기합니다.
    사람처럼 비규칙적인 요청 간격을 흉내 내어 봇 감지를 우회합니다.
    """
    delay = base + random.uniform(0, jitter)
    log = get_logger("utils")
    log.info("딜레이 %.2f초 대기 중…", delay)
    await asyncio.sleep(delay)
