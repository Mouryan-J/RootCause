# RB-013 — CPU Throttling in Containers

**Service:** Any containerized service  
**Severity:** Medium  
**Tags:** kubernetes, cpu, throttling, performance, limits

## Symptoms
- Application latency increases without corresponding traffic spike
- `container_cpu_cfs_throttled_seconds_total` metric rising
- CPU usage stays below `limits` but latency is high
- Periodic latency spikes every 100ms (CFS scheduler period)

## Possible Causes
- CPU limit set too low relative to burst workload needs
- CPU request set too high, preventing scheduling on available nodes
- LLM inference or embedding generation needs brief CPU bursts beyond the limit
- Python GIL contention amplifying throttling effects
- Cron-like batch jobs competing with API workers on the same CPU quota

## Diagnostic Steps

```bash
# Check CPU throttle ratio
# Prometheus:
rate(container_cpu_cfs_throttled_seconds_total{container="rootcause-api"}[5m])
/ rate(container_cpu_cfs_periods_total{container="rootcause-api"}[5m])
# > 0.25 (25% throttled) is a problem

# Check current CPU request/limit
kubectl get deployment rootcause-api -o jsonpath=\
'{.spec.template.spec.containers[0].resources}'

# Check actual CPU usage
kubectl top pod -l app=rootcause-api

# Check if throttling correlates with specific endpoints
# Use distributed traces to find CPU-heavy handlers
```

## Remediation Steps

### Immediate
1. Increase CPU limit to reduce throttling:
   ```bash
   kubectl set resources deployment/rootcause-api \
     --limits=cpu=2000m --requests=cpu=500m
   ```
2. Verify throttle ratio drops after applying new limits.

### Short-term
3. Profile the application to find CPU hotspots:
   ```bash
   # py-spy for Python
   pip install py-spy
   py-spy top --pid <pid>
   py-spy record -o profile.svg --pid <pid> --duration 30
   ```
4. Move CPU-intensive tasks (tokenization, embedding) to async background workers.
5. Consider using `uvicorn --workers 2` to leverage multiple CPU cores.

### Long-term
6. Set CPU limit at 2–4× the p99 CPU usage to allow bursts without constant throttling.
7. Use HPA (Horizontal Pod Autoscaler) on CPU metric to scale out instead of up:
   ```yaml
   metrics:
   - type: Resource
     resource:
       name: cpu
       target:
         type: Utilization
         averageUtilization: 70
   ```
8. Add `container_cpu_cfs_throttled_periods_total` dashboard panel.

## Prevention
- Never set CPU limits at 1:1 with typical usage — always allow burst headroom.
- Monitor throttle ratio in Grafana; alert if > 20% throttled.
- Test CPU behavior under p99 load, not just average load.
