# RB-008 — Memory Leak in Python Service

**Service:** Python Backend / Workers  
**Severity:** High  
**Tags:** python, memory, leak, oom, workers

## Symptoms
- RSS memory of Python process grows monotonically over hours/days
- `process_resident_memory_bytes` in Prometheus trends upward without plateau
- Pod eventually gets OOMKilled by Kubernetes
- Memory doesn't drop after periods of low traffic

## Possible Causes
- Global cache (dict or list) appended to without bounds
- Circular references preventing garbage collection
- LangChain / LangGraph objects retaining large message histories in memory
- Unclosed file handles or database connections accumulating
- Third-party library holding references (e.g., telemetry SDK batching unboundedly)
- Large LLM response stored in a module-level variable

## Diagnostic Steps

```bash
# Monitor memory growth
kubectl top pod -l app=rootcause-worker --watch

# Get PID inside container
kubectl exec -it <pod> -- ps aux | grep python
```

```python
# Use tracemalloc to find allocation sites
import tracemalloc
tracemalloc.start()

# ... run the workload ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

```python
# Use objgraph to find object count growth
import objgraph
objgraph.show_most_common_types(limit=10)
objgraph.show_growth()
```

```bash
# Quick check: memory before and after a batch of requests
curl /metrics | grep process_resident_memory_bytes
# run load, then:
curl /metrics | grep process_resident_memory_bytes
```

## Remediation Steps

### Immediate
1. Restart affected pods to reclaim memory (buys time):
   ```bash
   kubectl rollout restart deployment/rootcause-worker
   ```
2. Set a memory limit so Kubernetes kills and restarts pods automatically:
   ```yaml
   resources:
     limits:
       memory: "512Mi"
   ```

### Short-term
3. Add `tracemalloc` snapshot endpoint (`GET /debug/memory`) gated behind `APP_ENV=development`.
4. Review all module-level or class-level collections; add `maxlen` to any unbounded ones:
   ```python
   from collections import deque
   event_log = deque(maxlen=1000)
   ```
5. Clear LangGraph message history after each incident analysis completes.

### Long-term
6. Add Prometheus alert on `process_resident_memory_bytes` growing > 50MB/hour.
7. Run weekly memory regression test with `memray` in CI.
8. Add `max_messages` config to LangGraph `MessagesState` to cap history.

## Prevention
- Never use module-level mutable state for per-request data.
- Always bound caches and queues with a `maxlen` or explicit eviction.
- Add memory growth test to CI: process memory after 1000 requests should be < 2× baseline.
