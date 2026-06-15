# RB-017 — SSL Certificate Expiry

**Service:** TLS / HTTPS  
**Severity:** Critical  
**Tags:** ssl, tls, certificate, https, expiry

## Symptoms
- Clients receive `SSL_ERROR_RX_RECORD_TOO_LONG` or `certificate has expired`
- `curl` returns `SSL certificate problem: certificate has expired`
- Browser shows security warning; users cannot proceed
- Webhook deliveries failing with TLS handshake errors

## Possible Causes
- Auto-renewal (Let's Encrypt / cert-manager) failed silently
- Certificate renewed in wrong namespace or secret not updated in ingress
- Manual certificate not renewed before expiry
- cert-manager pod crashed or ClusterIssuer misconfigured
- DNS validation failing for Let's Encrypt renewal challenge

## Diagnostic Steps

```bash
# Check certificate expiry
echo | openssl s_client -connect yourdomain.com:443 2>/dev/null \
  | openssl x509 -noout -dates

# Check cert-manager certificate objects
kubectl get certificates -A
kubectl describe certificate rootcause-tls -n default

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager --tail=100

# Check if the TLS secret exists and is current
kubectl get secret rootcause-tls -o yaml | grep -A 5 "tls.crt"
kubectl get secret rootcause-tls -o jsonpath='{.data.tls\.crt}' \
  | base64 -d | openssl x509 -noout -dates

# Check ACME challenge status
kubectl get challenges -A
```

## Remediation Steps

### Immediate
1. Manually trigger certificate renewal:
   ```bash
   kubectl cert-manager renew rootcause-tls -n default
   ```
2. If cert-manager renewal is stuck, delete the certificate object and recreate:
   ```bash
   kubectl delete certificate rootcause-tls
   kubectl apply -f k8s/certificate.yaml
   ```
3. If you have a spare certificate from another provider, upload it immediately as a stopgap:
   ```bash
   kubectl create secret tls rootcause-tls \
     --cert=path/to/cert.crt --key=path/to/cert.key \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

### Short-term
4. Fix the underlying cert-manager issue (check ACME challenge, DNS records, firewall rules).
5. Verify auto-renewal works end-to-end in staging.

### Long-term
6. Add Prometheus alert: `certmanager_certificate_expiration_timestamp_seconds - time() < 604800` (7 days).
7. Add a separate external monitoring check (e.g., UptimeRobot certificate monitor).
8. Use `Certificate` with `renewBefore: 720h` (30 days) to give ample renewal window.

## Prevention
- Monitor certificate expiry externally (outside the cluster) — internal tooling can also expire.
- Alert at 30 days before expiry, not 7 days.
- Test renewal process quarterly in staging.
