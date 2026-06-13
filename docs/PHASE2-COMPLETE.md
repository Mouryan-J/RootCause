# Phase 2 — System Design — Complete

## Diagrams created
- System Architecture (all components and connections)
- Data Flow (what data moves at each step)
- Sequence Diagram (timing — what runs in parallel)
- Agent Workflow (LangGraph state and supervisor decisions)
- Database Design (four stores, each with a job)
- Deployment Architecture (dev vs production)
<img width="568" height="627" alt="image" src="https://github.com/user-attachments/assets/c830e9d7-6d5d-4f72-af14-f5cc0a7fe491" />

## Key decisions made
See docs/decisions/ for full ADRs.

1. Star topology — supervisor/worker, no agent-to-agent comms
2. Four databases — each for a different access pattern
3. Model routing — cheap for most, premium for RCA only
4. Hybrid dataset — synthetic runbooks + real postmortems

## Next phase
Phase 3 — Project Initialization
First task: set up Python environment with uv
