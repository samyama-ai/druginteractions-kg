"""Phase 2: SIDER side effects and indications loader.

Creates SideEffect and Indication nodes, HAS_SIDE_EFFECT and HAS_INDICATION edges.
Uses STITCH CID -> drug name mapping to link to existing Drug nodes.
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


def load_sider(
    client,
    data_dir: str,
    registry: Registry,
    tenant: str = "default",
) -> dict:
    """Load SIDER side effects and indications.

    Args:
        client: SamyamaClient instance
        data_dir: Root data directory with sider/ subdir
        registry: Deduplication registry
        tenant: Graph tenant

    Returns:
        Stats dict with node/edge counts
    """
    print("Phase 2: SIDER (side effects + indications)")

    create_index(client, "SideEffect", "meddra_id", tenant)
    create_index(client, "Indication", "meddra_id", tenant)

    sider_dir = os.path.join(data_dir, "sider")

    # Load STITCH CID -> drug name mapping
    cid_to_name: dict[str, str] = {}
    names_path = os.path.join(sider_dir, "drug_names.tsv")
    if os.path.exists(names_path):
        cid_to_name = _load_drug_names(names_path)
    else:
        print(f"  [WARN] SIDER drug_names not found: {names_path}")

    # Build drug name -> drugbank_id from registry
    name_to_dbid = _build_name_to_dbid(client, registry, tenant)

    se_nodes = 0
    ind_nodes = 0
    se_edges = 0
    ind_edges = 0

    # Load side effects
    se_path = os.path.join(sider_dir, "meddra_all_se.tsv")
    if os.path.exists(se_path):
        se_nodes, se_edges = _load_side_effects(
            client, se_path, registry, cid_to_name, name_to_dbid, tenant
        )

    # Load indications
    ind_path = os.path.join(sider_dir, "meddra_all_indications.tsv")
    if os.path.exists(ind_path):
        ind_nodes, ind_edges = _load_indications(
            client, ind_path, registry, cid_to_name, name_to_dbid, tenant
        )

    stats = {
        "source": "sider",
        "side_effect_nodes": se_nodes,
        "indication_nodes": ind_nodes,
        "has_side_effect_edges": se_edges,
        "has_indication_edges": ind_edges,
    }
    print(f"  Phase 2 done: {se_nodes} side effects, {ind_nodes} indications, "
          f"{se_edges + ind_edges} edges")
    return stats


def _load_drug_names(path: str) -> dict[str, str]:
    """Load STITCH CID -> drug name mapping."""
    cid_to_name: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                cid = parts[0].strip()
                name = parts[1].strip()
                if cid and name:
                    cid_to_name[cid] = name
    return cid_to_name


def _build_name_to_dbid(client, registry: Registry, tenant: str) -> dict[str, str]:
    """Build drug name -> drugbank_id mapping by querying existing Drug nodes."""
    name_to_dbid: dict[str, str] = {}
    try:
        result = client.query(
            "MATCH (d:Drug) RETURN d.name, d.drugbank_id", tenant
        )
        for row in result.records:
            name = row[0]
            dbid = row[1]
            if name and dbid:
                name_to_dbid[name.lower()] = dbid
    except Exception:
        pass
    return name_to_dbid


def _load_side_effects(
    client,
    path: str,
    registry: Registry,
    cid_to_name: dict[str, str],
    name_to_dbid: dict[str, str],
    tenant: str,
) -> tuple[int, int]:
    """Load SideEffect nodes and HAS_SIDE_EFFECT edges from SIDER.

    SIDER format: CID, UMLS_from_label, method, UMLS_side_effect, side_effect_name
    """
    progress = ProgressReporter("SideEffects", 0)
    se_batch: list[tuple[str, dict]] = []
    edge_batch: list[tuple[str, str, str, str, str, str, str, dict]] = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 5:
                continue

            cid = parts[0].strip()
            meddra_id = parts[3].strip()
            se_name = parts[4].strip()

            if not meddra_id or not se_name:
                continue

            # Resolve CID -> drug name -> drugbank_id
            drug_name = cid_to_name.get(cid)
            if not drug_name:
                continue
            drugbank_id = name_to_dbid.get(drug_name.lower())
            if not drugbank_id:
                continue

            # Create SideEffect node if new
            if meddra_id not in registry.side_effects:
                registry.side_effects.add(meddra_id)
                se_batch.append(("SideEffect", {"meddra_id": meddra_id, "name": se_name}))

            # Create edge if not duplicate
            edge_key = (drugbank_id, meddra_id)
            if edge_key not in registry.has_side_effect:
                registry.has_side_effect.add(edge_key)
                edge_batch.append((
                    "Drug", "drugbank_id", drugbank_id,
                    "SideEffect", "meddra_id", meddra_id,
                    "HAS_SIDE_EFFECT", {},
                ))
                progress.tick()

    if se_batch:
        batch_create_nodes(client, se_batch, tenant)

    edge_count = batch_create_edges(client, edge_batch, tenant)
    print(f"  SIDER SE: {len(se_batch)} nodes, {edge_count} edges")
    return len(se_batch), edge_count


def _load_indications(
    client,
    path: str,
    registry: Registry,
    cid_to_name: dict[str, str],
    name_to_dbid: dict[str, str],
    tenant: str,
) -> tuple[int, int]:
    """Load Indication nodes and HAS_INDICATION edges from SIDER.

    SIDER format: CID, UMLS_from_label, method, concept_name, type, UMLS_indication, indication_name
    """
    progress = ProgressReporter("Indications", 0)
    ind_batch: list[tuple[str, dict]] = []
    edge_batch: list[tuple[str, str, str, str, str, str, str, dict]] = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue

            cid = parts[0].strip()
            method = parts[2].strip()
            meddra_id = parts[5].strip()
            ind_name = parts[6].strip()

            if not meddra_id or not ind_name:
                continue

            # Resolve CID -> drug name -> drugbank_id
            drug_name = cid_to_name.get(cid)
            if not drug_name:
                continue
            drugbank_id = name_to_dbid.get(drug_name.lower())
            if not drugbank_id:
                continue

            # Create Indication node if new
            if meddra_id not in registry.indications:
                registry.indications.add(meddra_id)
                ind_batch.append(("Indication", {"meddra_id": meddra_id, "name": ind_name}))

            # Create edge if not duplicate
            edge_key = (drugbank_id, meddra_id)
            if edge_key not in registry.has_indication:
                registry.has_indication.add(edge_key)
                edge_props: dict = {}
                if method:
                    edge_props["method"] = method
                edge_batch.append((
                    "Drug", "drugbank_id", drugbank_id,
                    "Indication", "meddra_id", meddra_id,
                    "HAS_INDICATION", edge_props,
                ))
                progress.tick()

    if ind_batch:
        batch_create_nodes(client, ind_batch, tenant)

    edge_count = batch_create_edges(client, edge_batch, tenant)
    print(f"  SIDER IND: {len(ind_batch)} nodes, {edge_count} edges")
    return len(ind_batch), edge_count
