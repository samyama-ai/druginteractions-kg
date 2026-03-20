# Drug Interactions & Pharmacogenomics Knowledge Graph

A knowledge graph integrating drug-target interactions, side effects, bioactivity data, and adverse events from 6 open data sources, built on [Samyama Graph](https://github.com/samyama-ai/samyama-graph).

## Data Sources

| Source | Content | Nodes | License |
|--------|---------|------:|---------|
| DrugBank CC0 | Drug vocabulary | ~12K | CC0 |
| DGIdb | Drug-gene interactions | ~20K genes | Open |
| SIDER | Side effects & indications | ~9.4K | CC-BY-SA-4.0 |
| ChEMBL | Bioactivity (IC50, Ki) | ~500K | CC-BY-SA-3.0 |
| TTD | Therapeutic targets | ~3.4K | CC-BY-NC |
| OpenFDA FAERS | Adverse events | ~15K | Public domain |

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
