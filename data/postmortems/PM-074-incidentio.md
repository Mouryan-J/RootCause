# PM-074 — incident.io

**Company:** incident.io  
**Category:** Conflicts  
**Source:** https://incident.io/blog/one-two-skip-a-few

## Incident Summary

Customers noticed their per-organization `INC-N` IDs jumping by exactly 32 (e.g. `#INC-7` directly to `#INC-39`) after a Postgres HA upgrade that promoted a follower to primary. Postgres's `nextval` pre-allocates `SEQ_LOG_VALS = 32` sequence values on the WAL to avoid logging every `nextval`; a follower sees the post-crash state, so when promoted the sequence jumps forward by up to 32. Fix was to replace `nextval` with a `SELECT MAX(external_id)+1` trigger.
