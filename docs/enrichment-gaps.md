# Drug Interactions KG & Clinical Trials KG — Enrichment Gaps

> Status as of 2026-04-02

## Drug Interactions KG

| Source | Status | Action |
|--------|--------|--------|
| DrugBank CC0 | Loaded | Done |
| DGIdb | Loaded | Done (via GraphQL — old TSV URLs broken) |
| SIDER | Loaded | Done |
| ChEMBL 36 | Download complete (5.6GB) | Extract SQLite → TSV, extend Rust loader, rebuild snapshot |
| TTD | Blocked | Site migrated to JS app — no file downloads or API. Skip. |
| OpenFDA FAERS | Ready | Run API for top 500 drugs, add to snapshot |

### Current snapshot: 32,635 nodes, 189,003 edges (3 of 6 sources)
### Target: ~500K+ nodes with ChEMBL bioactivities + OpenFDA adverse events

## Clinical Trials KG

| Label | In snapshot? | Source | Feasible locally? |
|-------|-------------|--------|-------------------|
| ClinicalTrial (575K) | Yes | AACT | Done |
| Condition (125K) | Yes | AACT | Done |
| Intervention (472K) | Yes | AACT | Done |
| ArmGroup (1M) | Yes | AACT | Done |
| Outcome (3.5M) | Yes | AACT | Done |
| Sponsor (49K) | Yes | AACT | Done |
| Site (1M) | Yes | AACT | Done |
| AdverseEvent (145K) | Yes | AACT | Done |
| MeSHDescriptor (6K) | Yes | AACT | Done |
| Publication (750K) | Yes | AACT | Done |
| **Drug** | **No** | RxNorm API | **No** — needs 20GB+ graph loaded |
| **DrugClass** | **No** | RxNorm/ATC | **No** — same |
| **Gene** | **No** | Linked ontologies | **No** — same |
| **Protein** | **No** | UniProt | **No** — same |
| **LabTest** | **No** | LOINC | **No** — no loader code exists |

### Missing edge types
CODED_AS_DRUG, CLASSIFIED_AS, PARENT_CLASS, TARGETS, ENCODES, TREATS,
INTERACTS_WITH (drug-drug), HAS_ADVERSE_EFFECT, MEASURED_BY, TAGGED_WITH

### Plan
- Clinical trials enrichment (Drug/DrugClass/Gene/Protein) deferred to AWS VM
  (246GB RAM, needs loaded graph + Python ETL API calls)
- LabTest/LOINC needs loader code to be written first
