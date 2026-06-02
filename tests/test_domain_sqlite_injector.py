import unittest
import os
import shutil
import sqlite3
from pathlib import Path
from entigram.sqlite_ledger.injector import DomainSQLiteInjector

class TestDomainSQLiteInjector(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/tmp_injector")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.etg_dir = self.test_dir / ".etg"
        self.etg_dir.mkdir(parents=True, exist_ok=True)
        self.states_dir = self.etg_dir / "states"
        self.packages_dir = self.test_dir / "packages"
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup Manifest
        self.manifest_path = self.etg_dir / "entigram.yaml"
        with open(self.manifest_path, "w") as f:
            f.write("packages: [TestDomain]\n")
            
        # Setup TestDomain Package with a Schema
        self.test_pkg_dir = self.packages_dir / "TestDomain"
        self.test_pkg_dir.mkdir(parents=True, exist_ok=True)
        self.schema_path = self.test_pkg_dir / "schema.lds"
        with open(self.schema_path, "w") as f:
            f.write("ENTITY TestDomain {\n  id UUID PK\n  name String\n}\n")
            
        self.injector = DomainSQLiteInjector(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_inject_domain(self):
        # Run injection
        success = self.injector.inject_domain("TestDomain")
        self.assertTrue(success)
        
        # Verify DB creation
        db_path = self.states_dir / "TestDomain.db"
        self.assertTrue(db_path.exists())
        
        # Verify schema
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='testdomains';")
            table = cursor.fetchone()
            self.assertIsNotNone(table)
            self.assertEqual(table[0], "testdomains")
        finally:
            conn.close()

    def test_inject_all_active(self):
        successful = self.injector.inject_all_active()
        self.assertIn("TestDomain", successful)
        self.assertTrue((self.states_dir / "TestDomain.db").exists())

if __name__ == "__main__":
    unittest.main()
