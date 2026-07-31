# Getting Started — Drug Interactions Knowledge Graph

From `git clone` to your first answer. The **snapshot path** is the fastest (a few minutes).

---

## 1. Prerequisites

- **Python ≥ 3.10** (required by the `samyama` SDK; macOS ships 3.9 — use `python3.10`+).
- **git**
- **Docker** — to run the Samyama engine (needed for the snapshot import and for serving MCP / CLI / API).

## 2. Install

```bash
git clone https://github.com/samyama-ai/druginteractions-kg.git
cd druginteractions-kg
python3 -m venv .venv && source .venv/bin/activate     # Python >= 3.10
pip install -r requirements.txt
```

## 3. Run the engine (Docker)

```bash
docker run --rm -p 8080:8080 -p 6379:6379 public.ecr.aws/f9f6l5u4/samyama-graph:1.1.0
```

## 4. Load the graph — into the `druginteractions` tenant

### Option A — snapshot (recommended, ~seconds)
```bash
curl -LO https://github.com/samyama-ai/samyama-graph/releases/download/kg-snapshots-v5/druginteractions.sgsnap  # ~8 MB
curl -X POST http://localhost:8080/api/tenants -H 'Content-Type: application/json' \
  -d '{"id":"druginteractions","name":"Drug Interactions KG"}'
curl -X POST http://localhost:8080/api/tenants/druginteractions/snapshot/import -F "file=@druginteractions.sgsnap"
```

### Option B — build from source (downloads the 5 open datasets)
```bash
python -m etl.download_data --data-dir data
python -m etl.loader --data-dir data --url http://localhost:8080                 # all phases → druginteractions tenant
python -m etl.loader --data-dir data --url http://localhost:8080 --phases drugbank_dgidb sider   # subset
```
*(The loader defaults to the `druginteractions` tenant; override with `--tenant`. Omit `--url` to build
an in-memory graph instead.)*

## 5. Ask your first question

Fastest is **Claude over MCP** — see **[docs/QUERYING.md](docs/QUERYING.md)**. Quick check over HTTP —
drugs with the heaviest side-effect burden:

```bash
curl -s -X POST http://localhost:8080/api/query -H 'Content-Type: application/json' -d '{
  "graph": "druginteractions",
  "query": "MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect) RETURN d.name AS drug, count(se) AS side_effects ORDER BY side_effects DESC LIMIT 5"
}'
# → Pregabalin (839), Aripiprazole (827), Citalopram (823), Ropinirole (682), Risperidone (666)
```

## 6. The ETL pipeline

- Data sources: **DrugBank (CC0), DGIdb, SIDER, ChEMBL 36, OpenFDA FAERS**.
- `etl/download_data.py` — fetches the raw datasets into `data/`.
- `etl/loader.py` — orchestrates the phases (`drugbank_dgidb`, `sider`, `chembl_ttd`, `openfda`) into the
  graph (Drug, Gene, SideEffect, Indication, Bioactivity, AdverseEvent). Run `python -m etl.loader --help`.

## Next
- **[docs/QUERYING.md](docs/QUERYING.md)** — MCP (Claude), HTTP API, and the Samyama CLI
- **[README](README.md#schema)** — schema · **[Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html)** — 100 queries
