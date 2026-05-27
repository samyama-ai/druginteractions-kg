"""Narrated terminal demo: Drug interactions & pharmacogenomics on Samyama.

Record with asciinema:
    asciinema rec -c "python -m demo.demo" demo/druginteractions.cast

Loads a fast, real SUBSET of the Drug Interactions KG — the DrugBank CC0 drug
vocabulary plus the first 4,000 DGIdb drug-gene interactions and the first
4,000 SIDER drug-side-effect links — and walks through the questions a
pharmacologist asks: what genes do drugs hit, which drugs collide on the same
target (polypharmacy), and which drugs carry the heaviest side-effect burden.

Subset is bounded via the loader's `limit` arg so the whole demo loads in
well under a minute (full KG is ~245K nodes / 388K edges, ~33 GB of source).
All data is REAL (DrugBank CC0, DGIdb, SIDER) — no mocks.
"""

from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from samyama import SamyamaClient

from etl.loader import load_druginteractions

console = Console()
G = "druginteractions"
LIMIT = 4000


def pause(s: float = 1.4) -> None:
    time.sleep(s)


def step(title: str) -> None:
    console.print()
    console.rule(f"[bold cyan]{title}")
    pause(0.6)


def run(client, q, label):
    console.print(f"  [dim]cypher>[/dim] [yellow]{q}[/yellow]")
    rows = client.query(q, G).records
    one = len(rows) == 1 and len(rows[0]) == 1
    console.print(f"  [green]→[/green] {label}: [bold]{rows[0][0] if one else rows}[/bold]")
    pause()
    return rows


def main() -> None:
    console.print(Panel.fit(
        "[bold]Samyama · Drug Interactions Knowledge Graph[/bold]\n"
        "Drug targets, polypharmacy & side-effect burden across open pharma data\n"
        "[dim]data: DrugBank CC0 + DGIdb + SIDER · real public subset[/dim]",
        border_style="cyan",
    ))
    pause(1.2)

    step("1 · Load a real subset (DrugBank + DGIdb + SIDER) into Samyama")
    console.print(f"  [dim]capping DGIdb interactions and SIDER side-effects at {LIMIT} each…[/dim]")
    stats = load_druginteractions(client := SamyamaClient.embedded(), "data",
                                  phases=["drugbank_dgidb", "sider"],
                                  tenant=G, limit=LIMIT)
    console.print(f"  [green]loaded[/green] {stats.get('drug_nodes', 0)} drugs, "
                  f"{stats.get('gene_nodes', 0)} genes, "
                  f"{stats.get('side_effect_nodes', 0)} side effects")
    run(client, "MATCH ()-[r:INTERACTS_WITH_GENE]->() RETURN count(r) AS n",
        "drug-gene interactions loaded")
    run(client, "MATCH ()-[r:HAS_SIDE_EFFECT]->() RETURN count(r) AS n",
        "drug-side-effect links loaded")

    step("2 · Which genes are the busiest drug targets?")
    run(
        client,
        "MATCH (d:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene) "
        "RETURN g.gene_name AS gene, count(d) AS drugs "
        "ORDER BY drugs DESC LIMIT 5",
        "most-targeted genes (CYP enzymes dominate)",
    )

    step("3 · Polypharmacy: which drugs collide on a shared gene target?")
    console.print("  [dim]two drugs hitting the same gene → potential interaction…[/dim]")
    pause()
    run(
        client,
        "MATCH (d1:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene)<-[:INTERACTS_WITH_GENE]-(d2:Drug) "
        "WHERE d1.name < d2.name "
        "RETURN d1.name AS drug_a, d2.name AS drug_b, g.gene_name AS shared_target "
        "ORDER BY shared_target LIMIT 5",
        "drug pairs sharing a molecular target",
    )

    step("4 · Which drugs carry the heaviest side-effect burden?")
    run(
        client,
        "MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect) "
        "RETURN d.name AS drug, count(se) AS side_effects "
        "ORDER BY side_effects DESC LIMIT 5",
        "most side effects reported (SIDER)",
    )

    console.print()
    console.print(Panel.fit(
        "[bold green]Drug.drugbank_id joins this to clinicaltrials-kg and "
        "Gene.gene_name to pathways-kg[/bold green] — targets, interactions,\n"
        "and adverse effects answered on one engine, one Cypher query.",
        border_style="green",
    ))
    pause(1.5)


if __name__ == "__main__":
    main()
