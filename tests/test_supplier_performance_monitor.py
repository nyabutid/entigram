import unittest
import sqlite3
import shutil
from pathlib import Path
from entigram.supplier_performance_monitor import SupplierPerformanceMonitor

class TestSupplierPerformanceMonitor(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace_performance")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        self.states_dir = self.test_dir / ".etg" / "states"
        self.states_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.states_dir / "SupplyChain.db"
        conn = sqlite3.connect(self.db_path)
        with conn:
            conn.execute("CREATE TABLE suppliers (id TEXT PRIMARY KEY, name TEXT, rating REAL)")
            
            # Supplier 1: Rating 2.5 (UNDERPERFORMING)
            conn.execute("INSERT INTO suppliers VALUES ('sup-1', 'Low Qual Co', 2.5)")
            
            # Supplier 2: Rating 4.5 (OK)
            conn.execute("INSERT INTO suppliers VALUES ('sup-2', 'High Qual Co', 4.5)")
        conn.close()
        
        self.monitor = SupplierPerformanceMonitor(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_check_performance(self):
        warnings = self.monitor.check_performance(threshold=3.0)
        self.assertEqual(len(warnings), 1)
        
        warning = warnings[0]
        self.assertEqual(warning["supplier_id"], "sup-1")
        self.assertEqual(warning["rating"], "2.5")

if __name__ == "__main__":
    unittest.main()
