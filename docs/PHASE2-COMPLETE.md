# Phase 2 — System Design — Complete

## Diagrams created
**- System Architecture (all components and connections)**
<img width="568" height="627" alt="image" src="https://github.com/user-attachments/assets/c830e9d7-6d5d-4f72-af14-f5cc0a7fe491" />

What to notice in this diagram:
Five things an interviewer will ask about and you now know the answer to:
The Coordinator sits in the middle — it dispatches down and collects back up. Workers never talk to each other directly. The RCA agent is a separate component from the coordinator deliberately — it uses the premium model and that decision is isolated. The Comms agent output requires human approval before anything is posted. The cross-cutting layer (Redis, databases, model routing) supports everything but is not "in the flow" — it's infrastructure, not a step.

-** Data Flow (what data moves at each step)**
<img width="591" height="582" alt="image" src="https://github.com/user-attachments/assets/8cfd79ef-77c1-4459-9a7c-09be3e791fcc" />
What the data flow diagram adds that the architecture diagram doesn't: you can now see exactly what data format travels at each handoff. The coordinator passes incident_id + service + time_window + budget to each worker — not the raw alert. The RCA agent receives a fused evidence bundle — not individual agent results. The feedback loop closes the system — it makes the retrieval better over time. That closing loop is what makes this a learning system, not just a retrieval system.


**- Sequence Diagram (timing — what runs in parallel)**
<img width="577" height="567" alt="image" src="https://github.com/user-attachments/assets/30d003eb-2c4e-4274-bca0-cc7db1cc0dc9" />
What the sequence diagram adds: You can now see the timing story. Triage is sequential (must finish before coordinator can dispatch). Workers are parallel (the big time saving — 30 seconds of parallel work instead of 150 seconds sequential). The "no signal" path shows graceful degradation. The RCA agent only starts after workers finish — it cannot start earlier because it needs the evidence. Total time: ~47 seconds from alert to ranked RCA in the engineer's UI.

**- Agent Workflow (LangGraph state and supervisor decisions)**
<img width="587" height="562" alt="image" src="https://github.com/user-attachments/assets/a24b42e0-2500-4dfa-8427-f99961c6959f" />
What the agent workflow diagram adds: You now understand what LangGraph actually does. It manages a shared state object — a Python dictionary that all nodes can read and write to. Each node is a function. The supervisor is a conditional edge — it looks at the current state and decides which node runs next. The diamond in the middle is that decision. This is the diagram that lets you explain LangGraph in an interview without saying "it's like a flow chart thing."


**- Database Design (four stores, each with a job)**
<img width="622" height="452" alt="image" src="https://github.com/user-attachments/assets/d505da41-079a-466d-9af7-4400c13fc956" />
What the database diagram adds: You can now answer the single most common architecture interview question about this project — "why four databases?" The answer is that each one is the right tool for a different access pattern. PostgreSQL for relational records you query by ID. Redis for fast, temporary key-value lookups. Qdrant for vector similarity search with hybrid support. Neo4j for graph traversal across connected services. Using PostgreSQL for everything would work but would be slow and unnatural for the graph and vector use cases.

**- Deployment Architecture (dev vs production)**
<img width="567" height="442" alt="image" src="https://github.com/user-attachments/assets/7846f2b5-bf7c-4517-8d76-f4ab00035bb7" />

What the deployment diagram adds: You now have a clear picture of two environments — development (everything on your Windows machine via WSL2 and Docker, completely free) and production (Render + Vercel free tiers, public URL, secrets stored safely in Render's dashboard, never in your repo). The cold-start note is honest — Render's free tier sleeps, but for a portfolio demo that's fine.


## Key decisions made
See docs/decisions/ for full ADRs.

1. Star topology — supervisor/worker, no agent-to-agent comms
2. Four databases — each for a different access pattern
3. Model routing — cheap for most, premium for RCA only
4. Hybrid dataset — synthetic runbooks + real postmortems

## Next phase
Phase 3 — Project Initialization
First task: set up Python environment with uv
