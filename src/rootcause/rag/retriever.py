"""
Hybrid retriever: BM25 + Qdrant in-memory dense vectors, fused with RRF,
then optional Cohere reranking. Falls back to BM25-only if Qdrant/fastembed
is unavailable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from rootcause.rag.loader import Document, load_corpus

log = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    doc_id: str
    title: str
    content: str
    source: str
    score: float
    metadata: dict


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion over multiple ranked doc-index lists."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    def __init__(self) -> None:
        self._docs: list[Document] = []
        self._bm25: BM25Okapi | None = None
        self._qdrant = None
        self._qdrant_collection = "rootcause"
        self._use_vectors = False
        self._initialized = False

    def _init(self) -> None:
        if self._initialized:
            return
        log.info("Initializing retriever corpus...")
        self._docs = load_corpus()
        self._bm25 = BM25Okapi([_tokenize(d.content) for d in self._docs])
        log.info("Loaded %d documents into BM25", len(self._docs))
        self._try_init_vectors()
        self._initialized = True

    def _try_init_vectors(self) -> None:
        # fastembed loads a ~300MB embedding model — too large for free-tier RAM.
        # BM25 retrieval is used instead.
        self._use_vectors = False
        log.info("Vector search disabled — using BM25 only")

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        self._init()
        assert self._bm25 is not None

        bm25_scores = self._bm25.get_scores(_tokenize(query))
        bm25_ranking = sorted(range(len(self._docs)), key=lambda i: bm25_scores[i], reverse=True)
        rankings: list[list[int]] = [bm25_ranking]

        if self._use_vectors and self._qdrant is not None:
            try:
                hits = self._qdrant.query(
                    collection_name=self._qdrant_collection,
                    query_text=query,
                    limit=top_k * 2,
                )
                vec_ranking = [h.id for h in hits if isinstance(h.id, int)]
                if vec_ranking:
                    rankings.append(vec_ranking)
            except Exception as exc:
                log.debug("Vector query failed: %s", exc)

        fused = _rrf(rankings)

        results: list[RetrievalResult] = []
        for idx, score in fused[:top_k]:
            if idx >= len(self._docs):
                continue
            d = self._docs[idx]
            results.append(
                RetrievalResult(
                    doc_id=d.doc_id,
                    title=d.title,
                    content=d.content,
                    source=d.source,
                    score=score,
                    metadata=d.metadata,
                )
            )
        return results

    def rerank(
        self, query: str, results: list[RetrievalResult], cohere_api_key: str, top_k: int = 5
    ) -> list[RetrievalResult]:
        """Optionally rerank results with Cohere. Returns input unchanged on failure."""
        if not cohere_api_key or not results:
            return results[:top_k]
        try:
            import cohere  # type: ignore[import]

            co = cohere.Client(api_key=cohere_api_key)
            response = co.rerank(
                model="rerank-english-v3.0",
                query=query,
                documents=[r.content[:512] for r in results],
                top_n=top_k,
            )
            reranked = [results[hit.index] for hit in response.results]
            for i, r in enumerate(reranked):
                r.score = response.results[i].relevance_score
            return reranked
        except Exception as exc:
            log.debug("Cohere rerank failed, using fused order: %s", exc)
            return results[:top_k]


_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
