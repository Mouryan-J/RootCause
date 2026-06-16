"""
Retrieval worker node.

No LLM — calls the HybridRetriever (BM25 + Qdrant + RRF + optional Cohere rerank)
and queries Neo4j for service dependency context.
"""
from __future__ import annotations

import asyncio
import logging

from rootcause.agents.state import IncidentState
from rootcause.core.config import get_settings
from rootcause.db.neo4j_client import get_service_dependencies
from rootcause.rag.retriever import get_retriever

log = logging.getLogger(__name__)

TOP_K = 6


def _fetch_graph(service_name: str) -> dict:
    """Run the async Neo4j query safely from within a sync LangGraph node."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, get_service_dependencies(service_name)).result()
        return loop.run_until_complete(get_service_dependencies(service_name))
    except RuntimeError:
        return asyncio.run(get_service_dependencies(service_name))
    except Exception as exc:
        log.warning("graph_fetch_error: %s", exc)
        return {"depends_on": [], "depended_on_by": []}


def retrieval_node(state: IncidentState) -> dict:
    query = state.get("search_query") or state.get("description") or state.get("title", "")
    service = state.get("service", "")
    settings = get_settings()

    # RAG retrieval
    try:
        retriever = get_retriever()
        results = retriever.retrieve(query, top_k=TOP_K * 2)
        results = retriever.rerank(
            query=query,
            results=results,
            cohere_api_key=settings.cohere_api_key,
            top_k=TOP_K,
        )
        docs = [
            {
                "doc_id": r.doc_id,
                "title": r.title,
                "source": r.source,
                "score": round(r.score, 4),
                "excerpt": r.content[:1200],
            }
            for r in results
        ]
        log.info("Retrieved %d docs for query: %.80s", len(docs), query)
    except Exception as exc:
        log.error("Retrieval failed: %s", exc)
        docs = []

    # Neo4j service dependency graph
    service_graph = _fetch_graph(service) if service else {"depends_on": [], "depended_on_by": []}
    if service_graph["depends_on"] or service_graph["depended_on_by"]:
        log.info(
            "Graph context: %s depends on %d services, depended on by %d",
            service,
            len(service_graph["depends_on"]),
            len(service_graph["depended_on_by"]),
        )

    completed = list(state.get("completed_steps") or []) + ["retrieval"]
    return {
        "retrieved_docs": docs,
        "service_graph": service_graph,
        "completed_steps": completed,
    }
