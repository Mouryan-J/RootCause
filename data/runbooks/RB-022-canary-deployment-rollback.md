# RB-022 — Canary Deployment Rollback

**Service:** Deployment / Release  
**Severity:** High  
**Tags:** deployment, canary, rollback, release

## Symptoms
- Canary error rate higher than stable track (>2× baseline error rate)
- Canary p99 latency significantly higher than stable
- Canary health check failing while stable track is healthy
- Automated canary analysis (Flagger/Argo Rollouts) marks deployment as failed

## Possible Causes
- New code has a bug only triggered by a subset of production traffic
- New version has incompatible DB migration not yet applied to prod
- New dependency version incompatible with production environment
- New config value wrong or missing in production `.env` / secrets
- New version uses more memory/CPU than the canary resource limit allows

## Diagnostic Steps

```bash
# Compare error rates between canary and stable
# Prometheus:
sum by (version) (rate(http_requests_total{status=~"5.."}[5m]))
/ sum by (version) (rate(http_requests_total[5m]))

# Check canary pod logs for errors not present in stable
kubectl logs -l version=canary --tail=200 | grep ERROR

# Check if canary has different env/config from stable
kubectl exec -it <canary-pod> -- env | sort > /tmp/canary-env.txt
kubectl exec -it <stable-pod> -- env | sort > /tmp/stable-env.txt
diff /tmp/canary-env.txt /tmp/stable-env.txt

# Check resource usage
kubectl top pods -l app=rootcause-api
```

## Remediation Steps

### Immediate
1. Roll back canary immediately if error rate > 2× baseline for > 2 minutes:
   ```bash
   # Kubernetes with Argo Rollouts:
   kubectl argo rollouts abort rootcause-api
   kubectl argo rollouts undo rootcause-api

   # Standard Kubernetes:
   kubectl rollout undo deployment/rootcause-api
   ```
2. Verify rollback restored stable error rate within 2 minutes.
3. Confirm all canary pods are terminated:
   ```bash
   kubectl get pods -l app=rootcause-api -w
   ```

### Short-term
4. Reproduce the failure locally with the canary version against a production-like dataset.
5. Compare the canary config against stable; identify missing or wrong environment variables.
6. Check if the DB migration was applied before the canary started receiving traffic.

### Long-term
7. Automate canary rollback: use Flagger or Argo Rollouts with Prometheus metrics gate.
8. Define canary success criteria explicitly:
   - Error rate delta < 0.5%
   - p99 latency delta < 20%
   - Duration: 10 minutes at 5% traffic before full rollout
9. Never allow manual canary promotion without automated metrics gate passing.

## Prevention
- Automate canary analysis — manual canary promotion always carries human error risk.
- Apply DB migrations separately from code deploys, with backward compatibility.
- Test canary promotion criteria in staging before production.
