"""Load Drug Interactions KG via HTTP API.

Standalone loader that uses HTTP requests instead of the samyama SDK.
Handles DGIdb v5 column format differences.

Usage:
    python load_via_http.py --data-dir /path/to/data --url http://localhost:8080
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import time

import requests


def query(url: str, cypher: str, tenant: str = "default") -> dict:
    """Execute Cypher via HTTP."""
    resp = requests.post(
        f"{url}/api/query",
        json={"query": cypher, "tenant": tenant},
        timeout=30,
    )
    return resp.json()


def escape(val: str) -> str:
    if not isinstance(val, str):
        return str(val)
    return val.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def create_index(url: str, label: str, prop: str):
    try:
        query(url, f"CREATE INDEX ON :{label}({prop})")
    except Exception:
        pass


# ─── Phase 1: DrugBank + DGIdb ──────────────────────────────────────────

def load_phase1(url: str, data_dir: str) -> dict:
    """Load Drug nodes from DrugBank and Gene/Interaction edges from DGIdb."""
    print("Phase 1: DrugBank CC0 + DGIdb")

    create_index(url, "Drug", "drugbank_id")
    create_index(url, "Drug", "name")
    create_index(url, "Gene", "gene_name")

    # Load DrugBank vocabulary
    drugbank_path = os.path.join(data_dir, "drugbank", "drugbank_vocabulary.csv")
    name_to_id: dict[str, str] = {}
    drug_count = 0
    batch = []

    with open(drugbank_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dbid = row.get("DrugBank ID", "").strip()
            name = row.get("Common name", "").strip()
            cas = row.get("CAS", "").strip()
            if not dbid or not name:
                continue
            name_to_id[name.lower()] = dbid
            props = f"drugbank_id: '{escape(dbid)}', name: '{escape(name)}'"
            if cas:
                props += f", cas_number: '{escape(cas)}'"
            batch.append(f"(n{drug_count}:Drug {{{props}}})")
            drug_count += 1

            if len(batch) >= 200:
                query(url, "CREATE " + ", ".join(batch))
                batch = []

    if batch:
        query(url, "CREATE " + ", ".join(batch))

    print(f"  DrugBank: {drug_count} Drug nodes")

    # Load DGIdb interactions (v5 format)
    interactions_path = os.path.join(data_dir, "dgidb", "interactions.tsv")
    genes_seen: set[str] = set()
    edges_created = 0
    gene_count = 0
    gene_batch = []

    with open(interactions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene_name = row.get("gene_name", "").strip()
            drug_name = row.get("drug_name", "").strip()
            int_type = row.get("interaction_type", "").strip()
            source = row.get("interaction_source_db_name", "").strip()

            if not gene_name or not drug_name:
                continue

            # Find drugbank_id
            dbid = name_to_id.get(drug_name.lower())
            if not dbid:
                continue

            # Create Gene node if new
            if gene_name not in genes_seen:
                genes_seen.add(gene_name)
                gene_batch.append(f"(g{gene_count}:Gene {{gene_name: '{escape(gene_name)}'}})")
                gene_count += 1
                if len(gene_batch) >= 200:
                    query(url, "CREATE " + ", ".join(gene_batch))
                    gene_batch = []

    # Flush remaining genes
    if gene_batch:
        query(url, "CREATE " + ", ".join(gene_batch))

    print(f"  DGIdb: {gene_count} Gene nodes")

    # Now create edges (one by one — genes and drugs must exist)
    edges_seen: set[tuple] = set()
    with open(interactions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene_name = row.get("gene_name", "").strip()
            drug_name = row.get("drug_name", "").strip()
            int_type = row.get("interaction_type", "").strip()

            if not gene_name or not drug_name:
                continue
            dbid = name_to_id.get(drug_name.lower())
            if not dbid:
                continue

            edge_key = (dbid, gene_name)
            if edge_key in edges_seen:
                continue
            edges_seen.add(edge_key)

            props = ""
            if int_type and int_type != "NULL":
                props = f" {{interaction_type: '{escape(int_type)}'}}"

            cypher = (
                f"MATCH (a:Drug {{drugbank_id: '{escape(dbid)}'}}), "
                f"(b:Gene {{gene_name: '{escape(gene_name)}'}}) "
                f"CREATE (a)-[:INTERACTS_WITH_GENE{props}]->(b)"
            )
            try:
                query(url, cypher)
                edges_created += 1
            except Exception:
                pass

            if edges_created % 500 == 0:
                print(f"  Edges: {edges_created}...")

    print(f"  Phase 1 done: {drug_count} drugs, {gene_count} genes, {edges_created} interactions")
    return {"drug_nodes": drug_count, "gene_nodes": gene_count, "interaction_edges": edges_created}


# ─── Phase 2: SIDER ─────────────────────────────────────────────────────

def load_phase2(url: str, data_dir: str) -> dict:
    """Load SideEffect and Indication nodes from SIDER."""
    print("Phase 2: SIDER")

    create_index(url, "SideEffect", "meddra_id")
    create_index(url, "Indication", "meddra_id")

    sider_dir = os.path.join(data_dir, "sider")

    # CID -> drug name mapping
    cid_to_name: dict[str, str] = {}
    with open(os.path.join(sider_dir, "drug_names.tsv"), "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                cid_to_name[parts[0].strip()] = parts[1].strip()

    # Drug name -> drugbank_id from existing Drug nodes
    result = query(url, "MATCH (d:Drug) RETURN d.name, d.drugbank_id")
    name_to_dbid: dict[str, str] = {}
    for row in result.get("records", []):
        if row[0] and row[1]:
            name_to_dbid[row[0].lower()] = row[1]

    # Side effects
    se_seen: set[str] = set()
    se_edges = 0
    se_batch = []
    se_edge_seen: set[tuple] = set()

    se_path = os.path.join(sider_dir, "meddra_all_se.tsv")
    with open(se_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            cid, meddra_id, se_name = parts[0].strip(), parts[3].strip(), parts[4].strip()
            if not meddra_id or not se_name:
                continue
            drug_name = cid_to_name.get(cid)
            if not drug_name:
                continue
            dbid = name_to_dbid.get(drug_name.lower())
            if not dbid:
                continue

            if meddra_id not in se_seen:
                se_seen.add(meddra_id)
                se_batch.append(f"(s{len(se_seen)}:SideEffect {{meddra_id: '{escape(meddra_id)}', name: '{escape(se_name)}'}})")
                if len(se_batch) >= 200:
                    query(url, "CREATE " + ", ".join(se_batch))
                    se_batch = []

            edge_key = (dbid, meddra_id)
            if edge_key not in se_edge_seen:
                se_edge_seen.add(edge_key)

    if se_batch:
        query(url, "CREATE " + ", ".join(se_batch))

    print(f"  SIDER: {len(se_seen)} SideEffect nodes")

    # Create SE edges
    for dbid, meddra_id in se_edge_seen:
        try:
            query(url,
                f"MATCH (a:Drug {{drugbank_id: '{escape(dbid)}'}}), "
                f"(b:SideEffect {{meddra_id: '{escape(meddra_id)}'}}) "
                f"CREATE (a)-[:HAS_SIDE_EFFECT]->(b)")
            se_edges += 1
        except Exception:
            pass
        if se_edges % 500 == 0 and se_edges > 0:
            print(f"  SE edges: {se_edges}...")

    # Indications
    ind_seen: set[str] = set()
    ind_edges = 0
    ind_batch = []
    ind_edge_seen: set[tuple] = set()

    ind_path = os.path.join(sider_dir, "meddra_all_indications.tsv")
    with open(ind_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 7:
                continue
            cid, meddra_id, ind_name = parts[0].strip(), parts[5].strip(), parts[6].strip()
            if not meddra_id or not ind_name:
                continue
            drug_name = cid_to_name.get(cid)
            if not drug_name:
                continue
            dbid = name_to_dbid.get(drug_name.lower())
            if not dbid:
                continue

            if meddra_id not in ind_seen:
                ind_seen.add(meddra_id)
                ind_batch.append(f"(i{len(ind_seen)}:Indication {{meddra_id: '{escape(meddra_id)}', name: '{escape(ind_name)}'}})")
                if len(ind_batch) >= 200:
                    query(url, "CREATE " + ", ".join(ind_batch))
                    ind_batch = []

            edge_key = (dbid, meddra_id)
            if edge_key not in ind_edge_seen:
                ind_edge_seen.add(edge_key)

    if ind_batch:
        query(url, "CREATE " + ", ".join(ind_batch))

    # Create IND edges
    for dbid, meddra_id in ind_edge_seen:
        try:
            query(url,
                f"MATCH (a:Drug {{drugbank_id: '{escape(dbid)}'}}), "
                f"(b:Indication {{meddra_id: '{escape(meddra_id)}'}}) "
                f"CREATE (a)-[:HAS_INDICATION]->(b)")
            ind_edges += 1
        except Exception:
            pass
        if ind_edges % 500 == 0 and ind_edges > 0:
            print(f"  IND edges: {ind_edges}...")

    print(f"  Phase 2 done: {len(se_seen)} SEs, {se_edges} SE edges, {len(ind_seen)} indications, {ind_edges} IND edges")
    return {"side_effect_nodes": len(se_seen), "se_edges": se_edges,
            "indication_nodes": len(ind_seen), "ind_edges": ind_edges}


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Load Drug Interactions KG via HTTP")
    parser.add_argument("--data-dir", required=True, help="Data directory")
    parser.add_argument("--url", default="http://localhost:8080", help="Samyama URL")
    parser.add_argument("--phases", nargs="*", default=["1", "2"], help="Phases to run")
    args = parser.parse_args()

    t0 = time.time()
    stats = {}

    if "1" in args.phases:
        s = load_phase1(args.url, args.data_dir)
        stats.update(s)

    if "2" in args.phases:
        s = load_phase2(args.url, args.data_dir)
        stats.update(s)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"Drug Interactions KG loaded in {elapsed:.1f}s")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"{'='*60}")

    # Verify
    result = query(args.url, "MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC")
    print("\nNode counts:")
    for row in result.get("records", []):
        print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    main()
