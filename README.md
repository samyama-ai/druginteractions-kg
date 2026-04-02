# Drug Interactions & Pharmacogenomics Knowledge Graph

A knowledge graph integrating drug-target interactions, side effects, bioactivity data, and adverse events from 5 open data sources, built on [Samyama Graph](https://github.com/samyama-ai/samyama-graph).

**244,783 nodes** | **387,577 edges** | **7 node labels** | **6 edge types** | **8.1 MB snapshot**

## Snapshot

| | |
|---|---|
| **GitHub** | [kg-snapshots-v5](https://github.com/samyama-ai/samyama-graph/releases/tag/kg-snapshots-v5) |
| **S3** | `s3://samyama-data/snapshots/druginteractions.sgsnap` |

## Data Sources

| Source | Content | Nodes | License | Status |
|--------|---------|------:|---------|--------|
| DrugBank CC0 | Drug vocabulary | 19,842 | CC0 | Loaded |
| DGIdb | Drug-gene interactions | 6,449 genes | Open | Loaded (GraphQL) |
| SIDER | Side effects & indications | 8,702 | CC-BY-SA-4.0 | Loaded |
| ChEMBL 36 | Bioactivity (IC50, Ki, Kd, EC50) | 208,025 | CC-BY-SA-3.0 | Loaded |
| OpenFDA FAERS | Adverse events | 1,765 | Public domain | Loaded (top 500 drugs) |
| TTD | Therapeutic targets | — | CC-BY-NC | Unavailable (site migrated) |

## Quick Start

```bash
# 1. Download data
source ~/projects/venv/bin/activate
python -m etl.download_data --data-dir data

# 2. Run tests
pytest tests/ -v

# 3. Load into Samyama
python -m etl.loader --data-dir data --url http://localhost:8080

# 4. Start MCP server
python -m mcp_server.server --url http://localhost:8080
```

## Schema

```
Drug ──INTERACTS_WITH_GENE──> Gene
Drug ──HAS_SIDE_EFFECT──────> SideEffect
Drug ──HAS_INDICATION───────> Indication
Drug ──HAS_BIOACTIVITY──────> Bioactivity ──BIOACTIVITY_TARGET──> Gene
Drug ──TTD_TARGETS──────────> Target
Drug ──HAS_ADVERSE_EVENT────> AdverseEvent
Drug ──CLASSIFIED_AS────────> DrugClass ──PARENT_CLASS──> DrugClass
```

## Cross-KG Federation

This KG bridges to Pathways KG and Clinical Trials KG:

```cypher
-- Drug targets → Biological Pathways
MATCH (d:Drug {name: 'Metformin'})-[:INTERACTS_WITH_GENE]->(g:Gene)
MATCH (p:Protein {name: g.gene_name})-[:PARTICIPATES_IN]->(pw:Pathway)
RETURN pw.name, g.gene_name

-- Side effects of drugs in Phase 3 trials
MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect)
MATCH (i:Intervention {name: d.name})<-[:TESTS]-(ct:ClinicalTrial)
WHERE ct.phase CONTAINS '3'
RETURN d.name, se.name, ct.nct_id

-- Polypharmacy: shared targets between drugs
MATCH (d1:Drug {name: 'Warfarin'})-[:INTERACTS_WITH_GENE]->(g:Gene)
      <-[:INTERACTS_WITH_GENE]-(d2:Drug {name: 'Aspirin'})
RETURN g.gene_name AS shared_target
```

## MCP Tools

12 domain-specific tools: `drug_interactions`, `gene_drugs`, `drug_side_effects`,
`drug_indications`, `drug_bioactivity`, `drug_adverse_events`, `interaction_checker`,
`polypharmacy_risk`, `drug_class_hierarchy`, `gene_drug_landscape`, `side_effect_drugs`,
`target_development_status`.

## Project Structure

```
druginteractions-kg/
├── etl/
│   ├── helpers.py              # Registry, batch ops, escaping
│   ├── download_data.py        # Bulk downloads with resume
│   ├── loader.py               # Orchestrator (4 phases)
│   ├── drugbank_dgidb_loader.py
│   ├── sider_loader.py
│   ├── chembl_ttd_loader.py
│   └── openfda_loader.py
├── mcp_server/
│   ├── config.yaml             # 12 domain tools
│   └── server.py
├── tests/
│   ├── test_helpers.py
│   ├── test_drugbank_dgidb_loader.py
│   ├── test_sider_loader.py
│   ├── test_chembl_ttd_loader.py
│   └── test_openfda_loader.py
├── schema/
│   └── druginteractions_kg.cypher
└── docs/
    └── druginteractions-kg-plan.md
```
