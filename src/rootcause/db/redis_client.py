import redis.asyncio as aioredis

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis
    settings = get_settings()
    _redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
    await _redis.ping()
    log.info("redis_ready")


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        log.info("redis_closed")


def get_redis() -> aioredis.Redis | None:
    return _redis
