# Querying the Drug Interactions KG

Three ways to ask the graph questions, once it's loaded into the `druginteractions` tenant on a running
engine (see [GETTING_STARTED.md](../GETTING_STARTED.md)). All examples below were run live and return real
results.

---

## 1. Claude, over MCP (natural language)

```bash
# register this KG's MCP server with Claude Code (once), pointed at the running engine:
claude mcp add druginteractions -- python -m mcp_server.server --url http://localhost:8080 --graph druginteractions

# start a new Claude Code session (MCP servers load at session start), then just ask:
#   "which genes are targeted by the most drugs?"        → CYP3A4 (442)
#   "which drugs have the most reported side effects?"    → Pregabalin (839)
```

*(No engine? `python -m mcp_server.server --data-dir data` loads a graph in-memory and serves it.)*

## 2. HTTP API (`POST /api/query`)

```bash
curl -s -X POST http://localhost:8080/api/query -H 'Content-Type: application/json' -d '{
  "graph": "druginteractions",
  "query": "MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect) RETURN d.name AS drug, count(se) AS side_effects ORDER BY side_effects DESC LIMIT 3"
}'
```
```json
{"columns":["drug","side_effects"],
 "records":[["Pregabalin",839],["Aripiprazole",827],["Citalopram",823]]}
```

## 3. Samyama CLI (Redis wire protocol, `:6379`)

```bash
redis-cli -p 6379 GRAPH.QUERY druginteractions \
  "MATCH (d:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene) RETURN g.gene_name, count(d) AS drugs ORDER BY drugs DESC LIMIT 3"
# 1) "CYP3A4" 442
# 2) "AR"     424
# 3) "CYP2D6" 365
```

---

## More queries
See the [Biomedical Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html)
for 100 example queries, and the [schema](../README.md#schema) for the node/edge model.
