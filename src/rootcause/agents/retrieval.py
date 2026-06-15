"""
Retrieval worker node.

No LLM — calls the HybridRetriever (BM25 + Qdrant + RRF + optional Cohere rerank)
and stores the top results in state for downstream agents.
"""
from __future__ import annotations

import logging

from rootcause.agents.state import IncidentState
from rootcause.core.config import get_settings
from rootcause.rag.retriever import get_retriever

log = logging.getLogger(__name__)

TOP_K = 6


def retrieval_node(state: IncidentState) -> dict:
    query = state.get("search_query") or state.get("description") or state.get("title", "")
    settings = get_settings()

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
                # Truncate content for prompt — full text lives in the result object
                "excerpt": r.content[:1200],
            }
            for r in results
        ]
        log.info("Retrieved %d docs for query: %.80s", len(docs), query)

    except Exception as exc:
        log.error("Retrieval failed: %s", exc)
        docs = []

    completed = list(state.get("completed_steps") or []) + ["retrieval"]
    return {
        "retrieved_docs": docs,
        "completed_steps": completed,
    }
