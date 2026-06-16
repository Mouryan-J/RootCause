# RootCause — Complete Build Journal

Everything that was built, why it was built that way, and what you learned at each step.
Use this as a reference whenever you want to revisit a decision or understand a concept.

---

## Table of Contents

- [Phase 0 — Project Discovery](#phase-0--project-discovery)
- [Phase 1 — Dataset Research](#phase-1--dataset-research)
- [Phase 2 — System Design](#phase-2--system-design)
- [Phase 3 — Project Initialization](#phase-3--project-initialization)
- [Phase 4 — Backend Development](#phase-4--backend-development)
- [Phase 5 — RAG System](#phase-5--rag-system)
- [Phase 6 — Multi-Agent System](#phase-6--multi-agent-system)
- [Phase 7 — Databases](#phase-7--databases)
- [Phase 8 — Frontend](#phase-8--frontend)
- [Phase 9 — Observability](#phase-9--observability)
- [Phase 10 — Auth & Security](#phase-10--auth--security)
- [Phase 11 — Deployment](#phase-11--deployment)
- [Phase 12 — Testing](#phase-12--testing)
- [Phase 13 — CI/CD](#phase-13--cicd)
- [Phase 14 — Incident History Page](#phase-14--incident-history-page)
- [Phase 15 — Portfolio Polish](#phase-15--portfolio-polish)
- [Phase 16 — Full Tool Integration](#phase-16--full-tool-integration)

---

## Phase 0 — Project Discovery

### What was decided
Build an **Autonomous Incident RCA (Root Cause Analysis) & Response Copilot**.

When something breaks in production (a server crash, a database slowdown, an API failing), on-call engineers spend hours manually reading logs, checking dashboards, and digging through runbooks to find the cause. This project automates that entire investigation using AI agents.

### Why this project
- Real-world problem that every engineering team faces
- Demonstrates multiple advanced AI/ML concepts in one place: multi-agent systems, RAG, vector search, graph databases
- Has measurable output (you can objectively evaluate if the root cause guess is correct)
- Something you can demo live and explain to a non-technical person in one sentence

### Key concept: What is a "production incident"?
A production incident is when something in a live system stops working correctly. Examples:
- "Our checkout page is returning 500 errors for 20% of users"
- "Database response time went from 10ms to 8 seconds"
- "The payment service is down"

The process of figuring out WHY it happened is called Root Cause Analysis.

---

## Phase 1 — Dataset Research

### What was done
Collected two types of documents to use as the knowledge base for the AI:

**Runbooks (25 files in `data/runbooks/`):**
Runbooks are step-by-step guides that tell engineers exactly what to do when a specific problem occurs. Example: `RB-003-redis-memory-exhaustion.md` tells you how to investigate and fix Redis running out of memory. These were written from scratch, covering the most common infrastructure failure patterns:
- PostgreSQL high connection count
- Redis memory exhaustion
- API 5xx error spikes
- Pod OOMKilled (out of memory killed)
- Kafka consumer lag
- SSL certificate expiry
- DNS resolution failures
- And 18 more

**Postmortems (227 files in `data/postmortems/`):**
Postmortems are public write-ups from real companies describing incidents they had and what they found. These came from real outages at GitHub, Google, Cloudflare, Amazon, Slack, Stripe, Discord, etc. The AI uses these to understand what real incidents look like and what causes them.

**Eval dataset (50 queries in `data/eval/retrieval_eval.jsonl`):**
50 example queries paired with which runbooks should be returned. Used later to measure how well the retrieval system works.

### Key concept: Why do you need a knowledge base?
LLMs (like GPT-4 or Claude) are trained on general internet text. They know a lot about databases and infrastructure in general, but they don't know your specific runbooks or your company's specific incident patterns. By giving the AI access to a curated set of runbooks and postmortems, you "ground" its answers in real, authoritative documents instead of hallucinated guesses.

---

## Phase 2 — System Design

### What was decided
Before writing a single line of code, the full architecture was designed:

```
User (browser)
    ↓
FastAPI backend
    ↓
LangGraph agent pipeline
    ├── Triage agent
    ├── Retrieval agent  ←── Qdrant Cloud + Neo4j
    ├── RCA agent
    └── Remediation agent
    ↓
PostgreSQL (store results)
Redis (cache results)
Langfuse (trace LLM calls)
```

### Key decisions made at this stage

**Why FastAPI and not Django/Flask?**
FastAPI is modern Python with built-in async support (important for calling multiple LLM APIs without blocking), automatic API documentation, and type safety via Pydantic. Flask is synchronous by default which would be slow for LLM calls. Django is overkill for an API-only backend.

**Why LangGraph and not LangChain directly?**
LangGraph models the agent pipeline as a graph (nodes = agents, edges = routing logic). This gives you precise control over which agent runs when and what happens if one fails. Plain LangChain chains are linear and harder to customize. LangGraph lets you define a "supervisor" that decides which worker to call next based on the current state.

**Why PostgreSQL and not just a file or SQLite?**
PostgreSQL is a real production database that handles concurrent reads/writes safely. SQLite would break with multiple requests at the same time. Files don't support querying. PostgreSQL also has excellent async Python support via `asyncpg`.

**Why Redis?**
Once an incident analysis is complete, the result doesn't change. If the user refreshes the page or the frontend polls again, re-running the entire 4-agent pipeline (which takes 15–30 seconds and costs API money) would be wasteful. Redis stores the completed result for 30 minutes so repeated fetches are instant and free.

**Why Qdrant for vector search?**
Qdrant is a purpose-built vector database. When you convert text into a vector (a list of numbers representing meaning), you can find similar documents by comparing vectors mathematically. Qdrant does this efficiently at scale. The alternative (storing vectors in PostgreSQL with pgvector) would have been slower and more complex to set up.

**Why Neo4j for the service graph?**
Neo4j is a graph database, meaning it stores relationships between things natively. The question "which services does `payment-service` depend on, and which services depend on it?" is trivial in Neo4j (`MATCH (s)-[:DEPENDS_ON]->(dep)`) but requires complex JOIN queries in a relational database.

---

## Phase 3 — Project Initialization

### What was done
Set up the Python project structure from scratch.

**Tool used: `uv`**
`uv` is a modern Python package manager (like pip, but 10–100x faster). Instead of `pip install`, you use `uv add`. Dependencies go in `pyproject.toml`.

**Directory structure created:**
```
src/rootcause/
├── agents/       # The AI agents
├── api/          # HTTP endpoints
├── core/         # Shared utilities (config, security)
├── db/           # Database connections
└── rag/          # Retrieval system
```

**Why `src/rootcause/` and not just `rootcause/`?**
The `src/` layout is a Python best practice. It prevents Python from accidentally importing your local development code instead of the installed package. It also makes it clear that `src/` contains source code, not scripts or data.

**Key file: `pyproject.toml`**
This is the modern Python project config file. It replaces `setup.py`, `requirements.txt`, and `setup.cfg`. It specifies:
- Project name and version
- Dependencies
- Python version requirement
- Tool configurations (linter, formatter, test runner)

---

## Phase 4 — Backend Development

### What was done
Built the FastAPI application skeleton.

**Key files:**
- `src/rootcause/main.py` — Entry point. Creates the FastAPI app and starts the server.
- `src/rootcause/api/app.py` — Wires together routes, middleware, CORS.
- `src/rootcause/core/config.py` — All environment variables loaded via pydantic-settings.
- `src/rootcause/api/routes/incidents.py` — The main endpoint: POST /incidents/analyze.
- `src/rootcause/api/schemas/incident.py` — Pydantic models for request/response shapes.

### Key concept: What is an API endpoint?
An endpoint is a URL that your frontend can call to trigger something on the backend. For example:
- `POST /incidents/analyze` — submit a new incident for analysis
- `GET /incidents/{id}` — get the result of a past analysis
- `GET /health` — check if the server is running

`POST` means you're sending data. `GET` means you're fetching data.

### Key concept: What is Pydantic?
Pydantic validates that data is the right shape. If the frontend sends `{ "title": "DB slow", "severity": "critical" }`, Pydantic checks that both fields exist and are strings. If something is missing or wrong type, FastAPI automatically returns a clear error. This prevents bad data from reaching your agent pipeline.

### Key concept: What is pydantic-settings?
Instead of hardcoding secrets like API keys in code (dangerous), you store them in a `.env` file. pydantic-settings reads that file and makes the values available as a typed Python object:
```python
settings = get_settings()
api_key = settings.anthropic_api_key  # comes from .env
```

### Key concept: What is CORS?
CORS (Cross-Origin Resource Sharing) is a browser security rule. When your frontend at `root-cause-psi.vercel.app` tries to call your backend at `rootcause-api.onrender.com`, the browser blocks it by default because they're on different domains. You have to explicitly tell the backend "requests from this frontend are allowed." The CORS middleware handles this.

**Issue encountered:**
Using FastAPI's built-in `CORSMiddleware` with `allow_credentials=True` and wildcard origins caused conflicts. Fixed by setting `allow_credentials=False` (since we don't use cookies, just API keys in headers).

**Further issue:**
OpenTelemetry's FastAPI instrumentation was intercepting OPTIONS preflight requests (the browser's "am I allowed?" check) and returning 500 errors before CORS headers could be added. Removed OTel FastAPI instrumentation, kept only Langfuse for LLM tracing.

---

## Phase 5 — RAG System

### What is RAG?
RAG stands for Retrieval-Augmented Generation. Instead of asking the LLM "what caused this incident?" from memory, you:
1. Search your knowledge base for documents relevant to the incident
2. Include those documents in the prompt
3. Ask the LLM "based on THESE documents, what caused this incident?"

This keeps answers grounded in real runbooks rather than hallucinated guesses.

### What was built

**`src/rootcause/rag/loader.py` — Corpus loader**
Reads all 252 markdown files from `data/runbooks/` and `data/postmortems/` and returns them as `Document` objects with a unique `doc_id`, `content`, and `source` (runbook vs postmortem).

**`src/rootcause/rag/retriever.py` — Hybrid retriever**
This is the most technically sophisticated piece. It combines three retrieval methods:

**Method 1: BM25 (keyword search)**
BM25 (Best Match 25) is a classic information retrieval algorithm used by search engines. It finds documents that contain the same words as the query, weighted by how rare those words are across the whole corpus. "High connection count PostgreSQL" will strongly match a document that uses those exact words.

```python
bm25 = BM25Okapi([_tokenize(doc.content) for doc in docs])
scores = bm25.get_scores(_tokenize(query))
```

**Method 2: Qdrant vector search**
The query ("postgres connections exhausted") is converted to a 1536-dimension vector using Cohere's embedding model (`embed-english-v3.0`). Every document was also pre-embedded and stored in Qdrant. Qdrant finds the documents whose vectors are closest (by cosine similarity) to the query vector. This catches semantic similarity even when exact words don't match ("connection pool saturated" matches "high connection count").

```python
results = qdrant.search(
    collection_name="runbooks",
    query_vector=("cohere", embed(query)),
    limit=20,
)
```

**Method 3: RRF (Reciprocal Rank Fusion)**
BM25 returns its own ranked list. Qdrant returns its own ranked list. They often disagree. RRF combines them by giving each document a score of `1 / (rank + 60)` from each list and summing. Documents that rank highly in BOTH lists get the best combined scores.

```python
def rrf(bm25_ranking, vector_ranking, k=60):
    scores = defaultdict(float)
    for rank, doc_id in enumerate(bm25_ranking):
        scores[doc_id] += 1.0 / (rank + k)
    for rank, doc_id in enumerate(vector_ranking):
        scores[doc_id] += 1.0 / (rank + k)
    return sorted(scores, key=scores.get, reverse=True)
```

**Method 4: Cohere reranking**
After RRF gives a combined top-20 list, Cohere's reranker model does a final pass. Unlike BM25 or vector search (which look at query and document independently), Cohere's reranker reads the query AND each document together and scores their relevance jointly. This is slower but more accurate.

**Issue encountered:**
The original code used `fastembed` (local embedding model) to generate vectors. On Render's free tier, this caused out-of-memory (OOM) crashes because loading a local embedding model takes ~500MB of RAM. Fixed by switching from local embeddings to Cohere's cloud API (no local model needed).

**Issue encountered:**
The Qdrant client used `async` (non-blocking) code. FastAPI runs async code on the main thread. But the LangGraph agent runs in a separate background thread (via `asyncio.run_in_executor`). You can't use async code from a different thread than the one that owns the event loop. Fixed by using the synchronous Qdrant client inside the background thread.

### Evaluation results
After building the hybrid retriever, it was benchmarked against BM25-only on 50 labeled queries:

| Metric | BM25-only | Hybrid |
|---|---|---|
| Recall@1 | 84% | 96% |
| MRR | 89.5% | 97% |

Hybrid retrieval puts the right runbook as the #1 result 96% of the time vs 84% for BM25 alone. The +12% improvement comes from vector search catching semantic matches that exact-keyword BM25 misses.

---

## Phase 6 — Multi-Agent System

### What is LangGraph?
LangGraph is a library for building AI agent systems as a directed graph. Each node in the graph is a function (an agent). Edges define which node runs next. The graph maintains a shared "state" dictionary that every agent can read from and write to.

### The pipeline

**`src/rootcause/agents/state.py` — Shared state**
Every agent reads from and writes to this shared dict:
```python
class AgentState(TypedDict):
    incident_id: str
    title: str
    service: str
    severity: str
    logs: str
    triage_result: dict       # filled by Triage agent
    retrieved_docs: list      # filled by Retrieval agent
    service_graph: dict       # filled by Retrieval agent (Neo4j)
    root_causes: list         # filled by RCA agent
    remediation_steps: list   # filled by Remediation agent
    completed_steps: list
```

**`src/rootcause/agents/triage.py` — Triage agent**
Model: `gpt-4o-mini`
Input: raw incident title, service name, severity, logs
Output: structured classification (confirmed severity, key signals, refined search query)

The triage agent's job is to extract signal from noise. Raw logs can be thousands of lines. The triage agent identifies the 3–5 most important signals and rewrites them into a clean query that the retrieval agent can search with.

Prompt structure: system prompt explaining the role, then the incident details, then instruction to return JSON.

**`src/rootcause/agents/retrieval.py` — Retrieval agent**
No LLM call — this is pure code.
1. Takes the triage result's search query
2. Runs hybrid BM25 + Qdrant retrieval
3. Cohere reranks
4. Queries Neo4j for the service's dependencies
5. Returns top documents and service graph to state

**`src/rootcause/agents/rca.py` — RCA agent**
Model: `claude-haiku-4-5` (via Anthropic API)
Input: incident details + top retrieved runbooks + service dependency graph
Output: 1–3 ranked root cause hypotheses, each with confidence score (0–100%), evidence citations, contributing factors

Why Claude Haiku for RCA?
- The RCA step is the most important and needs careful reasoning
- Claude Haiku is fast and cheap while still being highly capable
- Haiku's reasoning about cause-and-effect chains is very good

The prompt includes the dependency graph context:
```
## Service Dependency Graph
payment-service depends on: postgres-primary (database), redis-cache (cache)
Services that depend on payment-service: checkout-service, order-service
```
This helps the model reason about cascade failures (e.g., "if postgres is slow, payment-service slows down, which causes checkout to time out").

**Issue encountered:**
The LLM sometimes returned JSON with string fields where Python expected a list. For example, `"evidence": "high connection count"` instead of `"evidence": ["high connection count"]`. Fixed by parsing the JSON response and normalizing the fields before passing to Pydantic validation.

**`src/rootcause/agents/remediation.py` — Remediation agent**
Model: `gpt-4o-mini`
Input: incident details + RCA results + retrieved runbook content
Output: numbered concrete fix steps referencing the matched runbooks

Why gpt-4o-mini for remediation?
- Step generation is more mechanical than analytical
- gpt-4o-mini is cheaper and fast enough
- The hard thinking (figuring out the root cause) was already done by RCA

**`src/rootcause/agents/graph.py` — The pipeline wiring**
This is where LangGraph connects everything:
```python
workflow = StateGraph(AgentState)
workflow.add_node("triage", run_triage)
workflow.add_node("retrieval", run_retrieval)
workflow.add_node("rca", run_rca)
workflow.add_node("remediation", run_remediation)
workflow.add_edge(START, "triage")
workflow.add_edge("triage", "retrieval")
workflow.add_edge("retrieval", "rca")
workflow.add_edge("rca", "remediation")
workflow.add_edge("remediation", END)
```

The pipeline runs in a background thread (not blocking the API) so the HTTP response returns immediately with an incident ID. The frontend polls for results.

---

## Phase 7 — Databases

### PostgreSQL (`src/rootcause/db/postgres.py` + `db/models.py`)

**What is SQLAlchemy?**
SQLAlchemy is the most popular Python database toolkit. It lets you define your database tables as Python classes (ORM = Object-Relational Mapping) and query them with Python instead of raw SQL.

**Async SQLAlchemy:**
Normal SQLAlchemy blocks the thread while waiting for the database. Async SQLAlchemy (`asyncpg` driver) lets the server handle other requests while waiting. This is important because database queries can take 10–100ms.

**The `Incident` table stores:**
- `incident_id` (UUID, primary key)
- `title`, `service`, `severity`, `logs`
- `status` (queued → processing → complete/failed)
- `summary`, `root_causes`, `remediation_steps` (JSON)
- `created_at`, `completed_at`

### Redis (`src/rootcause/db/redis_client.py`)

Redis is an in-memory key-value store. "In-memory" means all data lives in RAM, making reads/writes microsecond-fast (vs millisecond for PostgreSQL).

**How it's used:**
```python
# After analysis completes, cache the result
await redis.set(f"incident:{incident_id}", json.dumps(result), ex=1800)  # 30 min TTL

# Before re-running analysis, check cache first
cached = await redis.get(f"incident:{incident_id}")
if cached:
    return json.loads(cached)  # instant, no DB hit
```

**TTL** = Time to Live. After 30 minutes, Redis automatically deletes the entry. This prevents stale data from accumulating.

**Graceful fallback:**
If Redis is not running (e.g., local dev without Docker), the code catches the connection error and continues without caching. The incident still works, just without the cache speed.

### Qdrant (`src/rootcause/db/qdrant_client.py`)

Qdrant Cloud is used (not self-hosted). The client connects to your cloud instance:
```python
client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
```

A "collection" in Qdrant is like a table in PostgreSQL. The `runbooks` collection stores 252 vectors (one per document), each 1536-dimensional (Cohere's vector size).

### Neo4j (`src/rootcause/db/neo4j_client.py`)

Neo4j Aura is the cloud-hosted version. The data model:
- Nodes: `(:Service {name: "payment-service"})`
- Edges: `(payment)-[:DEPENDS_ON {dep_type: "database"}]->(postgres)`

Query to find what payment-service depends on:
```cypher
MATCH (s:Service {name: "payment-service"})-[r:DEPENDS_ON]->(dep:Service)
RETURN dep.name, r.dep_type
```

**Issue encountered:**
The Neo4j async driver (`AsyncGraphDatabase.driver`) shares an event loop. When called from a background thread (where the LangGraph pipeline runs), it tries to attach to a different event loop than the one it was created with, causing `Future attached to a different loop`. Fixed by using the synchronous driver instead (`GraphDatabase.driver`) inside the background thread.

**`scripts/seed_graph.py`:**
Before Neo4j could be queried, it needed data. This script creates 11 service nodes and 21 dependency edges:
```
payment-service → postgres-primary (database)
payment-service → redis-cache (cache)
checkout-service → payment-service (service)
api-gateway → checkout-service (service)
... etc
```

### Docker Compose (`docker-compose.yml`)

For local development, running PostgreSQL and Redis manually is annoying. Docker Compose defines them declaratively:
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: rootcause
  redis:
    image: redis:7
```

`docker compose up -d` starts both in the background. `docker compose down` stops them.

---

## Phase 8 — Frontend

### Tech stack: Next.js 15 + Tailwind CSS

**What is Next.js?**
Next.js is a React framework. React is a JavaScript library for building interactive UIs. Next.js adds routing, server-side rendering, and a project structure on top of React.

**What is Tailwind CSS?**
Instead of writing separate CSS files, Tailwind gives you utility classes like `bg-gray-900`, `text-sm`, `rounded-lg` that you apply directly in your HTML/JSX. This is faster and keeps styles co-located with the component.

### Key pages

**`frontend/src/app/page.tsx` — Home (redirects to submit)**
Simple landing that routes to the incident form.

**`frontend/src/components/IncidentForm.tsx` — Incident submission form**
A form with fields for title, service name, severity (dropdown: low/medium/high/critical), and logs (textarea). On submit, it calls `POST /incidents/analyze` and redirects to the results page with the returned incident ID.

**`frontend/src/app/incidents/[id]/page.tsx` — Results page**
A Next.js dynamic route. The `[id]` in the folder name means any URL like `/incidents/abc-123` will render this page with `id = "abc-123"`. The page renders `<ResultsPoller id={id} />`.

**`frontend/src/components/ResultsPoller.tsx` — Live polling**
The most interesting frontend component. It:
1. Calls `GET /incidents/{id}` immediately on mount
2. Sets a `setInterval` to call it again every 2 seconds
3. When status becomes `complete` or `failed`, clears the interval and stops polling
4. On completion, also fetches the service graph from `GET /graph/{service_name}`
5. Renders the results progressively as they arrive

**`frontend/src/app/incidents/page.tsx` — History page**
Table of all past incidents. Fetches `GET /incidents/` which returns all records from PostgreSQL. Shows severity (color-coded), status badge, and relative timestamps ("3 minutes ago").

**`frontend/src/lib/api.ts` — API client**
All API calls go through this single file. Reads `NEXT_PUBLIC_API_URL` from environment (set in Vercel's dashboard) so the same code works in dev (local backend) and production (Render backend).

**Issue encountered:**
The frontend was making requests to `localhost:8000` even in production because `NEXT_PUBLIC_API_URL` wasn't set in Vercel. Fixed by adding the environment variable in Vercel's project settings and redeploying.

**`frontend/src/components/ApiKeyGate.tsx`**
Wraps the app in a simple API key check. If no key is provided, shows a key entry screen. Stores the key in `localStorage` so you don't have to re-enter it.

---

## Phase 9 — Observability

### What is observability?
Observability means being able to understand what's happening inside your system from the outside. For LLM applications this specifically means:
- Which prompts were sent?
- What did the model respond?
- How many tokens were used?
- How long did each call take?
- What did it cost?

### Langfuse (`src/rootcause/core/telemetry.py`)

Langfuse is an LLM observability platform. Every time an agent calls an LLM, Langfuse records:
- The full prompt sent
- The full response received
- Token counts (input + output)
- Latency
- Model used
- Cost

It integrates with LangChain/LangGraph via a callback:
```python
from langfuse.langchain import CallbackHandler
handler = CallbackHandler()  # reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY from env
```

Pass it to any LangChain call:
```python
llm.invoke(prompt, config={"callbacks": [handler]})
```

You can then see a full trace in the Langfuse dashboard: each of the 4 agents as separate "spans" with their own input/output/cost.

**Issues encountered:**

*Issue 1: `No module named 'langfuse.callback'`*
Langfuse v3 moved the callback handler to `langfuse.langchain`. The v2 import path no longer exists.
Fixed with try/except:
```python
try:
    from langfuse.langchain import CallbackHandler  # v3+
except ImportError:
    from langfuse.callback import CallbackHandler   # v2
```

*Issue 2: `unexpected keyword argument 'secret_key'`*
In Langfuse v3, the `CallbackHandler` constructor no longer accepts `public_key`, `secret_key`, `host` as arguments. It reads them automatically from environment variables `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`.
Fixed by: `return CallbackHandler()` with no arguments.

*Issue 3: Traces not appearing in Langfuse dashboard*
The callback was failing silently. The logs showed `callback_failed`. Root cause: the wrong import path was being used, causing the handler to not initialize properly. After both fixes above, traces appeared correctly (17 observations per incident, $0.007561 cost).

---

## Phase 10 — Auth & Security

### What was built: `src/rootcause/core/security.py`

API key authentication using bearer tokens. Every request to the backend (except `/health`) must include:
```
Authorization: Bearer <your-api-key>
```

FastAPI's `Depends` system makes this easy:
```python
async def require_api_key(authorization: str = Header(None)):
    if authorization != f"Bearer {settings.api_key}":
        raise HTTPException(status_code=401, detail="Unauthorized")
```

Add to any route:
```python
@router.post("/analyze", dependencies=[Depends(require_api_key)])
```

**Why bearer tokens and not username/password?**
For API-to-API communication (frontend calling backend), a shared secret key is simpler and standard. Username/password is for human login flows. OAuth is for third-party authorization. Bearer tokens are the right tool here.

**Dev mode bypass:**
In development (`API_KEY` not set in `.env`), the auth check is skipped so you don't have to set up keys locally. This is controlled by checking `if not settings.api_key: return` at the start of the check function.

---

## Phase 11 — Deployment

### Render (backend)

Render is a cloud platform for running web services, databases, and background workers.

**`render.yaml` — Blueprint file**
This single file defines everything Render needs to know about the project:
```yaml
services:
  - type: web
    name: rootcause-api
    runtime: docker      # use the Dockerfile, not native Python
    buildCommand: ...
    startCommand: uvicorn rootcause.main:app
    
  - type: redis
    name: rootcause-redis

databases:
  - name: rootcause-postgres
    databaseName: rootcause
```

When you push this file to GitHub and connect Render to your repo, it creates all three resources automatically.

**`Dockerfile`**
Render uses Docker to build and run the backend. The Dockerfile:
1. Starts from a Python 3.12 base image
2. Installs `uv`
3. Copies `pyproject.toml` and installs dependencies
4. Copies source code
5. Exposes port 8000
6. Starts `uvicorn` (the ASGI server that runs FastAPI)

**Why Docker and not Render's native Python runtime?**
Render's native Python runtime has a fixed Python version and limited control. Docker gives you exact reproducibility — the same container that runs on your laptop runs in production.

**Free tier behavior:**
Render's free web service spins down after 15 minutes of no traffic. The next request takes ~30–60 seconds to spin back up (cold start). This is fine for a portfolio project.

### Vercel (frontend)

Vercel is the company that makes Next.js. Deploying Next.js to Vercel is the simplest option:
1. Connect GitHub repo to Vercel
2. Set `NEXT_PUBLIC_API_URL` to your Render backend URL
3. Every push to `main` triggers an automatic rebuild and deploy

`frontend/vercel.json` tells Vercel to run `npm run build` and serves the resulting Next.js app.

---

## Phase 12 — Testing

### What was built: `tests/unit/`

17 unit tests covering:

**Config tests** — verify environment variables are loaded correctly and defaults work
**Security tests** — verify that invalid API keys are rejected with 401, valid keys pass
**RAG tests** — verify BM25 tokenization, RRF scoring math, Recall@K and MRR metric calculations
**RCA parsing tests** — verify that the JSON response from the LLM is correctly parsed into root cause objects, including edge cases (string instead of list, missing fields)

**Key concept: Unit tests vs integration tests**
Unit tests test individual functions in isolation (with fake/mocked dependencies). Integration tests test the whole system end-to-end (real database, real API calls). Unit tests are fast and deterministic — they don't need API keys or a running database. Integration tests are slower but catch real failures.

**Why test RCA parsing specifically?**
The LLM doesn't always return perfectly formatted JSON. Sometimes it returns a string where you expect a list. Sometimes confidence scores are strings instead of floats. The parser normalizes this before Pydantic validation, and those normalization cases need tests.

**Tool: pytest**
Python's standard testing library. Run with `uv run pytest tests/unit/ -v` for verbose output showing each test name.

---

## Phase 13 — CI/CD

### What is CI/CD?
CI = Continuous Integration. Every time you push code to GitHub, automated checks run.
CD = Continuous Deployment. After checks pass, the code is automatically deployed.

### What was built: `.github/workflows/ci.yml`

GitHub Actions workflow that runs on every push to `main`:
1. Check out the code
2. Install `uv`
3. Set up Python 3.12
4. Install dependencies (`uv sync --extra dev`)
5. Run 17 unit tests (`uv run pytest tests/unit/`)
6. Run ruff linter (`uv run ruff check src/ tests/`)

If any step fails, GitHub shows a red ✗ on the commit. If all pass, green ✓.

**What is ruff?**
Ruff is a Python linter written in Rust. It checks code style and catches common mistakes:
- Unused imports
- Undefined variables
- Line too long
- Wrong string quote style
- And hundreds more rules

It's 10–100x faster than older linters (flake8, pylint).

**Issues encountered:**
13 ruff lint errors in the initial codebase, mostly:
- Unused imports (removed them)
- String formatting inconsistencies (fixed to use f-strings)
- Missing type annotations (added where required)

The CI fails if any lint errors remain, enforcing code quality on every commit.

---

## Phase 14 — Incident History Page

### What was built

**Backend: `GET /incidents/` endpoint**
Returns a list of all past incidents from PostgreSQL, ordered by `created_at` descending (newest first). Returns a lightweight summary (no full log content) to keep the response small.

**Frontend: `frontend/src/app/incidents/page.tsx`**
A table showing:
- Incident title
- Service name
- Severity (color-coded: red=critical, orange=high, yellow=medium, gray=low)
- Status badge (green=complete, blue=processing, gray=queued, red=failed)
- Relative timestamp ("3 minutes ago", "2 hours ago") using `Date` arithmetic

**Navigation added:**
`frontend/src/app/layout.tsx` — added "History" and "New Incident" links in the nav bar so users can move between pages.

**Key concept: Relative timestamps**
Instead of showing "2026-06-15 14:32:11 UTC" (hard to read), calculate the difference between now and then:
```javascript
function timeAgo(date) {
  const seconds = Math.floor((Date.now() - new Date(date)) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds/60)}m ago`
  return `${Math.floor(seconds/3600)}h ago`
}
```

---

## Phase 15 — Portfolio Polish

### What was done

Rewrote the README from scratch to be portfolio-quality:

1. **Badges** — CI status, Python version, backend/frontend deploy links. These are the small colored chips at the top of GitHub READMEs, auto-generated from `shields.io`.

2. **Features list** — concise bullet points covering what the system actually does, written for a technical recruiter or senior engineer reading it for the first time.

3. **Retrieval evaluation table** — concrete numbers showing that hybrid retrieval is measurably better than BM25-only (Recall@1: 84% → 96%, MRR: 89.5% → 97%). Numbers matter in portfolio projects.

4. **How it works** — numbered end-to-end walkthrough so readers immediately understand the data flow.

5. **Architecture diagram** — SVG diagram showing the two-column layout: left = sequential agent pipeline, right = data stores grouped by which agent uses them.

6. **Mermaid diagram** — collapsed in a `<details>` block for those who want to see the flowchart version.

7. **Project structure** — folder map so contributors know where to look.

8. **Running locally** — exact commands to clone, install, and run.

**SVG vs Mermaid:**
SVG renders natively on GitHub without any plugin. Mermaid requires GitHub's markdown renderer to support it (which it does, but it sometimes doesn't render correctly in non-GitHub contexts). Having both covers all bases.

---

## Phase 16 — Full Tool Integration

### What was done

Verified and wired up all the tools that were configured but not fully used:

### Neo4j — Service Dependency Graph in the Pipeline

The Neo4j client was created in Phase 7 but the retrieval agent wasn't actually querying it. Phase 16 added:

1. **`retrieval.py`** — After hybrid RAG retrieval, query Neo4j for the affected service's dependencies:
   ```python
   service_graph = get_service_dependencies(service)
   return {"retrieved_docs": docs, "service_graph": service_graph}
   ```

2. **`rca.py`** — Include the service graph in the RCA prompt:
   ```
   ## Service Dependency Graph
   payment-service depends on: postgres-primary (database), redis-cache (cache)
   Services that depend on payment-service: checkout-service
   ```
   This tells the LLM about cascade failure paths so it can reason "if postgres is slow → payment-service is slow → checkout times out".

3. **`frontend/src/components/ServiceGraphView.tsx`** — SVG visualization of the service dependency graph rendered on the results page. Shows callers (top) → affected service (middle, highlighted red) → dependencies (bottom) with arrows.

4. **`frontend/src/api/routes/graph.py`** — New endpoint `GET /graph/{service_name}` that returns the Neo4j data as JSON.

### Langfuse — Fixed and Confirmed Working

See Phase 9 for the two fixes (v3 import path and no-arg constructor). After fixes, confirmed working: each incident analysis produces a trace with 17 observations (LLM spans) and shows real token counts and cost.

### Redis — Already Working

Redis was provisioned via `render.yaml` (Phase 11). The cache code was already written (Phase 7). Confirmed working by submitting the same incident twice — second result returned instantly (cache hit) vs ~20 seconds (cache miss).

### Docker — Used for Render Deployment

The `Dockerfile` was already written in Phase 11. Render uses it to build and run the backend container. This was confirmed by checking that Render logs showed "Building Docker image" rather than "Building Python environment".

### Evaluation Framework — `scripts/run_eval.py`

Script to benchmark BM25 vs Hybrid retrieval on 50 labeled queries:
```
uv run python scripts/run_eval.py
```

Output:
```
BM25-only:   Recall@1 84.0%  MRR 89.5%
Hybrid:      Recall@1 96.0%  MRR 97.0%
Improvement: +12.0%          +7.5%
```

These numbers went into the README evaluation table.

---

## Key Bugs Fixed Across the Project

| Bug | Cause | Fix |
|---|---|---|
| OOM crash on Render | fastembed loading 500MB local model | Switch to Cohere cloud API |
| Qdrant `Future attached to different loop` | Async client called from background thread | Use sync Qdrant client in background thread |
| Neo4j `Future attached to different loop` | Same as above | Use sync `GraphDatabase.driver()` |
| CORS blocking frontend requests | `allow_credentials=True` with wildcard origin | Set `allow_credentials=False` |
| OTel returning 500 on OPTIONS | OTel intercepting preflight before CORS | Remove OTel FastAPI instrumentation |
| Frontend calling localhost in production | `NEXT_PUBLIC_API_URL` not set in Vercel | Add env var in Vercel project settings |
| Langfuse `No module named langfuse.callback` | v3 moved the module | Try `langfuse.langchain` first, fallback to `langfuse.callback` |
| Langfuse `unexpected keyword argument 'secret_key'` | v3 reads from env vars, not constructor | `CallbackHandler()` with no arguments |
| RCA Pydantic validation failure | LLM returns string where list expected | Normalize JSON fields before validation |
| git push rejected | Remote had changes not in local | `git pull --rebase` then push |

---

## Key Concepts Glossary

**API** — Application Programming Interface. A set of URLs your frontend can call to interact with the backend.

**Async / Await** — Code that doesn't block while waiting. `await database.query()` lets other requests run while the DB is thinking, instead of freezing everything.

**BM25** — A keyword-based search algorithm used in search engines. Scores documents by how many query words they contain, weighted by word rarity.

**CORS** — Cross-Origin Resource Sharing. Browser security rule requiring explicit permission for cross-domain API calls.

**Docker** — Packages your app and all its dependencies into a container that runs identically everywhere.

**Embeddings** — Converting text into a vector (list of numbers) that captures meaning. Similar texts have similar vectors.

**Event Loop** — Python's async engine. Only one event loop runs per thread. Using async code from multiple threads causes conflicts.

**FastAPI** — Modern Python web framework with automatic type validation and async support.

**LangGraph** — Library for building multi-agent AI systems as graphs. Nodes = agents, edges = routing.

**LLM** — Large Language Model. A neural network trained on text that can generate human-like responses. GPT-4o, Claude, Gemini are all LLMs.

**Neo4j** — Graph database. Stores nodes and relationships natively. Best for questions like "what does X depend on?"

**Pydantic** — Python library for data validation via type annotations.

**Qdrant** — Vector database. Stores embeddings and finds nearest neighbors by mathematical similarity.

**RAG** — Retrieval-Augmented Generation. Feeding retrieved documents into the LLM prompt to ground answers in real knowledge.

**Redis** — In-memory key-value store. Microsecond reads/writes. Used for caching and session storage.

**RRF** — Reciprocal Rank Fusion. Algorithm for combining multiple ranked lists into one.

**SQLAlchemy** — Python ORM (Object-Relational Mapper). Write Python to query databases instead of raw SQL.

**TTL** — Time to Live. How long a Redis key exists before being automatically deleted.

**uvicorn** — ASGI server that runs FastAPI in production. Like nginx for Python async apps.

**uv** — Modern Python package manager. 10–100x faster than pip.

**Vector similarity** — Measuring how close two vectors are (cosine similarity). Used by Qdrant to find relevant documents.
