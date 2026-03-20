"""Phase 4: OpenFDA FAERS adverse events loader.

Creates AdverseEvent nodes and HAS_ADVERSE_EVENT edges.
Supports two modes:
  - API mode: queries OpenFDA API per drug (rate-limited)
  - Cache mode: reads pre-downloaded JSON files from data/openfda/
"""

from __future__ import annotations

import json
import os
import time

from etl.helpers import (
    Registry,
    ProgressReporter,
    batch_create_nodes,
    batch_create_edges,
    create_index,
)

OPENFDA_API_URL = "https://api.fda.gov/drug/event.json"
RATE_LIMIT_DELAY = 0.5  # seconds between API requests


def load_openfda(
    client,
    data_dir: str,
    registry: Registry,
    tenant: str = "default",
    use_cache: bool = False,
    max_drugs: int = 0,
    top_n_events: int = 50,
) -> dict:
    """Load OpenFDA FAERS adverse events.

    Args:
        client: SamyamaClient instance
        data_dir: Root data directory with openfda/ subdir for cached files
        registry: Deduplication registry
        tenant: Graph tenant
        use_cache: If True, read from cached JSON files instead of API
        max_drugs: Maximum drugs to query (0 = all)
        top_n_events: Top N adverse events per drug

    Returns:
        Stats dict with node/edge counts
    """
    print("Phase 4: OpenFDA FAERS")

    create_index(client, "AdverseEvent", "term", tenant)

    # Get existing Drug nodes
    drug_names = _get_drug_names(client, tenant)
    if max_drugs > 0:
        drug_names = drug_names[:max_drugs]

    ae_nodes = 0
    ae_edges = 0

    openfda_dir = os.path.join(data_dir, "openfda")

    if use_cache:
        ae_nodes, ae_edges = _load_from_cache(
            client, openfda_dir, drug_names, registry, tenant, top_n_events
        )
    else:
        ae_nodes, ae_edges = _load_from_api(
            client, openfda_dir, drug_names, registry, tenant, top_n_events
        )

    stats = {
        "source": "openfda",
        "adverse_event_nodes": ae_nodes,
        "has_adverse_event_edges": ae_edges,
        "drugs_queried": len(drug_names),
    }
    print(f"  Phase 4 done: {ae_nodes} adverse events, {ae_edges} edges "
          f"({len(drug_names)} drugs queried)")
    return stats


def _get_drug_names(client, tenant: str) -> list[tuple[str, str]]:
    """Get (name, drugbank_id) pairs for all Drug nodes."""
    drugs: list[tuple[str, str]] = []
    try:
        result = client.query(
            "MATCH (d:Drug) RETURN d.name, d.drugbank_id ORDER BY d.name",
            tenant,
        )
        for row in result.records:
            if row[0] and row[1]:
                drugs.append((row[0], row[1]))
    except Exception:
        pass
    return drugs


def _load_from_cache(
    client,
    cache_dir: str,
    drug_names: list[tuple[str, str]],
    registry: Registry,
    tenant: str,
    top_n: int,
) -> tuple[int, int]:
    """Load adverse events from cached JSON files."""
    progress = ProgressReporter("OpenFDA-cache", len(drug_names))
    total_ae_nodes = 0
    total_ae_edges = 0

    for drug_name, drugbank_id in drug_names:
        cache_path = os.path.join(cache_dir, f"{drug_name}.json")
        if not os.path.exists(cache_path):
            continue

        with open(cache_path, "r") as f:
            data = json.load(f)

        results = data.get("results", [])
        n, e = _process_events(client, drugbank_id, results[:top_n], registry, tenant)
        total_ae_nodes += n
        total_ae_edges += e
        progress.tick()

    return total_ae_nodes, total_ae_edges


def _load_from_api(
    client,
    cache_dir: str,
    drug_names: list[tuple[str, str]],
    registry: Registry,
    tenant: str,
    top_n: int,
) -> tuple[int, int]:
    """Query OpenFDA API for adverse events per drug."""
    import requests

    os.makedirs(cache_dir, exist_ok=True)
    progress = ProgressReporter("OpenFDA-API", len(drug_names))
    total_ae_nodes = 0
    total_ae_edges = 0

    for drug_name, drugbank_id in drug_names:
        # Check cache first
        cache_path = os.path.join(cache_dir, f"{drug_name}.json")
        if os.path.exists(cache_path):
            with open(cache_path, "r") as f:
                data = json.load(f)
        else:
            try:
                resp = requests.get(
                    OPENFDA_API_URL,
                    params={
                        "search": f'patient.drug.medicinalproduct:"{drug_name}"',
                        "count": "patient.reaction.reactionmeddrapt.exact",
                        "limit": top_n,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

                # Cache the response
                with open(cache_path, "w") as f:
                    json.dump(data, f)
            except Exception as exc:
                print(f"  [WARN] OpenFDA query failed for {drug_name}: {exc}")
                progress.error()
                continue

            time.sleep(RATE_LIMIT_DELAY)

        results = data.get("results", [])
        n, e = _process_events(client, drugbank_id, results[:top_n], registry, tenant)
        total_ae_nodes += n
        total_ae_edges += e
        progress.tick()

    return total_ae_nodes, total_ae_edges


def _process_events(
    client,
    drugbank_id: str,
    results: list[dict],
    registry: Registry,
    tenant: str,
) -> tuple[int, int]:
    """Process adverse event results for a single drug.

    Results format: [{"term": "NAUSEA", "count": 15000}, ...]

    Returns (new_ae_nodes, new_edges).
    """
    ae_batch: list[tuple[str, dict]] = []
    edge_batch: list[tuple[str, str, str, str, str, str, str, dict]] = []

    for item in results:
        term = item.get("term", "").strip()
        count = item.get("count", 0)

        if not term:
            continue

        # Create AdverseEvent node if new
        if term not in registry.adverse_events:
            registry.adverse_events.add(term)
            ae_batch.append(("AdverseEvent", {"term": term}))

        # Create edge if not duplicate
        edge_key = (drugbank_id, term)
        if edge_key not in registry.has_adverse_event:
            registry.has_adverse_event.add(edge_key)
            edge_batch.append((
                "Drug", "drugbank_id", drugbank_id,
                "AdverseEvent", "term", term,
                "HAS_ADVERSE_EVENT", {"count": count},
            ))

    if ae_batch:
        batch_create_nodes(client, ae_batch, tenant)

    edge_count = batch_create_edges(client, edge_batch, tenant)
    return len(ae_batch), edge_count
