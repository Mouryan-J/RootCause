# RB-019 — Kafka Consumer Lag Spike

**Service:** Kafka / Message Queue  
**Severity:** High  
**Tags:** kafka, consumer-lag, messaging, throughput

## Symptoms
- Consumer group lag alert fires: `kafka_consumer_lag_sum > 10000`
- Events are processed with increasing delay
- Downstream systems receive events late (reporting, alerting pipelines affected)
- Consumer pods CPU/memory are not saturated — lag not caused by resource exhaustion

## Possible Causes
- Consumer processing time increased (slow downstream DB query, LLM call, etc.)
- Consumer pod count reduced (scale-down, OOMKill, deployment)
- Producer throughput spike — events arriving faster than consumers can process
- Rebalance storm: consumers repeatedly joining/leaving group, triggering rebalances
- Deserialization error causing consumer to stall on a single message
- Topic partition count too low — not enough parallelism

## Diagnostic Steps

```bash
# Check consumer group lag
kafka-consumer-groups.sh \
  --bootstrap-server $KAFKA_BROKERS \
  --describe --group rootcause-consumers

# Check consumer pod count
kubectl get pods -l app=rootcause-consumer

# Check for rebalances in consumer logs
kubectl logs -l app=rootcause-consumer --tail=200 | grep -i 'rebalance\|assign\|revoke'

# Check message processing time from traces/metrics
# Prometheus:
histogram_quantile(0.99, rate(kafka_consumer_fetch_latency_avg[5m]))
```

## Remediation Steps

### Immediate
1. Scale up consumers to match partition count (max parallelism = partition count):
   ```bash
   kubectl scale deployment/rootcause-consumer --replicas=6
   ```
2. If a single bad message is causing the stall, skip it:
   ```bash
   # Advance offset past the bad message
   kafka-consumer-groups.sh --bootstrap-server $KAFKA_BROKERS \
     --group rootcause-consumers \
     --topic incidents \
     --reset-offsets --shift-by 1 --execute
   ```

### Short-term
3. Identify what slowed consumer processing — add per-message processing time metric.
4. Move slow I/O (DB writes, LLM calls) to async sub-tasks to increase throughput.
5. Increase `max.poll.interval.ms` if long-running processing is legitimate:
   ```python
   consumer = KafkaConsumer(
       max_poll_interval_ms=300000,  # 5 minutes
       max_poll_records=10,  # fewer records per poll = more frequent commits
   )
   ```

### Long-term
6. Alert on consumer lag > 1000 messages for > 5 minutes.
7. Increase partition count if max scale-out is still insufficient:
   ```bash
   kafka-topics.sh --alter --topic incidents \
     --partitions 12 --bootstrap-server $KAFKA_BROKERS
   ```
8. Add Dead Letter Topic (DLT) for messages that fail after 3 retries.

## Prevention
- Set consumer lag alert before deployment; don't discover it from user reports.
- Test consumer throughput under 3× expected peak load in staging.
- Match partition count to maximum expected consumer pod count.
