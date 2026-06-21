# RootCauseAnalysis

[![CI](https://github.com/Mouryan-J/RootCause/actions/workflows/ci.yml/badge.svg)](https://github.com/Mouryan-J/RootCause/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Deploy](https://img.shields.io/badge/backend-render-46E3B7.svg)](https://rootcause-api.onrender.com)
[![Frontend](https://img.shields.io/badge/frontend-vercel-black.svg)](https://root-cause-psi.vercel.app)

**Autonomous Incident RCA & Response Copilot**

A multi-agent AI system that investigates production incidents and produces ranked root cause hypotheses with evidence, automatically.

**Live demo:** https://root-cause-psi.vercel.app

---

## Features

- **Multi-agent RCA pipeline**: LangGraph supervisor routes through triage → retrieval → RCA → remediation agents in sequence
- **Hybrid RAG retrieval**: BM25 + Qdrant vector search fused with Reciprocal Rank Fusion, then Cohere reranked for precision
- **Service dependency graph**: Neo4j graph of upstream/downstream service relationships, visualized on the results page
- **Ranked root causes**: 1–3 hypotheses with confidence scores (0–100%), evidence citations, and contributing factors
- **Remediation steps**: concrete, numbered fix steps referencing matched runbooks
- **Live results polling**: results page updates every 2 seconds until analysis completes
- **Incident history**: browse all past incidents with severity, status, and relative timestamps
- **LLM observability**: every agent call traced in Langfuse with token counts and cost per incident
- **Redis caching**: completed analyses cached for 30 minutes, eliminating repeat DB hits
- **CI/CD**: GitHub Actions runs ruff lint and 27 pytest unit tests on every push

---

## Retrieval Evaluation

Evaluated on 50 queries across database, cache, and infrastructure categories with ground-truth runbook mappings.

| Metric | BM25-only | Hybrid (BM25 + Qdrant + Cohere) | Improvement |
|---|---|---|---|
| Recall@1 | 84.0% | 96.0% | **+12.0%** |
| Recall@3 | 92.0% | 98.0% | **+6.0%** |
| Recall@5 | 98.0% | 98.0% | +0.0% |
| MRR | 89.5% | 97.0% | **+7.5%** |

Hybrid retrieval surfaces the correct runbook as the **top result 96% of the time**, compared to 84% for BM25 alone.

> Run `uv run python scripts/run_eval.py` to reproduce.

---

## RCA Reasoning Evaluation

The retrieval benchmark above tests document search — its queries largely reuse the target runbook's own wording, so a high score mostly proves the embedding/BM25 stack finds the right document. It does not prove the system reaches the correct *diagnosis*.

A separate, harder benchmark tests that: 8 hand-authored incidents (`rca_eval_v2.jsonl`) across 7 distinct failure classes (resource contention, feature-flag regressions, schema mismatches, dependency-version skew, cascading third-party latency, and a cache-invalidation race condition), where the title and logs never name the failure mode and every wrong candidate cause shares literal evidence with the real one — not a trivially-nominal distractor. A mechanism-matching LLM judge (a different model than the one being graded, hardened against scoring a vague restatement as correct) checks whether the system's top-ranked hypothesis names the actual causal mechanism, not just a topically-related guess.

| | Top-1 Accuracy | Top-3 Accuracy | Hallucination Rate | Fallback Rate |
|---|---|---|---|---|
| Bare LLM, no retrieval/graph | 100.0% (n=7) | 100.0% (n=7) | 7.1%* | 12.5% |
| Full RootCause pipeline | 100.0% (n=8) | 100.0% (n=8) | 0.0% | 0.0% |

\* both flagged citations were synthesized paraphrases of real evidence, not fabrications — see `docs/evaluation.md` for detail. End-to-end pipeline latency: 11–20s per incident, median ~15s.

**Honest takeaway:** a bare LLM call ties the full multi-agent pipeline on raw accuracy whenever the logs already name the services involved — at this scale (n=8), the extra machinery doesn't change the verdict. So a follow-up probe (`rca_eval_graph_test.jsonl`, 3 incidents) removed every service name from the logs, leaving only a *type signature* (e.g. a lock-wait-timeout error implies a database, without saying which one). Result: **the bare LLM never once named the actual dependency (0/3)** — it could only describe it generically ("downstream transactional store"). **The full pipeline, using its Neo4j dependency-graph lookup, named it correctly every time (3/3)** — "lock contention on postgres," "Redis cache eviction," "degraded latency to payment-service." That's the one concrete, measured point where the architecture does something a bare LLM structurally can't: turn a type-correct shrug into an actionable, specific diagnosis. The original 18-incident benchmark and its since-superseded numbers are kept in `docs/evaluation.md` for transparency.

The full writeup — methodology, worked examples, two real production bugs this evaluation process found and fixed, and honest limitations — is in [`docs/evaluation.md`](docs/evaluation.md).

> Run `uv run python scripts/run_rca_eval.py` to reproduce (makes real LLM calls).

---

## How it works

1. **Submit**: paste an incident title, affected service, severity, and raw logs into the form
2. **Triage**: the Triage agent (gpt-4o-mini) classifies severity and extracts key signals to build a search query
3. **Retrieve**: the Retrieval agent runs BM25 + Qdrant vector search in parallel, fuses the rankings with RRF, then Cohere reranks the top results; Neo4j is also queried for the service's upstream/downstream dependencies
4. **Analyze**: the RCA agent (claude-haiku) reads the retrieved runbooks and dependency context to produce 1–3 ranked root cause hypotheses with confidence scores and evidence citations
5. **Remediate**: the Remediation agent (gpt-4o-mini) writes numbered fix steps referencing the matched runbooks
6. **Result**: the page polls every 2 seconds and renders the full report once complete; the service dependency graph is visualized inline; the result is cached in Redis for 30 minutes

All past incidents are browsable in the history view.

---

## Architecture

![Architecture Diagram](docs/architecture.svg)

<details>
<summary>Mermaid diagram</summary>

```mermaid
flowchart TD
    User(["👤 User\nNext.js · Vercel"])

    subgraph API["FastAPI Backend · Render"]
        direction TB
        GW["API Gateway\nCORS · Auth · Logging"]

        subgraph LG["LangGraph Pipeline"]
            direction TB
            CO["Coordinator"]
            TR["Triage\ngpt-4o-mini"]
            RT["Retrieval\nBM25 + Qdrant + Cohere"]
            RC["RCA\nclaude-haiku"]
            RM["Remediation\ngpt-4o-mini"]

            CO --> TR --> CO
            CO --> RT --> CO
            CO --> RC --> CO
            CO --> RM --> CO
        end

        GW --> LG
    end

    subgraph DBs["Data Layer"]
        PG[("PostgreSQL\nIncident records")]
        RD[("Redis\nResult cache")]
        QD[("Qdrant Cloud\nRunbook vectors")]
        N4[("Neo4j Aura\nService graph")]
    end

    subgraph OBS["Observability"]
        LF["Langfuse\nLLM tracing"]
    end

    User -- "POST /incidents/analyze" --> GW
    RT -- "BM25 + vector search" --> QD
    RT -- "Service dependencies" --> N4
    LG -- "Store result" --> PG
    LG -- "Cache result" --> RD
    LG -- "Trace LLM calls" --> LF
    GW -- "GET /incidents/:id" --> PG
    GW -- "GET /incidents/:id (cached)" --> RD
    API -- "Results + graph" --> User
```

</details>

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, Tailwind CSS, deployed on Vercel |
| Backend | Python 3.12, FastAPI, deployed on Render |
| AI orchestration | LangGraph (supervisor/worker multi-agent) |
| LLM | Claude Haiku via Anthropic API |
| RAG retrieval | BM25 (rank-bm25) + Qdrant Cloud vectors + Cohere rerank |
| Embeddings | Cohere embed-english-v3.0 |
| Database | PostgreSQL (SQLAlchemy async) |
| Cache | Redis (optional, graceful fallback) |
| Observability | OpenTelemetry + structlog |
| CI | GitHub Actions (ruff lint + pytest) |

---

## Project structure

```
rootcause/
├── src/rootcause/
│   ├── agents/          # LangGraph agents (triage, retrieval, rca, remediation, graph)
│   ├── api/             # FastAPI routes, schemas, middleware
│   ├── core/            # Config, security, telemetry (Langfuse)
│   ├── db/              # SQLAlchemy models, PostgreSQL, Redis, Neo4j clients
│   └── rag/             # Corpus loader, BM25 + Qdrant hybrid retriever
├── frontend/
│   └── src/
│       ├── app/         # Next.js pages (submit, results, history)
│       ├── components/  # ResultsPoller, ServiceGraphView, form components
│       └── lib/         # API client
├── data/
│   ├── corpus/          # 252 runbooks and postmortems (source documents)
│   └── eval/            # retrieval_eval.jsonl (50 queries) + rca_eval.jsonl (18 incidents, v1) + rca_eval_v2.jsonl (8 incidents, hardened schema)
├── scripts/
│   ├── seed_graph.py    # Populates Neo4j with 11 services + 21 dependency edges
│   ├── run_eval.py      # BM25 vs Hybrid retrieval benchmark
│   └── run_rca_eval.py  # RCA reasoning benchmark (bare LLM vs full pipeline, LLM-judged)
├── docs/
│   └── evaluation.md    # RCA reasoning eval methodology, results, worked failure cases
└── tests/unit/          # 27 unit tests (config, security, RAG, RCA parsing, grounding filter, retry/fallback logic)
```

---

## Running locally

**Prerequisites:** Python 3.12+, [uv](https://github.com/astral-sh/uv), Node.js 20+

```bash
# Clone
git clone https://github.com/Mouryan-J/RootCause.git
cd RootCause

# Backend
cp .env.example .env          # fill in API keys
uv sync --extra dev
uv run python -m rootcause.main

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

**Required env vars** (see `.env.example`):

```
ANTHROPIC_API_KEY=...
DATABASE_URL=postgresql+asyncpg://...
QDRANT_URL=https://xxx.qdrant.io:6333
QDRANT_API_KEY=...
COHERE_API_KEY=...
```

---

## Running tests

```bash
uv run pytest tests/unit/ -v
uv run ruff check src/ tests/
```

17 unit tests covering config, security, RAG retrieval, and RCA agent parsing.

