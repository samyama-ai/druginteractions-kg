"""Tests for OpenFDA FAERS loader (Phase 4).

TDD: uses mock API responses instead of live OpenFDA calls.
Requires Phase 1 Drug nodes to exist first.
"""

import os
import tempfile
import json
import pytest

# --- Sample DrugBank vocab for Phase 1 pre-load ---
SAMPLE_DRUGBANK_VOCAB = """DrugBank ID,Accession Numbers,Common name,CAS,UNII,Synonyms,Standard InChI Key
DB00945,DB00945,Aspirin,50-78-2,R16CO5Y76E,"Acetylsalicylic acid",BSYNRYMUTXBXSQ-UHFFFAOYSA-N
DB00563,DB00563,Metformin,657-24-9,9100L32L2N,"Dimethylbiguanide",XZWYZXLIPXDOLR-UHFFFAOYSA-N
"""

# --- Sample OpenFDA response JSON (pre-downloaded) ---
SAMPLE_OPENFDA_ASPIRIN = {
    "results": [
        {"term": "NAUSEA", "count": 15000},
        {"term": "HEADACHE", "count": 12000},
        {"term": "GASTROINTESTINAL HAEMORRHAGE", "count": 8000},
    ]
}

SAMPLE_OPENFDA_METFORMIN = {
    "results": [
        {"term": "DIARRHOEA", "count": 20000},
        {"term": "NAUSEA", "count": 18000},
        {"term": "LACTIC ACIDOSIS", "count": 5000},
    ]
}


def _write_fixture(tmpdir, subdir, filename, content):
    d = os.path.join(tmpdir, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


@pytest.fixture(scope="module")
def phase4_data():
    """Pre-load Phase 1 Drug nodes, then load Phase 4 from cached JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_fixture(tmpdir, "drugbank", "drugbank_vocabulary.csv", SAMPLE_DRUGBANK_VOCAB)

        # Write cached OpenFDA responses
        openfda_dir = os.path.join(tmpdir, "openfda")
        os.makedirs(openfda_dir, exist_ok=True)
        with open(os.path.join(openfda_dir, "Aspirin.json"), "w") as f:
            json.dump(SAMPLE_OPENFDA_ASPIRIN, f)
        with open(os.path.join(openfda_dir, "Metformin.json"), "w") as f:
            json.dump(SAMPLE_OPENFDA_METFORMIN, f)

        try:
            from samyama import SamyamaClient
            from etl.helpers import Registry
            from etl.drugbank_dgidb_loader import load_drugbank_dgidb
            from etl.openfda_loader import load_openfda

            client = SamyamaClient.embedded()
            registry = Registry()

            # Phase 1: create Drug nodes
            load_drugbank_dgidb(client, tmpdir, registry)

            # Phase 4: load OpenFDA from cached files
            stats = load_openfda(client, tmpdir, registry, use_cache=True)
            yield client, stats, registry
        except ImportError:
            pytest.skip("samyama package not available")


def _q(client, cypher):
    try:
        r = client.query_readonly(cypher, "default")
        return [dict(zip(r.columns, row)) for row in r.records]
    except Exception:
        r = client.query(cypher, "default")
        return [dict(zip(r.columns, row)) for row in r.records]


class TestAdverseEventNodes:
    def test_adverse_events_created(self, phase4_data):
        client, _, _ = phase4_data
        rows = _q(client, "MATCH (ae:AdverseEvent) RETURN ae.term ORDER BY ae.term")
        terms = [r["ae.term"] for r in rows]
        assert "NAUSEA" in terms
        assert "HEADACHE" in terms
        assert "LACTIC ACIDOSIS" in terms

    def test_adverse_event_dedup(self, phase4_data):
        client, _, _ = phase4_data
        # NAUSEA appears for both drugs but should be one node
        rows = _q(client, "MATCH (ae:AdverseEvent {term: 'NAUSEA'}) RETURN count(*) AS c")
        assert rows[0]["c"] == 1


class TestHasAdverseEvent:
    def test_aspirin_adverse_events(self, phase4_data):
        client, _, _ = phase4_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[:HAS_ADVERSE_EVENT]->(ae:AdverseEvent)
            RETURN ae.term ORDER BY ae.term
        """)
        terms = [r["ae.term"] for r in rows]
        assert "NAUSEA" in terms
        assert "HEADACHE" in terms
        assert "GASTROINTESTINAL HAEMORRHAGE" in terms

    def test_metformin_adverse_events(self, phase4_data):
        client, _, _ = phase4_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Metformin'})-[:HAS_ADVERSE_EVENT]->(ae:AdverseEvent)
            RETURN ae.term ORDER BY ae.term
        """)
        terms = [r["ae.term"] for r in rows]
        assert "DIARRHOEA" in terms
        assert "LACTIC ACIDOSIS" in terms

    def test_edge_has_count(self, phase4_data):
        client, _, _ = phase4_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[r:HAS_ADVERSE_EVENT]->(ae:AdverseEvent {term: 'NAUSEA'})
            RETURN r.count
        """)
        assert rows[0]["r.count"] == 15000

    def test_shared_adverse_event(self, phase4_data):
        client, _, _ = phase4_data
        rows = _q(client, """
            MATCH (d1:Drug)-[:HAS_ADVERSE_EVENT]->(ae:AdverseEvent {term: 'NAUSEA'})
                  <-[:HAS_ADVERSE_EVENT]-(d2:Drug)
            WHERE d1.name < d2.name
            RETURN d1.name, d2.name
        """)
        assert len(rows) >= 1


class TestRegistryState:
    def test_adverse_events_tracked(self, phase4_data):
        _, _, registry = phase4_data
        assert "NAUSEA" in registry.adverse_events
        assert "HEADACHE" in registry.adverse_events

    def test_edges_tracked(self, phase4_data):
        _, _, registry = phase4_data
        assert ("DB00945", "NAUSEA") in registry.has_adverse_event


class TestStats:
    def test_stats_returned(self, phase4_data):
        _, stats, _ = phase4_data
        assert stats["source"] == "openfda"
        assert stats["adverse_event_nodes"] >= 5
        assert stats["has_adverse_event_edges"] >= 6
