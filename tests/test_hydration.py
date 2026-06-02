import unittest
import os
import shutil
import tempfile
import json
import yaml
from pathlib import Path
from entigram.injector import inject_entigram_manifest
from entigram.sqlite_ledger.manager import LedgerManager
from entigram.cli_runner.etg_cli import main
from unittest.mock import patch
import sys

class TestHydration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Initialize an Entigram workspace
        inject_entigram_manifest(self.test_dir, ["Banking"], "Codex")
        
        # Add some data to the ledger
        self.ledger_path = Path(self.test_dir) / ".etg" / "entigram_state.db"
        manager = LedgerManager(str(self.ledger_path))
        conn = manager._get_connection()
        conn.execute("INSERT INTO semantic_alignments (source_domain, target_domain, source_concept, target_concept, status) VALUES (?, ?, ?, ?, ?)",
                     ("DomainA", "DomainB", "User", "Account", "approved"))
        conn.execute("INSERT INTO human_resolutions (conflict_id, entity_type, resolved_state, rationale) VALUES (?, ?, ?, ?)",
                     ("C1", "Supplier", "active", "verified"))
        conn.commit()
        conn.close()
        
        # Add a Schema
        with open(Path(self.test_dir) / "schema.lds", "w") as f:
            f.write("ENTITY: User\n  - name (String)")

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)

    def test_hydrate_command(self):
        """Verifies that the hydrate command produces a valid hydration sequence."""
        test_args = ["entigram", "hydrate"]
        with patch.object(sys, 'argv', test_args):
            with patch('sys.stdout', new_callable=lambda: open(os.devnull, 'w')) as devnull:
                # We want to capture stdout for real here to verify the content
                from io import StringIO
                captured_output = StringIO()
                with patch('sys.stdout', captured_output):
                    try:
                        main()
                    except SystemExit:
                        pass
                
                output = captured_output.getvalue()
                self.assertIn("--- ENTIGRAM HYDRATION SEQUENCE ---", output)
                self.assertIn("--- SEQUENCE COMPLETE ---", output)
                self.assertIn("ENTIGRAM_BOOT_VECTOR", output)
                self.assertIn("DomainA", output)
                self.assertIn("DomainB", output)
                self.assertIn("User", output)
                self.assertIn("active", output)

    def test_boot_alias(self):
        """Verifies that 'boot' is a valid alias for 'hydrate'."""
        test_args = ["entigram", "boot"]
        with patch.object(sys, 'argv', test_args):
            from io import StringIO
            captured_output = StringIO()
            with patch('sys.stdout', captured_output):
                try:
                    main()
                except SystemExit:
                    pass
            
            output = captured_output.getvalue()
            self.assertIn("--- ENTIGRAM HYDRATION SEQUENCE ---", output)

if __name__ == "__main__":
    unittest.main()
