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

Apache 2.0

> ⚠️ **The licence above covers this repository's code, not the data.** This graph is
> derived from an upstream source (DrugBank (CC0), DGIdb (drug-gene), SIDER (side effects), ChEMBL 36 (bioactivity), OpenFDA FAERS (adverse events)), whose
> own terms govern redistribution and are **not stated here**. Establish and record them
> before redistributing or quoting this dataset. The frontmatter is therefore
> `license: other` rather than `apache-2.0`.

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
