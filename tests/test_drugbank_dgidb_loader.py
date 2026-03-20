"""Tests for DrugBank CC0 + DGIdb loader (Phase 1).

TDD: sample fixture data, embedded client, query helper.
"""

import os
import tempfile
import pytest

# --- Sample DrugBank vocabulary CSV ---
SAMPLE_DRUGBANK_VOCAB = """DrugBank ID,Accession Numbers,Common name,CAS,UNII,Synonyms,Standard InChI Key
DB00945,DB00945,Aspirin,50-78-2,R16CO5Y76E,"Acetylsalicylic acid",BSYNRYMUTXBXSQ-UHFFFAOYSA-N
DB00563,DB00563,Metformin,657-24-9,9100L32L2N,"Dimethylbiguanide",XZWYZXLIPXDOLR-UHFFFAOYSA-N
DB01050,DB01050,Ibuprofen,15687-27-1,WK2XYI10QM,"",HEFNNWSXXWATRW-JTQLQIEISA-N
"""

# --- Sample DGIdb interactions TSV ---
SAMPLE_DGIDB_INTERACTIONS = """gene_name\tgene_claim_name\tentrez_id\tinteraction_claim_source\tinteraction_types\tdrug_claim_name\tdrug_claim_primary_name\tdrug_name\tdrug_chembl_id\tPMIDs
PTGS2\tCOX-2\t5743\tDrugBank\tinhibitor\tAspirin\tAspirin\tASPIRIN\tCHEMBL25\t12345
AMPK\tAMPK\t5562\tDrugBank\tactivator\tMetformin\tMetformin\tMETFORMIN\tCHEMBL1431\t67890
PTGS1\tCOX-1\t5742\tDrugBank\tinhibitor\tAspirin\tAspirin\tASPIRIN\tCHEMBL25\t12345
PTGS2\tCOX-2\t5743\tDrugBank\tinhibitor\tIbuprofen\tIbuprofen\tIBUPROFEN\tCHEMBL521\t11111
"""

# --- Sample DGIdb genes TSV ---
SAMPLE_DGIDB_GENES = """gene_claim_name\tgene_name\tentrez_id\tgene_categories
COX-2\tPTGS2\t5743\tDRUG RESISTANCE;CLINICALLY ACTIONABLE
AMPK\tAMPK\t5562\tKINASE
COX-1\tPTGS1\t5742\tDRUG RESISTANCE
"""

# --- Sample DGIdb drugs TSV ---
SAMPLE_DGIDB_DRUGS = """drug_claim_name\tdrug_name\tchembl_id\tdrug_claim_source
Aspirin\tASPIRIN\tCHEMBL25\tDrugBank
Metformin\tMETFORMIN\tCHEMBL1431\tDrugBank
Ibuprofen\tIBUPROFEN\tCHEMBL521\tDrugBank
"""


def _write_fixture(tmpdir, subdir, filename, content):
    """Write fixture data to a temp file."""
    d = os.path.join(tmpdir, subdir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


@pytest.fixture(scope="module")
def phase1_data():
    """Create fixture data files and load Phase 1 into embedded graph."""
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_fixture(tmpdir, "drugbank", "drugbank_vocabulary.csv", SAMPLE_DRUGBANK_VOCAB)
        _write_fixture(tmpdir, "dgidb", "interactions.tsv", SAMPLE_DGIDB_INTERACTIONS)
        _write_fixture(tmpdir, "dgidb", "genes.tsv", SAMPLE_DGIDB_GENES)
        _write_fixture(tmpdir, "dgidb", "drugs.tsv", SAMPLE_DGIDB_DRUGS)

        try:
            from samyama import SamyamaClient
            from etl.helpers import Registry
            from etl.drugbank_dgidb_loader import load_drugbank_dgidb

            client = SamyamaClient.embedded()
            registry = Registry()
            stats = load_drugbank_dgidb(client, tmpdir, registry)
            yield client, stats, registry
        except ImportError:
            pytest.skip("samyama package not available")


def _q(client, cypher):
    """Query helper — returns list of dicts."""
    try:
        r = client.query_readonly(cypher, "default")
        return [dict(zip(r.columns, row)) for row in r.records]
    except Exception:
        r = client.query(cypher, "default")
        return [dict(zip(r.columns, row)) for row in r.records]


class TestDrugNodes:
    def test_drugs_created(self, phase1_data):
        client, stats, _ = phase1_data
        rows = _q(client, "MATCH (d:Drug) RETURN d.name ORDER BY d.name")
        names = [r["d.name"] for r in rows]
        assert "Aspirin" in names
        assert "Metformin" in names
        assert "Ibuprofen" in names

    def test_drug_count(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (d:Drug) RETURN count(*) AS c")
        assert rows[0]["c"] == 3

    def test_drug_has_drugbank_id(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (d:Drug {name: 'Aspirin'}) RETURN d.drugbank_id")
        assert rows[0]["d.drugbank_id"] == "DB00945"

    def test_drug_has_cas(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (d:Drug {name: 'Aspirin'}) RETURN d.cas_number")
        assert rows[0]["d.cas_number"] == "50-78-2"

    def test_drug_has_chembl_id(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (d:Drug {name: 'Aspirin'}) RETURN d.chembl_id")
        assert rows[0]["d.chembl_id"] == "CHEMBL25"


class TestGeneNodes:
    def test_genes_created(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (g:Gene) RETURN g.gene_name ORDER BY g.gene_name")
        names = [r["g.gene_name"] for r in rows]
        assert "PTGS2" in names
        assert "AMPK" in names
        assert "PTGS1" in names

    def test_gene_count(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (g:Gene) RETURN count(*) AS c")
        assert rows[0]["c"] == 3

    def test_gene_has_entrez_id(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, "MATCH (g:Gene {gene_name: 'PTGS2'}) RETURN g.entrez_id")
        assert rows[0]["g.entrez_id"] == "5743"


class TestInteractsWithGene:
    def test_aspirin_targets(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[:INTERACTS_WITH_GENE]->(g:Gene)
            RETURN g.gene_name ORDER BY g.gene_name
        """)
        names = [r["g.gene_name"] for r in rows]
        assert "PTGS2" in names
        assert "PTGS1" in names

    def test_metformin_targets(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Metformin'})-[:INTERACTS_WITH_GENE]->(g:Gene)
            RETURN g.gene_name
        """)
        assert len(rows) == 1
        assert rows[0]["g.gene_name"] == "AMPK"

    def test_interaction_has_type(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, """
            MATCH (d:Drug {name: 'Aspirin'})-[i:INTERACTS_WITH_GENE]->(g:Gene {gene_name: 'PTGS2'})
            RETURN i.interaction_type
        """)
        assert rows[0]["i.interaction_type"] == "inhibitor"

    def test_shared_target_ptgs2(self, phase1_data):
        client, _, _ = phase1_data
        rows = _q(client, """
            MATCH (d1:Drug)-[:INTERACTS_WITH_GENE]->(g:Gene {gene_name: 'PTGS2'})
                  <-[:INTERACTS_WITH_GENE]-(d2:Drug)
            WHERE d1.name < d2.name
            RETURN d1.name, d2.name
        """)
        assert len(rows) >= 1


class TestRegistryState:
    def test_drugs_tracked(self, phase1_data):
        _, _, registry = phase1_data
        assert "DB00945" in registry.drugs
        assert "DB00563" in registry.drugs

    def test_genes_tracked(self, phase1_data):
        _, _, registry = phase1_data
        assert "PTGS2" in registry.genes
        assert "AMPK" in registry.genes

    def test_edges_tracked(self, phase1_data):
        _, _, registry = phase1_data
        assert ("DB00945", "PTGS2") in registry.interacts_with_gene


class TestStats:
    def test_stats_returned(self, phase1_data):
        _, stats, _ = phase1_data
        assert stats["source"] == "drugbank_dgidb"
        assert stats["drug_nodes"] == 3
        assert stats["gene_nodes"] == 3
        assert stats["interaction_edges"] >= 4
