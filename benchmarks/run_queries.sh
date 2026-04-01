#!/bin/bash
# Run curated real-world queries against the Drug Interactions KG
# Usage: ./benchmarks/run_queries.sh [--data-dir PATH]
#
# Loads data from --data-dir (default: data/), runs 10 PROFILE queries,
# captures results to benchmarks/query_results.txt

set -euo pipefail
export PATH="$HOME/.cargo/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SG_DIR="$(dirname "$REPO_DIR")/samyama-graph"
DATA_DIR="${1:-$REPO_DIR/data}"
OUTPUT="$SCRIPT_DIR/query_results.txt"

echo "=== Drug Interactions KG — Query Benchmark ==="
echo "Data dir:   $DATA_DIR"
echo "Output:     $OUTPUT"
echo "Samyama:    $SG_DIR"
echo ""

cd "$SG_DIR"

cargo run --release --example druginteractions_loader -- \
  --data-dir "$DATA_DIR" \
  --query << 'QUERIES' 2>&1 | tee "$OUTPUT"
PROFILE MATCH (n) RETURN labels(n) AS label, count(n) AS count ORDER BY count DESC
PROFILE MATCH (d:Drug)-[r:INTERACTS_WITH_GENE]->(g:Gene) RETURN d.name AS drug, g.gene_name AS gene, r.interaction_type AS type ORDER BY d.name LIMIT 20
PROFILE MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect) WITH d, count(se) AS se_count WHERE se_count > 100 RETURN d.name AS drug, se_count ORDER BY se_count DESC LIMIT 20
PROFILE MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect) WITH se, count(d) AS drug_count WHERE drug_count > 50 RETURN se.name AS side_effect, drug_count ORDER BY drug_count DESC LIMIT 20
PROFILE MATCH (d:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene)<-[:INTERACTS_WITH_GENE]-(d2:Drug) WHERE d.name < d2.name WITH d, d2, collect(g.gene_name) AS shared_genes, count(g) AS gene_count WHERE gene_count >= 5 RETURN d.name AS drug1, d2.name AS drug2, gene_count, shared_genes ORDER BY gene_count DESC LIMIT 15
PROFILE MATCH (d:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene) WITH g, count(d) AS drug_count WHERE drug_count > 20 RETURN g.gene_name AS gene, drug_count ORDER BY drug_count DESC LIMIT 20
PROFILE MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect) WHERE se.name = 'Nausea' RETURN d.name AS drug ORDER BY d.name LIMIT 30
PROFILE MATCH (d:Drug)-[:HAS_INDICATION]->(ind:Indication) WITH ind, count(d) AS drug_count WHERE drug_count > 10 RETURN ind.name AS indication, drug_count ORDER BY drug_count DESC LIMIT 20
PROFILE MATCH (d:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene) WHERE g.gene_name = 'EGFR' RETURN d.name AS drug, d.drugbank_id AS dbid ORDER BY d.name
PROFILE MATCH (d:Drug)-[:HAS_SIDE_EFFECT]->(se:SideEffect)<-[:HAS_SIDE_EFFECT]-(d2:Drug) WHERE d.name = 'Imatinib' AND d.name <> d2.name WITH d2, count(se) AS shared_se RETURN d2.name AS similar_drug, shared_se ORDER BY shared_se DESC LIMIT 15
exit
QUERIES

echo ""
echo "Results saved to $OUTPUT"
