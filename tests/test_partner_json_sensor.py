import unittest
import json
import shutil
import sqlite3
from pathlib import Path
from entigram.sensing.partner_sensor import PartnerJSONSensor

class TestPartnerJSONSensor(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_json_sensor")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        
        self.json_data = [
            {"id": "V1", "name": "Vendor 1", "score": 0.95},
            {"id": "V2", "name": "Vendor 2", "score": 0.88}
        ]
        self.json_path = self.test_dir / "data.json"
        with open(self.json_path, "w") as f:
            json.dump(self.json_data, f)
            
        self.sensor = PartnerJSONSensor(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_ingest_json(self):
        success = self.sensor.ingest_json(str(self.json_path), "TestDomain", "vendors")
        self.assertTrue(success)
        
        db_path = self.test_dir / ".etg" / "states" / "TestDomain.db"
        self.assertTrue(db_path.exists())
        
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT * FROM vendors")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "V1")
        self.assertEqual(rows[0][1], "Vendor 1")
        conn.close()

if __name__ == "__main__":
    unittest.main()
