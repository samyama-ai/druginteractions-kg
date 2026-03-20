// Drug Interactions & Pharmacogenomics Knowledge Graph — Schema
//
// 9 Node Labels, 9 Edge Types (Interaction modeled as edge properties)
// Sources: DrugBank CC0, DGIdb, SIDER, ChEMBL, TTD, OpenFDA FAERS

// --- Indexes ---
CREATE INDEX ON :Drug(drugbank_id);
CREATE INDEX ON :Drug(name);
CREATE INDEX ON :Gene(gene_name);
CREATE INDEX ON :SideEffect(meddra_id);
CREATE INDEX ON :Indication(meddra_id);
CREATE INDEX ON :Bioactivity(chembl_assay_id);
CREATE INDEX ON :Target(ttd_target_id);
CREATE INDEX ON :DrugClass(atc_code);
CREATE INDEX ON :AdverseEvent(term);

// --- Node Labels ---
// Drug:         drugbank_id, name, cas_number, chembl_id
// Gene:         gene_name, entrez_id, gene_claim_name
// SideEffect:   meddra_id, name, frequency
// Indication:   meddra_id, name
// Bioactivity:  chembl_assay_id, assay_type, pchembl_value, standard_type, standard_value, standard_units
// Target:       ttd_target_id, name, uniprot_id, target_type
// DrugClass:    atc_code, name, level
// AdverseEvent: term, count, serious_count

// --- Edge Types ---
// INTERACTS_WITH_GENE: Drug -> Gene  (interaction_type, score, source)
// HAS_SIDE_EFFECT:     Drug -> SideEffect  (frequency, frequency_lower, frequency_upper)
// HAS_INDICATION:      Drug -> Indication  (method)
// HAS_BIOACTIVITY:     Drug -> Bioactivity
// BIOACTIVITY_TARGET:  Bioactivity -> Gene
// TTD_TARGETS:         Drug -> Target  (clinical_status)
// HAS_ADVERSE_EVENT:   Drug -> AdverseEvent  (count)
// CLASSIFIED_AS:       Drug -> DrugClass
// PARENT_CLASS:        DrugClass -> DrugClass

// --- Cross-KG Bridge Properties ---
// Drug.drugbank_id   -> Clinical Trials KG Drug.drugbank_id
// Drug.name          -> Clinical Trials KG Intervention.name
// Gene.gene_name     -> Pathways KG Protein.gene_name / Protein.name
// Target.uniprot_id  -> Pathways KG Protein.uniprot_id
