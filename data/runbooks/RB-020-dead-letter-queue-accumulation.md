# RB-020 — Dead Letter Queue (DLQ) Accumulation

**Service:** Message Queue / Task Worker  
**Severity:** Medium  
**Tags:** dlq, messaging, errors, worker, retries

## Symptoms
- DLQ depth growing steadily: `redis_list_length{key="dlq:incidents"} > 100`
- Tasks that should complete are silently failing and ending up in DLQ
- Application events are lost — users notice missing notifications or delayed state
- Alert fires on `dlq_depth > threshold`

## Possible Causes
- Unhandled exception in worker code causes task to be sent to DLQ after max retries
- Deserialization failure: message format changed but workers not updated
- External dependency consistently unavailable for duration of retry window
- Task payload too large for the worker to process within timeout
- Misconfigured retry policy: max retries = 0, everything goes to DLQ immediately

## Diagnostic Steps

```bash
# Check DLQ depth
redis-cli LLEN dlq:incidents
redis-cli LRANGE dlq:incidents 0 4  # peek at first 5 messages

# Check worker error logs
kubectl logs -l app=rootcause-worker --tail=500 | grep -i 'error\|dlq\|retry\|failed'

# Check Celery (if applicable) failed tasks
celery -A rootcause inspect reserved
celery -A rootcause events  # real-time event monitor
```

```python
# Inspect a DLQ message manually
import json, redis
r = redis.Redis(...)
msg = r.lindex('dlq:incidents', 0)
payload = json.loads(msg)
print(payload)  # identify the failing task type and error
```

## Remediation Steps

### Immediate
1. Inspect the DLQ messages to understand the failure pattern:
   - Same error on all? → Systematic bug
   - Random errors? → Transient dependency issue
2. If it's a transient issue (dependency was down), replay the DLQ:
   ```python
   # Move DLQ messages back to main queue
   while True:
       msg = redis.rpoplpush('dlq:incidents', 'queue:incidents')
       if msg is None:
           break
   ```

### Short-term
3. Fix the underlying bug causing the failures (add error handling, update deserialization).
4. Deploy the fix, then replay the DLQ.
5. Add structured error logging before DLQ send to capture failure reason:
   ```python
   logger.error("task_failed_to_dlq",
       task_id=task.id,
       error=str(exc),
       retry_count=task.retries)
   ```

### Long-term
6. Add DLQ inspector endpoint: `GET /admin/dlq/peek` to view without CLI.
7. Implement DLQ replay API: `POST /admin/dlq/replay?limit=100`.
8. Alert on DLQ depth > 50 for > 15 minutes.
9. Set DLQ TTL — auto-expire messages older than 7 days to prevent unbounded growth.

## Prevention
- Write tests for error paths in every worker task.
- Monitor DLQ depth from day one — it's a leading indicator of silent failures.
- Review DLQ contents weekly; never let messages accumulate without investigation.
