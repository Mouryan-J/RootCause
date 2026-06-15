# RB-011 — Kubernetes Pod OOMKilled

**Service:** Any containerized service  
**Severity:** High  
**Tags:** kubernetes, oom, memory, container, limits

## Symptoms
- Pod status shows `OOMKilled` in `kubectl get pods`
- `kubectl describe pod <name>` shows `Last State: Terminated Reason: OOMKilled`
- CrashLoopBackOff follows repeated OOMKills
- Alerts fire on pod restart count > 3 in 10 minutes

## Possible Causes
- Memory limit set too low for actual workload
- Memory leak in application (see RB-008)
- Sudden traffic spike loading more data into memory than usual
- Large LLM response or embedding batch exceeding expected memory
- JVM (Neo4j, Kafka) heap + off-heap exceeding container limit

## Diagnostic Steps

```bash
# Check pod status and last termination reason
kubectl describe pod <pod-name> -n <namespace> | grep -A 10 "Last State"

# Check current memory usage vs limit
kubectl top pod <pod-name>

# Check memory limit in deployment spec
kubectl get deployment <name> -o jsonpath='{.spec.template.spec.containers[0].resources}'

# Check node-level OOM events
kubectl get events --field-selector reason=OOMKilling -n <namespace>

# Check if the node itself is memory-pressured
kubectl describe node <node-name> | grep -A 5 "Conditions"
```

```bash
# Historical memory metrics (if Prometheus + node-exporter)
container_memory_working_set_bytes{container="rootcause-api"}
```

## Remediation Steps

### Immediate
1. Increase memory limit to stop the OOMKill loop:
   ```bash
   kubectl set resources deployment/rootcause-api \
     --limits=memory=1Gi --requests=memory=512Mi
   ```
2. Verify pods are stable after the limit increase.

### Short-term
3. Profile memory usage: capture heap snapshot or use `tracemalloc` (see RB-008).
4. Identify the specific operation causing the spike (large batch? big LLM response?).
5. Add memory usage metric: `process_resident_memory_bytes` in Prometheus.
6. Set VPA (Vertical Pod Autoscaler) to auto-recommend limits based on observed usage.

### Long-term
7. Add memory limit as a percentage of observed p99 usage + 30% headroom.
8. Add alert on `container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85`.
9. For LLM workloads, stream responses instead of loading full response into memory.

## Prevention
- Always set both `requests` and `limits` — never leave memory limits unset.
- Right-size limits using observed data, not guesses (use VPA recommendations).
- Load test with representative payloads before setting production limits.
