import unittest
import os
import yaml
from pathlib import Path
from entigram.schema_compiler.parser import SchemaParser

class TestPhase2Integrity(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path(__file__).parent.parent
        self.etg_yaml_path = self.workspace_root / ".etg" / "entigram.yaml"
        with open(self.etg_yaml_path, 'r') as f:
            self.manifest = yaml.safe_load(f)
        self.packages = self.manifest.get('packages', [])

    def _get_pkg_path(self, pkg_name):
        # Check user packages first
        user_pkg_path = self.workspace_root / ".etg" / "packages" / pkg_name
        if user_pkg_path.exists():
            return user_pkg_path
        # Fallback to default packages
        return self.workspace_root / "packages" / pkg_name

    def test_package_directories_exist(self):
        """Verifies that every package listed in the manifest exists."""
        for pkg_name in self.packages:
            if pkg_name == "Entigram Schemas": continue # Root package
            
            # Allow simulated packages added during testing
            if pkg_name in ["SentinelTestCustom", "MyCustomPackage", ".keep"]: continue

            pkg_path = self._get_pkg_path(pkg_name)
            self.assertTrue(pkg_path.exists(), f"Package directory missing: {pkg_path}")

    def test_package_schema_files_exist(self):
        """Verifies that every package has a schema.lds file."""
        for pkg_name in self.packages:
            if pkg_name == "Entigram Schemas": continue
            if pkg_name in ["SentinelTestCustom", "MyCustomPackage", ".keep"]: continue

            schema_path = self._get_pkg_path(pkg_name) / "schema.lds"
            self.assertTrue(schema_path.exists(), f"Missing schema.lds in {pkg_name}")

    def test_package_schema_validity(self):
        """Attempts to parse the Schema for every package to ensure it is syntactically correct."""
        for pkg_name in self.packages:
            if pkg_name == "Entigram Schemas": continue
            if pkg_name in ["SentinelTestCustom", "MyCustomPackage", ".keep"]: continue

            schema_path = self._get_pkg_path(pkg_name) / "schema.lds"
            content = schema_path.read_text()
            parser = SchemaParser(content)
            try:
                entities, relationships = parser.parse()
                self.assertGreater(len(entities), 0, f"No entities found in {pkg_name} Schema")
            except Exception as e:
                self.fail(f"Schema parsing failed for {pkg_name}: {e}")

    def test_package_skills_exist(self):
        """Verifies that every package has a SKILL.md file."""
        for pkg_name in self.packages:
            if pkg_name == "Entigram Schemas": continue
            if pkg_name in ["SentinelTestCustom", "MyCustomPackage", ".keep"]: continue

            skill_path = self._get_pkg_path(pkg_name) / "SKILL.md"
            self.assertTrue(skill_path.exists(), f"Missing SKILL.md in {pkg_name}")

    def test_package_ontologies_exist(self):
        """Verifies that every package has a schema.ttl file."""
        for pkg_name in self.packages:
            if pkg_name == "Entigram Schemas": continue
            if pkg_name in ["SentinelTestCustom", "MyCustomPackage", ".keep"]: continue
            
            ontology_path = self._get_pkg_path(pkg_name) / "schema.ttl"
            self.assertTrue(ontology_path.exists(), f"Missing schema.ttl in {pkg_name}")

if __name__ == "__main__":
    unittest.main()
