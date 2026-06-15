# RB-015 — Autoscaling Not Triggering Under Load

**Service:** Kubernetes HPA  
**Severity:** High  
**Tags:** kubernetes, hpa, autoscaling, capacity

## Symptoms
- CPU/memory utilization high but pod count stays at `minReplicas`
- HPA shows `<unknown>` for current metrics
- `kubectl describe hpa` shows `unable to get metrics` or `failed to compute desired replicas`
- Application latency rises under load with no scale-out

## Possible Causes
- `metrics-server` not installed or not running in the cluster
- CPU `requests` not set on the deployment (HPA requires requests to compute utilization %)
- HPA target metric name wrong or metrics API not returning data
- `minReplicas == maxReplicas` (effectively disabled)
- Scale-down cooldown preventing scale-up due to a bug in HPA configuration
- Custom metric adapter (Prometheus Adapter) not configured correctly

## Diagnostic Steps

```bash
# Check HPA status
kubectl describe hpa rootcause-api-hpa

# Check if metrics-server is running
kubectl get pods -n kube-system | grep metrics-server

# Check if metrics API is available
kubectl top pods -l app=rootcause-api

# Check if CPU requests are set
kubectl get deployment rootcause-api \
  -o jsonpath='{.spec.template.spec.containers[0].resources.requests}'

# Check HPA events
kubectl get events --field-selector involvedObject.kind=HorizontalPodAutoscaler
```

## Remediation Steps

### Immediate
1. If metrics-server is missing, install it:
   ```bash
   kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
   ```
2. If CPU requests are missing, add them (this is required for HPA to function):
   ```bash
   kubectl set resources deployment/rootcause-api --requests=cpu=250m
   ```
3. If HPA target is wrong, correct it:
   ```yaml
   metrics:
   - type: Resource
     resource:
       name: cpu
       target:
         type: Utilization
         averageUtilization: 70
   ```

### Short-term
4. Manually scale out as a stopgap while fixing HPA:
   ```bash
   kubectl scale deployment/rootcause-api --replicas=5
   ```
5. Verify HPA can see metrics after fix:
   ```bash
   kubectl get hpa rootcause-api-hpa --watch
   ```

### Long-term
6. Add Grafana panel showing HPA current vs desired vs min vs max replicas.
7. Add alert: `kube_horizontalpodautoscaler_status_current_replicas == kube_horizontalpodautoscaler_spec_max_replicas` for > 5 minutes (maxed out).
8. Test autoscaling in staging using a load test before production deploy.

## Prevention
- Always set `resources.requests` for CPU on every deployment.
- Test HPA in staging: apply load, verify scale-out occurs within 3 minutes.
- Alert on HPA `<unknown>` metric status immediately — it means HPA is blind.
