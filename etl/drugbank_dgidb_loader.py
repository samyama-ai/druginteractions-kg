"""Phase 1: DrugBank CC0 vocabulary + DGIdb interactions loader.

Creates Drug nodes from DrugBank vocabulary CSV, Gene nodes from DGIdb,
and INTERACTS_WITH_GENE edges with interaction type properties.
"""

from __future__ import annotations

import csv
import os

from etl.helpers import (
    Registry,
    ProgressReporter,
    batch_create_nodes,
    batch_create_edges,
    create_index,
)


def load_drugbank_dgidb(
    client,
    data_dir: str,
    registry: Registry,
    tenant: str = "default",
) -> dict:
    """Load DrugBank drugs and DGIdb gene interactions.

    Args:
        client: SamyamaClient instance
        data_dir: Root data directory with drugbank/ and dgidb/ subdirs
        registry: Deduplication registry
        tenant: Graph tenant

    Returns:
        Stats dict with node/edge counts
    """
    print("Phase 1: DrugBank CC0 + DGIdb")

    # Create indexes first
    create_index(client, "Drug", "drugbank_id", tenant)
    create_index(client, "Drug", "name", tenant)
    create_index(client, "Gene", "gene_name", tenant)

    # Name -> drugbank_id lookup (populated from DrugBank vocab)
    name_to_id: dict[str, str] = {}

    drug_nodes = 0
    gene_nodes = 0
    interaction_edges = 0

    # --- Load DrugBank vocabulary CSV ---
    drugbank_path = os.path.join(data_dir, "drugbank", "drugbank_vocabulary.csv")
    if os.path.exists(drugbank_path):
        drug_nodes, name_to_id = _load_drugbank_vocab(client, drugbank_path, registry, tenant)
    else:
        print(f"  [WARN] DrugBank vocabulary not found: {drugbank_path}")

    # --- Load DGIdb data ---
    dgidb_dir = os.path.join(data_dir, "dgidb")

    # Build chembl_id lookup from DGIdb drugs.tsv
    chembl_lookup: dict[str, str] = {}
    drugs_path = os.path.join(dgidb_dir, "drugs.tsv")
    if os.path.exists(drugs_path):
        chembl_lookup = _load_dgidb_drugs_chembl(drugs_path)

    # Load DGIdb interactions (creates Gene nodes + edges)
    interactions_path = os.path.join(dgidb_dir, "interactions.tsv")
    if os.path.exists(interactions_path):
        g, e = _load_dgidb_interactions(
            client, interactions_path, registry, name_to_id, chembl_lookup, tenant
        )
        gene_nodes += g
        interaction_edges += e
    else:
        print(f"  [WARN] DGIdb interactions not found: {interactions_path}")

    stats = {
        "source": "drugbank_dgidb",
        "drug_nodes": drug_nodes,
        "gene_nodes": gene_nodes,
        "interaction_edges": interaction_edges,
    }
    print(f"  Phase 1 done: {drug_nodes} drugs, {gene_nodes} genes, {interaction_edges} interactions")
    return stats


def _load_drugbank_vocab(
    client, path: str, registry: Registry, tenant: str
) -> tuple[int, dict[str, str]]:
    """Load Drug nodes from DrugBank vocabulary CSV.

    Returns (count, name_to_drugbank_id_dict).
    """
    node_batch: list[tuple[str, dict]] = []
    name_to_id: dict[str, str] = {}

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            drugbank_id = row.get("DrugBank ID", "").strip()
            name = row.get("Common name", "").strip()
            cas = row.get("CAS", "").strip()

            if not drugbank_id or not name:
                continue
            if drugbank_id in registry.drugs:
                continue

            registry.drugs.add(drugbank_id)
            name_to_id[name.lower()] = drugbank_id

            props = {"drugbank_id": drugbank_id, "name": name}
            if cas:
                props["cas_number"] = cas
            node_batch.append(("Drug", props))

    if node_batch:
        batch_create_nodes(client, node_batch, tenant)

    print(f"  DrugBank: {len(node_batch)} Drug nodes")
    return len(node_batch), name_to_id


def _load_dgidb_drugs_chembl(path: str) -> dict[str, str]:
    """Build drug_name -> chembl_id lookup from DGIdb drugs.tsv."""
    lookup: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            drug_name = row.get("drug_name", "").strip()
            chembl_id = row.get("chembl_id", "").strip()
            if drug_name and chembl_id:
                lookup[drug_name.upper()] = chembl_id
    return lookup


def _load_dgidb_interactions(
    client,
    path: str,
    registry: Registry,
    name_to_id: dict[str, str],
    chembl_lookup: dict[str, str],
    tenant: str,
) -> tuple[int, int]:
    """Load Gene nodes and INTERACTS_WITH_GENE edges from DGIdb interactions.tsv.

    Returns (gene_count, edge_count).
    """
    progress = ProgressReporter("DGIdb", 0)
    gene_batch: list[tuple[str, dict]] = []
    edge_batch: list[tuple[str, str, str, str, str, str, str, dict]] = []
    enriched_drugs: set[str] = set()

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene_name = row.get("gene_name", "").strip()
            drug_claim = row.get("drug_claim_primary_name", "").strip()
            drug_name_upper = row.get("drug_name", "").strip()
            interaction_type = row.get("interaction_types", "").strip()
            source = row.get("interaction_claim_source", "").strip()
            entrez_id = row.get("entrez_id", "").strip()
            drug_chembl_id = row.get("drug_chembl_id", "").strip()

            if not gene_name or not drug_claim:
                continue

            # Resolve drug to drugbank_id via name lookup
            drugbank_id = name_to_id.get(drug_claim.lower())
            if not drugbank_id:
                continue

            # Create Gene node if new
            if gene_name not in registry.genes:
                registry.genes.add(gene_name)
                gene_props: dict = {"gene_name": gene_name}
                if entrez_id:
                    gene_props["entrez_id"] = entrez_id
                gene_batch.append(("Gene", gene_props))

            # Enrich Drug node with chembl_id
            chembl_id = drug_chembl_id or chembl_lookup.get(drug_name_upper, "")
            if chembl_id and drugbank_id not in enriched_drugs:
                enriched_drugs.add(drugbank_id)
                try:
                    client.query(
                        f"MATCH (d:Drug {{drugbank_id: '{drugbank_id}'}}) "
                        f"SET d.chembl_id = '{chembl_id}'",
                        tenant,
                    )
                except Exception:
                    pass

            # Create edge if not duplicate
            edge_key = (drugbank_id, gene_name)
            if edge_key not in registry.interacts_with_gene:
                registry.interacts_with_gene.add(edge_key)
                edge_props: dict = {}
                if interaction_type:
                    edge_props["interaction_type"] = interaction_type
                if source:
                    edge_props["source"] = source
                edge_batch.append((
                    "Drug", "drugbank_id", drugbank_id,
                    "Gene", "gene_name", gene_name,
                    "INTERACTS_WITH_GENE", edge_props,
                ))
                progress.tick()

    # Batch create genes first, then edges
    if gene_batch:
        batch_create_nodes(client, gene_batch, tenant)

    edge_count = batch_create_edges(client, edge_batch, tenant)

    print(f"  DGIdb: {len(gene_batch)} genes, {edge_count} interactions")
    return len(gene_batch), edge_count
