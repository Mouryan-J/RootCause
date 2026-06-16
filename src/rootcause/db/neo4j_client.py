from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase, GraphDatabase

from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger

log = get_logger(__name__)

_driver: AsyncDriver | None = None
_uri: str = ""
_auth: tuple[str, str] = ("", "")


async def init_neo4j() -> None:
    global _driver, _uri, _auth
    settings = get_settings()
    if not settings.neo4j_uri:
        raise RuntimeError("NEO4J_URI not set — skipping Neo4j")
    _uri = settings.neo4j_uri
    _auth = (settings.neo4j_user, settings.neo4j_password)
    _driver = AsyncGraphDatabase.driver(_uri, auth=_auth)
    await _driver.verify_connectivity()
    log.info("neo4j_ready", uri=_uri)


async def close_neo4j() -> None:
    global _driver
    if _driver:
        await _driver.close()
        log.info("neo4j_closed")


def get_neo4j() -> AsyncDriver | None:
    return _driver


def get_service_dependencies(service_name: str) -> dict:
    """
    Return upstream and downstream dependencies for a service.
    Uses sync driver — safe to call from background threads (LangGraph nodes).

    Returns:
        {
            "depends_on": [{"name": str, "dep_type": str}, ...],
            "depended_on_by": [{"name": str, "dep_type": str}, ...]
        }
    """
    if not _uri:
        return {"depends_on": [], "depended_on_by": []}

    try:
        driver = GraphDatabase.driver(_uri, auth=_auth)
        with driver.session() as session:
            depends_on = session.run(
                """
                MATCH (s:Service {name: $name})-[r:DEPENDS_ON]->(dep:Service)
                RETURN dep.name AS name, r.dep_type AS dep_type
                """,
                name=service_name,
            ).data()

            depended_on_by = session.run(
                """
                MATCH (caller:Service)-[r:DEPENDS_ON]->(s:Service {name: $name})
                RETURN caller.name AS name, r.dep_type AS dep_type
                """,
                name=service_name,
            ).data()

        driver.close()
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
