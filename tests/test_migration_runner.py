import unittest
import sqlite3
import os
import shutil
from pathlib import Path
from entigram.sqlite_ledger.migration_runner import MigrationRunner

class TestMigrationRunner(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/tmp_migrations")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_agent.db"
        self.migrations_dir = self.test_dir / "migrations"
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_migration_execution(self):
        # Create a sample migration
        mig1 = self.migrations_dir / "V2026.01.01.0001__init.sql"
        with open(mig1, "w") as f:
            f.write("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT);")
            
        runner = MigrationRunner(str(self.db_path), str(self.migrations_dir))
        executed = runner.run_migrations()
        
        self.assertEqual(len(executed), 1)
        self.assertEqual(executed[0], mig1.name)
        
        # Verify table exists
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        self.assertIsNotNone(cursor.fetchone())
        
        # Verify migration recorded
        cursor.execute("SELECT filename FROM migrations;")
        self.assertEqual(cursor.fetchone()[0], mig1.name)
        conn.close()

    def test_idempotency(self):
        mig1 = self.migrations_dir / "V2026.01.01.0001__init.sql"
        with open(mig1, "w") as f:
            f.write("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT);")
            
        runner = MigrationRunner(str(self.db_path), str(self.migrations_dir))
        runner.run_migrations()
        
        # Run again, should do nothing
        executed = runner.run_migrations()
        self.assertEqual(len(executed), 0)

if __name__ == "__main__":
    unittest.main()
