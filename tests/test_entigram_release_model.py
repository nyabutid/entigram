from pathlib import Path
import unittest

from entigram.governance.commissioner import Commissioner
from entigram.ontology_compiler.compiler import OntologyCompiler
from entigram.schema_compiler.compiler import SchemaCompiler
from entigram.schema_compiler.parser import SchemaParser


def _load_project_model():
    schema_text = Path("schema.lds").read_text()
    parser = SchemaParser(schema_text)
    entities, relationships = parser.parse()
    return schema_text, entities, relationships


class TestEntigramReleaseModel(unittest.TestCase):
    def test_release_process_entities_are_modeled(self):
        _, entities, relationships = _load_project_model()

        expected_entities = {
            "Entigram_Release",
            "Entigram_Release_Channel",
            "Entigram_Release_Check",
        }
        self.assertTrue(expected_entities.issubset(entities.keys()))

        release_attrs = {attr["name"] for attr in entities["Entigram_Release"].attributes}
        self.assertTrue({
            "version",
            "source_tag",
            "pypi_artifact",
            "pypi_sha256",
            "homebrew_formula_ref",
            "homebrew_sha256",
            "standard_packages_ref",
            "website_ref",
            "release_status",
        }.issubset(release_attrs))

        channel_attrs = {attr["name"] for attr in entities["Entigram_Release_Channel"].attributes}
        self.assertTrue({
            "name",
            "artifact_ref",
            "checksum",
            "verification_command",
            "required",
            "status",
            "rationale",
        }.issubset(channel_attrs))

        check_attrs = {attr["name"] for attr in entities["Entigram_Release_Check"].attributes}
        self.assertTrue({"command", "expected_result", "evidence_ref", "passed"}.issubset(check_attrs))

        relationship_pairs = {(rel.entity_a, rel.entity_b) for rel in relationships}
        self.assertIn(("Entigram_Project", "Entigram_Release"), relationship_pairs)
        self.assertIn(("Entigram_Release", "Entigram_Release_Channel"), relationship_pairs)
        self.assertIn(("Entigram_Release", "Entigram_Release_Check"), relationship_pairs)
        self.assertIn(("Entigram_Release_Check", "Entigram_Delivery_Evidence"), relationship_pairs)

    def test_release_model_compiles_to_sql_and_ttl(self):
        _, entities, relationships = _load_project_model()

        sql = SchemaCompiler(entities, relationships).compile()
        self.assertIn("CREATE TABLE IF NOT EXISTS entigram_releases", sql)
        self.assertIn("pypi_sha256 TEXT", sql)
        self.assertIn("homebrew_sha256 TEXT", sql)

        ttl = OntologyCompiler(entities, relationships).compile()
        self.assertIn("mk:Entigram_Release a owl:Class", ttl)
        self.assertIn("mk:Entigram_Release_Channel a owl:Class", ttl)
        self.assertIn("mk:Entigram_Release_Check a owl:Class", ttl)
        self.assertIn("mk:Entigram_Release_pypi_sha256 a owl:DatatypeProperty", ttl)
        self.assertIn("mk:Entigram_Release_homebrew_sha256 a owl:DatatypeProperty", ttl)
        self.assertIn("mk:relates_Entigram_Release_to_Entigram_Release_Channel", ttl)

    def test_release_orchestration_expectation_is_commissioned(self):
        schema_text, _, _ = _load_project_model()

        checklist = Commissioner(schema_text).build_checklist(
            proofs=["python -m unittest tests.test_entigram_release_model passed"]
        )

        names = {item["name"] for item in checklist["items"]}
        self.assertIn("Release Orchestration", names)
        release_item = next(item for item in checklist["items"] if item["name"] == "Release Orchestration")
        self.assertEqual(release_item["status"], "passed")


if __name__ == "__main__":
    unittest.main()
