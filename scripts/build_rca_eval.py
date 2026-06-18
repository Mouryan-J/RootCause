"""
Build the RCA reasoning evaluation dataset.

Unlike retrieval_eval.jsonl (which tests "can the retriever find the right
document"), this dataset tests "can the RCA agent diagnose the correct root
cause from ambiguous, noisy, symptom-only input." No incident title or log
line names the failure mode directly — that's the entire point. Each
incident has 2-3 candidate causes, exactly one correct, with the wrong ones
chosen because they're genuinely tempting given a superficial reading of the
same evidence.

Deliberately omits a separate `metrics_snapshot` field — all signals live
inside the unstructured `logs` text, the way a real on-call engineer would
actually encounter them, rather than handed to the system as a clean
key-value dict.

Run:  uv run python scripts/build_rca_eval.py
"""
import json
from collections import Counter
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "data" / "eval"


def _incident(
    incident_id: str,
    title: str,
    service: str,
    severity: str,
    log_lines: list[str],
    candidate_causes: list[dict],
    supporting_evidence_lines: list[int],
    distractor_evidence_lines: list[int],
    expected_remediation: list[str],
    difficulty_tier: int,
    required_reasoning_hops: int,
    category: str,
) -> dict:
    assert sum(1 for c in candidate_causes if c["is_correct"]) == 1, incident_id
    assert all(1 <= i <= len(log_lines) for i in supporting_evidence_lines), incident_id
    assert all(1 <= i <= len(log_lines) for i in distractor_evidence_lines), incident_id
    return {
        "incident_id": incident_id,
        "title": title,
        "service": service,
        "severity": severity,
        "logs": "\n".join(log_lines),
        "candidate_causes": candidate_causes,
        "supporting_evidence_lines": supporting_evidence_lines,
        "distractor_evidence_lines": distractor_evidence_lines,
        "expected_remediation": expected_remediation,
        "difficulty_tier": difficulty_tier,
        "required_reasoning_hops": required_reasoning_hops,
        "category": category,
    }


EVAL_INCIDENTS: list[dict] = [
    _incident(
        "RCA-EVAL-001",
        "API requests to order-service timing out intermittently over the last 20 minutes",
        "order-service", "high",
        [
            "13:25:00 INFO ci-cd: order-service deployed v3.8.1 (adds nightly reconciliation batch job, runs every 5 min)",
            "13:40:02 WARN order-service: db pool checkout took 4200ms (expected <50ms)",
            "13:40:15 ERROR order-service: could not obtain connection from pool within 5000ms",
            "13:41:00 INFO order-service: pg_stat_activity shows 198/200 connections in use",
            "13:41:05 INFO order-service: of those, 142 connections are idle-in-transaction, oldest started at 13:26:40",
            "13:41:30 WARN order-service: 40 requests queued waiting for db connection",
            "13:42:00 INFO order-service: request rate steady at ~120 req/s (baseline 110-130 req/s)",
        ],
        [
            {"id": "deploy_connection_leak", "label": "v3.8.1's new reconciliation job opens a DB connection per item and doesn't release it on exception, leaking connections every 5-minute run until the pool is exhausted", "is_correct": True, "why_plausible": None},
            {"id": "traffic_spike", "label": "A traffic spike overwhelmed normal connection pool sizing", "is_correct": False, "why_plausible": "Connections sitting near the 200 limit looks like a textbook load problem"},
        ],
        supporting_evidence_lines=[1, 5, 7],
        distractor_evidence_lines=[4],
        expected_remediation=[
            "Roll back order-service to v3.8.0, or patch the reconciliation job to release connections in a finally/context-manager block",
            "Set idle_in_transaction_session_timeout and add a pool-saturation alert",
        ],
        difficulty_tier=1, required_reasoning_hops=1, category="database",
    ),
    _incident(
        "RCA-EVAL-002",
        "Checkout latency increased roughly 4x over the last 30 minutes",
        "checkout-service", "high",
        [
            "13:55:00 INFO api-gateway: deployed payment-service v2.14.3 (canary 10%->100%) -- changelog: refactored pricing calc, added tax-lookup query",
            "14:02:11 WARN checkout-service: upstream call to payment-service took 2300ms (expected <300ms)",
            "14:02:14 WARN checkout-service: upstream call to payment-service took 2800ms",
            "14:03:02 ERROR payment-service: redis-cache GET timeout after 200ms",
            "14:03:05 INFO payment-service: cache miss rate 38% (baseline 4%)",
            "14:03:40 WARN postgres-primary: connections in use 180/200 (max 200)",
            "14:05:00 ERROR checkout-service: 12% of requests returning 504 Gateway Timeout",
        ],
        [
            {"id": "deploy_tax_lookup_regression", "label": "The new tax-lookup query added in v2.14.3 runs per line item with cache keys that don't match the existing warm cache set, adding DB round-trips and cache misses per checkout request", "is_correct": True, "why_plausible": None},
            {"id": "redis_cache_exhaustion", "label": "Redis cache is failing or evicting, causing a DB fallback", "is_correct": False, "why_plausible": "Cache miss rate jumping from 4% to 38% and a cache GET timeout look like Redis itself is the problem"},
            {"id": "postgres_pool_exhaustion", "label": "Postgres connection pool is independently near its limit", "is_correct": False, "why_plausible": "180/200 connections is the most alarming, concrete-looking number in the logs"},
        ],
        supporting_evidence_lines=[1, 2, 3, 5],
        distractor_evidence_lines=[4, 6, 7],
        expected_remediation=[
            "Roll back payment-service to v2.14.2",
            "Before redeploying, add a cache key strategy for the tax-lookup query so it doesn't add a DB round-trip per line item",
        ],
        difficulty_tier=2, required_reasoning_hops=2, category="deploy_regression",
    ),
    _incident(
        "RCA-EVAL-003",
        "Notification delivery lag climbing for the last 20 minutes",
        "notification-worker", "medium",
        [
            "10:10:00 INFO notification-worker: kafka consumer group lag climbing, 12k -> 80k messages over 20 minutes",
            "10:12:00 WARN notification-worker: webhook POST to partner-crm-api took 6200ms (expected <500ms)",
            "10:12:30 WARN notification-worker: webhook POST to partner-crm-api took 7100ms",
            "10:13:00 INFO kafka-broker-3: disk usage 71% (baseline 68%)",
            "10:13:10 INFO notification-worker: consumer throughput dropped from 800 msg/s to 60 msg/s",
            "10:14:00 INFO notification-worker: no errors in consumer loop, no rebalances, partition count unchanged",
        ],
        [
            {"id": "slow_downstream_webhook", "label": "partner-crm-api is responding slowly, and notification-worker calls it synchronously per message, so the slow downstream throttles the whole consumer to its response time", "is_correct": True, "why_plausible": None},
            {"id": "kafka_broker_capacity", "label": "Kafka broker disk pressure is slowing consumption", "is_correct": False, "why_plausible": "Disk usage and the word 'kafka' in the alert make the broker an easy first suspect"},
        ],
        supporting_evidence_lines=[2, 3, 5, 6],
        distractor_evidence_lines=[4],
        expected_remediation=[
            "Move webhook delivery off the synchronous consumer loop into an async/bounded-concurrency dispatcher with its own retry queue",
            "Add a per-call timeout and circuit breaker on partner-crm-api calls",
        ],
        difficulty_tier=2, required_reasoning_hops=2, category="messaging",
    ),
    _incident(
        "RCA-EVAL-004",
        "image-resizer pod restarted by Kubernetes, memory climbed steadily beforehand",
        "image-resizer", "high",
        [
            "09:00:00 INFO image-resizer: pod started, RSS 180MB",
            "11:00:00 INFO image-resizer: RSS 950MB, request rate unchanged at ~40 req/s",
            "11:45:00 WARN image-resizer: RSS 1.9GB, approaching container limit of 2GB",
            "11:50:12 ERROR kubelet: pod image-resizer-7d9f OOMKilled, exit code 137",
            "11:50:13 INFO image-resizer: pod restarted, RSS 180MB",
            "11:52:00 INFO image-resizer: traffic steady, no deploys in last 6 hours",
        ],
        [
            {"id": "gradual_memory_leak", "label": "Memory grows monotonically under steady traffic with no deploys -- a classic unbounded-cache or unclosed-resource leak in the image-processing path", "is_correct": True, "why_plausible": None},
            {"id": "traffic_spike_oom", "label": "A traffic spike pushed memory usage over the limit", "is_correct": False, "why_plausible": "OOMKilled events are usually associated with load spikes"},
        ],
        supporting_evidence_lines=[1, 2, 3, 6],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Profile the image-resizer process for unbounded growth (likely an in-memory thumbnail cache without eviction, or unclosed image buffers)",
            "Add a memory ceiling alert at 70% of container limit, and a periodic worker restart as a stopgap",
        ],
        difficulty_tier=1, required_reasoning_hops=1, category="resource_exhaustion",
    ),
    _incident(
        "RCA-EVAL-005",
        "Node disk pressure causing pod evictions on node-3",
        "payments-api", "medium",
        [
            "08:00:00 INFO node-3: disk usage 60%",
            "08:30:00 INFO ci-cd: payments-api deployed v5.2.0 (changelog: more detailed debug logging for fraud checks)",
            "09:15:00 WARN node-3: disk usage 88%",
            "09:20:00 WARN node-3: disk usage 94%, DiskPressure=true",
            "09:21:00 INFO kubelet: evicting pod payments-api-2 due to DiskPressure",
            "09:22:00 INFO payments-api: /var/log/payments-api.log is 38GB (was 200MB at last check)",
        ],
        [
            {"id": "verbose_logging_fills_disk", "label": "v5.2.0's new debug-level fraud-check logging writes far more volume than before, filling node disk and triggering eviction -- not a real capacity shortfall", "is_correct": True, "why_plausible": None},
            {"id": "organic_disk_growth", "label": "The node ran out of disk from normal data growth", "is_correct": False, "why_plausible": "DiskPressure and eviction events look like a generic capacity problem unless you check what's actually consuming the space"},
        ],
        supporting_evidence_lines=[2, 6],
        distractor_evidence_lines=[3, 4, 5],
        expected_remediation=[
            "Roll back the log level introduced in v5.2.0, or move fraud-check debug logs to sampled/structured logging with a volume cap",
            "Add log rotation/size limits and a disk-usage-by-directory alert instead of just node-level DiskPressure",
        ],
        difficulty_tier=2, required_reasoning_hops=1, category="resource_exhaustion",
    ),
    _incident(
        "RCA-EVAL-006",
        "Users being logged out unexpectedly, session lookups failing intermittently",
        "session-service", "high",
        [
            "16:00:00 INFO ci-cd: profile-service deployed v1.9.0 (changelog: cache full user activity history per session, was previously just last 10 events)",
            "16:05:00 WARN redis-sessions: used_memory 7.8GB / maxmemory 8GB",
            "16:06:00 WARN redis-sessions: evicted_keys climbing, 200/s",
            "16:06:30 ERROR session-service: session lookups failing, users being logged out unexpectedly",
            "16:07:00 INFO redis-sessions: avg value size for activity-history keys grew from 1.2KB to 45KB",
            "16:08:00 INFO session-service: request rate normal, ~500 req/s (baseline 480-520)",
        ],
        [
            {"id": "oversized_values_from_new_feature", "label": "profile-service's v1.9.0 now caches full activity history per session instead of last 10 events, making each value ~40x larger and exhausting Redis memory at the same key count", "is_correct": True, "why_plausible": None},
            {"id": "organic_cache_growth", "label": "Normal traffic growth filled the cache", "is_correct": False, "why_plausible": "Memory near the limit with rising eviction count looks like ordinary cache pressure from more traffic"},
        ],
        supporting_evidence_lines=[1, 5, 6],
        distractor_evidence_lines=[2, 3],
        expected_remediation=[
            "Roll back profile-service to v1.8.x, or cap cached activity history to a bounded window/size",
            "Separate session keys from large activity-history caches into different Redis logical DBs/instances",
        ],
        difficulty_tier=2, required_reasoning_hops=2, category="cache",
    ),
    _incident(
        "RCA-EVAL-007",
        "public-api returning SSL handshake errors for all clients",
        "public-api", "critical",
        [
            "00:00:00 INFO cert-manager: certificate public-api-tls renewal attempt failed, ACME challenge timeout",
            "00:00:05 WARN cert-manager: will retry renewal in 24h (no alert configured on renewal failure)",
            "06:00:00 ERROR public-api: certificate public-api-tls expired 2 hours ago (6 days after the failed renewal attempt above)",
            "06:00:01 ERROR client-sdk: SSL handshake failed, certificate has expired",
            "06:00:05 INFO public-api: traffic and deploy history unremarkable in the last 7 days",
        ],
        [
            {"id": "cert_renewal_silently_failed", "label": "cert-manager's automatic renewal failed a week before expiry and retried silently with no alerting, so the cert expired with nobody aware", "is_correct": True, "why_plausible": None},
            {"id": "recent_deploy_broke_tls", "label": "A recent deploy misconfigured TLS", "is_correct": False, "why_plausible": "TLS failures are commonly deploy-caused, so a recent deploy is the default suspect"},
        ],
        supporting_evidence_lines=[1, 2, 5],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Manually trigger cert renewal / issue an emergency certificate now to restore service",
            "Add alerting on cert-manager renewal failures, not just on certificate expiry",
        ],
        difficulty_tier=1, required_reasoning_hops=1, category="dns_cert",
    ),
    _incident(
        "RCA-EVAL-008",
        "Checkout failing with 504s, billing-service reporting thread pool exhaustion",
        "billing-service", "critical",
        [
            "12:00:00 WARN billing-service: calls to stripe-api p99 latency 4500ms (expected <400ms)",
            "12:00:30 INFO billing-service: Stripe status page reports 'investigating elevated error rates' (checked manually)",
            "12:01:00 WARN billing-service: retry count per request climbing, avg 3.2 retries (baseline 0.1)",
            "12:01:30 ERROR billing-service: thread pool exhausted, 0 available workers for new requests",
            "12:02:00 ERROR checkout-service: billing-service unavailable, 504s on /checkout",
            "12:02:10 INFO billing-service: no deploys in last 48 hours",
        ],
        [
            {"id": "upstream_provider_outage_amplified_by_retries", "label": "Stripe (external payment provider) is degraded; billing-service's aggressive retry policy with no circuit breaker amplifies the load and exhausts its own thread pool, which then cascades to checkout-service", "is_correct": True, "why_plausible": None},
            {"id": "billing_service_own_bug", "label": "billing-service itself has a bug causing the slowdown", "is_correct": False, "why_plausible": "The visible failure (thread pool exhaustion, 504s) is happening inside billing-service, making it the natural first place to look"},
        ],
        supporting_evidence_lines=[1, 2, 6],
        distractor_evidence_lines=[4, 5],
        expected_remediation=[
            "Add a circuit breaker around Stripe calls so retries stop amplifying load once the upstream is clearly degraded",
            "Shed load gracefully instead of exhausting the thread pool, and monitor third-party status as a first-class signal",
        ],
        difficulty_tier=3, required_reasoning_hops=2, category="network_third_party",
    ),
    _incident(
        "RCA-EVAL-009",
        "inventory-sync failing 100% of warehouse-api calls since this morning",
        "inventory-sync", "high",
        [
            "07:00:00 INFO secrets-vault: API key for warehouse-api rotated (scheduled quarterly rotation)",
            "07:00:10 ERROR inventory-sync: warehouse-api call failed, 401 Unauthorized",
            "07:00:15 INFO inventory-sync: secret client caches credentials in-memory with no TTL/refresh, last loaded at process start 3 days ago",
            "07:01:00 WARN inventory-sync: 100% of warehouse-api calls failing since 07:00:10",
            "07:02:00 INFO inventory-sync: no code deploy in last 5 days",
        ],
        [
            {"id": "stale_cached_credential", "label": "inventory-sync caches the warehouse-api credential in memory indefinitely and never reloads it, so the routine secret rotation invalidated its long-held cached key", "is_correct": True, "why_plausible": None},
            {"id": "warehouse_api_outage", "label": "warehouse-api itself is down or rejecting valid traffic", "is_correct": False, "why_plausible": "401s and a 100% failure rate look like the downstream service is broken"},
        ],
        supporting_evidence_lines=[1, 3, 5],
        distractor_evidence_lines=[4],
        expected_remediation=[
            "Restart inventory-sync to force a fresh credential load (immediate fix)",
            "Add credential TTL/auto-refresh on rotation events instead of caching indefinitely at process start",
        ],
        difficulty_tier=2, required_reasoning_hops=1, category="config",
    ),
    _incident(
        "RCA-EVAL-010",
        "Multiple unrelated services timing out against recommendations-service",
        "recommendations-service", "high",
        [
            "15:00:00 WARN recommendations-service: p99 latency to user-profile-service 3800ms (expected <200ms)",
            "15:01:00 WARN cart-service: retries to recommendations-service climbing, 4.5 avg retries/request",
            "15:01:30 WARN search-service: retries to recommendations-service climbing, 5.1 avg retries/request",
            "15:02:00 ERROR recommendations-service: request queue depth 2400, workers all busy",
            "15:02:30 INFO user-profile-service: GC pause spiked to 1800ms at 14:58, correlates with deploy of v4.0 at 14:55 (new caching layer)",
            "15:03:00 ERROR recommendations-service: 30% of requests timing out",
        ],
        [
            {"id": "upstream_gc_pause_amplified_by_mesh_retries", "label": "user-profile-service's new caching layer (deployed 14:55) causes long GC pauses, which slows recommendations-service's calls to it; mesh-wide retry policies then amplify that single slow dependency into load and timeouts across multiple unrelated services", "is_correct": True, "why_plausible": None},
            {"id": "recommendations_service_overloaded", "label": "recommendations-service itself is simply overloaded", "is_correct": False, "why_plausible": "The queue depth and timeout errors are visibly happening inside recommendations-service, making it look like the source rather than a victim"},
        ],
        supporting_evidence_lines=[1, 5],
        distractor_evidence_lines=[4, 6],
        expected_remediation=[
            "Roll back user-profile-service's v4.0 caching layer or tune its GC settings to eliminate the long pauses",
            "Cap retry counts and add circuit breakers mesh-wide so one slow dependency can't amplify into a multi-service retry storm",
        ],
        difficulty_tier=3, required_reasoning_hops=2, category="service_mesh",
    ),
    _incident(
        "RCA-EVAL-011",
        "by-region reports extremely slow since this morning's deploy",
        "reporting-service", "medium",
        [
            "10:00:00 INFO ci-cd: reporting-service deployed v2.3.0, includes migration adding `region` column to `orders` table",
            "10:05:00 WARN reporting-service: /reports/by-region queries taking 9000ms (expected <200ms)",
            "10:05:30 INFO postgres-primary: query plan for /reports/by-region shows Seq Scan on orders (4.2M rows)",
            "10:06:00 INFO postgres-primary: CPU and memory utilization normal, no other slow queries",
        ],
        [
            {"id": "missing_index_after_migration", "label": "The migration added a `region` column but no index, so the new by-region report query does a full sequential scan over 4.2M rows", "is_correct": True, "why_plausible": None},
            {"id": "db_under_resourced", "label": "The database server is under-provisioned", "is_correct": False, "why_plausible": "Slow queries are often blamed on database capacity by default"},
        ],
        supporting_evidence_lines=[1, 3, 4],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Add an index on orders(region) and re-run ANALYZE",
            "Add a migration checklist step requiring an index review for any new filterable/sortable column",
        ],
        difficulty_tier=1, required_reasoning_hops=1, category="database",
    ),
    _incident(
        "RCA-EVAL-012",
        "Dead letter queue depth climbing rapidly for events-processor",
        "events-processor", "medium",
        [
            "09:00:00 INFO ci-cd: upstream-service deployed v1.4.0, event payload field `discount_pct` changed from int to float",
            "09:05:00 WARN events-processor: DLQ depth climbing, 50 -> 4000 messages in 30 minutes",
            "09:06:00 ERROR events-processor: schema validation failed: discount_pct expected integer, got float, for 100% of failing messages",
            "09:07:00 INFO events-processor: worker count and CPU/memory normal, no scaling issue",
        ],
        [
            {"id": "schema_change_regression", "label": "upstream-service's v1.4.0 changed discount_pct's type, and events-processor's schema validator rejects the new shape, dead-lettering every affected message", "is_correct": True, "why_plausible": None},
            {"id": "events_processor_backlog", "label": "events-processor workers are under-provisioned and can't keep up with volume", "is_correct": False, "why_plausible": "A growing DLQ is the classic symptom people associate with a worker capacity/backlog problem"},
        ],
        supporting_evidence_lines=[1, 3, 4],
        distractor_evidence_lines=[2],
        expected_remediation=[
            "Update events-processor's schema validator to accept float for discount_pct (or have upstream-service revert the type change)",
            "Add contract testing between upstream-service and consumers before payload schema changes ship",
        ],
        difficulty_tier=2, required_reasoning_hops=1, category="messaging",
    ),
    _incident(
        "RCA-EVAL-013",
        "pricing-engine response times degraded, node CPU looks fine",
        "pricing-engine", "medium",
        [
            "11:00:00 WARN pricing-engine: p99 response time degraded from 80ms to 900ms",
            "11:01:00 INFO pricing-engine: CPU utilization (as % of node) reported at 35%, looks low",
            "11:01:30 INFO kubelet: container_cpu_cfs_throttled_periods_total climbing rapidly for pricing-engine",
            "11:02:00 INFO pricing-engine: container CPU limit set to 250m (0.25 core), request set to 100m",
            "11:02:30 INFO pricing-engine: traffic volume unremarkable, no deploys today",
        ],
        [
            {"id": "cpu_cfs_throttling", "label": "The container's CPU limit (250m) is far below what the workload needs in bursts; cgroup CFS throttling kicks in even though node-level utilization looks low, because the metric that matters is the container's own quota, not the node's", "is_correct": True, "why_plausible": None},
            {"id": "node_under_load", "label": "The underlying node is under heavy load from other workloads", "is_correct": False, "why_plausible": "Slow response times naturally suggest 'not enough compute somewhere', and node CPU is usually checked first"},
        ],
        supporting_evidence_lines=[2, 3, 4],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Raise the container's CPU limit (and request) to match observed burst usage",
            "Alert on container_cpu_cfs_throttled_periods_total directly, not just node/pod aggregate CPU%",
        ],
        difficulty_tier=2, required_reasoning_hops=1, category="resource_exhaustion",
    ),
    _incident(
        "RCA-EVAL-014",
        "search-api canary showing elevated error rate after deploy",
        "search-api", "high",
        [
            "14:00:00 INFO ci-cd: search-api canary v9.1.0 deployed to 10% of traffic",
            "14:02:00 WARN search-api: canary slice error rate 9% (stable slice 0.2%)",
            "14:02:30 INFO search-api: errors are NullPointerException in new `facet_filter` code path, added in v9.1.0",
            "14:03:00 INFO elasticsearch-cluster: cluster health green, no errors or slow queries logged",
        ],
        [
            {"id": "canary_code_bug", "label": "v9.1.0's new facet_filter code path throws a NullPointerException on a class of requests; the error is isolated to the canary slice running the new code", "is_correct": True, "why_plausible": None},
            {"id": "elasticsearch_issue", "label": "The underlying search backend is having problems", "is_correct": False, "why_plausible": "search-api errors might intuitively be blamed on its main datastore"},
        ],
        supporting_evidence_lines=[1, 2, 3, 4],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Roll back the canary to stable immediately (error isolated to the 10% slice)",
            "Fix the null-check in facet_filter and add a unit test for the missing-field case before re-attempting the canary",
        ],
        difficulty_tier=1, required_reasoning_hops=1, category="deploy_regression",
    ),
    _incident(
        "RCA-EVAL-015",
        "new_checkout_flow rolled out to 100% of users instead of the planned 5%",
        "feature-flag-service", "medium",
        [
            "13:00:00 WARN feature-flag-service(prod): flag `new_checkout_flow` returning true for 100% of users (expected 5% rollout per config repo)",
            "13:01:00 INFO feature-flag-service(staging): flag `new_checkout_flow` correctly returning true for 5% of users",
            "13:02:00 INFO config-repo: last commit to flags.yaml was 9 days ago, sets new_checkout_flow rollout to 5%",
            "13:03:00 INFO feature-flag-service(prod): admin UI shows rollout overridden to 100% by a manual change made 2 days ago, not reflected in git",
            "13:04:00 INFO new_checkout_flow: error rate among affected users 6% (untested at this scale)",
        ],
        [
            {"id": "undocumented_manual_override", "label": "Someone manually changed the rollout percentage to 100% directly in the admin UI 2 days ago, bypassing the git-tracked config -- production has silently drifted from the declared/reviewed state", "is_correct": True, "why_plausible": None},
            {"id": "deploy_bug", "label": "A recent deployment incorrectly applied the rollout config", "is_correct": False, "why_plausible": "Config-looking-wrong often gets blamed on the most recent deploy by default"},
        ],
        supporting_evidence_lines=[2, 3, 4],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Revert the rollout to 5% via the admin UI immediately to limit exposure to the untested flow",
            "Lock manual overrides behind the same review process as git-tracked config, or remove the admin UI's ability to bypass git entirely",
        ],
        difficulty_tier=2, required_reasoning_hops=1, category="config",
    ),
    _incident(
        "RCA-EVAL-016",
        "shipping-rates-service intermittently failing to reach carrier-api",
        "shipping-rates-service", "high",
        [
            "08:00:00 INFO platform-team: migrated internal DNS provider from CoreDNS to a new managed service at 07:30",
            "08:05:00 WARN shipping-rates-service: intermittent 'getaddrinfo ENOTFOUND' for carrier-api.internal, ~8% of calls",
            "08:06:00 INFO shipping-rates-service: failures are not correlated with any specific carrier-api instance or region",
            "08:07:00 INFO new-dns-service: client-side DNS cache TTL defaults to 1s (CoreDNS was configured at 30s), causing far higher query volume against the new resolver",
            "08:08:00 WARN new-dns-service: resolver query rate 40x normal, occasional rate-limit-style drops under burst",
            "08:09:00 INFO shipping-rates-service: no code deploy or config change to shipping-rates-service itself in 10 days",
        ],
        [
            {"id": "dns_migration_ttl_mismatch", "label": "The DNS provider migration changed the effective client-side cache TTL from 30s to 1s, multiplying query volume against the new resolver 40x and causing it to intermittently drop queries under burst -- an infrastructure change in a different team's system, not a shipping-rates-service problem", "is_correct": True, "why_plausible": None},
            {"id": "carrier_api_flaky", "label": "carrier-api itself is intermittently unavailable", "is_correct": False, "why_plausible": "ENOTFOUND-style errors against carrier-api naturally point first at carrier-api as the broken party"},
        ],
        supporting_evidence_lines=[1, 3, 4, 5, 6],
        distractor_evidence_lines=[2],
        expected_remediation=[
            "Set an explicit, longer DNS cache TTL on the new resolver (or in client-side resolver config) to bring query volume back to normal",
            "Add DNS resolution failure-rate monitoring as its own signal, separate from per-service uptime",
        ],
        difficulty_tier=3, required_reasoning_hops=2, category="network_third_party",
    ),
    _incident(
        "RCA-EVAL-017",
        "checkout-worker queue backing up, no autoscaling response",
        "checkout-worker", "high",
        [
            "17:00:00 WARN checkout-worker: queue depth climbing, 200 -> 9000 over 25 minutes",
            "17:05:00 INFO hpa-checkout-worker: current replicas 4, desired replicas 4 (no change)",
            "17:06:00 INFO hpa-checkout-worker: target metric `external.queue_depth` reporting value 0 consistently for the last hour",
            "17:07:00 INFO checkout-worker: CPU and memory per-pod normal, ~40% utilization",
            "17:08:00 INFO platform-team: queue_depth metric exporter was renamed during last week's monitoring migration; HPA config still references the old metric name",
        ],
        [
            {"id": "hpa_metric_misconfigured", "label": "The HPA is configured against a custom metric name that no longer exists after a monitoring migration, so it always reads 0 and never scales up regardless of real queue depth", "is_correct": True, "why_plausible": None},
            {"id": "insufficient_max_replicas", "label": "The HPA's max replica count has been reached", "is_correct": False, "why_plausible": "Queue backlog with no scale-up easily reads as 'hit the ceiling' rather than 'never started climbing'"},
        ],
        supporting_evidence_lines=[2, 3, 5],
        distractor_evidence_lines=[4],
        expected_remediation=[
            "Update the HPA's metric reference to the new exporter name immediately, and manually scale replicas in the meantime to drain the backlog",
            "Add an alert that fires when a custom HPA metric reports a flat/zero value for an extended period",
        ],
        difficulty_tier=2, required_reasoning_hops=1, category="resource_exhaustion",
    ),
    _incident(
        "RCA-EVAL-018",
        "Users reporting profile updates don't appear to save, though the UI confirms success",
        "profile-api", "medium",
        [
            "12:00:00 INFO support-team: users report 'my profile update didn't save' despite UI confirming success",
            "12:01:00 INFO profile-api: writes go to postgres-primary; reads for this endpoint go to postgres-replica-2 for load balancing",
            "12:02:00 WARN postgres-replica-2: replication lag 45 seconds (baseline <1s)",
            "12:03:00 INFO postgres-primary: write throughput and latency normal, writes confirmed committed",
            "12:04:00 INFO etl-job: large nightly export job running against postgres-replica-2 since 11:50, consuming heavy I/O",
        ],
        [
            {"id": "replica_lag_from_etl_job", "label": "A heavy ETL export job running against postgres-replica-2 is consuming I/O and causing 45s of replication lag, so users who read-after-write from the replica see stale data even though their write succeeded on the primary", "is_correct": True, "why_plausible": None},
            {"id": "app_write_bug", "label": "profile-api has a bug where writes don't actually persist", "is_correct": False, "why_plausible": "'My update didn't save' is exactly how users describe an application-level write bug, the intuitive first read of the report"},
        ],
        supporting_evidence_lines=[2, 3, 4, 5],
        distractor_evidence_lines=[],
        expected_remediation=[
            "Move read-after-write checks for this endpoint to the primary (or add a short client-side delay) until lag clears",
            "Throttle or reschedule the nightly ETL job to a replica not used for user-facing reads",
        ],
        difficulty_tier=3, required_reasoning_hops=2, category="database",
    ),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "rca_eval.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for entry in EVAL_INCIDENTS:
            f.write(json.dumps(entry) + "\n")

    categories = Counter(e["category"] for e in EVAL_INCIDENTS)
    tiers = Counter(e["difficulty_tier"] for e in EVAL_INCIDENTS)
    hops = Counter(e["required_reasoning_hops"] for e in EVAL_INCIDENTS)

    print(f"Saved {len(EVAL_INCIDENTS)} RCA reasoning incidents to {out_path}")
    print(f"Categories       : {dict(categories)}")
    print(f"Difficulty tiers : {dict(tiers)}")
    print(f"Reasoning hops   : {dict(hops)}")


if __name__ == "__main__":
    main()
