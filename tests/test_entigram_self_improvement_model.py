from pathlib import Path
import unittest

from entigram.governance.commissioner import Commissioner
from entigram.schema_compiler.parser import SchemaParser
from entigram.schema_compiler.compiler import SchemaCompiler
from entigram.ontology_compiler.compiler import OntologyCompiler


def _load_project_model():
    schema_text = Path("schema.lds").read_text()
    parser = SchemaParser(schema_text)
    entities, relationships = parser.parse()
    return schema_text, entities, relationships


class TestEntigramSelfImprovementModel(unittest.TestCase):
    def test_self_improvement_entities_are_modeled(self):
        _, entities, relationships = _load_project_model()

        expected_entities = {
            "Entigram_Expectation",
            "Entigram_Delivery_Evidence",
            "Entigram_Delivery_Evaluation",
            "Entigram_Improvement_Proposal",
            "Entigram_Lesson",
            "Entigram_Delivery_Snapshot",
            "Entigram_Artifact",
            "Entigram_Delivery_Drift",
        }
        self.assertTrue(expected_entities.issubset(entities.keys()))

        agent_attrs = {attr["name"] for attr in entities["Entigram_Agent"].attributes}
        self.assertTrue({
            "handoff_policy", "default_proof_policy", "proof_capabilities"
        }.issubset(agent_attrs))

        proposal_attrs = {attr["name"] for attr in entities["Entigram_Agent_Proposal"].attributes}
        self.assertTrue({"expected_benefit", "rollback_plan"}.issubset(proposal_attrs))

        snapshot_attrs = {attr["name"] for attr in entities["Entigram_Delivery_Snapshot"].attributes}
        self.assertTrue({"snapshot_id", "schema_hash", "warden_status", "artifact_ids"}.issubset(snapshot_attrs))

        artifact_attrs = {attr["name"] for attr in entities["Entigram_Artifact"].attributes}
        self.assertTrue({"path", "artifact_role", "sha256", "size_bytes"}.issubset(artifact_attrs))

        drift_attrs = {attr["name"] for attr in entities["Entigram_Delivery_Drift"].attributes}
        self.assertTrue({"snapshot_id", "artifact_path", "drift_status"}.issubset(drift_attrs))

        relationship_pairs = {(rel.entity_a, rel.entity_b) for rel in relationships}
        self.assertIn(("Entigram_Project", "Entigram_Expectation"), relationship_pairs)
        self.assertIn(("Entigram_Expectation", "Entigram_Delivery_Evidence"), relationship_pairs)
        self.assertIn(("Entigram_Expectation", "Entigram_Delivery_Evaluation"), relationship_pairs)
        self.assertIn(("Entigram_Expectation", "Entigram_Improvement_Proposal"), relationship_pairs)
        self.assertIn(("Entigram_Project", "Entigram_Lesson"), relationship_pairs)
        self.assertIn(("Entigram_Project", "Entigram_Delivery_Snapshot"), relationship_pairs)
        self.assertIn(("Entigram_Project", "Entigram_Artifact"), relationship_pairs)
        self.assertIn(("Entigram_Delivery_Snapshot", "Entigram_Artifact"), relationship_pairs)
        self.assertIn(("Entigram_Delivery_Snapshot", "Entigram_Delivery_Drift"), relationship_pairs)

    def test_self_improvement_model_compiles_to_sql_and_ttl(self):
        _, entities, relationships = _load_project_model()

        sql = SchemaCompiler(entities, relationships).compile()
        self.assertIn("CREATE TABLE IF NOT EXISTS entigram_expectations", sql)
        self.assertIn("entigram_expectation_id TEXT", sql)

        ttl = OntologyCompiler(entities, relationships).compile()
        self.assertIn("mk:Entigram_Expectation a owl:Class", ttl)
        self.assertIn("mk:Entigram_Delivery_Evidence a owl:Class", ttl)
        self.assertIn("mk:Entigram_Delivery_Snapshot a owl:Class", ttl)
        self.assertIn("mk:Entigram_Artifact a owl:Class", ttl)
        self.assertIn("mk:Entigram_Delivery_Drift a owl:Class", ttl)
        self.assertIn("mk:Entigram_Agent_proof_capabilities a owl:DatatypeProperty", ttl)
        self.assertIn("mk:Entigram_Artifact_sha256 a owl:DatatypeProperty", ttl)
        self.assertIn("mk:Entigram_Delivery_Drift_drift_status a owl:DatatypeProperty", ttl)
        self.assertIn("mk:Entigram_Expectation_developer_expectation a owl:DatatypeProperty", ttl)
        self.assertIn("mk:relates_Entigram_Expectation_to_Entigram_Delivery_Evidence", ttl)

    def test_self_improvement_expectations_are_commissioned(self):
        schema_text, _, _ = _load_project_model()

        checklist = Commissioner(schema_text).build_checklist(
            proofs=["python -m unittest tests.test_entigram_self_improvement_model passed"]
        )

        names = {item["name"] for item in checklist["items"]}
        self.assertIn("Entigram Self-Improvement Loop", names)
        self.assertIn("Agent Delivery Proof", names)
        self.assertTrue(checklist["valid"])


if __name__ == "__main__":
    unittest.main()
