# RB-016 — DNS Resolution Failures

**Service:** DNS / Service Discovery  
**Severity:** Critical  
**Tags:** dns, networking, service-discovery, coreDNS

## Symptoms
- `socket.gaierror: [Errno -2] Name or service not known`
- `ConnectionError: HTTPSConnectionPool ... Max retries exceeded`
- Services unable to reach each other by hostname within cluster
- External API calls failing with DNS-level errors
- `nslookup` / `dig` returning `SERVFAIL` or `NXDOMAIN`

## Possible Causes
- CoreDNS pods crashing or OOMKilled in Kubernetes
- DNS search domain misconfiguration (`resolv.conf`)
- Split-horizon DNS issue (internal vs external resolution conflict)
- ndots configuration causing excessive DNS lookups for short names
- DNS cache poisoned or stale
- Network policy blocking UDP port 53 to CoreDNS

## Diagnostic Steps

```bash
# Test DNS from inside a pod
kubectl run -it --rm dns-test --image=busybox --restart=Never -- \
  nslookup kubernetes.default

# Check CoreDNS pod status
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check CoreDNS logs
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100

# Check resolv.conf inside affected pod
kubectl exec -it <pod-name> -- cat /etc/resolv.conf

# Test external DNS
kubectl exec -it <pod-name> -- nslookup api.openai.com
```

```bash
# Check DNS error rate (CoreDNS Prometheus metrics)
rate(coredns_dns_responses_total{rcode="SERVFAIL"}[5m])
```

## Remediation Steps

### Immediate
1. Restart CoreDNS pods if they are crashing:
   ```bash
   kubectl rollout restart deployment/coredns -n kube-system
   ```
2. Verify DNS works from inside a test pod after restart.

### Short-term
3. If ndots is causing excessive lookups, tune in pod spec:
   ```yaml
   dnsConfig:
     options:
     - name: ndots
       value: "2"
   ```
4. If external DNS is failing from pods, check egress network policies:
   ```bash
   kubectl get networkpolicies -n <namespace>
   ```
5. Increase CoreDNS memory limit if it is OOMKilling:
   ```bash
   kubectl set resources deployment/coredns -n kube-system --limits=memory=256Mi
   ```

### Long-term
6. Add `coredns_dns_responses_total{rcode="SERVFAIL"}` alert in Grafana.
7. Use NodeLocal DNSCache to reduce CoreDNS load and improve resolution latency.
8. Add DNS health check to synthetic monitoring suite.

## Prevention
- Monitor CoreDNS memory usage; OOMKill is the most common cause of DNS outages.
- Test DNS resolution after any network policy change.
- Keep CoreDNS version updated — older versions have known stability issues.
