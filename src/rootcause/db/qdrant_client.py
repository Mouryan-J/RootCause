from qdrant_client import AsyncQdrantClient

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_client: AsyncQdrantClient | None = None


async def init_qdrant() -> None:
    global _client
    settings = get_settings()
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL not set — skipping Qdrant")
    _client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    await _client.get_collections()
    log.info("qdrant_ready", url=settings.qdrant_url)


async def close_qdrant() -> None:
    global _client
    if _client:
        await _client.close()
        log.info("qdrant_closed")


def get_qdrant() -> AsyncQdrantClient | None:
    return _client
