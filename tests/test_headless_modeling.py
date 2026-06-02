import unittest
from unittest.mock import patch, MagicMock
import os
import sys
from pathlib import Path
from entigram.cli_runner.etg_cli import main

class TestHeadlessModeling(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_headless_ws")
        self.test_dir.mkdir(exist_ok=True)
        (self.test_dir / ".etg").mkdir(exist_ok=True)
        with open(self.test_dir / ".etg" / "entigram.yaml", "w") as f:
            f.write("cli_engine: Antigravity\n")
        
        self.draft_path = self.test_dir / "draft_schema.lds"
        with open(self.draft_path, "w") as f:
            f.write("ENTITY: Existing\nATTRIBUTES:\n  - .id (UUID)\n")

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_model_command_append(self, mock_which, mock_run):
        mock_which.return_value = "/usr/local/bin/agy"
        
        # Mock successful agy run output
        mock_run.return_value = MagicMock(
            stdout="ENTITY: Library\nATTRIBUTES:\n  - .id (UUID)\n  - name (String)\n\nRELATIONSHIPS:\n- Library (1) [MUST] --- [MAY] (MANY) Book",
            returncode=0
        )

        # Simulate CLI arguments
        test_args = [
            "etg", "model", "A library with books", 
            "--dir", str(self.test_dir), 
            "--append"
        ]
        
        with patch.object(sys, 'argv', test_args):
            main()

        # Verify agy was called headlessly (with input=prompt)
        # Call index 0 is likely the first agy check or similar, let's check all calls
        found_agy_call = False
        for call in mock_run.call_args_list:
            args, kwargs = call
            if args[0][0] == "agy" and "input" in kwargs:
                found_agy_call = True
                self.assertIn("A library with books", kwargs["input"])
                break
        self.assertTrue(found_agy_call)

        # Verify draft_schema.lds was updated
        with open(self.draft_path, "r") as f:
            content = f.read()
            self.assertIn("ENTITY: Library", content)
            self.assertIn("RELATIONSHIPS:", content)
            self.assertIn("Book", content)

if __name__ == "__main__":
    unittest.main()
