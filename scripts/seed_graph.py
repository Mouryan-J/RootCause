"""
Seed Neo4j with a sample service dependency graph.

Usage:
    uv run python scripts/seed_graph.py

Requires NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env
"""
from __future__ import annotations

from neo4j import GraphDatabase

from rootcause.core.config import get_settings

SERVICES = [
    "api-gateway",
    "auth-service",
    "payment-service",
    "cart-service",
    "order-service",
    "recommendation-service",
    "notification-service",
    "postgres",
    "redis",
    "ml-model-service",
    "email-service",
]

DEPENDENCIES: list[tuple[str, str, str]] = [
    # (from, to, dep_type)
    ("api-gateway", "auth-service", "service"),
    ("api-gateway", "payment-service", "service"),
    ("api-gateway", "recommendation-service", "service"),
    ("api-gateway", "cart-service", "service"),
    ("auth-service", "postgres", "database"),
    ("auth-service", "redis", "cache"),
    ("payment-service", "postgres", "database"),
    ("payment-service", "redis", "cache"),
    ("payment-service", "auth-service", "service"),
    ("payment-service", "order-service", "service"),
    ("cart-service", "redis", "cache"),
    ("cart-service", "postgres", "database"),
    ("cart-service", "payment-service", "service"),
    ("order-service", "postgres", "database"),
    ("order-service", "payment-service", "service"),
    ("order-service", "notification-service", "service"),
    ("recommendation-service", "postgres", "database"),
    ("recommendation-service", "redis", "cache"),
    ("recommendation-service", "ml-model-service", "service"),
    ("notification-service", "redis", "cache"),
    ("notification-service", "email-service", "service"),
]


def seed(uri: str, user: str, password: str) -> None:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Clear existing data
        session.run("MATCH (n) DETACH DELETE n")
        print("Cleared existing graph.")

        # Create service nodes
        for name in SERVICES:
            session.run("MERGE (:Service {name: $name})", name=name)
        print(f"Created {len(SERVICES)} service nodes.")

        # Create dependency edges
        for from_svc, to_svc, dep_type in DEPENDENCIES:
            session.run(
                """
                MATCH (a:Service {name: $from_svc}), (b:Service {name: $to_svc})
                MERGE (a)-[:DEPENDS_ON {dep_type: $dep_type}]->(b)
                """,
                from_svc=from_svc,
                to_svc=to_svc,
                dep_type=dep_type,
            )
        print(f"Created {len(DEPENDENCIES)} dependency edges.")

    driver.close()
    print("Done. Graph seeded successfully.")


if __name__ == "__main__":
    settings = get_settings()
    if not settings.neo4j_uri:
        raise SystemExit("NEO4J_URI not set in .env")
    seed(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
