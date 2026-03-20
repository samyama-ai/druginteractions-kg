# Drug Interactions & Pharmacogenomics Knowledge Graph

## Overview

A knowledge graph integrating drug-target interactions, side effects, bioactivity data,
and adverse events from 6 open data sources. Completes the biomedical trifecta alongside
Pathways KG and Clinical Trials KG, enabling cross-KG federation queries.

## Schema

**9 Node Labels (~65K nodes):**
- Drug (~12K) — DrugBank CC0 + DGIdb
- Gene (~20K) — DGIdb
- SideEffect (~5.9K) — SIDER
- Indication (~3.5K) — SIDER
- Bioactivity (~500K) — ChEMBL (human, pChEMBL >= 5)
- Target (~3.4K) — TTD
- DrugClass (~6K) — ATC hierarchy
- AdverseEvent (~15K) — OpenFDA FAERS

**9 Edge Types (~900K edges):**
- INTERACTS_WITH_GENE: Drug -> Gene (interaction_type, source)
- HAS_SIDE_EFFECT: Drug -> SideEffect
- HAS_INDICATION: Drug -> Indication (method)
- HAS_BIOACTIVITY: Drug -> Bioactivity
- BIOACTIVITY_TARGET: Bioactivity -> Gene
- TTD_TARGETS: Drug -> Target (clinical_status)
- HAS_ADVERSE_EVENT: Drug -> AdverseEvent (count)
- CLASSIFIED_AS: Drug -> DrugClass
- PARENT_CLASS: DrugClass -> DrugClass

## Cross-KG Bridge Properties

- `Drug.drugbank_id` -> Clinical Trials KG `Drug.drugbank_id`
- `Drug.name` -> Clinical Trials KG `Intervention.name`
- `Gene.gene_name` -> Pathways KG `Protein.gene_name`
- `Target.uniprot_id` -> Pathways KG `Protein.uniprot_id`

## Data Sources

| Source | License | Size |
|--------|---------|------|
| DrugBank CC0 | CC0 | ~6 MB |
| DGIdb | Open | ~15 MB |
| SIDER | CC-BY-SA-4.0 | ~20 MB |
| ChEMBL | CC-BY-SA-3.0 | ~4 GB |
| TTD | CC-BY-NC | ~10 MB |
| OpenFDA | Public domain | API |

## ETL Phases

1. **DrugBank + DGIdb** — Drug nodes, Gene nodes, INTERACTS_WITH_GENE edges
2. **SIDER** — SideEffect/Indication nodes, HAS_SIDE_EFFECT/HAS_INDICATION edges
3. **ChEMBL + TTD** — Bioactivity/Target/DrugClass nodes + edges
4. **OpenFDA** — AdverseEvent nodes, HAS_ADVERSE_EVENT edges

## MCP Tools (12)

1. drug_interactions — gene targets of a drug
2. gene_drugs — drugs targeting a gene
3. drug_side_effects — SIDER side effects
4. drug_indications — approved indications
5. drug_bioactivity — ChEMBL binding affinities
6. drug_adverse_events — FAERS events
7. interaction_checker — shared targets between drugs
8. polypharmacy_risk — shared targets + side effects
9. drug_class_hierarchy — ATC classification
10. gene_drug_landscape — full landscape for a gene
11. side_effect_drugs — reverse: drugs with side effect
12. target_development_status — TTD clinical stage
