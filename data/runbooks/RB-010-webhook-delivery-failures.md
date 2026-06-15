# RB-010 — Webhook Delivery Failures

**Service:** Webhook Dispatcher  
**Severity:** Medium  
**Tags:** webhook, http, delivery, retries, integration

## Symptoms
- Webhook delivery success rate drops below 95% in monitoring
- Partner/customer systems report missing events
- Dead letter queue for failed webhooks growing
- Application logs show `ConnectionRefusedError`, `TimeoutError`, or non-2xx HTTP responses from endpoint

## Possible Causes
- Target endpoint is down or returning errors (5xx)
- Target endpoint changed URL without updating webhook registration
- TLS certificate on target endpoint expired
- Firewall rules blocking outbound connections from dispatcher
- Payload too large (target rejects with 413)
- Target rate-limiting the dispatcher (429 responses)

## Diagnostic Steps

```bash
# Check webhook delivery logs
kubectl logs -l app=webhook-dispatcher --tail=500 | grep -i 'error\|failed\|5[0-9][0-9]'

# Test connectivity to target endpoint manually
curl -v -X POST https://target.example.com/webhook \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Check TLS certificate
openssl s_client -connect target.example.com:443 < /dev/null 2>/dev/null | openssl x509 -noout -dates

# Check dead letter queue depth
redis-cli LLEN webhook:dlq
```

```python
# Sample the last 10 failed delivery attempts from logs or DB
# to identify which endpoints are failing and why
```

## Remediation Steps

### Immediate
1. Check if the target endpoint is reachable from the dispatcher pod:
   ```bash
   kubectl exec -it <dispatcher-pod> -- curl -v https://target.example.com/webhook
   ```
2. If endpoint is down — pause delivery to that endpoint to stop filling the DLQ:
   ```python
   # Set endpoint status to 'paused' in webhook_subscriptions table
   UPDATE webhook_subscriptions SET status='paused', paused_reason='endpoint_unreachable'
   WHERE endpoint_url = '<url>';
   ```
3. Notify the webhook subscriber of the outage.

### Short-term
4. Implement exponential backoff retry: attempt 1 → 1min, 2 → 5min, 3 → 30min, 4 → 2h, 5 → 24h.
5. Add DLQ replay capability: once endpoint recovers, replay failed events in order.
6. Validate TLS certificates on webhook registration, not just at delivery time.

### Long-term
7. Implement circuit breaker per endpoint: after 5 consecutive failures, pause delivery for 10 minutes.
8. Add webhook delivery dashboard: per-endpoint success rate, p99 latency, DLQ depth.
9. Support webhook signature verification so target can reject forged payloads.

## Prevention
- Test webhook endpoint reachability on registration (not just format).
- Alert on per-endpoint error rate > 10% for 5 minutes.
- Expire webhooks after 30 consecutive days of delivery failure with email notification to owner.
