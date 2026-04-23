# Drug Interactions Knowledge Graph

**245K nodes. 388K edges. Drug targets, side effects, bioactivity, and adverse events from 5 open sources.**

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

## Schema

**6 node labels** -- Drug, Gene, SideEffect, Indication, Bioactivity, AdverseEvent

**5 edge types** -- INTERACTS_WITH_GENE, HAS_SIDE_EFFECT, HAS_INDICATION, HAS_ADVERSE_EVENT, BIOACTIVITY_TARGET

**5 data sources** -- DrugBank (CC0), DGIdb (drug-gene), SIDER (side effects), ChEMBL 36 (bioactivity), OpenFDA FAERS (adverse events)

## Quick Start

### Load from snapshot (recommended)

```bash
# Download (8.1 MB)
curl -LO https://github.com/samyama-ai/samyama-graph/releases/download/kg-snapshots-v5/druginteractions.sgsnap

# Start Samyama and import
./target/release/samyama
curl -X POST http://localhost:8080/api/tenants \
  -H 'Content-Type: application/json' \
  -d '{"id":"druginteractions","name":"Drug Interactions KG"}'
curl -X POST http://localhost:8080/api/tenants/druginteractions/snapshot/import \
  -F "file=@druginteractions.sgsnap"
```

### Build from source

```bash
git clone https://github.com/samyama-ai/druginteractions-kg.git && cd druginteractions-kg
pip install -e ".[dev]"
python -m etl.download_data --data-dir data
python -m etl.loader --data-dir data --url http://localhost:8080
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

## Part of the Biomedical Trifecta

This KG is one of three biomedical knowledge graphs that together form Samyama's billion-edge benchmark: [Clinical Trials](https://github.com/samyama-ai/clinicaltrials-kg) (27M edges) + [Pathways](https://github.com/samyama-ai/pathways-kg) (835K edges) + **Drug Interactions** (388K edges), federated with [PubMed](https://github.com/samyama-ai/pubmed-kg) (1.04B edges).

## Links

| | |
|---|---|
| Samyama Graph | [github.com/samyama-ai/samyama-graph](https://github.com/samyama-ai/samyama-graph) |
| The Book | [samyama-ai.github.io/samyama-graph-book](https://samyama-ai.github.io/samyama-graph-book/) |
| Benchmark (100 queries) | [Biomedical Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html) |
| Contact | [samyama.dev/contact](https://samyama.dev/contact) |

## License

Apache 2.0
