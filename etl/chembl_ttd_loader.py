"""Phase 3: ChEMBL bioactivities + TTD targets + ATC drug classes loader.

Creates Bioactivity, Target, and DrugClass nodes with corresponding edges.
ChEMBL data is expected as pre-extracted TSV (from SQLite, filtered human pchembl>=5).
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


def load_chembl_ttd(
    client,
    data_dir: str,
    registry: Registry,
    tenant: str = "default",
) -> dict:
    """Load ChEMBL bioactivities, TTD targets, and ATC drug classes.

    Args:
        client: SamyamaClient instance
        data_dir: Root data directory with chembl/ and ttd/ subdirs
        registry: Deduplication registry
        tenant: Graph tenant

    Returns:
        Stats dict with node/edge counts
    """
    print("Phase 3: ChEMBL + TTD")

    create_index(client, "Bioactivity", "chembl_assay_id", tenant)
    create_index(client, "Target", "ttd_target_id", tenant)
    create_index(client, "DrugClass", "atc_code", tenant)

    # Build drug lookups from Drug nodes
    name_to_dbid, chembl_to_dbid = _build_drug_lookups(client, tenant)

    bio_nodes = 0
    bio_edges = 0
    bio_target_edges = 0
    target_nodes = 0
    ttd_edges = 0
    dc_nodes = 0
    classified_edges = 0
    parent_edges = 0

    # ChEMBL bioactivities
    chembl_path = os.path.join(data_dir, "chembl", "chembl_activities.tsv")
    if os.path.exists(chembl_path):
        bio_nodes, bio_edges, bio_target_edges = _load_chembl(
            client, chembl_path, registry, name_to_dbid, chembl_to_dbid, tenant
        )

    # TTD targets
    ttd_path = os.path.join(data_dir, "ttd", "ttd_targets.tsv")
    if os.path.exists(ttd_path):
        target_nodes, ttd_edges = _load_ttd_targets(
            client, ttd_path, registry, name_to_dbid, tenant
        )

    # ATC drug classes
    atc_path = os.path.join(data_dir, "ttd", "atc_classification.tsv")
    if os.path.exists(atc_path):
        dc_nodes, classified_edges, parent_edges = _load_atc(
            client, atc_path, registry, name_to_dbid, tenant
        )

    stats = {
        "source": "chembl_ttd",
        "bioactivity_nodes": bio_nodes,
        "has_bioactivity_edges": bio_edges,
        "bioactivity_target_edges": bio_target_edges,
        "target_nodes": target_nodes,
        "ttd_targets_edges": ttd_edges,
        "drug_class_nodes": dc_nodes,
        "classified_as_edges": classified_edges,
        "parent_class_edges": parent_edges,
    }
    print(f"  Phase 3 done: {bio_nodes} bioactivities, {target_nodes} targets, "
          f"{dc_nodes} drug classes")
    return stats


def _build_drug_lookups(client, tenant: str) -> tuple[dict[str, str], dict[str, str]]:
    """Query existing Drug nodes to build name and chembl_id lookups.

    Returns (name_to_dbid, chembl_to_dbid).
    """
    name_to_dbid: dict[str, str] = {}
    chembl_to_dbid: dict[str, str] = {}
    try:
        result = client.query(
            "MATCH (d:Drug) RETURN d.name, d.drugbank_id, d.chembl_id", tenant
        )
        for row in result.records:
            name, dbid, chembl = row[0], row[1], row[2] if len(row) > 2 else None
            if name and dbid:
                name_to_dbid[name.lower()] = dbid
            if chembl and dbid:
                chembl_to_dbid[chembl] = dbid
    except Exception:
        pass
    return name_to_dbid, chembl_to_dbid


def _load_chembl(
    client,
    path: str,
    registry: Registry,
    name_to_dbid: dict[str, str],
    chembl_to_dbid: dict[str, str],
    tenant: str,
) -> tuple[int, int, int]:
    """Load Bioactivity nodes, HAS_BIOACTIVITY + BIOACTIVITY_TARGET edges.

    ChEMBL TSV format: chembl_id, chembl_assay_id, assay_type, standard_type,
    standard_value, standard_units, pchembl_value, target_chembl_id, target_name,
    target_type, gene_name, organism

    Returns (bioactivity_count, has_bioactivity_edges, bioactivity_target_edges).
    """
    progress = ProgressReporter("ChEMBL", 0)
    bio_batch: list[tuple[str, dict]] = []
    has_bio_edges: list[tuple[str, str, str, str, str, str, str, dict]] = []
    bio_target_edges: list[tuple[str, str, str, str, str, str, str, dict]] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            chembl_id = row.get("chembl_id", "").strip()
            assay_id = row.get("chembl_assay_id", "").strip()
            assay_type = row.get("assay_type", "").strip()
            std_type = row.get("standard_type", "").strip()
            std_value = row.get("standard_value", "").strip()
            std_units = row.get("standard_units", "").strip()
            pchembl = row.get("pchembl_value", "").strip()
            gene_name = row.get("gene_name", "").strip()

            if not assay_id:
                continue

            # Find drug by chembl_id (from lookup or query)
            drugbank_id = chembl_to_dbid.get(chembl_id)
            if not drugbank_id:
                drugbank_id = _find_drug_by_chembl(client, chembl_id, name_to_dbid, tenant)

            # Create Bioactivity node if new
            if assay_id not in registry.bioactivities:
                registry.bioactivities.add(assay_id)
                props: dict = {"chembl_assay_id": assay_id}
                if assay_type:
                    props["assay_type"] = assay_type
                if std_type:
                    props["standard_type"] = std_type
                if std_value:
                    try:
                        props["standard_value"] = float(std_value)
                    except ValueError:
                        props["standard_value"] = std_value
                if std_units:
                    props["standard_units"] = std_units
                if pchembl:
                    try:
                        props["pchembl_value"] = float(pchembl)
                    except ValueError:
                        pass
                bio_batch.append(("Bioactivity", props))

            # HAS_BIOACTIVITY edge (Drug -> Bioactivity)
            if drugbank_id:
                edge_key = (drugbank_id, assay_id)
                if edge_key not in registry.has_bioactivity:
                    registry.has_bioactivity.add(edge_key)
                    has_bio_edges.append((
                        "Drug", "drugbank_id", drugbank_id,
                        "Bioactivity", "chembl_assay_id", assay_id,
                        "HAS_BIOACTIVITY", {},
                    ))

            # BIOACTIVITY_TARGET edge (Bioactivity -> Gene)
            if gene_name:
                # Ensure Gene node exists
                if gene_name not in registry.genes:
                    registry.genes.add(gene_name)
                    batch_create_nodes(client, [("Gene", {"gene_name": gene_name})], tenant)

                bt_key = (assay_id, gene_name)
                if bt_key not in registry.bioactivity_target:
                    registry.bioactivity_target.add(bt_key)
                    bio_target_edges.append((
                        "Bioactivity", "chembl_assay_id", assay_id,
                        "Gene", "gene_name", gene_name,
                        "BIOACTIVITY_TARGET", {},
                    ))

            progress.tick()

    # Batch create bioactivities
    if bio_batch:
        batch_create_nodes(client, bio_batch, tenant)

    hb_count = batch_create_edges(client, has_bio_edges, tenant)
    bt_count = batch_create_edges(client, bio_target_edges, tenant)

    print(f"  ChEMBL: {len(bio_batch)} bioactivities, {hb_count} HAS_BIOACTIVITY, "
          f"{bt_count} BIOACTIVITY_TARGET")
    return len(bio_batch), hb_count, bt_count


def _find_drug_by_chembl(
    client, chembl_id: str, name_to_dbid: dict[str, str], tenant: str
) -> str | None:
    """Find drugbank_id by chembl_id on existing Drug nodes."""
    if not chembl_id:
        return None
    try:
        result = client.query(
            f"MATCH (d:Drug {{chembl_id: '{chembl_id}'}}) RETURN d.drugbank_id",
            tenant,
        )
        if result.records:
            return result.records[0][0]
    except Exception:
        pass
    return None


def _load_ttd_targets(
    client,
    path: str,
    registry: Registry,
    name_to_dbid: dict[str, str],
    tenant: str,
) -> tuple[int, int]:
    """Load Target nodes and TTD_TARGETS edges.

    TTD TSV format: TTD_target_id, target_name, uniprot_id, target_type,
    drug_name, clinical_status

    Returns (target_count, edge_count).
    """
    progress = ProgressReporter("TTD", 0)
    target_batch: list[tuple[str, dict]] = []
    edge_batch: list[tuple[str, str, str, str, str, str, str, dict]] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            target_id = row.get("TTD_target_id", "").strip()
            target_name = row.get("target_name", "").strip()
            uniprot_id = row.get("uniprot_id", "").strip()
            target_type = row.get("target_type", "").strip()
            drug_name = row.get("drug_name", "").strip()
            clinical_status = row.get("clinical_status", "").strip()

            if not target_id:
                continue

            # Create Target node if new
            if target_id not in registry.targets:
                registry.targets.add(target_id)
                props: dict = {"ttd_target_id": target_id, "name": target_name}
                if uniprot_id:
                    props["uniprot_id"] = uniprot_id
                if target_type:
                    props["target_type"] = target_type
                target_batch.append(("Target", props))

            # TTD_TARGETS edge (Drug -> Target)
            if drug_name:
                drugbank_id = name_to_dbid.get(drug_name.lower())
                if drugbank_id:
                    edge_key = (drugbank_id, target_id)
                    if edge_key not in registry.ttd_targets:
                        registry.ttd_targets.add(edge_key)
                        edge_props: dict = {}
                        if clinical_status:
                            edge_props["clinical_status"] = clinical_status
                        edge_batch.append((
                            "Drug", "drugbank_id", drugbank_id,
                            "Target", "ttd_target_id", target_id,
                            "TTD_TARGETS", edge_props,
                        ))
                        progress.tick()

    if target_batch:
        batch_create_nodes(client, target_batch, tenant)

    edge_count = batch_create_edges(client, edge_batch, tenant)
    print(f"  TTD: {len(target_batch)} targets, {edge_count} TTD_TARGETS edges")
    return len(target_batch), edge_count


def _load_atc(
    client,
    path: str,
    registry: Registry,
    name_to_dbid: dict[str, str],
    tenant: str,
) -> tuple[int, int, int]:
    """Load DrugClass nodes, CLASSIFIED_AS and PARENT_CLASS edges from ATC hierarchy.

    ATC TSV format: atc_code, name, level, drug_name

    Returns (class_count, classified_edges, parent_edges).
    """
    progress = ProgressReporter("ATC", 0)
    class_batch: list[tuple[str, dict]] = []
    classified_edges: list[tuple[str, str, str, str, str, str, str, dict]] = []
    parent_edges: list[tuple[str, str, str, str, str, str, str, dict]] = []

    # Collect all ATC entries for hierarchy building
    atc_entries: list[dict] = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            atc_code = row.get("atc_code", "").strip()
            name = row.get("name", "").strip()
            level = row.get("level", "").strip()
            drug_name = row.get("drug_name", "").strip()

            if not atc_code or not name:
                continue

            atc_entries.append({
                "atc_code": atc_code,
                "name": name,
                "level": int(level) if level.isdigit() else 0,
                "drug_name": drug_name,
            })

            # Create DrugClass node if new
            if atc_code not in registry.drug_classes:
                registry.drug_classes.add(atc_code)
                props: dict = {"atc_code": atc_code, "name": name}
                if level.isdigit():
                    props["level"] = int(level)
                class_batch.append(("DrugClass", props))

            # CLASSIFIED_AS edge (Drug -> DrugClass) for level 5 entries with drug_name
            if drug_name and level == "5":
                drugbank_id = name_to_dbid.get(drug_name.lower())
                if drugbank_id:
                    edge_key = (drugbank_id, atc_code)
                    if edge_key not in registry.classified_as:
                        registry.classified_as.add(edge_key)
                        classified_edges.append((
                            "Drug", "drugbank_id", drugbank_id,
                            "DrugClass", "atc_code", atc_code,
                            "CLASSIFIED_AS", {},
                        ))

    # Create DrugClass nodes
    if class_batch:
        batch_create_nodes(client, class_batch, tenant)

    # Build PARENT_CLASS edges from ATC hierarchy
    # ATC codes: A (1), A10 (2-3), A10B (3-4 chars), A10BA (4-5), A10BA02 (7)
    # Parent is the shorter prefix code
    for entry in atc_entries:
        atc_code = entry["atc_code"]
        level = entry["level"]
        parent_code = _atc_parent(atc_code, level)
        if parent_code and parent_code in registry.drug_classes:
            edge_key = (atc_code, parent_code)
            if edge_key not in registry.parent_class:
                registry.parent_class.add(edge_key)
                parent_edges.append((
                    "DrugClass", "atc_code", atc_code,
                    "DrugClass", "atc_code", parent_code,
                    "PARENT_CLASS", {},
                ))

    cl_count = batch_create_edges(client, classified_edges, tenant)
    pa_count = batch_create_edges(client, parent_edges, tenant)

    print(f"  ATC: {len(class_batch)} classes, {cl_count} CLASSIFIED_AS, "
          f"{pa_count} PARENT_CLASS")
    return len(class_batch), cl_count, pa_count


def _atc_parent(code: str, level: int) -> str | None:
    """Derive ATC parent code from child code and level.

    ATC levels: 1 (1 char), 2 (3 chars), 3 (4 chars), 4 (5 chars), 5 (7 chars)
    """
    parent_lens = {5: 5, 4: 4, 3: 3, 2: 1}
    parent_len = parent_lens.get(level)
    if parent_len and len(code) >= parent_len:
        return code[:parent_len]
    return None
