# RootCause

[![CI](https://github.com/Mouryan-J/RootCause/actions/workflows/ci.yml/badge.svg)](https://github.com/Mouryan-J/RootCause/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Deploy](https://img.shields.io/badge/backend-render-46E3B7.svg)](https://rootcause-api.onrender.com)
[![Frontend](https://img.shields.io/badge/frontend-vercel-black.svg)](https://root-cause-psi.vercel.app)

**Autonomous Incident RCA & Response Copilot**

A multi-agent AI system that investigates production incidents and produces ranked root cause hypotheses with evidence — automatically.

**Live demo:** https://root-cause-psi.vercel.app

---

## Features

- **Multi-agent RCA pipeline** — LangGraph supervisor routes through triage → retrieval → RCA → remediation agents in sequence
- **Hybrid RAG retrieval** — BM25 + Qdrant vector search fused with Reciprocal Rank Fusion, then Cohere reranked for precision
- **Service dependency graph** — Neo4j graph of upstream/downstream service relationships, visualized on the results page
- **Ranked root causes** — 1–3 hypotheses with confidence scores (0–100%), evidence citations, and contributing factors
- **Remediation steps** — concrete, numbered fix steps referencing matched runbooks
- **Live results polling** — results page updates every 2 seconds until analysis completes
- **Incident history** — browse all past incidents with severity, status, and relative timestamps
- **LLM observability** — every agent call traced in Langfuse with token counts and cost per incident
- **Redis caching** — completed analyses cached for 30 minutes, eliminating repeat DB hits
- **CI/CD** — GitHub Actions runs ruff lint and 17 pytest unit tests on every push

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

## What it does

Submit a production incident (title, service, severity, logs) and RootCause will:

1. **Triage** — classify severity and extract signals from logs
2. **Retrieve** — find relevant runbooks via hybrid BM25 + vector search (Qdrant + Cohere)
3. **Analyze** — generate ranked root cause hypotheses with confidence scores and evidence
4. **Remediate** — produce concrete remediation steps referencing matched runbooks

Results stream back in real time via polling. All past incidents are browsable in the history view.

---

## Architecture

```
Browser (Next.js on Vercel)
        │
        ▼
FastAPI backend (Render)
        │
   ┌────┴────────────────────────────┐
   │         LangGraph pipeline      │
   │                                 │
   │  ┌──────────┐  ┌────────────┐  │
   │  │  Triage  │→ │ Retrieval  │  │
   │  └──────────┘  └─────┬──────┘  │
   │                       │        │
   │              BM25 + Qdrant     │
   │              + Cohere rerank   │
   │                       │        │
   │                  ┌────▼──────┐ │
   │                  │    RCA    │ │
   │                  └────┬──────┘ │
   │                       │        │
   │               ┌───────▼─────┐  │
   │               │ Remediation │  │
   │               └─────────────┘  │
   └─────────────────────────────────┘
        │                │
   PostgreSQL          Qdrant Cloud
   (incidents)         (runbook vectors)
```

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

---

## Phases

- [x] Phase 0 — Project Discovery
- [x] Phase 1 — Dataset Research
- [x] Phase 2 — System Design
- [x] Phase 3 — Project Initialization
- [x] Phase 4 — Backend Development
- [x] Phase 5 — RAG System
- [x] Phase 6 — Multi-Agent System
- [x] Phase 7 — Databases
- [x] Phase 8 — Frontend
- [x] Phase 9 — Evaluation Framework
- [x] Phase 10 — Observability
- [x] Phase 11 — Cost Optimization
- [x] Phase 12 — Testing
- [x] Phase 13 — CI/CD
- [x] Phase 14 — Deployment
- [x] Phase 15 — Portfolio Polish
- [x] Phase 16 — Final Review
