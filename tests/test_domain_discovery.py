import unittest
import sqlite3
import json
import os
import shutil
from pathlib import Path
from entigram.schema_compiler.discoverer import (
    DomainDiscoverer,
    available_discovery_adapters,
    discover_source,
    load_discovery_adapter_module,
)

class TestDomainDiscoverer(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/tmp_discovery")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "legacy.db"
        
        # Create a sample database with relationships
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT);")
            conn.execute("CREATE TABLE posts (id TEXT PRIMARY KEY, title TEXT, user_id TEXT, FOREIGN KEY(user_id) REFERENCES users(id));")
        conn.close()

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_discovery(self):
        discoverer = DomainDiscoverer(str(self.db_path))
        schema = discoverer.discover_schema()
        
        # Verify Entities
        self.assertIn("ENTITY: User", schema)
        self.assertIn("ENTITY: Post", schema)
        
        # Verify Attributes (including PK dot notation)
        self.assertIn(". id (TEXT)", schema)
        self.assertIn("- username (TEXT)", schema)
        
        # Verify Relationships
        self.assertIn("RELATIONSHIPS:", schema)
        self.assertIn("User (1) [MUST] --- [MAY] (MANY) Post", schema)

    def test_csv_adapter_discovers_draft_schema_with_inferred_types(self):
        csv_path = self.test_dir / "partner_orders.csv"
        csv_path.write_text(
            "id,total,active,created_at,customer_name\n"
            "ord-1,12.50,true,2026-07-01,Alice\n"
            "ord-2,19.75,false,2026-07-02,Bob\n"
        )

        result = discover_source(str(csv_path), source="csv", domain_name="PartnerOrder")
        schema = result.to_schema(include_metadata_comment=True)

        self.assertEqual(result.adapter, "csv")
        self.assertIn("Status: discovery output is a draft", schema)
        self.assertIn("ENTITY: PartnerOrder", schema)
        self.assertIn(". id (String)", schema)
        self.assertIn("- total (Decimal, MUST)", schema)
        self.assertIn("- active (Boolean, MUST)", schema)
        self.assertIn("- created_at (DateTime, MUST)", schema)
        self.assertFalse(result.metadata["trusted"])

    def test_json_adapter_discovers_union_of_object_keys(self):
        json_path = self.test_dir / "accounts.json"
        json_path.write_text(json.dumps([
            {"id": "acct-1", "owner": "Alice", "limit": 100},
            {"id": "acct-2", "owner": "Bob", "risk_score": 0.42},
        ]))

        result = discover_source(str(json_path), source="json")
        schema = result.to_schema()

        self.assertEqual(result.adapter, "json")
        self.assertIn("ENTITY: Account", schema)
        self.assertIn(". id (String)", schema)
        self.assertIn("- owner (String, MUST)", schema)
        self.assertIn("- limit (Integer)", schema)
        self.assertIn("- risk_score (Decimal)", schema)

    def test_sqlite_discovery_reports_model_review_findings(self):
        review_db = self.test_dir / "review.db"
        conn = sqlite3.connect(review_db)
        with conn:
            conn.execute("CREATE TABLE customers (name TEXT, email TEXT);")
            conn.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, customer_id TEXT, phone1 TEXT, phone2 TEXT);")
        conn.close()

        result = discover_source(str(review_db), source="sqlite")
        codes = {finding.code for finding in result.findings}

        self.assertIn("NO_PRIMARY_KEY", codes)
        self.assertIn("NO_FOREIGN_KEYS_IN_MULTI_ENTITY_SOURCE", codes)
        self.assertIn("FK_LIKE_COLUMN_WITHOUT_CONSTRAINT", codes)
        self.assertIn("REPEATING_COLUMN_GROUP", codes)
        self.assertEqual(result.metadata["finding_count"], len(result.findings))

        customer_finding = next(finding for finding in result.findings if finding.code == "NO_PRIMARY_KEY")
        self.assertEqual(customer_finding.entity, "Customer")
        self.assertEqual(customer_finding.severity, "warning")

    def test_discovery_report_serializes_findings(self):
        csv_path = self.test_dir / "partial.csv"
        csv_path.write_text("id,description\n,")

        result = discover_source(str(csv_path), source="csv", domain_name="Partial")
        report = result.to_dict()
        codes = {finding["code"] for finding in report["findings"]}

        self.assertIn("LOW_CONFIDENCE_ATTRIBUTE_INFERENCE", codes)
        self.assertIn("finding_count", report["metadata"])

    def test_csv_discovery_flags_low_cardinality_strings(self):
        csv_path = self.test_dir / "tickets.csv"
        csv_path.write_text(
            "id,status\n"
            "1,open\n"
            "2,closed\n"
            "3,open\n"
            "4,pending\n"
            "5,open\n"
        )

        result = discover_source(str(csv_path), source="csv", domain_name="Ticket")
        findings = [finding for finding in result.findings if finding.code == "LOW_CARDINALITY_STRING"]

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].attribute, "status")
        self.assertEqual(findings[0].severity, "info")

    def test_adapter_registry_exposes_standard_sources(self):
        self.assertEqual(available_discovery_adapters(), ["csv", "json", "sqlite"])

    def test_dynamic_adapter_module_can_register_package_adapter(self):
        adapter_path = self.test_dir / "source_adapter.py"
        adapter_path.write_text("""
from entigram.schema_compiler.discoverer import DiscoveryEntity, DiscoveryResult, SourceDiscoveryAdapter

class MockPackageAdapter(SourceDiscoveryAdapter):
    name = "mock-package"

    def __init__(self, endpoint, domain_name=None):
        self.endpoint = endpoint
        self.domain_name = domain_name

    def discover(self):
        return DiscoveryResult(
            adapter=self.name,
            source_ref=self.endpoint,
            entities=[DiscoveryEntity(name=self.domain_name or "MockEntity")],
            metadata={"trusted": False},
        )

def register(registry):
    registry(MockPackageAdapter.name, MockPackageAdapter)
""")

        registered = load_discovery_adapter_module(str(adapter_path))
        result = discover_source("mock://endpoint", source="mock-package", domain_name="LoadedEntity")

        self.assertEqual(registered, ["mock-package"])
        self.assertEqual(result.entities[0].name, "LoadedEntity")

if __name__ == "__main__":
    unittest.main()
