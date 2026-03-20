"""Tests for SIDER loader (Phase 2).

TDD: sample fixture data for side effects and indications.
Requires Phase 1 Drug nodes to exist first.
"""

import os
import tempfile
import pytest

# --- Sample SIDER drug_names.tsv (STITCH CID -> drug name) ---
SAMPLE_DRUG_NAMES = """CID100000085\tAspirin
CID100000086\tMetformin
"""

# --- Sample DrugBank vocab for Phase 1 pre-load ---
SAMPLE_DRUGBANK_VOCAB = """DrugBank ID,Accession Numbers,Common name,CAS,UNII,Synonyms,Standard InChI Key
DB00945,DB00945,Aspirin,50-78-2,R16CO5Y76E,"Acetylsalicylic acid",BSYNRYMUTXBXSQ-UHFFFAOYSA-N
DB00563,DB00563,Metformin,657-24-9,9100L32L2N,"Dimethylbiguanide",XZWYZXLIPXDOLR-UHFFFAOYSA-N
"""

# --- Sample SIDER side effects (meddra_all_se.tsv format) ---
# CID, UMLS_CUI_from_label, method, UMLS_CUI_for_side_effect, side_effect_name
SAMPLE_SIDE_EFFECTS = """CID100000085\tC0000001\tindication_from_label\tC0002871\tAnemia
CID100000085\tC0000001\tindication_from_label\tC0018681\tHeadache
CID100000085\tC0000001\tindication_from_label\tC0027497\tNausea
CID100000086\tC0000001\tindication_from_label\tC0011991\tDiarrhea
CID100000086\tC0000001\tindication_from_label\tC0027497\tNausea
"""

# --- Sample SIDER indications (meddra_all_indications.tsv format) ---
# CID, UMLS_CUI_from_label, method, concept_name, MedDRA_concept_type, UMLS_CUI_for_indication, indication_name
SAMPLE_INDICATIONS = """CID100000085\tC0000001\tmarker/mechanism\tPain\tpt\tC0030193\tPain
CID100000085\tC0000001\tmarker/mechanism\tFever\tpt\tC0015967\tFever
CID100000086\tC0000001\tmarker/mechanism\tDiabetes\tpt\tC0011849\tDiabetes Mellitus Type 2
"""


def _write_fixture(tmpdir, subdir, filename, content):
    d = os.path.join(tmpdir, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


@pytest.fixture(scope="module")
def phase2_data():
    """Pre-load Phase 1 Drug nodes, then load Phase 2 SIDER data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_fixture(tmpdir, "drugbank", "drugbank_vocabulary.csv", SAMPLE_DRUGBANK_VOCAB)
        _write_fixture(tmpdir, "sider", "drug_names.tsv", SAMPLE_DRUG_NAMES)
        _write_fixture(tmpdir, "sider", "meddra_all_se.tsv", SAMPLE_SIDE_EFFECTS)
        _write_fixture(tmpdir, "sider", "meddra_all_indications.tsv", SAMPLE_INDICATIONS)

        try:
            from samyama import SamyamaClient
            from etl.helpers import Registry
            from etl.drugbank_dgidb_loader import load_drugbank_dgidb
            from etl.sider_loader import load_sider

            client = SamyamaClient.embedded()
            registry = Registry()

            # Phase 1: create Drug nodes
            load_drugbank_dgidb(client, tmpdir, registry)

            # Phase 2: load SIDER
            stats = load_sider(client, tmpdir, registry)
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


class TestSideEffectNodes:
    def test_side_effects_created(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, "MATCH (se:SideEffect) RETURN se.name ORDER BY se.name")
        names = [r["se.name"] for r in rows]
        assert "Headache" in names
        assert "Nausea" in names
        assert "Diarrhea" in names

    def test_side_effect_has_meddra_id(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, "MATCH (se:SideEffect {name: 'Headache'}) RETURN se.meddra_id")
        assert rows[0]["se.meddra_id"] == "C0018681"

    def test_side_effect_dedup(self, phase2_data):
        client, _, _ = phase2_data
        # Nausea appears for both Aspirin and Metformin but should be one node
        rows = _q(client, "MATCH (se:SideEffect {name: 'Nausea'}) RETURN count(*) AS c")
        assert rows[0]["c"] == 1


class TestHasSideEffect:
    def test_aspirin_side_effects(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[:HAS_SIDE_EFFECT]->(se:SideEffect)
            RETURN se.name ORDER BY se.name
        """)
        names = [r["se.name"] for r in rows]
        assert "Headache" in names
        assert "Nausea" in names

    def test_metformin_side_effects(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Metformin'})-[:HAS_SIDE_EFFECT]->(se:SideEffect)
            RETURN se.name ORDER BY se.name
        """)
        names = [r["se.name"] for r in rows]
        assert "Diarrhea" in names
        assert "Nausea" in names


class TestIndicationNodes:
    def test_indications_created(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, "MATCH (ind:Indication) RETURN ind.name ORDER BY ind.name")
        names = [r["ind.name"] for r in rows]
        assert "Pain" in names
        assert "Fever" in names
        assert "Diabetes Mellitus Type 2" in names


class TestHasIndication:
    def test_aspirin_indications(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[:HAS_INDICATION]->(ind:Indication)
            RETURN ind.name ORDER BY ind.name
        """)
        names = [r["ind.name"] for r in rows]
        assert "Pain" in names
        assert "Fever" in names

    def test_metformin_indications(self, phase2_data):
        client, _, _ = phase2_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Metformin'})-[:HAS_INDICATION]->(ind:Indication)
            RETURN ind.name
        """)
        assert rows[0]["ind.name"] == "Diabetes Mellitus Type 2"


class TestRegistryState:
    def test_side_effects_tracked(self, phase2_data):
        _, _, registry = phase2_data
        assert "C0018681" in registry.side_effects
        assert "C0027497" in registry.side_effects

    def test_indications_tracked(self, phase2_data):
        _, _, registry = phase2_data
        assert "C0030193" in registry.indications

    def test_edges_tracked(self, phase2_data):
        _, _, registry = phase2_data
        assert ("DB00945", "C0018681") in registry.has_side_effect


class TestStats:
    def test_stats_returned(self, phase2_data):
        _, stats, _ = phase2_data
        assert stats["source"] == "sider"
        assert stats["side_effect_nodes"] >= 4
        assert stats["indication_nodes"] >= 3
        assert stats["has_side_effect_edges"] >= 5
        assert stats["has_indication_edges"] >= 3
