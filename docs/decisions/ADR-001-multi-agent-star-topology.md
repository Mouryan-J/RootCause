# ADR 001 — Multi-Agent Star Topology

## Decision
Use supervisor/worker star topology — workers never communicate 
directly with each other.

## Why
- Simpler to debug: all communication paths go through one place
- Lower latency: all workers run in true parallel with no wait chains
- Easier failure handling: coordinator handles timeouts, not agents
- Deterministic: same input always takes the same path

## Alternatives considered
- Mesh topology: agents talk freely. Rejected — N² communication 
  paths, emergent behaviour, hard to trace.
- Sequential pipeline: one agent after another. Rejected — too slow 
  for a latency-sensitive system.
