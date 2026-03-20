"""Tests for ChEMBL + TTD loader (Phase 3).

TDD: sample fixture data for bioactivities, targets, and drug classes.
Requires Phase 1 Drug nodes to exist first.
"""

import os
import tempfile
import pytest

# --- Sample DrugBank vocab for Phase 1 pre-load ---
SAMPLE_DRUGBANK_VOCAB = """DrugBank ID,Accession Numbers,Common name,CAS,UNII,Synonyms,Standard InChI Key
DB00945,DB00945,Aspirin,50-78-2,R16CO5Y76E,"Acetylsalicylic acid",BSYNRYMUTXBXSQ-UHFFFAOYSA-N
DB00563,DB00563,Metformin,657-24-9,9100L32L2N,"Dimethylbiguanide",XZWYZXLIPXDOLR-UHFFFAOYSA-N
"""

# --- Minimal DGIdb data to enrich drugs with chembl_id ---
SAMPLE_DGIDB_INTERACTIONS = """gene_name\tgene_claim_name\tentrez_id\tinteraction_claim_source\tinteraction_types\tdrug_claim_name\tdrug_claim_primary_name\tdrug_name\tdrug_chembl_id\tPMIDs
PTGS2\tCOX-2\t5743\tDrugBank\tinhibitor\tAspirin\tAspirin\tASPIRIN\tCHEMBL25\t12345
AMPK\tAMPK\t5562\tDrugBank\tactivator\tMetformin\tMetformin\tMETFORMIN\tCHEMBL1431\t67890
"""

SAMPLE_DGIDB_DRUGS = """drug_claim_name\tdrug_name\tchembl_id\tdrug_claim_source
Aspirin\tASPIRIN\tCHEMBL25\tDrugBank
Metformin\tMETFORMIN\tCHEMBL1431\tDrugBank
"""

# --- Sample ChEMBL bioactivity TSV (pre-extracted from SQLite) ---
SAMPLE_CHEMBL_ACTIVITIES = """chembl_id\tchembl_assay_id\tassay_type\tstandard_type\tstandard_value\tstandard_units\tpchembl_value\ttarget_chembl_id\ttarget_name\ttarget_type\tgene_name\torganism
CHEMBL25\tCHEMBL614786\tB\tIC50\t50.0\tnM\t7.3\tCHEMBL218\tCyclooxygenase-2\tSINGLE PROTEIN\tPTGS2\tHomo sapiens
CHEMBL25\tCHEMBL614787\tB\tKi\t100.0\tnM\t7.0\tCHEMBL221\tCyclooxygenase-1\tSINGLE PROTEIN\tPTGS1\tHomo sapiens
CHEMBL1431\tCHEMBL614788\tB\tIC50\t200.0\tnM\t6.7\tCHEMBL2722\tAMP-activated protein kinase\tSINGLE PROTEIN\tAMPK\tHomo sapiens
"""

# --- Sample TTD targets TSV ---
SAMPLE_TTD_TARGETS = """TTD_target_id\ttarget_name\tuniprot_id\ttarget_type\tdrug_name\tclinical_status
T12345\tCyclooxygenase-2\tP35354\tSuccessful target\tAspirin\tApproved
T67890\tAMP-activated protein kinase\tQ13131\tClinical Trial target\tMetformin\tPhase III
"""

# --- Sample ATC classification ---
SAMPLE_ATC = """atc_code\tname\tlevel\tdrug_name
N02BA01\tAcetylsalicylic acid\t5\tAspirin
N02BA\tSalicylic acid and derivatives\t4\t
N02B\tOther analgesics and antipyretics\t3\t
A10BA02\tMetformin\t5\tMetformin
A10BA\tBiguanides\t4\t
"""


def _write_fixture(tmpdir, subdir, filename, content):
    d = os.path.join(tmpdir, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


@pytest.fixture(scope="module")
def phase3_data():
    """Pre-load Phase 1 Drug+Gene nodes, then load Phase 3."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_fixture(tmpdir, "drugbank", "drugbank_vocabulary.csv", SAMPLE_DRUGBANK_VOCAB)
        _write_fixture(tmpdir, "dgidb", "interactions.tsv", SAMPLE_DGIDB_INTERACTIONS)
        _write_fixture(tmpdir, "dgidb", "drugs.tsv", SAMPLE_DGIDB_DRUGS)
        _write_fixture(tmpdir, "chembl", "chembl_activities.tsv", SAMPLE_CHEMBL_ACTIVITIES)
        _write_fixture(tmpdir, "ttd", "ttd_targets.tsv", SAMPLE_TTD_TARGETS)
        _write_fixture(tmpdir, "ttd", "atc_classification.tsv", SAMPLE_ATC)

        try:
            from samyama import SamyamaClient
            from etl.helpers import Registry
            from etl.drugbank_dgidb_loader import load_drugbank_dgidb
            from etl.chembl_ttd_loader import load_chembl_ttd

            client = SamyamaClient.embedded()
            registry = Registry()

            # Phase 1: create Drug nodes (genes created from DGIdb interactions)
            load_drugbank_dgidb(client, tmpdir, registry)

            # Phase 3: load ChEMBL + TTD
            stats = load_chembl_ttd(client, tmpdir, registry)
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


class TestBioactivityNodes:
    def test_bioactivities_created(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, "MATCH (b:Bioactivity) RETURN count(*) AS c")
        assert rows[0]["c"] == 3

    def test_bioactivity_has_assay_id(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (b:Bioactivity {chembl_assay_id: 'CHEMBL614786'})
            RETURN b.pchembl_value, b.standard_type
        """)
        assert len(rows) == 1
        assert rows[0]["b.standard_type"] == "IC50"


class TestHasBioactivity:
    def test_aspirin_bioactivities(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[:HAS_BIOACTIVITY]->(b:Bioactivity)
            RETURN b.chembl_assay_id ORDER BY b.chembl_assay_id
        """)
        assert len(rows) == 2

    def test_metformin_bioactivities(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Metformin'})-[:HAS_BIOACTIVITY]->(b:Bioactivity)
            RETURN b.chembl_assay_id
        """)
        assert len(rows) == 1


class TestBioactivityTarget:
    def test_bioactivity_targets_gene(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (b:Bioactivity {chembl_assay_id: 'CHEMBL614786'})-[:BIOACTIVITY_TARGET]->(g:Gene)
            RETURN g.gene_name
        """)
        assert len(rows) == 1
        assert rows[0]["g.gene_name"] == "PTGS2"


class TestTargetNodes:
    def test_targets_created(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, "MATCH (t:Target) RETURN t.name ORDER BY t.name")
        names = [r["t.name"] for r in rows]
        assert "Cyclooxygenase-2" in names
        assert "AMP-activated protein kinase" in names

    def test_target_has_uniprot_id(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, "MATCH (t:Target {name: 'Cyclooxygenase-2'}) RETURN t.uniprot_id")
        assert rows[0]["t.uniprot_id"] == "P35354"


class TestTTDTargets:
    def test_aspirin_ttd_targets(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[r:TTD_TARGETS]->(t:Target)
            RETURN t.name, r.clinical_status
        """)
        assert len(rows) == 1
        assert rows[0]["t.name"] == "Cyclooxygenase-2"
        assert rows[0]["r.clinical_status"] == "Approved"


class TestDrugClassNodes:
    def test_drug_classes_created(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, "MATCH (dc:DrugClass) RETURN dc.name ORDER BY dc.name")
        names = [r["dc.name"] for r in rows]
        assert "Acetylsalicylic acid" in names
        assert "Biguanides" in names

    def test_drug_class_has_atc_code(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, "MATCH (dc:DrugClass {name: 'Biguanides'}) RETURN dc.atc_code")
        assert rows[0]["dc.atc_code"] == "A10BA"


class TestClassifiedAs:
    def test_aspirin_classified(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[:CLASSIFIED_AS]->(dc:DrugClass)
            RETURN dc.name
        """)
        assert len(rows) >= 1


class TestParentClass:
    def test_atc_hierarchy(self, phase3_data):
        client, _, _ = phase3_data
        rows = _q(client, """
            MATCH (child:DrugClass)-[:PARENT_CLASS]->(parent:DrugClass)
            RETURN child.name, parent.name
        """)
        assert len(rows) >= 1


class TestStats:
    def test_stats_returned(self, phase3_data):
        _, stats, _ = phase3_data
        assert stats["source"] == "chembl_ttd"
        assert stats["bioactivity_nodes"] == 3
        assert stats["target_nodes"] == 2
        assert stats["drug_class_nodes"] >= 4
