# RB-006 — API 5xx Error Rate Spike

**Service:** API Gateway / Backend Service  
**Severity:** Critical  
**Tags:** api, http, 5xx, errors, availability

## Symptoms
- Error rate alert fires: `http_requests_total{status=~"5.."} / http_requests_total > 0.01`
- Users report "Internal Server Error" or "Service Unavailable"
- Grafana dashboard shows error rate spike correlated with a deploy or traffic event
- Application logs show uncaught exceptions or panic/crash messages

## Possible Causes
- Recent deployment introduced a bug (regression)
- Downstream dependency (database, external API) became unavailable
- Resource exhaustion: OOM, file descriptor limit, thread pool saturation
- Configuration error in new deploy (missing env var, wrong endpoint URL)
- Unhandled exception in a newly exercised code path

## Diagnostic Steps

```bash
# Check error rate and which endpoints are affected
# (Prometheus)
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# Check recent deployments
kubectl rollout history deployment/rootcause-api
git log --oneline -10

# Tail application logs for exceptions
kubectl logs -l app=rootcause-api --tail=200 | grep -i 'error\|exception\|traceback'

# Check if downstream dependencies are healthy
curl -f http://postgres-svc:5432 || echo "postgres unreachable"
redis-cli -h redis-svc PING
```

```python
# In application: check Langfuse traces for failed LLM calls
# Or check structlog output for request correlation
```

## Remediation Steps

### Immediate
1. If a deployment is the likely cause, roll back:
   ```bash
   kubectl rollout undo deployment/rootcause-api
   ```
2. Verify rollback restored previous error rate within 2 minutes.
3. If not deployment-related, check each downstream dependency:
   - Database: can you connect and run `SELECT 1`?
   - Redis: does `PING` return `PONG`?
   - External APIs: check status pages.

### Short-term
4. Enable debug logging temporarily:
   ```bash
   kubectl set env deployment/rootcause-api LOG_LEVEL=DEBUG
   ```
5. Reproduce the error locally with the same request payload from logs.
6. Add unit test for the failing code path before re-deploying the fix.

### Long-term
7. Add integration test suite that covers all 3xx/5xx scenarios before deploy.
8. Implement circuit breaker on downstream calls (use `tenacity` with `stop_after_attempt`).

## Prevention
- Enforce canary deployment: route 5% of traffic to new version before full rollout.
- Alert on `error_rate > 1%` for 2 consecutive minutes.
- Add synthetic health check that exercises the full request path every 30 seconds.
