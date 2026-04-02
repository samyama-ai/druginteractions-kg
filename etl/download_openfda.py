"""Download OpenFDA FAERS adverse event data for top drugs.

Queries the OpenFDA drug/event API for each drug name, extracts top N
adverse reactions by count, and saves as TSV.

Usage:
    python -m etl.download_openfda --data-dir data --max-drugs 500
    python -m etl.download_openfda --data-dir data --max-drugs 500 --top-n 30
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

import requests

OPENFDA_API = "https://api.fda.gov/drug/event.json"
RATE_LIMIT = 0.4  # seconds between requests


def get_top_drugs(data_dir: Path, max_drugs: int) -> list[tuple[str, str]]:
    """Get drugs most likely to have OpenFDA data.

    Strategy: read DGIdb interactions to find drugs with the most gene
    interactions (well-studied drugs), then cross-reference with DrugBank
    for the canonical name and ID. Falls back to alphabetical DrugBank
    if DGIdb data isn't available.
    """
    # Build DrugBank name -> ID lookup
    vocab_path = data_dir / "drugbank" / "drugbank_vocabulary.csv"
    name_to_dbid: dict[str, str] = {}
    dbid_to_name: dict[str, str] = {}
    with open(vocab_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dbid = row.get("DrugBank ID", "").strip()
            name = row.get("Common name", "").strip()
            if dbid and name:
                name_to_dbid[name.lower()] = dbid
                dbid_to_name[dbid] = name

    # Try to rank by DGIdb interaction count (well-studied = more FDA data)
    interactions_path = data_dir / "dgidb" / "interactions.tsv"
    if interactions_path.exists():
        drug_counts: dict[str, int] = {}
        with open(interactions_path, "r") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                dname = row.get("drug_name", "").strip().lower()
                if dname:
                    drug_counts[dname] = drug_counts.get(dname, 0) + 1

        # Sort by interaction count (descending) and resolve to DrugBank IDs
        ranked = sorted(drug_counts.items(), key=lambda x: -x[1])
        drugs = []
        seen = set()
        for dname, _ in ranked:
            dbid = name_to_dbid.get(dname)
            if dbid and dbid not in seen:
                seen.add(dbid)
                drugs.append((dbid, dbid_to_name[dbid]))
            if len(drugs) >= max_drugs:
                break
        if drugs:
            print(f"  Selected top {len(drugs)} drugs by DGIdb interaction count")
            return drugs

    # Fallback: alphabetical DrugBank
    drugs = [(dbid, name) for name, dbid in sorted(name_to_dbid.items())]
    if max_drugs > 0:
        drugs = drugs[:max_drugs]
    return drugs


def fetch_adverse_events(drug_name: str, top_n: int = 50) -> list[dict]:
    """Query OpenFDA for top adverse events for a drug."""
    params = {
        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
        "count": "patient.reaction.reactionmeddrapt.exact",
        "limit": top_n,
    }
    try:
        resp = requests.get(OPENFDA_API, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("results", [])
        elif resp.status_code == 404:
            return []  # no data for this drug
        else:
            return []
    except requests.RequestException:
        return []


def download(data_dir: Path, max_drugs: int, top_n: int) -> int:
    drugs = get_top_drugs(data_dir, max_drugs)
    print(f"Querying OpenFDA for {len(drugs)} drugs, top {top_n} events each ...",
          flush=True)

    out_dir = data_dir / "openfda"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "adverse_events.tsv"

    total_rows = 0
    drugs_with_data = 0

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["drugbank_id", "drug_name", "adverse_event_term", "count"])

        for i, (dbid, name) in enumerate(drugs):
            events = fetch_adverse_events(name, top_n)
            if events:
                drugs_with_data += 1
                for ev in events:
                    term = ev.get("term", "")
                    count = ev.get("count", 0)
                    writer.writerow([dbid, name, term, count])
                    total_rows += 1

            if (i + 1) % 50 == 0:
                pct = (i + 1) * 100 // len(drugs)
                print(f"  {i+1}/{len(drugs)} ({pct}%) — {drugs_with_data} with data, "
                      f"{total_rows} rows", flush=True)

            time.sleep(RATE_LIMIT)

    print(f"\nDone: {drugs_with_data}/{len(drugs)} drugs had data, "
          f"{total_rows} adverse event rows -> {out_path}")
    return total_rows


def main():
    parser = argparse.ArgumentParser(description="Download OpenFDA adverse events")
    parser.add_argument("--data-dir", required=True, help="Root data directory")
    parser.add_argument("--max-drugs", type=int, default=500,
                        help="Max drugs to query (default: 500)")
    parser.add_argument("--top-n", type=int, default=50,
                        help="Top N events per drug (default: 50)")
    args = parser.parse_args()

    download(Path(args.data_dir), args.max_drugs, args.top_n)


if __name__ == "__main__":
    main()
