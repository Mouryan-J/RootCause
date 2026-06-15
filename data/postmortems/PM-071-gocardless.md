# PM-071 — GoCardless

**Company:** GoCardless  
**Category:** Conflicts  
**Source:** https://gocardless.com/blog/zero-downtime-postgres-migrations-the-hard-parts/

## Incident Summary

All queries on a critical PostgreSQL table were blocked by the combination of an extremely fast database migration and a long-running read query, causing 15 seconds of downtime.
