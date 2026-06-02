import unittest
import sqlite3
import os
import shutil
from pathlib import Path
from entigram.schema_compiler.discoverer import DomainDiscoverer

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

if __name__ == "__main__":
    unittest.main()
