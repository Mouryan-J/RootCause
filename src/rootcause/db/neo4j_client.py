from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_driver: AsyncDriver | None = None


async def init_neo4j() -> None:
    global _driver
    settings = get_settings()
    if not settings.neo4j_uri:
        raise RuntimeError("NEO4J_URI not set — skipping Neo4j")
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


async def get_service_dependencies(service_name: str) -> dict:
    """
    Return upstream and downstream dependencies for a service.

    Returns:
        {
            "depends_on": [{"name": str, "dep_type": str}, ...],
            "depended_on_by": [{"name": str, "dep_type": str}, ...]
        }
    """
    driver = get_neo4j()
    if not driver:
        return {"depends_on": [], "depended_on_by": []}

    try:
        async with driver.session() as session:
            # What does this service depend on?
            downstream = await session.run(
                """
                MATCH (s:Service {name: $name})-[r:DEPENDS_ON]->(dep:Service)
                RETURN dep.name AS name, r.dep_type AS dep_type
                """,
                name=service_name,
            )
            depends_on = [{"name": r["name"], "dep_type": r["dep_type"]} async for r in downstream]

            # What depends on this service?
            upstream = await session.run(
                """
                MATCH (caller:Service)-[r:DEPENDS_ON]->(s:Service {name: $name})
                RETURN caller.name AS name, r.dep_type AS dep_type
                """,
                name=service_name,
            )
            depended_on_by = [{"name": r["name"], "dep_type": r["dep_type"]} async for r in upstream]

        log.info(
            "neo4j_graph_fetched",
            service=service_name,
            depends_on=len(depends_on),
            depended_on_by=len(depended_on_by),
        )
        return {"depends_on": depends_on, "depended_on_by": depended_on_by}

    except Exception as exc:
        log.warning("neo4j_query_failed", service=service_name, error=str(exc))
        return {"depends_on": [], "depended_on_by": []}
