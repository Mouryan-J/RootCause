# ADR 003 — Model Routing Strategy

## Decision
Route different tasks to different model tiers based on complexity.

## Routing rules
- Triage, log summary, comms draft → claude-haiku-4-5 / gpt-4o-mini
- RCA synthesis (causal reasoning) → premium model only
- Runbook retrieval → no LLM, pure vector search

## Why
RCA synthesis is the one step that requires deep causal reasoning. 
Every other step is classification, summarisation, or retrieval — 
tasks that cheap, fast models handle well. Routing saves ~75% cost 
vs using the premium model for everything.
