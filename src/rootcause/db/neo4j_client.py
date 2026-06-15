from neo4j import AsyncDriver, AsyncGraphDatabase

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_driver: AsyncDriver | None = None


async def init_neo4j() -> None:
    global _driver
    settings = get_settings()
    _driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    await _driver.verify_connectivity()
    log.info("neo4j_ready", uri=settings.neo4j_uri)


async def close_neo4j() -> None:
    global _driver
    if _driver:
        await _driver.close()
        log.info("neo4j_closed")


def get_neo4j() -> AsyncDriver | None:
    return _driver
