# AI_CONTEXT.md — RootCause

> Read this file first. It tells you what exists, what is stubbed, and what is next.

## Project
Autonomous Incident RCA and Response Copilot.  
Multi-agent AI system (LangGraph) + Hybrid RAG (Qdrant) + FastAPI backend + Next.js frontend.

## Current Phase
**Phase 11 — Deployment (Render + Vercel) — COMPLETE**  
Next: Phase 12 — Tests (pytest)

## What exists and works
| Path | Status | Notes |
|------|--------|-------|
| `pyproject.toml` | DONE | All deps declared, ruff + pytest configured |
| `src/rootcause/core/config.py` | DONE | pydantic-settings, loads .env |
| `src/rootcause/core/logging.py` | DONE | structlog, JSON in prod, pretty in dev |
| `src/rootcause/core/telemetry.py` | DONE — Phase 9 | OTel init, FastAPI instrumentation, Langfuse callback factory |
| `src/rootcause/core/security.py` | DONE — Phase 10 | require_api_key FastAPI dependency (disabled when API_SECRET_KEY is empty) |
| `src/rootcause/main.py` | DONE | uvicorn entry point, creates app |
| `src/rootcause/api/app.py` | DONE | FastAPI factory, CORS + request-ID + logging middleware |
| `src/rootcause/api/routes/health.py` | DONE | GET /health |
| `src/rootcause/api/routes/incidents.py` | DONE | POST /incidents/analyze, GET /incidents/{id} |
| `src/rootcause/api/schemas/health.py` | DONE | HealthResponse |
| `src/rootcause/api/schemas/incident.py` | DONE | IncidentRequest, IncidentResponse, AnalysisResult, RootCause, Severity |
| `docs/decisions/` | DONE | 4 ADRs from Phase 2 |
| `.env.example` | DONE | Template with all required keys |
| `.gitignore` | DONE | Python, Node, secrets, data/raw |

## What is stubbed (directory exists, code not yet written)
| Path | Will contain |
|------|-------------|
| `src/rootcause/api/` | DONE — Phase 4 |
| `src/rootcause/agents/` | DONE — Phase 6 (graph, triage, retrieval, rca, remediation) |
| `src/rootcause/rag/` | DONE — Phase 6 (loader, hybrid retriever: BM25+Qdrant+RRF+Cohere) |
| `src/rootcause/db/` | DONE — Phase 7 (postgres, redis, qdrant, neo4j clients + Incident model) |
| `tests/` | pytest tests — Phase 12 |
| `data/runbooks/` | DONE — 25 markdown runbooks (RB-001 to RB-025) |
| `data/postmortems/` | DONE — 227 real postmortems from danluu/post-mortems (PM-001 to PM-227), 5 categories |
| `data/eval/` | DONE — retrieval_eval.jsonl, 50 queries mapped to expected runbooks, 3 difficulty levels |
| `scripts/fetch_postmortems.py` | DONE — fetches and parses danluu/post-mortems README into normalized markdown |
| `scripts/build_eval.py` | DONE — generates the eval JSONL from hardcoded ground-truth query→runbook mappings |
| `frontend/` | DONE — Phase 8 (Next.js 16, React 19, Tailwind 4, incident form + live results poller) |
| `.github/workflows/` | CI/CD — Phase 13 |
| `docker-compose.yml` | DONE — Phase 7 (postgres, redis, qdrant, neo4j, api) |
| `Dockerfile` | DONE — Phase 11 (added data/ copy) |
| `render.yaml` | DONE — Phase 11 (Render Blueprint: web + managed postgres + redis) |
| `frontend/vercel.json` | DONE — Phase 11 |

## Architecture decisions (do not revisit)
- Star topology: workers never talk to each other, all via coordinator
- 4 databases: PostgreSQL (records), Redis (cache), Qdrant (vectors), Neo4j (graph)
- Model routing: gpt-4o-mini for agents, claude-haiku-4-5-20251001 for RCA synthesis
- Hybrid RAG: BM25 + dense vectors fused with RRF, then Cohere reranker

## Environment
- Python 3.12, managed by uv
- Virtual env at `.venv/` (not committed)
- `.env` must be created from `.env.example` (not committed)
- Windows development, Render + Vercel deployment

## Key import paths
```python
from rootcause.core.config import get_settings
from rootcause.core.logging import get_logger, configure_logging
from rootcause.api.app import create_app
from rootcause.api.schemas import IncidentRequest, AnalysisResult, AnalysisStatus
from rootcause.agents import run_analysis          # Phase 6
from rootcause.rag import get_retriever            # Phase 6
```

## Agent pipeline (Phase 6)
Star topology — coordinator routes to each worker in sequence, workers never communicate directly.

```
POST /incidents/analyze
  → BackgroundTask: run_analysis()
      → coordinator → triage (gpt-4o-mini) → coordinator
      → coordinator → retrieval (BM25+Qdrant+RRF+Cohere) → coordinator
      → coordinator → rca (claude-haiku-4-5-20251001) → coordinator
      → coordinator → remediation (gpt-4o-mini) → coordinator → END
  → GET /incidents/{id} polls AnalysisResult
```

All LLM nodes fall back gracefully if API keys are absent.
