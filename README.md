# Drug Interactions Knowledge Graph

**245K nodes. 388K edges. Drug targets, side effects, bioactivity, and adverse events from 5 open sources.**

![Drug interactions demo](demo/druginteractions.gif)

> Part of the **Samyama** ecosystem — loaded into and queried via the graph engine at [samyama-ai/samyama-graph](https://github.com/samyama-ai/samyama-graph).
> This repo holds the loader and source-data specifics for the KG.

<a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache_2.0-blue" alt="License"></a>

---

We loaded DrugBank, DGIdb, SIDER, ChEMBL, and OpenFDA into one graph, then asked:

> *"Which drug has the most reported side effects?"*

```cypher
MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect)
RETURN d.name, count(se) AS side_effects
ORDER BY side_effects DESC LIMIT 5
```

| Drug | Side Effects |
|------|-------------|
| **Pregabalin** | **839** |
| Duloxetine | 791 |
| Quetiapine | 764 |
| Olanzapine | 738 |
| Aripiprazole | 712 |

**One query across five pharmacological databases.** Powered by [Samyama Graph](https://github.com/samyama-ai/samyama-graph).

[See all 100 benchmark queries →](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html)

---

## Documentation

New here? Start with the guides:

| Guide | What it covers |
|-------|----------------|
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | prerequisites (Python ≥ 3.10) · install · run the engine (Docker) · load the graph · first query |
| **[docs/QUERYING.md](docs/QUERYING.md)** | ask questions via **MCP (Claude)**, the **HTTP API**, or the **Samyama CLI** |
| [Biomedical Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html) | 100 example queries |

---

## Demo

A narrated walkthrough on a fast, real subset (DrugBank CC0 + DGIdb + SIDER; DGIdb interactions and SIDER side-effects capped at 4,000 each via the loader's `limit` arg, loads in ~15s): load → busiest drug-target genes (CYP enzymes) → polypharmacy (drugs sharing a gene target) → heaviest side-effect burden.

```bash
python -m demo.demo                                                          # run live
asciinema rec --overwrite --cols 92 --rows 32 --idle-time-limit 2.0 \
  -c "bash -c 'python -m demo.demo'" demo/druginteractions.cast              # re-record
agg demo/druginteractions.cast demo/druginteractions.gif                     # convert to gif
```

---

## Schema

**6 node labels** -- Drug, Gene, SideEffect, Indication, Bioactivity, AdverseEvent

**5 edge types** -- INTERACTS_WITH_GENE, HAS_SIDE_EFFECT, HAS_INDICATION, HAS_ADVERSE_EVENT, BIOACTIVITY_TARGET

**5 data sources** -- DrugBank (CC0), DGIdb (drug-gene), SIDER (side effects), ChEMBL 36 (bioactivity), OpenFDA FAERS (adverse events)

## Quick Start

**Full walkthrough → [GETTING_STARTED.md](GETTING_STARTED.md)** (prerequisites, Docker, loading, querying).

### Load from snapshot (recommended)

Needs **Python ≥ 3.10** for the tooling and **Docker** for the engine:

```bash
pip install -r requirements.txt
docker run --rm -p 8080:8080 -p 6379:6379 public.ecr.aws/f9f6l5u4/samyama-graph:1.1.0

curl -LO https://github.com/samyama-ai/samyama-graph/releases/download/kg-snapshots-v5/druginteractions.sgsnap  # ~8 MB
curl -X POST http://localhost:8080/api/tenants -H 'Content-Type: application/json' -d '{"id":"druginteractions","name":"Drug Interactions KG"}'
curl -X POST http://localhost:8080/api/tenants/druginteractions/snapshot/import -F "file=@druginteractions.sgsnap"
```

### Build from source

```bash
git clone https://github.com/samyama-ai/druginteractions-kg.git && cd druginteractions-kg
pip install -r requirements.txt          # or: pip install -e ".[dev]" for tests
python -m etl.download_data --data-dir data
python -m etl.loader --data-dir data --url http://localhost:8080     # → druginteractions tenant
```

## Example Queries

```cypher
-- Polypharmacy: shared gene targets between two drugs
MATCH (d1:Drug {name: 'Warfarin'})-[:INTERACTS_WITH_GENE]->(g:Gene)
      <-[:INTERACTS_WITH_GENE]-(d2:Drug {name: 'Aspirin'})
RETURN g.gene_name AS shared_target

-- Side effects of drugs in Phase 3 clinical trials (cross-KG)
MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect)
MATCH (i:Intervention {name: d.name})<-[:TESTS]-(ct:ClinicalTrial)
WHERE ct.phase CONTAINS '3'
RETURN d.name, se.name, ct.nct_id
```

## Use with Claude (MCP)

```bash
python -m mcp_server.server --url http://localhost:8080 --graph druginteractions   # against a running engine
python -m mcp_server.server --data-dir data                                        # embedded, loads on startup
python -m mcp_server.server --url http://localhost:8080 --list-tools                # see all tools
```

Register it with Claude and ask in natural language — full steps in **[docs/QUERYING.md](docs/QUERYING.md)**.

## Part of the Biomedical Trifecta

This KG is one of three biomedical knowledge graphs that together form Samyama's billion-edge benchmark: [Clinical Trials](https://github.com/samyama-ai/clinicaltrials-kg) (27M edges) + [Pathways](https://github.com/samyama-ai/pathways-kg) (835K edges) + **Drug Interactions** (388K edges), merged on load with [PubMed](https://github.com/samyama-ai/pubmed-kg) (1.04B edges).

## Links

| | |
|---|---|
| Samyama Graph | [github.com/samyama-ai/samyama-graph](https://github.com/samyama-ai/samyama-graph) |
| The Book | [samyama-ai.github.io/samyama-graph-book](https://samyama-ai.github.io/samyama-graph-book/) |
| Benchmark (100 queries) | [Biomedical Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html) |
| Contact | [samyama.dev/contact](https://samyama.dev/contact) |

## License

Apache 2.0
