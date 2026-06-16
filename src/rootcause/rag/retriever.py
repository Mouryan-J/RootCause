"""
Hybrid retriever: BM25 + Qdrant Cloud dense vectors, fused with RRF,
then optional Cohere reranking. Falls back to BM25-only if Qdrant/Cohere
embeddings are unavailable.
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


def _cohere_embed(texts: list[str], api_key: str, input_type: str = "search_document") -> list[list[float]] | None:
    """Generate embeddings via Cohere API. Returns None on failure."""
    try:
        import cohere
        co = cohere.Client(api_key=api_key)
        response = co.embed(
            texts=texts,
            model="embed-english-v3.0",
            input_type=input_type,
        )
        return response.embeddings
    except Exception as exc:
        log.warning("cohere_embed_failed: %s", exc)
        return None


class HybridRetriever:
    def __init__(self) -> None:
        self._docs: list[Document] = []
        self._bm25: BM25Okapi | None = None
        self._qdrant_collection = "rootcause_runbooks"
        self._use_vectors = False
        self._cohere_api_key: str = ""
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
        try:
            from rootcause.core.config import get_settings
            from rootcause.db.qdrant_client import get_qdrant

            settings = get_settings()
            qdrant = get_qdrant()
            if qdrant is None or not settings.cohere_api_key:
                log.info("Qdrant or Cohere key unavailable — using BM25 only")
                return

            self._cohere_api_key = settings.cohere_api_key

            # Check if collection already exists and has vectors
            import asyncio
            loop = asyncio.get_event_loop()
            collections = loop.run_until_complete(qdrant.get_collections())
            existing = [c.name for c in collections.collections]

            if self._qdrant_collection not in existing:
                log.info("Indexing %d docs into Qdrant Cloud via Cohere embeddings...", len(self._docs))
                embeddings = _cohere_embed(
                    [d.content[:2048] for d in self._docs],
                    api_key=self._cohere_api_key,
                )
                if embeddings is None:
                    log.warning("Cohere embedding failed — using BM25 only")
                    return

                from qdrant_client.models import Distance, PointStruct, VectorParams
                dim = len(embeddings[0])
                loop.run_until_complete(qdrant.create_collection(
                    collection_name=self._qdrant_collection,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                ))
                points = [
                    PointStruct(
                        id=i,
                        vector=embeddings[i],
                        payload={"doc_id": self._docs[i].doc_id, "title": self._docs[i].title},
                    )
                    for i in range(len(self._docs))
                ]
                loop.run_until_complete(qdrant.upsert(
                    collection_name=self._qdrant_collection,
                    points=points,
                ))
                log.info("Qdrant Cloud vector index ready (%d docs)", len(self._docs))
            else:
                log.info("Qdrant Cloud collection already exists — reusing")

            self._use_vectors = True

        except Exception as exc:
            log.warning("Vector search unavailable, using BM25 only: %s", exc)
            self._use_vectors = False

    def retrieve(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        self._init()
        assert self._bm25 is not None

        bm25_scores = self._bm25.get_scores(_tokenize(query))
        bm25_ranking = sorted(range(len(self._docs)), key=lambda i: bm25_scores[i], reverse=True)
        rankings: list[list[int]] = [bm25_ranking]

        if self._use_vectors and self._cohere_api_key:
            try:
                from rootcause.db.qdrant_client import get_qdrant
                import asyncio
                qdrant = get_qdrant()
                if qdrant:
                    query_vec = _cohere_embed(
                        [query],
                        api_key=self._cohere_api_key,
                        input_type="search_query",
                    )
                    if query_vec:
                        loop = asyncio.get_event_loop()
                        hits = loop.run_until_complete(qdrant.search(
                            collection_name=self._qdrant_collection,
                            query_vector=query_vec[0],
                            limit=top_k * 2,
                        ))
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
            import cohere

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
