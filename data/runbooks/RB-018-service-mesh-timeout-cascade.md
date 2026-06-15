# RB-018 — Service Mesh Timeout Cascade

**Service:** Service Mesh (Istio/Linkerd)  
**Severity:** Critical  
**Tags:** service-mesh, istio, timeout, cascade, circuit-breaker

## Symptoms
- Multiple services simultaneously returning 503/504 errors
- Timeout errors propagating upstream (A→B→C all fail)
- Distributed traces show each service hitting its deadline
- Partial requests completing while others fail (non-deterministic)
- Recovery is slow even after root cause is fixed

## Possible Causes
- Slow downstream service causes upstream services to hold connections and exhaust pools
- Retry storms: each layer retries, multiplying load on the slow service
- No circuit breaker — all callers continue sending requests to an unhealthy service
- Global timeout policy too long, allowing request queues to grow unboundedly
- Missing bulkhead (thread/connection pool isolation between service calls)

## Diagnostic Steps

```bash
# Check Istio service mesh stats
istioctl proxy-config clusters <pod-name> --fqdn <service-name>

# Check for 503/504 at each hop in distributed trace
# Identify which service first became slow

# Check Envoy upstream connection pool stats
kubectl exec -it <pod> -c istio-proxy -- \
  pilot-agent request GET stats | grep upstream_cx_overflow

# Check retry budget consumption
istioctl dashboard kiali  # look for retry/error annotations on graph edges
```

```bash
# Prometheus: find which service has the highest error rate
sum by (destination_service) (rate(istio_requests_total{response_code=~"5.."}[5m]))
```

## Remediation Steps

### Immediate
1. Enable circuit breaker for the identified failing service:
   ```yaml
   apiVersion: networking.istio.io/v1alpha3
   kind: DestinationRule
   spec:
     trafficPolicy:
       outlierDetection:
         consecutive5xxErrors: 5
         interval: 10s
         baseEjectionTime: 30s
   ```
2. Shed load on the overloaded service — scale it up or reduce incoming rate.

### Short-term
3. Set global timeout at the mesh level (shorter than retry timeout):
   ```yaml
   # VirtualService
   timeout: 5s
   retries:
     attempts: 2
     perTryTimeout: 2s
     retryOn: "gateway-error,connect-failure"
   ```
4. Add connection pool limits per service to prevent pool exhaustion:
   ```yaml
   connectionPool:
     http:
       http2MaxRequests: 100
       pendingRequests: 50
   ```

### Long-term
5. Implement retry budgets (max X% of requests retried) to prevent retry storms.
6. Add Kiali or Grafana service graph alerts for error rate > 5% on any edge.
7. Conduct chaos engineering exercise (kill one service) to verify circuit breakers fire.

## Prevention
- Implement circuit breakers before traffic reaches production.
- Short, consistent timeouts at every hop — never leave I/O calls with infinite timeout.
- Regularly test fault injection (`fault: abort`) in staging to verify resilience patterns.
