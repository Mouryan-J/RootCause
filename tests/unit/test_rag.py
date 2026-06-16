from rootcause.rag.retriever import HybridRetriever, RetrievalResult, _rrf, _tokenize


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
