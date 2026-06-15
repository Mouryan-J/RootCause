# RB-001 — PostgreSQL High Connection Count

**Service:** PostgreSQL  
**Severity:** High  
**Tags:** database, postgres, connections, pgbouncer

## Symptoms
- `FATAL: remaining connection slots are reserved for non-replication superuser connections`
- Connection pool exhaustion errors in application logs
- `pg_stat_activity` shows connections near `max_connections` limit
- New queries queue or fail immediately

## Possible Causes
- Application connection pool misconfigured (too many connections per pod × too many pods)
- Connection leak: connections opened but never closed after exceptions
- Spike in traffic without corresponding pgbouncer scaling
- Long-running idle transactions holding connections
- Missing pgbouncer or connection pooler in front of Postgres

## Diagnostic Steps

```sql
-- Check current connection count vs limit
SELECT count(*), max_connections
FROM pg_stat_activity, (SELECT setting::int AS max_connections FROM pg_settings WHERE name = 'max_connections') s
GROUP BY max_connections;

-- Identify idle connections by application
SELECT application_name, state, count(*)
FROM pg_stat_activity
GROUP BY application_name, state
ORDER BY count DESC;

-- Find long-running idle transactions
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND query_start < now() - interval '5 minutes';
```

```bash
# Check pgbouncer pool stats if present
psql -p 6432 -U pgbouncer pgbouncer -c "SHOW POOLS;"
psql -p 6432 -U pgbouncer pgbouncer -c "SHOW STATS;"
```

## Remediation Steps

### Immediate (stop the bleeding)
1. Terminate idle connections older than 10 minutes:
   ```sql
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle' AND query_start < now() - interval '10 minutes';
   ```
2. If connections still at limit, restart the most heavily connected application pod(s).

### Short-term
3. Reduce `pool_size` in application's database config to `(max_connections * 0.8) / num_pods`.
4. Enable pgbouncer in transaction-pooling mode if not already in use.
5. Set `idle_in_transaction_session_timeout = 30s` in `postgresql.conf`.

### Long-term
6. Add Prometheus alert on `pg_stat_activity_count > max_connections * 0.8`.
7. Review ORM connection pool settings (`pool_size`, `max_overflow`, `pool_timeout`).

## Prevention
- Always deploy pgbouncer between application and Postgres.
- Set `statement_timeout` and `idle_in_transaction_session_timeout` in `postgresql.conf`.
- Monitor `pg_stat_activity` count in Grafana with alert at 80% capacity.
