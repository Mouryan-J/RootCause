# RB-009 — gRPC Deadline Exceeded Errors

**Service:** gRPC Service  
**Severity:** High  
**Tags:** grpc, deadline, timeout, rpc

## Symptoms
- Client-side errors: `StatusCode.DEADLINE_EXCEEDED` or `grpc.StatusCode.DEADLINE_EXCEEDED`
- Partial request completion — some RPCs succeed, some time out
- Server-side logs show requests still in progress when client gave up
- Latency histogram shows bimodal distribution: fast requests and requests at exactly the deadline

## Possible Causes
- Client deadline set too low for current server processing time
- Server processing time genuinely increased (slow downstream, CPU contention)
- Network latency increased between client and server
- Server thread/goroutine pool saturated — requests queued too long
- Cascading timeouts: client deadline expires while server waits on its own downstream call

## Diagnostic Steps

```bash
# Check gRPC server metrics (if using grpc_prometheus)
# Prometheus:
grpc_server_handling_seconds_bucket{grpc_type="unary"}
rate(grpc_server_handled_total{grpc_code="DeadlineExceeded"}[5m])

# Check server-side processing time distribution
histogram_quantile(0.99, rate(grpc_server_handling_seconds_bucket[5m]))

# Network round-trip check
ping -c 20 <grpc_server_host>
traceroute <grpc_server_host>
```

```python
# Add deadline propagation debug logging on server:
import grpc

def intercept(continuation, client_call_details, request_or_iterator):
    deadline = client_call_details.timeout
    print(f"Received call with deadline: {deadline}s remaining")
    return continuation(client_call_details, request_or_iterator)
```

## Remediation Steps

### Immediate
1. Identify if deadlines are too tight or server is too slow:
   - If p99 server time < client deadline → network or queueing issue
   - If p99 server time > client deadline → server is slow
2. Temporarily increase client deadline to gather baseline:
   ```python
   stub.MyMethod(request, timeout=30.0)  # was 5.0
   ```
3. If server is overloaded, scale out:
   ```bash
   kubectl scale deployment/grpc-service --replicas=5
   ```

### Short-term
4. Implement deadline propagation: server should not start work if deadline already exceeded:
   ```python
   if context.time_remaining() < 0.1:
       context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "Deadline exceeded before processing")
   ```
5. Add retry with exponential backoff on the client (idempotent RPCs only):
   ```python
   options = [('grpc.enable_retries', 1), ('grpc.service_config', retry_policy)]
   ```
6. Review and fix any blocking calls inside gRPC handlers (use `asyncio` / thread pools).

### Long-term
7. Adopt hedged requests for latency-sensitive RPCs.
8. Add per-RPC SLO dashboard with deadline breach rate alert.

## Prevention
- Set deadlines based on measured p99 + 2× buffer, not arbitrary round numbers.
- Always propagate deadlines downstream — never start new I/O with a fresh timeout if the incoming deadline has already been exceeded.
- Test deadline behavior under load in staging.
