# RB-003 — Redis Memory Exhaustion

**Service:** Redis  
**Severity:** Critical  
**Tags:** redis, memory, cache, eviction

## Symptoms
- `OOM command not allowed when used memory > 'maxmemory'` errors in application logs
- Redis `INFO memory` shows `used_memory` near or above `maxmemory`
- Cache hit rate drops suddenly (keys being evicted)
- Application latency spikes as fallback to database occurs

## Possible Causes
- Large keys not expiring (missing TTL on cache entries)
- Traffic spike causing rapid cache population
- `maxmemory-policy` set to `noeviction` — writes fail instead of evicting old keys
- Memory leak in application writing unbounded data to Redis
- Key explosion from misconfigured cache key patterns (e.g., per-request unique keys)

## Diagnostic Steps

```bash
# Connect to Redis
redis-cli -h $REDIS_HOST

# Memory overview
INFO memory

# Check maxmemory config
CONFIG GET maxmemory
CONFIG GET maxmemory-policy

# Find largest keys (sample-based, safe for production)
redis-cli --bigkeys

# Find keys without TTL (dangerous on large keyspaces — use a sample)
redis-cli --scan --pattern '*' | head -1000 | xargs -I{} redis-cli TTL {}

# Check eviction stats
INFO stats | grep evicted
```

## Remediation Steps

### Immediate
1. If `maxmemory-policy` is `noeviction`, switch to `allkeys-lru` to allow eviction:
   ```bash
   redis-cli CONFIG SET maxmemory-policy allkeys-lru
   ```
2. Identify and delete the largest keys causing bloat:
   ```bash
   redis-cli --bigkeys
   redis-cli DEL <large_key>
   ```
3. If memory is critically full, flush non-critical cache databases:
   ```bash
   redis-cli SELECT 1
   redis-cli FLUSHDB ASYNC
   ```

### Short-term
4. Audit all `SET` calls in application code — ensure every key has a TTL:
   ```python
   redis.set("key", value, ex=3600)  # always pass ex=
   ```
5. Increase `maxmemory` if the workload genuinely requires more cache.
6. Segment caches by database number (0=sessions, 1=query cache, 2=rate limits).

### Long-term
7. Add Grafana alert on `redis_memory_used_bytes / redis_memory_max_bytes > 0.85`.
8. Implement key naming conventions that include service prefix and TTL hint.

## Prevention
- Enforce TTL policy in code review: no `SET` without `EX` or `PX`.
- Monitor `redis_evicted_keys_total` metric; sudden spikes indicate memory pressure.
- Use Redis Cluster or separate instances for large, unbounded workloads.
