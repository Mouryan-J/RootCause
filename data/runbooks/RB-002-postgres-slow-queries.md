# RB-002 — PostgreSQL Slow Queries and Missing Indexes

**Service:** PostgreSQL  
**Severity:** Medium–High  
**Tags:** database, postgres, performance, indexes, query-plan

## Symptoms
- API p99 latency spikes correlate with DB query duration
- `pg_stat_statements` shows queries with `mean_exec_time > 1000ms`
- `EXPLAIN ANALYZE` output shows `Seq Scan` on large tables
- Application logs contain `slow query` warnings

## Possible Causes
- New code path introduced a query without a covering index
- Table grew past threshold where sequential scan became slower than index scan
- Statistics out of date — planner choosing wrong execution plan
- `N+1` query pattern in ORM code
- Index bloat after high-churn delete/update workload

## Diagnostic Steps

```sql
-- Top 10 slowest queries (requires pg_stat_statements)
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Find tables with sequential scans on large row counts
SELECT schemaname, relname, seq_scan, seq_tup_read, idx_scan
FROM pg_stat_user_tables
WHERE seq_scan > 0 AND n_live_tup > 10000
ORDER BY seq_tup_read DESC;

-- Identify missing indexes via pg_missing_indexes (if extension installed)
-- Otherwise, manually run EXPLAIN ANALYZE on the slow query:
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) <slow_query_here>;
```

```bash
# Check for table bloat
vacuumdb --analyze --verbose -d rootcause
```

## Remediation Steps

### Immediate
1. Run `ANALYZE <table_name>` to refresh planner statistics.
2. If a specific query is identified, create the missing index:
   ```sql
   CREATE INDEX CONCURRENTLY idx_incidents_service_created
   ON incidents (service, created_at DESC);
   ```
   Use `CONCURRENTLY` to avoid table lock.

### Short-term
3. Review ORM queries for N+1 patterns; use `select_related` / `joinedload`.
4. Add `pg_stat_statements` to `shared_preload_libraries` if not present.
5. Set `log_min_duration_statement = 500` in `postgresql.conf` to capture slow queries in logs.

### Long-term
6. Schedule weekly `VACUUM ANALYZE` on high-churn tables.
7. Review execution plans as part of code review for any new query-generating code.

## Prevention
- Run `EXPLAIN ANALYZE` on all new query patterns in staging before deploy.
- Add Grafana alert on `pg_stat_statements.mean_exec_time` for key queries.
- Use `auto_explain` extension with `log_min_duration = 1000` in production.
