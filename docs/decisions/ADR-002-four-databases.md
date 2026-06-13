# ADR 002 — Four Databases

## Decision
Use four separate data stores, each chosen for its access pattern.

## Breakdown
- PostgreSQL: relational records (incidents, hypotheses, feedback)
- Redis: fast ephemeral state (cache, coordination, rate limiting)
- Qdrant: vector + hybrid search (runbook retrieval)
- Neo4j: graph traversal (service dependency multi-hop)

## Why not one database
A single PostgreSQL instance could store everything but would be 
slow for vector search and unnatural for graph traversal. Each 
store is the right tool for its job.
