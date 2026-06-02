import unittest
import sqlite3
import shutil
from pathlib import Path
from entigram.warehouse_auditor import WarehouseAuditor

class TestWarehouseAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace_warehouse")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        self.states_dir = self.test_dir / ".etg" / "states"
        self.states_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.states_dir / "SupplyChain.db"
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("CREATE TABLE warehouses (id TEXT PRIMARY KEY, location_name TEXT, capacity INTEGER)")
            conn.execute("CREATE TABLE inventory_items (id TEXT PRIMARY KEY, warehouse_id TEXT, quantity INTEGER)")
            
            # Warehouse 1: Capacity 100, Total 120 (VIOLATION)
            conn.execute("INSERT INTO warehouses VALUES ('wh-1', 'Main Hub', 100)")
            conn.execute("INSERT INTO inventory_items VALUES ('inv-1', 'wh-1', 50)")
            conn.execute("INSERT INTO inventory_items VALUES ('inv-2', 'wh-1', 70)")
            
            # Warehouse 2: Capacity 200, Total 150 (OK)
            conn.execute("INSERT INTO warehouses VALUES ('wh-2', 'East Wing', 200)")
            conn.execute("INSERT INTO inventory_items VALUES ('inv-3', 'wh-2', 150)")
        conn.close()
        
        self.auditor = WarehouseAuditor(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_validate_capacity(self):
        violations = self.auditor.validate_capacity()
        self.assertEqual(len(violations), 1)
        
        violation = violations[0]
        self.assertEqual(violation["warehouse_id"], "wh-1")
        self.assertEqual(violation["total_quantity"], "120")
        self.assertEqual(violation["capacity"], "100")

if __name__ == "__main__":
    unittest.main()
