---
license: other
pretty_name: Drug Interactions Knowledge Graph
tags:
  - knowledge-graph
  - samyama
  - property-graph
  - pharmacology
language:
  - en
size_categories:
  - 100K<n<1M
---

# Dataset Card for `druginteractions-kg`

**245K nodes. 388K edges. Drug targets, side effects, bioactivity, and adverse events from 5 open sources.**

> Part of the **Samyama** ecosystem. This card describes the dataset; the repository
> holds the loader and source-data specifics.

## Structure

**6 node labels** -- Drug, Gene, SideEffect, Indication, Bioactivity, AdverseEvent

**5 edge types** -- INTERACTS_WITH_GENE, HAS_SIDE_EFFECT, HAS_INDICATION, HAS_ADVERSE_EVENT, BIOACTIVITY_TARGET

**5 data sources** -- DrugBank (CC0), DGIdb (drug-gene), SIDER (side effects), ChEMBL 36 (bioactivity), OpenFDA FAERS (adverse events)

## Provenance and licence

Apache 2.0 covers the loader. The five sources do not combine into one permissive licence:
ChEMBL is CC BY-SA 3.0 (share-alike), SIDER is non-commercial, and DGIdb carries per-source
terms that may forbid redistribution. DrugBank here is the **Open Data vocabulary** (CC0),
not the full CC BY-NC dataset. **Ship the loader, not the graph** — or build a snapshot from
the CC0 subset only. See [`DATA-LICENSES.md`](DATA-LICENSES.md).


## Reproducing

The loader in this repository rebuilds the graph from the upstream source. See the
README's Quick Start for the snapshot download and the from-source build.

## Known limitations

- Counts here are those stated by the repository README at the time this card was
  written; they are not re-measured by the card.
- Where a field above says *not recorded*, that is a gap in this repository rather
  than a property of the data.

## Links

| | |
|---|---|
| Samyama Graph | [github.com/samyama-ai/samyama-graph](https://github.com/samyama-ai/samyama-graph) |
| The Book | [samyama-ai.github.io/samyama-graph-book](https://samyama-ai.github.io/samyama-graph-book/) |
| Benchmark (100 queries) | [Biomedical Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html) |
| Contact | [samyama.dev/contact](https://samyama.dev/contact) |
