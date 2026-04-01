"""Download DGIdb data via GraphQL API and save as TSV files.

The old monthly TSV download URLs (dgidb.org/data/monthly_tsvs/) stopped
serving static files sometime in 2025. This script uses the GraphQL API
at dgidb.org/api/graphql to fetch the same data.

Usage:
    python -m etl.download_dgidb_graphql --data-dir data/dgidb
    python -m etl.download_dgidb_graphql --data-dir data/dgidb --page-size 1000
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import requests

API = "https://dgidb.org/api/graphql"


def fetch_paginated(query_template: str, root_key: str, page_size: int = 500,
                    delay: float = 0.1) -> list[dict]:
    """Fetch all pages from a DGIdb GraphQL paginated query."""
    results = []
    has_next = True
    cursor = None
    page = 0

    while has_next:
        after_clause = f', after: "{cursor}"' if cursor else ""
        query = query_template.format(first=page_size, after=after_clause)

        resp = requests.post(API, json={"query": query}, timeout=30)
        resp.raise_for_status()
        data = resp.json()["data"][root_key]

        total = data["totalCount"]
        results.extend(data["nodes"])

        page += 1
        pct = len(results) * 100 // max(total, 1)
        print(f"  Page {page}: {len(results)}/{total} ({pct}%)", flush=True)

        has_next = data["pageInfo"]["hasNextPage"]
        cursor = data["pageInfo"]["endCursor"]
        time.sleep(delay)

    return results


def download_interactions(data_dir: Path, page_size: int) -> int:
    print("Fetching interactions via GraphQL...", flush=True)
    query_tpl = """{{
      interactions(first: {first}{after}) {{
        totalCount
        pageInfo {{ hasNextPage endCursor }}
        nodes {{
          drug {{ name conceptId }}
          gene {{ name conceptId }}
          interactionScore
          interactionTypes {{ type directionality }}
          sources {{ sourceDbName }}
        }}
      }}
    }}"""

    nodes = fetch_paginated(query_tpl, "interactions", page_size)

    out = data_dir / "interactions.tsv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["gene_name", "gene_concept_id", "drug_name", "drug_concept_id",
                     "interaction_types", "interaction_score", "sources"])
        for i in nodes:
            gene = i["gene"] or {}
            drug = i["drug"] or {}
            itypes = ";".join(t["type"] for t in (i.get("interactionTypes") or []))
            sources = ";".join(s["sourceDbName"] for s in (i.get("sources") or []))
            w.writerow([
                gene.get("name", ""), gene.get("conceptId", ""),
                drug.get("name", ""), drug.get("conceptId", ""),
                itypes, i.get("interactionScore", ""), sources,
            ])

    print(f"  -> {out} ({len(nodes)} interactions)")
    return len(nodes)


def download_genes(data_dir: Path, page_size: int) -> int:
    print("\nFetching genes via GraphQL...", flush=True)
    query_tpl = """{{ genes(first: {first}{after}) {{
        totalCount pageInfo {{ hasNextPage endCursor }}
        nodes {{ name conceptId longName geneCategories {{ name }} }}
    }} }}"""

    nodes = fetch_paginated(query_tpl, "genes", page_size)

    out = data_dir / "genes.tsv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["gene_name", "concept_id", "long_name", "categories"])
        for g in nodes:
            cats = ";".join(c["name"] for c in (g.get("geneCategories") or []))
            w.writerow([g.get("name", ""), g.get("conceptId", ""),
                        g.get("longName", ""), cats])

    print(f"  -> {out} ({len(nodes)} genes)")
    return len(nodes)


def download_drugs(data_dir: Path, page_size: int) -> int:
    print("\nFetching drugs via GraphQL...", flush=True)
    query_tpl = """{{ drugs(first: {first}{after}) {{
        totalCount pageInfo {{ hasNextPage endCursor }}
        nodes {{ name conceptId approved }}
    }} }}"""

    nodes = fetch_paginated(query_tpl, "drugs", page_size)

    out = data_dir / "drugs.tsv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["drug_name", "concept_id", "approved"])
        for d in nodes:
            w.writerow([d.get("name", ""), d.get("conceptId", ""),
                        d.get("approved", "")])

    print(f"  -> {out} ({len(nodes)} drugs)")
    return len(nodes)


def main():
    parser = argparse.ArgumentParser(description="Download DGIdb data via GraphQL API")
    parser.add_argument("--data-dir", required=True, help="Output directory for TSV files")
    parser.add_argument("--page-size", type=int, default=500, help="Records per GraphQL page")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    n_interactions = download_interactions(data_dir, args.page_size)
    n_genes = download_genes(data_dir, args.page_size)
    n_drugs = download_drugs(data_dir, args.page_size)
    elapsed = time.time() - t0

    print(f"\nDone in {elapsed:.0f}s — {n_interactions} interactions, "
          f"{n_genes} genes, {n_drugs} drugs -> {data_dir}")


if __name__ == "__main__":
    main()
