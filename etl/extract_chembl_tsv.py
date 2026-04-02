"""Extract bioactivity data from ChEMBL SQLite into TSV for the Rust/Python loaders.

Filters: human targets only, pchembl_value >= 5 (active compounds).
Joins activities → assays → target_dictionary → component_sequences for gene names.

Usage:
    python -m etl.extract_chembl_tsv --db data/chembl/chembl_36/chembl_36_sqlite/chembl_36.db --out data/chembl/chembl_activities.tsv
    python -m etl.extract_chembl_tsv --db data/chembl/chembl_36/chembl_36_sqlite/chembl_36.db --out data/chembl/chembl_activities.tsv --min-pchembl 6
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import time
from pathlib import Path


QUERY = """
SELECT
    md.chembl_id          AS chembl_id,
    act.assay_id          AS chembl_assay_id,
    ass.assay_type        AS assay_type,
    act.standard_type     AS standard_type,
    act.standard_value    AS standard_value,
    act.standard_units    AS standard_units,
    act.pchembl_value     AS pchembl_value,
    td.chembl_id          AS target_chembl_id,
    td.pref_name          AS target_name,
    td.target_type        AS target_type,
    cs.accession          AS uniprot_id,
    gsyn.component_synonym AS gene_name,
    td.organism            AS organism
FROM activities act
JOIN assays ass ON act.assay_id = ass.assay_id
JOIN molecule_dictionary md ON act.molregno = md.molregno
JOIN target_dictionary td ON ass.tid = td.tid
LEFT JOIN target_components tc ON td.tid = tc.tid
LEFT JOIN component_sequences cs ON tc.component_id = cs.component_id
LEFT JOIN component_synonyms gsyn
    ON tc.component_id = gsyn.component_id AND gsyn.syn_type = 'GENE_SYMBOL'
WHERE act.pchembl_value >= ?
  AND td.organism = 'Homo sapiens'
  AND act.standard_type IN ('IC50', 'Ki', 'Kd', 'EC50', 'GI50', 'AC50')
ORDER BY act.pchembl_value DESC
"""


def extract(db_path: str, out_path: str, min_pchembl: float = 5.0) -> int:
    print(f"Opening {db_path} ...")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    print(f"Querying bioactivities (pchembl >= {min_pchembl}, human, IC50/Ki/Kd/EC50/GI50/AC50) ...")
    t0 = time.time()
    cursor = conn.execute(QUERY, (min_pchembl,))

    columns = [
        "chembl_id", "chembl_assay_id", "assay_type", "standard_type",
        "standard_value", "standard_units", "pchembl_value",
        "target_chembl_id", "target_name", "target_type",
        "uniprot_id", "gene_name", "organism",
    ]

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(out, "w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(columns)

        batch = cursor.fetchmany(10000)
        while batch:
            for row in batch:
                writer.writerow([row[c] or "" for c in columns])
                count += 1
            if count % 100000 == 0:
                print(f"  {count:,} rows ...", flush=True)
            batch = cursor.fetchmany(10000)

    elapsed = time.time() - t0
    conn.close()

    print(f"Done: {count:,} rows in {elapsed:.1f}s -> {out}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Extract ChEMBL bioactivities to TSV")
    parser.add_argument("--db", required=True, help="Path to chembl_XX.db SQLite file")
    parser.add_argument("--out", required=True, help="Output TSV path")
    parser.add_argument("--min-pchembl", type=float, default=5.0,
                        help="Minimum pchembl_value filter (default: 5.0)")
    args = parser.parse_args()

    extract(args.db, args.out, args.min_pchembl)


if __name__ == "__main__":
    main()
