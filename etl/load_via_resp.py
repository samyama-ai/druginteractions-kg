"""Load Drug Interactions KG via RESP protocol (redis-cli).

Faster than HTTP for bulk edge creation since RESP avoids HTTP overhead.
Requires redis-cli to be installed and Samyama listening on port 6379.

Usage:
    python load_via_resp.py --data-dir /path/to/data
    python load_via_resp.py --data-dir /path/to/data --port 6379 --phases 1 2
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import time


def resp_query(cypher: str, port: int = 6379) -> str:
    """Execute Cypher via redis-cli GRAPH.QUERY."""
    result = subprocess.run(
        ["redis-cli", "-p", str(port), "GRAPH.QUERY", "default", cypher],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout


def escape(val: str) -> str:
    if not isinstance(val, str):
        return str(val)
    return val.replace("\\", "\\\\").replace("'", "\\'")


# ─── Phase 1: DrugBank + DGIdb ──────────────────────────────────────────

def load_phase1(data_dir: str, port: int) -> dict:
    """Load Drug nodes from DrugBank and Gene+Interaction edges from DGIdb."""
    print("Phase 1: DrugBank CC0 + DGIdb")

    resp_query("CREATE INDEX ON :Drug(drugbank_id)", port)
    resp_query("CREATE INDEX ON :Drug(name)", port)
    resp_query("CREATE INDEX ON :Gene(gene_name)", port)

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
            batch.append(f"(n{len(batch)}:Drug {{{props}}})")
            drug_count += 1

            if len(batch) >= 200:
                resp_query("CREATE " + ", ".join(batch), port)
                batch = []

    if batch:
        resp_query("CREATE " + ", ".join(batch), port)
    print(f"  DrugBank: {drug_count} Drug nodes")

    # Load DGIdb genes
    interactions_path = os.path.join(data_dir, "dgidb", "interactions.tsv")
    genes_seen: set[str] = set()
    gene_batch = []

    with open(interactions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene = row.get("gene_name", "").strip()
            if gene and gene not in genes_seen:
                genes_seen.add(gene)
                gene_batch.append(f"(g{len(gene_batch)}:Gene {{gene_name: '{escape(gene)}'}})")
                if len(gene_batch) >= 200:
                    resp_query("CREATE " + ", ".join(gene_batch), port)
                    gene_batch = []

    if gene_batch:
        resp_query("CREATE " + ", ".join(gene_batch), port)
    print(f"  DGIdb: {len(genes_seen)} Gene nodes")

    # Create interaction edges
    edges_seen: set[tuple] = set()
    edges = []
    with open(interactions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene = row.get("gene_name", "").strip()
            drug = row.get("drug_name", "").strip()
            int_type = row.get("interaction_type", "").strip()
            if not gene or not drug:
                continue
            dbid = name_to_id.get(drug.lower())
            if not dbid:
                continue
            key = (dbid, gene)
            if key in edges_seen:
                continue
            edges_seen.add(key)
            prop = ""
            if int_type and int_type != "NULL":
                prop = f" {{interaction_type: '{escape(int_type)}'}}"
            edges.append((dbid, gene, prop))

    print(f"  Creating {len(edges)} interaction edges...")
    t0 = time.time()
    created = 0
    for i, (dbid, gene, prop) in enumerate(edges):
        cypher = (
            f"MATCH (a:Drug {{drugbank_id: '{dbid}'}}), "
            f"(b:Gene {{gene_name: '{escape(gene)}'}}) "
            f"CREATE (a)-[:INTERACTS_WITH_GENE{prop}]->(b)"
        )
        try:
            resp_query(cypher, port)
            created += 1
        except Exception:
            pass
        if (i + 1) % 1000 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            print(f"    {i+1}/{len(edges)} ({rate:.0f}/s, {elapsed:.0f}s)")

    elapsed = time.time() - t0
    print(f"  Phase 1 done: {drug_count} drugs, {len(genes_seen)} genes, "
          f"{created} interactions ({elapsed:.0f}s)")
    return {"drug_nodes": drug_count, "gene_nodes": len(genes_seen),
            "interaction_edges": created}


# ─── Phase 2: SIDER ─────────────────────────────────────────────────────

def load_phase2(data_dir: str, port: int) -> dict:
    """Load SideEffect and Indication nodes from SIDER."""
    print("Phase 2: SIDER")

    resp_query("CREATE INDEX ON :SideEffect(meddra_id)", port)
    resp_query("CREATE INDEX ON :Indication(meddra_id)", port)

    sider_dir = os.path.join(data_dir, "sider")

    # CID -> drug name
    cid_to_name: dict[str, str] = {}
    with open(os.path.join(sider_dir, "drug_names.tsv"), "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                cid_to_name[parts[0].strip()] = parts[1].strip()

    # Drug name -> drugbank_id (query from graph)
    out = resp_query("MATCH (d:Drug) RETURN d.name, d.drugbank_id", port)
    name_to_dbid: dict[str, str] = {}
    lines = out.strip().split("\n")
    for i in range(2, len(lines), 2):  # skip header, pairs of lines
        if i + 1 < len(lines):
            name = lines[i].strip()
            dbid = lines[i + 1].strip()
            if name and dbid:
                name_to_dbid[name.lower()] = dbid

    # Alternative: build from DrugBank CSV directly
    drugbank_path = os.path.join(data_dir, "drugbank", "drugbank_vocabulary.csv")
    with open(drugbank_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("Common name", "").strip()
            dbid = row.get("DrugBank ID", "").strip()
            if name and dbid:
                name_to_dbid[name.lower()] = dbid

    # Side effects — collect unique nodes and edges
    se_seen: set[str] = set()
    se_edge_data: list[tuple[str, str]] = set()
    se_batch = []

    with open(os.path.join(sider_dir, "meddra_all_se.tsv"), "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            cid, mid, se_name = parts[0], parts[3].strip(), parts[4].strip()
            if not mid or not se_name:
                continue
            drug_name = cid_to_name.get(cid.strip())
            if not drug_name:
                continue
            dbid = name_to_dbid.get(drug_name.lower())
            if not dbid:
                continue
            if mid not in se_seen:
                se_seen.add(mid)
                se_batch.append(
                    f"(s{len(se_batch)}:SideEffect {{meddra_id: '{escape(mid)}', name: '{escape(se_name)}'}})")
                if len(se_batch) >= 200:
                    resp_query("CREATE " + ", ".join(se_batch), port)
                    se_batch = []
            se_edge_data.add((dbid, mid))

    if se_batch:
        resp_query("CREATE " + ", ".join(se_batch), port)
    print(f"  SIDER: {len(se_seen)} SideEffect nodes, {len(se_edge_data)} edges to create")

    # Create SE edges
    t0 = time.time()
    se_created = 0
    for i, (dbid, mid) in enumerate(se_edge_data):
        cypher = (
            f"MATCH (a:Drug {{drugbank_id: '{escape(dbid)}'}}), "
            f"(b:SideEffect {{meddra_id: '{escape(mid)}'}}) "
            f"CREATE (a)-[:HAS_SIDE_EFFECT]->(b)"
        )
        try:
            resp_query(cypher, port)
            se_created += 1
        except Exception:
            pass
        if (i + 1) % 1000 == 0:
            elapsed = time.time() - t0
            print(f"    SE edges: {i+1}/{len(se_edge_data)} ({(i+1)/elapsed:.0f}/s)")

    # Indications
    ind_seen: set[str] = set()
    ind_edge_data: set[tuple[str, str]] = set()
    ind_batch = []

    with open(os.path.join(sider_dir, "meddra_all_indications.tsv"), "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 7:
                continue
            cid, mid, ind_name = parts[0], parts[5].strip(), parts[6].strip()
            if not mid or not ind_name:
                continue
            drug_name = cid_to_name.get(cid.strip())
            if not drug_name:
                continue
            dbid = name_to_dbid.get(drug_name.lower())
            if not dbid:
                continue
            if mid not in ind_seen:
                ind_seen.add(mid)
                ind_batch.append(
                    f"(i{len(ind_batch)}:Indication {{meddra_id: '{escape(mid)}', name: '{escape(ind_name)}'}})")
                if len(ind_batch) >= 200:
                    resp_query("CREATE " + ", ".join(ind_batch), port)
                    ind_batch = []
            ind_edge_data.add((dbid, mid))

    if ind_batch:
        resp_query("CREATE " + ", ".join(ind_batch), port)
    print(f"  SIDER: {len(ind_seen)} Indication nodes, {len(ind_edge_data)} edges to create")

    ind_created = 0
    for i, (dbid, mid) in enumerate(ind_edge_data):
        cypher = (
            f"MATCH (a:Drug {{drugbank_id: '{escape(dbid)}'}}), "
            f"(b:Indication {{meddra_id: '{escape(mid)}'}}) "
            f"CREATE (a)-[:HAS_INDICATION]->(b)"
        )
        try:
            resp_query(cypher, port)
            ind_created += 1
        except Exception:
            pass
        if (i + 1) % 1000 == 0:
            elapsed = time.time() - t0
            print(f"    IND edges: {i+1}/{len(ind_edge_data)}")

    print(f"  Phase 2 done: {len(se_seen)} SEs ({se_created} edges), "
          f"{len(ind_seen)} indications ({ind_created} edges)")
    return {"side_effect_nodes": len(se_seen), "se_edges": se_created,
            "indication_nodes": len(ind_seen), "ind_edges": ind_created}


def main():
    parser = argparse.ArgumentParser(description="Load Drug Interactions KG via RESP")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", type=int, default=6379)
    parser.add_argument("--phases", nargs="*", default=["1", "2"])
    args = parser.parse_args()

    t0 = time.time()
    stats = {}
    if "1" in args.phases:
        stats.update(load_phase1(args.data_dir, args.port))
    if "2" in args.phases:
        stats.update(load_phase2(args.data_dir, args.port))

    elapsed = time.time() - t0
    print(f"\nTotal: {elapsed:.0f}s")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
