from qdrant_client import AsyncQdrantClient

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_client: AsyncQdrantClient | None = None


async def init_qdrant() -> None:
    global _client
    settings = get_settings()
    _client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    await _client.get_collections()
    log.info("qdrant_ready", host=settings.qdrant_host, port=settings.qdrant_port)


async def close_qdrant() -> None:
    global _client
    if _client:
        await _client.close()
        log.info("qdrant_closed")


def get_qdrant() -> AsyncQdrantClient | None:
    return _client
