import unittest
import sqlite3
import os
import shutil
from pathlib import Path
from entigram.product_cataloger import ProductCataloger

class TestProductCataloger(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace_cataloger")
        self.test_dir.mkdir(exist_ok=True)
        self.states_dir = self.test_dir / ".etg" / "states"
        self.states_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.states_dir / "SupplyChain.db"
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("CREATE TABLE suppliers (id TEXT PRIMARY KEY, name TEXT, tax_id TEXT, rating REAL)")
            conn.execute("CREATE TABLE products (id TEXT PRIMARY KEY, sku TEXT, name TEXT, category TEXT, supplier_id TEXT)")
            
            # Valid supplier
            conn.execute("INSERT INTO suppliers VALUES ('sup-1', 'Valid Corp', 'EIN-1234', 4.5)")
            
            # Valid product
            conn.execute("INSERT INTO products VALUES ('prod-1', 'SKU-001', 'Widget A', 'Tools', 'sup-1')")
            # Missing SKU
            conn.execute("INSERT INTO products VALUES ('prod-2', '', 'Widget B', 'Tools', 'sup-1')")
            # Invalid supplier
            conn.execute("INSERT INTO products VALUES ('prod-3', 'SKU-003', 'Widget C', 'Tools', 'sup-invalid')")
            # Null supplier
            conn.execute("INSERT INTO products VALUES ('prod-4', 'SKU-004', 'Widget D', 'Tools', NULL)")
            # Duplicate SKU (same as prod-1)
            conn.execute("INSERT INTO products VALUES ('prod-5', 'SKU-001', 'Widget E', 'Tools', 'sup-1')")
        conn.close()
        
        self.cataloger = ProductCataloger(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_validate_catalog(self):
        violations = self.cataloger.validate_catalog()
        self.assertEqual(len(violations), 4)
        
        violation_prod_2 = next((v for v in violations if v["product_id"] == "prod-2"), None)
        self.assertIsNotNone(violation_prod_2)
        self.assertEqual(violation_prod_2["error"], "Missing SKU")
        
        violation_prod_3 = next((v for v in violations if v["product_id"] == "prod-3"), None)
        self.assertIsNotNone(violation_prod_3)
        self.assertEqual(violation_prod_3["error"], "Invalid or missing supplier association: sup-invalid")
        
        violation_prod_4 = next((v for v in violations if v["product_id"] == "prod-4"), None)
        self.assertIsNotNone(violation_prod_4)
        self.assertEqual(violation_prod_4["error"], "Invalid or missing supplier association: None")

        violation_prod_5 = next((v for v in violations if v["product_id"] == "prod-5"), None)
        self.assertIsNotNone(violation_prod_5)
        self.assertEqual(violation_prod_5["error"], "Duplicate SKU: SKU-001 (already used by prod-1)")

if __name__ == "__main__":
    unittest.main()