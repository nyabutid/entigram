import unittest
import sqlite3
import os
import shutil
from pathlib import Path
from entigram.supplier_auditor import SupplierAuditor

class TestSupplierAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace_auditor")
        self.test_dir.mkdir(exist_ok=True)
        self.states_dir = self.test_dir / ".etg" / "states"
        self.states_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.states_dir / "SupplyChain.db"
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("CREATE TABLE suppliers (id TEXT PRIMARY KEY, name TEXT, tax_id TEXT, rating REAL)")
            # Valid supplier
            conn.execute("INSERT INTO suppliers VALUES ('sup-1', 'Valid Corp', 'EIN-1234', 4.5)")
            # Missing tax_id
            conn.execute("INSERT INTO suppliers VALUES ('sup-2', 'Missing Corp', '', 3.2)")
            # Invalid format tax_id
            conn.execute("INSERT INTO suppliers VALUES ('sup-3', 'Invalid Corp', '12345678', 4.0)")
            # Valid VAT
            conn.execute("INSERT INTO suppliers VALUES ('sup-4', 'Euro Corp', 'VAT-DE123', 4.8)")
        conn.close()
        
        self.auditor = SupplierAuditor(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_validate_credentials(self):
        violations = self.auditor.validate_credentials()
        self.assertEqual(len(violations), 2)
        
        # Check specific violations
        violation_sup_2 = next((v for v in violations if v["supplier_id"] == "sup-2"), None)
        self.assertIsNotNone(violation_sup_2)
        self.assertEqual(violation_sup_2["error"], "Missing tax_id")
        
        violation_sup_3 = next((v for v in violations if v["supplier_id"] == "sup-3"), None)
        self.assertIsNotNone(violation_sup_3)
        self.assertEqual(violation_sup_3["error"], "Invalid tax_id format: 12345678")

if __name__ == "__main__":
    unittest.main()
