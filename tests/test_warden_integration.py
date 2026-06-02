import unittest
import os
import shutil
import json
import sqlite3
from pathlib import Path
from entigram.broker import EntigramBroker
from entigram.injector import inject_entigram_manifest

class TestWardenIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_warden_integration_workspace")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()

        # Initialize workspace
        inject_entigram_manifest(str(self.test_dir), ["Entigram Schemas"], "Antigravity")
        
        # Create a schema.lds
        self.schema_content = """
        ENTITY Supplier {
            id UUID PK
            name String
        }
        """
        (self.test_dir / "schema.lds").write_text(self.schema_content)
        
        self.broker = EntigramBroker(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_broker_rejects_invalid_payload(self):
        # 1. Lock the laws
        self.broker.warden.lock_fingerprint()
        
        # 2. Propose a resolution with an invalid attribute 'rating' (not in Schema)
        invalid_state = json.dumps({"name": "Global Fasteners", "rating": 5})
        success = self.broker.propose_resolution("CONFLICT-1", "Supplier", invalid_state, "Hallucinated rating")
        
        self.assertFalse(success, "Broker should have rejected payload with unknown attribute 'rating'")

    def test_broker_rejects_on_integrity_violation(self):
        # 1. Lock the laws
        self.broker.warden.lock_fingerprint()
        
        # 2. Tamper with the laws (change Schema)
        (self.test_dir / "schema.lds").write_text(self.schema_content + "\nENTITY Tampered { id UUID PK }")
        
        # 3. Propose a valid resolution (should fail due to integrity violation)
        valid_state = json.dumps({"name": "Global Fasteners"})
        success = self.broker.propose_resolution("CONFLICT-1", "Supplier", valid_state, "Valid but tainted")
        
        self.assertFalse(success, "Broker should have rejected proposal due to integrity violation (TAINTED)")

    def test_broker_allows_valid_payload_when_protected(self):
        # 1. Lock the laws
        self.broker.warden.lock_fingerprint()
        
        # 2. Propose a valid resolution
        valid_state = json.dumps({"name": "Global Fasteners"})
        success = self.broker.propose_resolution("CONFLICT-1", "Supplier", valid_state, "Valid and protected")
        
        self.assertTrue(success, "Broker should have allowed valid payload when protected")

if __name__ == "__main__":
    unittest.main()
