"""
Build the RAG retrieval evaluation dataset.
Each entry is a realistic incident query mapped to expected runbook IDs.

Run:  uv run python scripts/build_eval.py
"""
import json
from collections import Counter
from pathlib import Path

OUT_DIR = Path(__file__).parent.parent / "data" / "eval"

EVAL_QUERIES = [
    # RB-001 — Postgres high connections
    {
        "id": "eval-001",
        "query": "PostgreSQL is rejecting new connections with: remaining connection slots are reserved for non-replication superuser connections",
        "expected_runbooks": ["RB-001"],
        "category": "database",
        "difficulty": "easy",
    },
    {
        "id": "eval-002",
        "query": "API pods are timing out connecting to the database, pg_stat_activity shows we are near max_connections limit and pgbouncer pool is full",
        "expected_runbooks": ["RB-001"],
        "category": "database",
        "difficulty": "medium",
    },
    # RB-002 — Postgres slow queries
    {
        "id": "eval-003",
        "query": "Database queries that used to take 10ms are now taking 8 seconds, Grafana shows pg_stat_activity full of long-running queries",
        "expected_runbooks": ["RB-002"],
        "category": "database",
        "difficulty": "easy",
    },
    {
        "id": "eval-004",
        "query": "Postgres autovacuum has not run in 3 days and query plans are using sequential scans instead of indexes",
        "expected_runbooks": ["RB-002"],
        "category": "database",
        "difficulty": "medium",
    },
    # RB-003 — Redis memory exhaustion
    {
        "id": "eval-005",
        "query": "Redis is returning OOM command not allowed when used_memory exceeds maxmemory",
        "expected_runbooks": ["RB-003"],
        "category": "cache",
        "difficulty": "easy",
    },
    {
        "id": "eval-006",
        "query": "Cache layer is completely unresponsive, Redis INFO shows used_memory near maxmemory and evicted_keys rising fast",
        "expected_runbooks": ["RB-003"],
        "category": "cache",
        "difficulty": "medium",
    },
    # RB-004 — Redis eviction spike
    {
        "id": "eval-007",
        "query": "Redis keyspace hit rate dropped from 95% to 40% overnight, evicted_keys counter is increasing rapidly",
        "expected_runbooks": ["RB-004"],
        "category": "cache",
        "difficulty": "easy",
    },
    {
        "id": "eval-008",
        "query": "After a traffic spike our cache effectiveness degraded, Redis is evicting keys before TTL expiry causing cache stampede",
        "expected_runbooks": ["RB-004", "RB-003"],
        "category": "cache",
        "difficulty": "medium",
    },
    # RB-005 — Neo4j heap exhaustion
    {
        "id": "eval-009",
        "query": "Neo4j is throwing OutOfMemoryError and graph queries are failing with Java heap space error",
        "expected_runbooks": ["RB-005"],
        "category": "database",
        "difficulty": "easy",
    },
    {
        "id": "eval-010",
        "query": "Neo4j process restarted three times today, logs show GC overhead limit exceeded before each crash",
        "expected_runbooks": ["RB-005"],
        "category": "database",
        "difficulty": "medium",
    },
    # RB-006 — API 5xx error spike
    {
        "id": "eval-011",
        "query": "Error rate alert fired: 8% of requests returning 500 Internal Server Error starting 10 minutes after the last deployment",
        "expected_runbooks": ["RB-006"],
        "category": "api",
        "difficulty": "easy",
    },
    {
        "id": "eval-012",
        "query": "Users reporting Service Unavailable, Grafana shows error rate spike correlated with 2pm deploy, downstream DB looks fine",
        "expected_runbooks": ["RB-006", "RB-022"],
        "category": "api",
        "difficulty": "medium",
    },
    # RB-007 — API latency degradation
    {
        "id": "eval-013",
        "query": "p99 API latency jumped from 200ms to 4 seconds, no increase in error rate but users reporting slow responses",
        "expected_runbooks": ["RB-007"],
        "category": "api",
        "difficulty": "easy",
    },
    {
        "id": "eval-014",
        "query": "API response times consistently degraded, DB connection pool metrics look normal but downstream service calls are taking 10x longer",
        "expected_runbooks": ["RB-007"],
        "category": "api",
        "difficulty": "medium",
    },
    # RB-008 — Python memory leak
    {
        "id": "eval-015",
        "query": "Python API process RSS memory grows from 200MB to 2GB over 6 hours then gets OOMKilled by the kernel",
        "expected_runbooks": ["RB-008"],
        "category": "application",
        "difficulty": "easy",
    },
    {
        "id": "eval-016",
        "query": "Container memory usage is monotonically increasing under steady traffic, process_resident_memory_bytes never decreases between requests",
        "expected_runbooks": ["RB-008", "RB-011"],
        "category": "application",
        "difficulty": "medium",
    },
    # RB-009 — gRPC deadline exceeded
    {
        "id": "eval-017",
        "query": "gRPC calls between services are failing with StatusCode.DEADLINE_EXCEEDED, only for requests that take longer than 5 seconds",
        "expected_runbooks": ["RB-009"],
        "category": "networking",
        "difficulty": "easy",
    },
    {
        "id": "eval-018",
        "query": "Intermittent gRPC timeout errors in service-to-service communication under high load, retries are amplifying the problem",
        "expected_runbooks": ["RB-009", "RB-018"],
        "category": "networking",
        "difficulty": "medium",
    },
    # RB-010 — Webhook delivery failures
    {
        "id": "eval-019",
        "query": "Webhook delivery success rate dropped to 30%, external endpoints returning 404 and connection timeouts",
        "expected_runbooks": ["RB-010"],
        "category": "api",
        "difficulty": "easy",
    },
    {
        "id": "eval-020",
        "query": "Third-party integrations are not receiving events, webhook queue is growing and delivery attempts are failing silently with no alerting",
        "expected_runbooks": ["RB-010"],
        "category": "api",
        "difficulty": "medium",
    },
    # RB-011 — Pod OOMKilled
    {
        "id": "eval-021",
        "query": "kubectl get pods shows OOMKilled status, pod keeps restarting in CrashLoopBackOff every 2 minutes",
        "expected_runbooks": ["RB-011"],
        "category": "kubernetes",
        "difficulty": "easy",
    },
    {
        "id": "eval-022",
        "query": "Production pod terminated with exit code 137, kubectl describe shows Last State: Terminated Reason: OOMKilled",
        "expected_runbooks": ["RB-011"],
        "category": "kubernetes",
        "difficulty": "easy",
    },
    # RB-012 — Node disk pressure
    {
        "id": "eval-023",
        "query": "Kubernetes node has DiskPressure condition true, pods are being evicted and new ones cannot be scheduled",
        "expected_runbooks": ["RB-012"],
        "category": "kubernetes",
        "difficulty": "easy",
    },
    {
        "id": "eval-024",
        "query": "Node filesystem usage at 94%, kubelet evicting pods and emitting DiskPressure events in kubectl get events",
        "expected_runbooks": ["RB-012"],
        "category": "kubernetes",
        "difficulty": "medium",
    },
    # RB-013 — CPU throttling
    {
        "id": "eval-025",
        "query": "Container CPU throttling at 80%, requests are slow but memory usage and error rates are both normal",
        "expected_runbooks": ["RB-013"],
        "category": "kubernetes",
        "difficulty": "easy",
    },
    {
        "id": "eval-026",
        "query": "Pods responding slowly under load, container_cpu_cfs_throttled_seconds increasing rapidly in Prometheus while utilization appears low",
        "expected_runbooks": ["RB-013"],
        "category": "kubernetes",
        "difficulty": "medium",
    },
    # RB-014 — Load balancer health check failures
    {
        "id": "eval-027",
        "query": "Load balancer health checks failing for 2 of 5 backend pods, traffic is routing to healthy pods only causing overload",
        "expected_runbooks": ["RB-014"],
        "category": "networking",
        "difficulty": "easy",
    },
    {
        "id": "eval-028",
        "query": "ALB is marking instances unhealthy even though application logs show successful request processing on those instances",
        "expected_runbooks": ["RB-014"],
        "category": "networking",
        "difficulty": "medium",
    },
    # RB-015 — Autoscaling not triggering
    {
        "id": "eval-029",
        "query": "HPA is not scaling up pods despite CPU utilization above 80% for 10 minutes, min replicas already reached",
        "expected_runbooks": ["RB-015"],
        "category": "kubernetes",
        "difficulty": "easy",
    },
    {
        "id": "eval-030",
        "query": "HorizontalPodAutoscaler shows unknown metrics, cluster under load but replica count not increasing beyond current value",
        "expected_runbooks": ["RB-015"],
        "category": "kubernetes",
        "difficulty": "medium",
    },
    # RB-016 — DNS resolution failures
    {
        "id": "eval-031",
        "query": "Services cannot resolve each other by hostname inside Kubernetes cluster, DNS lookup timeouts appearing in pod logs",
        "expected_runbooks": ["RB-016"],
        "category": "networking",
        "difficulty": "easy",
    },
    {
        "id": "eval-032",
        "query": "Intermittent connection refused between microservices, nslookup for internal service names fails from inside pods sporadically",
        "expected_runbooks": ["RB-016"],
        "category": "networking",
        "difficulty": "medium",
    },
    # RB-017 — SSL certificate expiry
    {
        "id": "eval-033",
        "query": "SSL certificate expired 2 days ago, all HTTPS traffic to the service failing with certificate verification error",
        "expected_runbooks": ["RB-017"],
        "category": "security",
        "difficulty": "easy",
    },
    {
        "id": "eval-034",
        "query": "TLS certificate expires in 3 days, users seeing browser security warnings, cert-manager did not auto-renew",
        "expected_runbooks": ["RB-017"],
        "category": "security",
        "difficulty": "easy",
    },
    # RB-018 — Service mesh timeout cascade
    {
        "id": "eval-035",
        "query": "Istio timeout errors cascading through microservices, one slow upstream is causing failures across 5 downstream services",
        "expected_runbooks": ["RB-018"],
        "category": "networking",
        "difficulty": "medium",
    },
    {
        "id": "eval-036",
        "query": "Service mesh showing retry storms, a single degraded service is amplifying load 10x across the entire mesh via retries",
        "expected_runbooks": ["RB-018", "RB-007"],
        "category": "networking",
        "difficulty": "hard",
    },
    # RB-019 — Kafka consumer lag
    {
        "id": "eval-037",
        "query": "Kafka consumer group lag at 500k messages and growing, events are being processed hours behind real-time",
        "expected_runbooks": ["RB-019"],
        "category": "messaging",
        "difficulty": "easy",
    },
    {
        "id": "eval-038",
        "query": "Message processing throughput dropped 70%, kafka-consumer-groups shows lag accumulating on all partitions simultaneously",
        "expected_runbooks": ["RB-019"],
        "category": "messaging",
        "difficulty": "medium",
    },
    # RB-020 — Dead letter queue accumulation
    {
        "id": "eval-039",
        "query": "Dead letter queue has 50k messages, events that failed 3 processing attempts are accumulating with no alerting",
        "expected_runbooks": ["RB-020"],
        "category": "messaging",
        "difficulty": "easy",
    },
    {
        "id": "eval-040",
        "query": "DLQ depth spiked overnight, root cause unclear because dead-lettered messages have no attached error context or stack trace",
        "expected_runbooks": ["RB-020", "RB-019"],
        "category": "messaging",
        "difficulty": "medium",
    },
    # RB-021 — Celery task backlog
    {
        "id": "eval-041",
        "query": "Celery task queue has 10k pending tasks, workers are running but throughput is far below the submission rate",
        "expected_runbooks": ["RB-021"],
        "category": "messaging",
        "difficulty": "easy",
    },
    {
        "id": "eval-042",
        "query": "Background job processing backed up by 2 hours, Celery inspect shows workers are idle but queue keeps growing",
        "expected_runbooks": ["RB-021"],
        "category": "messaging",
        "difficulty": "medium",
    },
    # RB-022 — Canary deployment rollback
    {
        "id": "eval-043",
        "query": "Canary release showing 3x higher error rate than stable after 15 minutes, need to roll back immediately",
        "expected_runbooks": ["RB-022"],
        "category": "deployment",
        "difficulty": "easy",
    },
    {
        "id": "eval-044",
        "query": "New deployment version failing health checks in canary traffic slice, need to revert to previous stable version",
        "expected_runbooks": ["RB-022", "RB-006"],
        "category": "deployment",
        "difficulty": "medium",
    },
    # RB-023 — Database migration failure
    {
        "id": "eval-045",
        "query": "Alembic migration failed halfway through, database schema is now inconsistent with both old and new columns present",
        "expected_runbooks": ["RB-023"],
        "category": "database",
        "difficulty": "easy",
    },
    {
        "id": "eval-046",
        "query": "Production deploy failed during schema migration, application is down because expected column does not exist in the table",
        "expected_runbooks": ["RB-023"],
        "category": "database",
        "difficulty": "medium",
    },
    # RB-024 — Configuration drift
    {
        "id": "eval-047",
        "query": "Production behaves differently from staging despite identical deployment manifests, suspected manual configuration drift",
        "expected_runbooks": ["RB-024"],
        "category": "deployment",
        "difficulty": "medium",
    },
    {
        "id": "eval-048",
        "query": "Manual change made to production config 2 weeks ago is causing an incident today, change was never captured in git or Terraform",
        "expected_runbooks": ["RB-024"],
        "category": "deployment",
        "difficulty": "hard",
    },
    # RB-025 — Dependency version conflict
    {
        "id": "eval-049",
        "query": "Production pod crashes on startup with ImportError that does not reproduce locally, suspect dependency version mismatch in Docker image",
        "expected_runbooks": ["RB-025"],
        "category": "deployment",
        "difficulty": "easy",
    },
    {
        "id": "eval-050",
        "query": "CI passed but production deploy fails with pkg_resources.ContextualVersionConflict on startup after adding a new library",
        "expected_runbooks": ["RB-025"],
        "category": "deployment",
        "difficulty": "medium",
    },
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "retrieval_eval.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for entry in EVAL_QUERIES:
            f.write(json.dumps(entry) + "\n")

    categories = Counter(e["category"] for e in EVAL_QUERIES)
    difficulties = Counter(e["difficulty"] for e in EVAL_QUERIES)

    print(f"Saved {len(EVAL_QUERIES)} eval queries to {out_path}")
    print(f"Categories : {dict(categories)}")
    print(f"Difficulties: {dict(difficulties)}")


if __name__ == "__main__":
    main()
