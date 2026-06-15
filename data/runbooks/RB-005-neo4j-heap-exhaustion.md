# RB-005 — Neo4j Heap Exhaustion / OOM

**Service:** Neo4j  
**Severity:** Critical  
**Tags:** neo4j, graph, memory, heap, jvm

## Symptoms
- Neo4j process killed by OOM killer (`dmesg` shows `Out of memory: Killed process`)
- `java.lang.OutOfMemoryError: Java heap space` in `neo4j.log`
- Graph queries timing out or returning partial results
- Neo4j bolt port (7687) stops accepting connections

## Possible Causes
- Unbounded traversal queries (no `LIMIT` or depth constraint)
- Large `MATCH` patterns loading millions of nodes into heap
- Insufficient `dbms.memory.heap.max_size` for dataset size
- Memory leak in long-running transaction
- Page cache too small, causing excessive I/O and compensating heap usage

## Diagnostic Steps

```bash
# Check Neo4j memory config
grep -E 'heap|pagecache' /etc/neo4j/neo4j.conf

# Check recent OOM events
dmesg | grep -i 'killed process\|out of memory' | tail -20

# Check Neo4j logs
tail -100 /var/log/neo4j/neo4j.log | grep -i 'error\|warn\|memory'

# In Neo4j browser or cypher-shell — find long-running queries
CALL dbms.listQueries() YIELD queryId, username, query, elapsedTimeMillis
WHERE elapsedTimeMillis > 10000
RETURN queryId, username, query, elapsedTimeMillis
ORDER BY elapsedTimeMillis DESC;
```

```bash
# JVM heap stats via JMX (if enabled)
jcmd <neo4j_pid> VM.native_memory summary
```

## Remediation Steps

### Immediate
1. Kill runaway queries:
   ```cypher
   CALL dbms.killQuery('<queryId>');
   ```
2. Restart Neo4j if process is unresponsive:
   ```bash
   systemctl restart neo4j
   # or in Docker:
   docker restart neo4j
   ```

### Short-term
3. Increase heap size in `neo4j.conf`:
   ```
   dbms.memory.heap.initial_size=2g
   dbms.memory.heap.max_size=4g
   ```
4. Increase page cache (ideally = graph store size):
   ```
   dbms.memory.pagecache.size=2g
   ```
5. Add query timeout to prevent unbounded traversals:
   ```
   dbms.transaction.timeout=30s
   ```

### Long-term
6. Audit all Cypher queries — add `LIMIT` to all `MATCH` patterns.
7. Use `EXPLAIN` / `PROFILE` on expensive queries to understand cardinality.
8. Add Grafana alert on JVM heap usage > 85%.

## Prevention
- Follow Neo4j memory sizing guide: `heap ≈ 1/4 RAM`, `pagecache ≈ graph_size`.
- Never run unbounded traversals (`MATCH (n)-[*]-(m)`) without depth limit.
- Set `dbms.transaction.timeout` in all production environments.
