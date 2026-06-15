# RB-007 — API Latency p99 Degradation

**Service:** API / Backend  
**Severity:** High  
**Tags:** latency, performance, p99, slow-requests

## Symptoms
- p99 latency alert fires (e.g., `> 2s` for endpoints that normally run `< 200ms`)
- p50 latency unchanged — only tail latency affected
- Distributed trace shows a specific downstream call as the bottleneck
- Users report intermittent slowness or timeouts

## Possible Causes
- Slow downstream dependency (DB, LLM API, vector store) affecting tail requests
- Lock contention in database (long-running queries blocking others)
- GC pressure in JVM-based service
- Large payload processing (embedding generation, log parsing) blocking async workers
- Missing database index causing occasional full table scans

## Diagnostic Steps

```bash
# Identify which endpoint has the highest p99
# Prometheus query:
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Break down by endpoint path to find the culprit
histogram_quantile(0.99, sum by (path) (rate(http_request_duration_seconds_bucket[5m])))
```

```bash
# Check distributed traces (Langfuse or OpenTelemetry)
# Look for spans with duration > 1s in the last 30 minutes

# Check for DB lock contention
psql -c "SELECT pid, wait_event_type, wait_event, query FROM pg_stat_activity WHERE wait_event IS NOT NULL;"

# Check async task queue depth (if using background workers)
redis-cli LLEN celery
```

## Remediation Steps

### Immediate
1. Use distributed tracing to identify the exact span causing the tail latency.
2. If a single downstream call is responsible, add a timeout and fallback:
   ```python
   async with asyncio.timeout(5.0):
       result = await slow_downstream_call()
   ```
3. If DB lock contention: identify and terminate the blocking query:
   ```sql
   SELECT pg_cancel_backend(<blocking_pid>);
   ```

### Short-term
4. Add `EXPLAIN ANALYZE` on slow DB queries; create missing index.
5. Move heavy processing (embedding generation) to background task queue.
6. Implement response caching for frequently requested, rarely changing data.

### Long-term
7. Add per-endpoint p99 SLO alerts with 5-minute burn rate.
8. Profile the service with `py-spy` or `austin` to identify hot paths.
9. Consider read replicas for read-heavy DB queries.

## Prevention
- Set explicit timeouts on all I/O operations: DB queries, external API calls, LLM requests.
- Test with realistic p99 load in staging using `locust` or `k6`.
- Alert on p99 > 2× p50 as an early warning of tail latency growth.
