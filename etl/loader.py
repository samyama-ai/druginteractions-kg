"""Drug Interactions KG — Main ETL Orchestrator.

Ties together all phase loaders (DrugBank/DGIdb, SIDER, ChEMBL/TTD, OpenFDA)
into a single load_druginteractions() entry point with phase selection.

Usage:
    python -m etl.loader --data-dir data --phases drugbank_dgidb sider
    python -m etl.loader --data-dir data  # All phases
    python -m etl.loader --data-dir data --url http://localhost:8080
"""

from __future__ import annotations

import argparse
import sys
import time

from etl.helpers import Registry


ALL_PHASES = ["drugbank_dgidb", "sider", "chembl_ttd", "openfda"]


def _run_phase(
    phase: str,
    client,
    data_dir: str,
    registry: Registry,
    *,
    tenant: str = "default",
    openfda_use_cache: bool = False,
    openfda_max_drugs: int = 0,
) -> dict:
    """Dispatch to the appropriate phase loader."""
    if phase == "drugbank_dgidb":
        from etl.drugbank_dgidb_loader import load_drugbank_dgidb
        return load_drugbank_dgidb(client, data_dir, registry, tenant=tenant)

    elif phase == "sider":
        from etl.sider_loader import load_sider
        return load_sider(client, data_dir, registry, tenant=tenant)

    elif phase == "chembl_ttd":
        from etl.chembl_ttd_loader import load_chembl_ttd
        return load_chembl_ttd(client, data_dir, registry, tenant=tenant)

    elif phase == "openfda":
        from etl.openfda_loader import load_openfda
        return load_openfda(
            client, data_dir, registry,
            tenant=tenant,
            use_cache=openfda_use_cache,
            max_drugs=openfda_max_drugs,
        )

    else:
        print(f"[WARN] Unknown phase: {phase}, skipping")
        return {"source": phase, "error": "unknown phase"}


def load_druginteractions(
    client,
    data_dir: str = "data",
    phases: list[str] | None = None,
    tenant: str = "default",
    openfda_use_cache: bool = False,
    openfda_max_drugs: int = 0,
) -> dict:
    """Load drug interactions data into the knowledge graph.

    Runs each requested phase in order, sharing a single Registry for
    cross-phase deduplication.

    Args:
        client: SamyamaClient instance (embedded or remote).
        data_dir: Root directory containing per-source subdirectories.
        phases: List of phases to run. Default: all phases.
        tenant: Graph tenant name.
        openfda_use_cache: Use cached OpenFDA JSON files.
        openfda_max_drugs: Max drugs to query from OpenFDA (0 = all).

    Returns:
        Combined statistics dict.
    """
    if phases is None:
        phases = list(ALL_PHASES)

    invalid = [p for p in phases if p not in ALL_PHASES]
    if invalid:
        print(f"[WARN] Unknown phases ignored: {invalid}")
        phases = [p for p in phases if p in ALL_PHASES]

    if not phases:
        print("[ERROR] No valid phases to run.")
        return {}

    print("=" * 60)
    print(f"Drug Interactions KG — Loading {len(phases)} phase(s): {', '.join(phases)}")
    print(f"  data_dir: {data_dir}")
    print(f"  tenant:   {tenant}")
    print("=" * 60)

    registry = Registry()
    phase_results: list[dict] = []
    t0_total = time.time()

    for phase in phases:
        print(f"\n{'─' * 50}")
        print(f"Phase: {phase.upper()}")
        print(f"{'─' * 50}")

        t0_phase = time.time()
        try:
            stats = _run_phase(
                phase, client, data_dir, registry,
                tenant=tenant,
                openfda_use_cache=openfda_use_cache,
                openfda_max_drugs=openfda_max_drugs,
            )
            elapsed = time.time() - t0_phase
            stats["elapsed_s"] = round(elapsed, 1)
            stats["status"] = "ok"
        except FileNotFoundError as exc:
            elapsed = time.time() - t0_phase
            stats = {
                "source": phase, "status": "skipped",
                "reason": str(exc), "elapsed_s": round(elapsed, 1),
            }
            print(f"[SKIP] {phase}: {exc}")
        except Exception as exc:
            elapsed = time.time() - t0_phase
            stats = {
                "source": phase, "status": "error",
                "reason": str(exc), "elapsed_s": round(elapsed, 1),
            }
            print(f"[ERROR] {phase}: {exc}")

        phase_results.append(stats)
        print(f"  Phase {phase} completed in {elapsed:.1f}s")

    elapsed_total = time.time() - t0_total

    # Summary
    print(f"\n{'=' * 60}")
    print("Drug Interactions KG — Load Summary")
    print(f"{'=' * 60}")
    print(f"{'Phase':<20s} {'Status':<10s} {'Time':>8s}  Details")
    print(f"{'─' * 60}")

    for result in phase_results:
        source = result.get("source", "?")
        status = result.get("status", "?")
        elapsed_s = result.get("elapsed_s", 0)
        detail_parts = []
        for k, v in result.items():
            if k in ("source", "status", "elapsed_s", "reason"):
                continue
            if isinstance(v, (int, float)) and v > 0:
                detail_parts.append(f"{k}={v}")
        detail = ", ".join(detail_parts[:5]) if detail_parts else result.get("reason", "")
        print(f"  {source:<18s} {status:<10s} {elapsed_s:>6.1f}s  {detail}")

    print(f"{'─' * 60}")
    print(f"  {'TOTAL':<18s} {'':10s} {elapsed_total:>6.1f}s")

    # Registry summary
    print(f"\nRegistry totals:")
    print(f"  Drugs:           {len(registry.drugs):>8,d}")
    print(f"  Genes:           {len(registry.genes):>8,d}")
    print(f"  Side Effects:    {len(registry.side_effects):>8,d}")
    print(f"  Indications:     {len(registry.indications):>8,d}")
    print(f"  Bioactivities:   {len(registry.bioactivities):>8,d}")
    print(f"  Targets:         {len(registry.targets):>8,d}")
    print(f"  Drug Classes:    {len(registry.drug_classes):>8,d}")
    print(f"  Adverse Events:  {len(registry.adverse_events):>8,d}")
    print(f"{'=' * 60}\n")

    combined: dict = {
        "phases_loaded": [r.get("source") for r in phase_results if r.get("status") == "ok"],
        "total_elapsed_s": round(elapsed_total, 1),
    }
    for result in phase_results:
        for k, v in result.items():
            if isinstance(v, int) and k not in ("elapsed_s",):
                combined[k] = combined.get(k, 0) + v

    return combined


def main():
    parser = argparse.ArgumentParser(
        description="Load drug interactions data into Samyama graph.",
    )
    parser.add_argument("--data-dir", default="data",
                        help="Root directory for data files (default: data)")
    parser.add_argument("--phases", nargs="*", default=None,
                        help=f"Phases to load (default: all). Choices: {', '.join(ALL_PHASES)}")
    parser.add_argument("--tenant", default="default",
                        help="Graph tenant name (default: default)")
    parser.add_argument("--url", default=None,
                        help="Samyama server URL (omit for embedded mode)")
    parser.add_argument("--openfda-cache", action="store_true",
                        help="Use cached OpenFDA JSON files")
    parser.add_argument("--openfda-max-drugs", type=int, default=0,
                        help="Max drugs to query from OpenFDA (0=all)")
    args = parser.parse_args()

    from samyama import SamyamaClient

    if args.url:
        client = SamyamaClient.connect(args.url)
    else:
        client = SamyamaClient.embedded()

    load_druginteractions(
        client,
        data_dir=args.data_dir,
        phases=args.phases,
        tenant=args.tenant,
        openfda_use_cache=args.openfda_cache,
        openfda_max_drugs=args.openfda_max_drugs,
    )


if __name__ == "__main__":
    main()
