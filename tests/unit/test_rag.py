import sys
import types

from rootcause.rag.retriever import (
    MIN_RERANK_SCORE,
    HybridRetriever,
    RetrievalResult,
    _rrf,
    _tokenize,
)


def test_tokenize_lowercases():
    assert _tokenize("Hello World") == ["hello", "world"]


def test_tokenize_splits_on_space():
    assert _tokenize("a b c") == ["a", "b", "c"]


def test_rrf_single_ranking():
    ranking = [0, 1, 2]
    result = _rrf([ranking])
    indices = [idx for idx, _ in result]
    assert indices[0] == 0  # highest ranked doc should have highest score


def test_rrf_fuses_two_rankings():
    # Both rankings agree on doc 0 being first
    r1 = [0, 1, 2]
    r2 = [0, 2, 1]
    result = _rrf([r1, r2])
    assert result[0][0] == 0  # doc 0 should still win


def test_rrf_scores_are_positive():
    result = _rrf([[0, 1, 2], [1, 0, 2]])
    for _, score in result:
        assert score > 0


def test_retriever_falls_back_to_bm25_without_qdrant(monkeypatch):
    retriever = HybridRetriever()
    # Patch load_corpus to return minimal docs
    from rootcause.rag.loader import Document
    fake_docs = [
        Document(doc_id="RB-001", title="Postgres runbook", content="postgres connection pool", source="runbook"),
        Document(doc_id="RB-002", title="Redis runbook", content="redis memory eviction", source="runbook"),
    ]
    monkeypatch.setattr("rootcause.rag.retriever.load_corpus", lambda: fake_docs)
    monkeypatch.setattr("rootcause.core.config.get_settings", lambda: type("S", (), {"qdrant_url": "", "cohere_api_key": ""})())

    results = retriever.retrieve("postgres connection issues", top_k=2)
    assert len(results) > 0
    assert isinstance(results[0], RetrievalResult)
    assert results[0].doc_id in ("RB-001", "RB-002")


def _fake_cohere_module(relevance_scores: list[float]):
    """Build a fake `cohere` module whose Client().rerank() returns the given
    per-document relevance scores, in document order."""
    hit_cls = types.SimpleNamespace
    response = types.SimpleNamespace(
        results=[hit_cls(index=i, relevance_score=s) for i, s in enumerate(relevance_scores)]
    )

    class FakeClient:
        def __init__(self, api_key):
            pass

        def rerank(self, model, query, documents, top_n):
            return response

    fake_module = types.ModuleType("cohere")
    fake_module.Client = FakeClient
    return fake_module


def test_rerank_drops_results_below_min_score(monkeypatch):
    monkeypatch.setitem(sys.modules, "cohere", _fake_cohere_module([0.9, 0.01, 0.5]))
    retriever = HybridRetriever()
    results = [
        RetrievalResult(doc_id=f"D{i}", title="t", content="c", source="runbook", score=0.0, metadata={})
        for i in range(3)
    ]
    reranked = retriever.rerank("query", results, cohere_api_key="fake-key", top_k=3)
    assert all(r.score >= MIN_RERANK_SCORE for r in reranked)
    assert [r.doc_id for r in reranked] == ["D0", "D2"]


def test_rerank_returns_empty_when_all_below_min_score(monkeypatch):
    monkeypatch.setitem(sys.modules, "cohere", _fake_cohere_module([0.01, 0.02]))
    retriever = HybridRetriever()
    results = [
        RetrievalResult(doc_id=f"D{i}", title="t", content="c", source="runbook", score=0.0, metadata={})
        for i in range(2)
    ]
    reranked = retriever.rerank("query", results, cohere_api_key="fake-key", top_k=2)
    assert reranked == []
