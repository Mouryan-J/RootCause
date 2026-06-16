"""
Retrieval evaluation script.

Measures Recall@K and MRR for BM25-only vs Hybrid (BM25 + Qdrant + Cohere rerank).

Usage:
    uv run python scripts/run_eval.py
"""
from __future__ import annotations

import json
from pathlib import Path

from rootcause.core.config import get_settings
from rootcause.rag.loader import load_corpus
from rootcause.rag.retriever import BM25Okapi, HybridRetriever, _tokenize

EVAL_PATH = Path("data/eval/retrieval_eval.jsonl")
TOP_K_VALUES = [1, 3, 5]


def load_eval() -> list[dict]:
    with open(EVAL_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def recall_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
    retrieved_k = set(retrieved[:k])
    expected_set = set(expected)
    return 1.0 if retrieved_k & expected_set else 0.0


def reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
    expected_set = set(expected)
    for rank, doc_id in enumerate(retrieved, 1):
        if doc_id in expected_set:
            return 1.0 / rank
    return 0.0


def run_bm25_eval(queries: list[dict]) -> dict:
    docs = load_corpus()
    bm25 = BM25Okapi([_tokenize(d.content) for d in docs])
    doc_ids = [d.doc_id for d in docs]

    recalls = {k: [] for k in TOP_K_VALUES}
    mrr_scores = []

    for q in queries:
        scores = bm25.get_scores(_tokenize(q["query"]))
        ranking = sorted(range(len(docs)), key=lambda i: scores[i], reverse=True)
        retrieved = [doc_ids[i] for i in ranking]

        for k in TOP_K_VALUES:
            recalls[k].append(recall_at_k(retrieved, q["expected_runbooks"], k))
        mrr_scores.append(reciprocal_rank(retrieved, q["expected_runbooks"]))

    return {
        **{f"recall@{k}": round(sum(recalls[k]) / len(recalls[k]), 3) for k in TOP_K_VALUES},
        "mrr": round(sum(mrr_scores) / len(mrr_scores), 3),
    }


def run_hybrid_eval(queries: list[dict]) -> dict:
    retriever = HybridRetriever()
    settings = get_settings()

    recalls = {k: [] for k in TOP_K_VALUES}
    mrr_scores = []

    for i, q in enumerate(queries):
        results = retriever.retrieve(q["query"], top_k=10)
        results = retriever.rerank(
            query=q["query"],
            results=results,
            cohere_api_key=settings.cohere_api_key,
            top_k=10,
        )
        retrieved = [r.doc_id for r in results]

        for k in TOP_K_VALUES:
            recalls[k].append(recall_at_k(retrieved, q["expected_runbooks"], k))
        mrr_scores.append(reciprocal_rank(retrieved, q["expected_runbooks"]))

        if (i + 1) % 10 == 0:
            print(f"  {i + 1}/{len(queries)} queries done...")

    return {
        **{f"recall@{k}": round(sum(recalls[k]) / len(recalls[k]), 3) for k in TOP_K_VALUES},
        "mrr": round(sum(mrr_scores) / len(mrr_scores), 3),
    }


def print_results(name: str, results: dict) -> None:
    print(f"\n{'─' * 40}")
    print(f"  {name}")
    print(f"{'─' * 40}")
    for k in TOP_K_VALUES:
        pct = results[f"recall@{k}"] * 100
        bar = "█" * int(pct / 5)
        print(f"  Recall@{k}  {pct:5.1f}%  {bar}")
    print(f"  MRR        {results['mrr'] * 100:5.1f}%")


def by_category(queries: list[dict], retriever_fn) -> dict:
    cats: dict[str, list[dict]] = {}
    for q in queries:
        cats.setdefault(q["category"], []).append(q)
    return {cat: retriever_fn(qs) for cat, qs in cats.items()}


if __name__ == "__main__":
    queries = load_eval()
    print(f"\nRunning evaluation on {len(queries)} queries...\n")

    print("[ 1/2 ] BM25-only...")
    bm25_results = run_bm25_eval(queries)
    print_results("BM25-only", bm25_results)

    print("\n[ 2/2 ] Hybrid (BM25 + Qdrant + Cohere rerank)...")
    hybrid_results = run_hybrid_eval(queries)
    print_results("Hybrid (BM25 + Qdrant + Cohere rerank)", hybrid_results)

    print(f"\n{'═' * 40}")
    print("  Improvement (Hybrid vs BM25)")
    print(f"{'═' * 40}")
    for k in TOP_K_VALUES:
        delta = (hybrid_results[f"recall@{k}"] - bm25_results[f"recall@{k}"]) * 100
        sign = "+" if delta >= 0 else ""
        print(f"  Recall@{k}  {sign}{delta:.1f}%")
    mrr_delta = (hybrid_results["mrr"] - bm25_results["mrr"]) * 100
    sign = "+" if mrr_delta >= 0 else ""
    print(f"  MRR        {sign}{mrr_delta:.1f}%")
    print()
