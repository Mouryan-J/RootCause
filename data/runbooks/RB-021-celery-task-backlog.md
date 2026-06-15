# RB-021 — Celery Task Backlog

**Service:** Celery Workers  
**Severity:** High  
**Tags:** celery, workers, queue, backlog, async

## Symptoms
- Celery queue depth growing: `celery inspect stats` shows high `total` task count
- Tasks that should complete in seconds are taking minutes
- Redis queue key length > expected: `redis-cli LLEN celery`
- Background jobs (report generation, email sending) delayed significantly

## Possible Causes
- Worker count too low for incoming task rate
- Task processing time increased (slow external calls)
- Workers stuck on long-running tasks, not picking up new ones
- `prefetch_multiplier` too high — each worker reserved too many tasks
- Task routing misconfigured — tasks sent to wrong queue with no consumers

## Diagnostic Steps

```bash
# Check active, reserved, and scheduled tasks
celery -A rootcause inspect active
celery -A rootcause inspect reserved
celery -A rootcause inspect stats

# Check queue depth in Redis
redis-cli LLEN celery
redis-cli LLEN celery:high_priority

# Check worker pod count
kubectl get pods -l app=rootcause-worker

# Check for stuck tasks (running > 5 minutes)
celery -A rootcause inspect active | grep -B5 "time_start"
```

## Remediation Steps

### Immediate
1. Scale up workers:
   ```bash
   kubectl scale deployment/rootcause-worker --replicas=8
   ```
2. If workers are stuck (not consuming), restart them:
   ```bash
   celery -A rootcause control pool_restart
   # or:
   kubectl rollout restart deployment/rootcause-worker
   ```
3. Reduce `prefetch_multiplier` so tasks are distributed more evenly:
   ```python
   # celeryconfig.py
   worker_prefetch_multiplier = 1
   ```

### Short-term
4. Add task time limit to prevent workers being blocked indefinitely:
   ```python
   @celery_app.task(soft_time_limit=60, time_limit=90)
   def analyze_incident(incident_id: str) -> dict:
       ...
   ```
5. Add priority queues for time-sensitive tasks:
   ```python
   analyze_incident.apply_async(queue='high_priority')
   ```
6. Add Flower monitoring dashboard for Celery:
   ```bash
   celery -A rootcause flower --port=5555
   ```

### Long-term
7. Alert on `celery_queue_length > 500` for > 3 minutes.
8. Implement HPA on custom metric: Celery queue depth drives worker replica count.
9. Move truly async work to dedicated queues with separate worker pools.

## Prevention
- Set `task_time_limit` on every task — never allow unbounded execution.
- Right-size worker count based on observed task throughput in staging.
- Monitor queue depth continuously; a growing queue is always a leading indicator of trouble.
