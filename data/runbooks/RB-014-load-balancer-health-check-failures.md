# RB-014 — Load Balancer Health Check Failures

**Service:** Load Balancer / Ingress  
**Severity:** Critical  
**Tags:** load-balancer, health-check, ingress, availability

## Symptoms
- Load balancer marks backend instances as unhealthy
- Traffic is routed to a reduced set of backends or none at all
- Health check endpoint returns non-2xx or times out
- Clients receive 502/503 errors at the LB level

## Possible Causes
- Application startup is slow — health check fires before app is ready
- Health check endpoint itself has a bug (throws 500)
- Health check timeout too short for slow dependency checks
- Application is healthy but port/path in LB config is wrong
- Underlying dependency (DB, Redis) checked by health endpoint is down

## Diagnostic Steps

```bash
# Test health check endpoint directly from the LB's network
curl -v http://<backend-ip>:8000/health

# Check what the LB is configured to check
# (Render, AWS ALB, or nginx upstream config)

# Check application startup logs
kubectl logs <pod-name> --previous  # if pod was restarted

# Check if the /health endpoint itself errors
kubectl exec -it <pod-name> -- curl -s http://localhost:8000/health
```

```python
# Verify the health check endpoint logic — it should NOT check
# external dependencies by default. Keep it lightweight:
# Good:  return {"status": "ok"}
# Risky: check DB connection (fails if DB is slow, marks healthy pod as unhealthy)
```

## Remediation Steps

### Immediate
1. Verify the health check URL and port match the running application:
   ```bash
   kubectl get svc rootcause-api -o yaml | grep -A 5 port
   ```
2. Hit the health endpoint directly from inside the pod:
   ```bash
   kubectl exec -it <pod> -- curl http://localhost:8000/health
   ```
3. If health check is too strict (checking DB), temporarily simplify it to return 200 always.

### Short-term
4. Split into two endpoints:
   - `/health` — liveness: returns `200 {"status":"ok"}` always if process is running
   - `/ready` — readiness: checks DB, Redis connectivity; used for traffic routing
5. Increase health check timeout and grace period in LB config:
   - Initial delay: 30s (allow startup)
   - Timeout: 5s
   - Interval: 10s
   - Unhealthy threshold: 3 consecutive failures

### Long-term
6. Add startup probe (`/health`) separate from readiness probe (`/ready`).
7. Implement health check response with component status for observability:
   ```json
   {
     "status": "ok",
     "components": {
       "postgres": "ok",
       "redis": "ok",
       "qdrant": "degraded"
     }
   }
   ```

## Prevention
- Always configure `initialDelaySeconds` in Kubernetes probes to match startup time.
- Use separate liveness and readiness probes — don't combine them.
- Test health check behavior during DB/Redis downtime before production deploy.
