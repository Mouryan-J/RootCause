# AI_CONTEXT.md — RootCause

> Read this file first. It tells you what exists, what is stubbed, and what is next.

## Project
Autonomous Incident RCA and Response Copilot.  
Multi-agent AI system (LangGraph) + Hybrid RAG (Qdrant) + FastAPI backend + Next.js frontend.

## Current Phase
**Phase 3 — Project Initialization — COMPLETE**  
Next: Phase 4 — Backend Development

## What exists and works
| Path | Status | Notes |
|------|--------|-------|
| `pyproject.toml` | DONE | All deps declared, ruff + pytest configured |
| `src/rootcause/core/config.py` | DONE | pydantic-settings, loads .env |
| `src/rootcause/core/logging.py` | DONE | structlog, JSON in prod, pretty in dev |
| `docs/decisions/` | DONE | 4 ADRs from Phase 2 |
| `.env.example` | DONE | Template with all required keys |
| `.gitignore` | DONE | Python, Node, secrets, data/raw |

## What is stubbed (directory exists, code not yet written)
| Path | Will contain |
|------|-------------|
| `src/rootcause/api/` | FastAPI app — Phase 4 |
| `src/rootcause/agents/` | LangGraph agents — Phase 6 |
| `src/rootcause/rag/` | Retrieval pipeline — Phase 5 |
| `src/rootcause/db/` | DB connections — Phase 7 |
| `tests/` | pytest tests — Phase 12 |
| `data/runbooks/` | 25 synthetic markdown runbooks — Phase 5 |
| `frontend/` | Next.js app — Phase 8 |
| `.github/workflows/` | CI/CD — Phase 13 |
| `docker-compose.yml` | All services — Phase 7 |

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
```
