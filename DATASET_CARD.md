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


## Freshness

**Refresh cadence:** The 5 upstreams do not share one cadence, and this repository
has no automated refresh for any of them -- `etl/download_data.py` must be re-run
manually per source:
- **ChEMBL** publishes numbered releases several times a year (ChEMBL 36 is the
  version currently loaded).
- **openFDA FAERS** publishes a new quarterly adverse-event extract every quarter.
- **DrugBank**'s Open Data vocabulary and **DGIdb**'s aggregated claims are released
  as irregular, versioned updates (DrugBank roughly 1-2x/year; DGIdb on no fixed
  schedule).
- **SIDER** has had no substantive update in years and should be treated as an
  effectively static, frozen source, not a periodically refreshed one.

**Data as of:** The per-source licence terms in [`DATA-LICENSES.md`](DATA-LICENSES.md)
were checked/re-verified on 2026-09-18 for all 5 sources (SIDER's page was unreachable
that day and its licence is unconfirmed) -- these are licence-check dates, not data
re-fetch dates. The loader code itself (`etl/`) was last modified 2026-07-31 (`git
log`); that is the most recent point at which the from-source build path is known to
have been exercised. No later "graph built on <date>" record exists in this repo, so
treat 2026-07-31 as the upper bound on how current a from-source rebuild would be.

## Reproducing

The loader in this repository rebuilds the graph from the upstream source. See the
README's Quick Start for the snapshot download and the from-source build.

## Known limitations

- Counts here are those stated by the repository README at the time this card was
  written; they are not re-measured by the card.
- Where a field above says *not recorded*, that is a gap in this repository rather
  than a property of the data.

## Citation

Please cite this repository if you use it. See [`CITATION.cff`](CITATION.cff) for
machine-readable metadata (CFF 1.2.0).

```bibtex
@misc{druginteractions_kg_2026,
  title        = {Drug Interactions Knowledge Graph},
  author       = {Samyama},
  year         = {2026},
  howpublished = {\url{https://git.samyama.ai/Samyama.ai/druginteractions-kg}}
}
```

**No DOI.** This release has not been deposited to Zenodo, so there is no DOI to
cite. Getting one is open work -- it requires a human to make the Zenodo deposit
(KG-06).

## Links

| | |
|---|---|
| Samyama Graph | [github.com/samyama-ai/samyama-graph](https://github.com/samyama-ai/samyama-graph) |
| The Book | [samyama-ai.github.io/samyama-graph-book](https://samyama-ai.github.io/samyama-graph-book/) |
| Benchmark (100 queries) | [Biomedical Benchmark](https://samyama-ai.github.io/samyama-graph-book/biomedical_benchmark.html) |
| Contact | [samyama.dev/contact](https://samyama.dev/contact) |
