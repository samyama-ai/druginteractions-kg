# Data licences

`LICENSE` in this repository covers the **loader code**. It says nothing about the
upstream data this repository reads and, where a snapshot is published, redistributes.
That gap is what this file closes (samyama-cloud#97).

Each row records what the source's **own terms page** says, with the URL and the date it
was read. Where a source could not be re-verified it says so rather than guessing: an
unverified licence written down as fact is worse than the silence it replaces.

| Source | What we load | What its terms page says | Checked |
|---|---|---|---|
| [DrugBank **Open Data** vocabulary](https://go.drugbank.com/releases/latest) | `drugbank_vocabulary.csv` — drug ids, names, synonyms (`etl/drugbank_dgidb_loader.py`) | CC0 1.0 (public domain), commercial use included. This is the open vocabulary file, **not** the full DrugBank dataset, which is CC BY-NC 4.0 and is not used here. The distinction is the whole reason this row is worth reading. | 2026-09-18 |
| [DGIdb](https://dgidb.org/downloads) | Drug–gene interaction claims | The DGIdb application is MIT-licensed, but the data it aggregates keeps its sources' terms and **some of those prohibit redistribution**. DGIdb points readers at its per-source licence table. Which of its sources reach this graph is **not yet established**. | 2026-09-18 (per-source terms not checked) |
| [SIDER](http://sideeffects.embl.de/) | Drug side effects | **Not re-verified** — `sideeffects.embl.de` was behind a bot check on the date below. SIDER has historically been distributed under a Creative Commons **non-commercial** licence. Treat as non-commercial until confirmed. | 2026-09-18 (unreachable) |
| [ChEMBL 36](https://www.ebi.ac.uk/chembl/) | Bioactivity | CC BY-SA 3.0. **Share-alike**: a distribution that includes ChEMBL-derived data has to be offered under the same terms. | 2026-09-18 |
| [openFDA FAERS](https://open.fda.gov/terms/) | Adverse events | Public domain under CC0 1.0; attribution requested, not required. | 2026-09-18 |

**The derived graph cannot be published under one permissive licence.** ChEMBL is
share-alike, SIDER is non-commercial, and DGIdb carries per-source terms that may forbid
redistribution outright. Combined, the join is at best **non-commercial and share-alike**,
and possibly not redistributable at all until the DGIdb sources are enumerated.

**What that means in practice:** ship the **loader**, not the graph. Anyone can run it
against sources they are entitled to use. If a published snapshot is wanted, build it from
the CC0 subset only — DrugBank Open Data plus openFDA — and say so in its name.

## How to read the "derived graph" line

A graph built from several sources carries **all** of their terms at once. The
restrictive ones win: one non-commercial source makes the join non-commercial, one
share-alike source makes the join share-alike. That is why the derived licence below is
not simply the most permissive source in the table.

## If you redistribute

- Keep the attributions named above with the data.
- State which snapshot version you took, so a reader can check it against the source.
- Re-read the terms pages: licences change, and the dates in this table are when we last
  looked.
