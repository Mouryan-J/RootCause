# RB-004 — Redis Keyspace Eviction Spike

**Service:** Redis  
**Severity:** Medium  
**Tags:** redis, eviction, cache, hit-rate

## Symptoms
- `redis_evicted_keys_total` counter rises sharply in Grafana
- Cache hit rate (`keyspace_hits / (keyspace_hits + keyspace_misses)`) drops below 80%
- Increased database query load as application falls back from cache
- Application latency p50 degrades (cache misses go to DB)

## Possible Causes
- `maxmemory` limit reached, forcing LRU eviction of valid cache entries
- Traffic spike — more keys written than memory can hold
- Large short-lived keys flooding the keyspace and pushing out long-lived keys
- Memory policy (`volatile-lru`) only evicting keys with TTL, but TTL-less keys consuming most memory

## Diagnostic Steps

```bash
redis-cli INFO stats | grep -E 'keyspace_(hits|misses)|evicted_keys'
redis-cli INFO memory | grep -E 'used_memory_human|maxmemory_human'
redis-cli INFO keyspace

# Eviction rate per second
redis-cli --stat | grep evicted
```

```python
# Calculate hit rate
hits = int(redis.info('stats')['keyspace_hits'])
misses = int(redis.info('stats')['keyspace_misses'])
hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
print(f"Hit rate: {hit_rate:.2%}")
```

## Remediation Steps

### Immediate
1. Check if `maxmemory` is being hit:
   ```bash
   redis-cli INFO memory | grep maxmemory
   ```
2. If memory is full, temporarily increase `maxmemory`:
   ```bash
   redis-cli CONFIG SET maxmemory 2gb
   ```
3. Switch eviction policy to protect frequently accessed keys:
   ```bash
   redis-cli CONFIG SET maxmemory-policy allkeys-lfu
   ```

### Short-term
4. Segment cache by importance — put critical long-lived keys in a separate Redis database or instance.
5. Add `OBJECT FREQ` monitoring with `maxmemory-policy allkeys-lfu` to track access frequency.
6. Review application code for large transient keys — ensure they have short TTLs.

### Long-term
7. Implement cache warming after restarts or eviction spikes.
8. Add alert: `evicted_keys rate > 100/min` triggers PagerDuty.

## Prevention
- Separate session cache (small, high-value) from query cache (large, replaceable) on different instances.
- Use `allkeys-lfu` policy in Redis 4+ for better cache retention of popular keys.
- Monitor hit rate continuously; target > 90% for production workloads.
