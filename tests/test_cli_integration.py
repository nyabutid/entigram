import unittest
import os
import sys
import shutil
import tempfile
import yaml
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from entigram.cli_runner.etg_cli import main

class TestCLIIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.old_stdout = sys.stdout
        sys.stdout = StringIO()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.test_dir)
        sys.stdout = self.old_stdout

    def run_cli(self, args):
        sys.stdout = StringIO()
        with patch.object(sys, 'argv', ['etg'] + args):
            try:
                main()
                return True, sys.stdout.getvalue()
            except SystemExit as e:
                return e.code == 0, sys.stdout.getvalue()
            except Exception as e:
                return False, str(e)

    def test_init_command(self):
        # Test init without --dir (requires Y/n)
        with patch('builtins.input', return_value='y'):
            success, output = self.run_cli(['init'])
            self.assertTrue(success)
            self.assertIn("Workspace initialized", output)
            self.assertTrue(os.path.exists(".etg/entigram.yaml"))
            with open(".etg/entigram.yaml", "r") as f:
                manifest = yaml.safe_load(f)
            self.assertEqual(manifest["workspace_schema_version"], 1)
            self.assertNotIn("entigram_version", manifest)
            self.assertEqual(manifest["schema_paths"], ["schema.lds"])
            self.assertTrue(manifest["state_ledger"].endswith(".etg/state.db"))

    def test_version_flag(self):
        success, output = self.run_cli(['--version'])
        self.assertTrue(success)
        self.assertIn("etg 1.7.0", output)

    def test_config_command(self):
        # First initialize
        self.run_cli(['init', '--dir', '.', '--force'])
        
        # Test config --list
        success, output = self.run_cli(['config', '--list'])
        self.assertTrue(success)
        self.assertIn("cli_engine", output)

        # Test config --engine (Catch the NameError fix)
        success, output = self.run_cli(['config', '--engine', 'Claude Code'])
        self.assertTrue(success)
        self.assertIn("engine updated to: Claude Code", output)

    def test_build_command(self):
        # Initialize
        self.run_cli(['init', '--dir', '.', '--force'])
        
        # Create a dummy Schema
        with open("schema.lds", "w") as f:
            f.write("""
ENTITY: Test
ATTRIBUTES:
  - id (String, PK)
""")
            
        with patch('builtins.input', return_value='y'):
            success, output = self.run_cli(['build', '--format', 'sql'])
            self.assertTrue(success)
            self.assertIn("CREATE TABLE", output)

    def test_broker_export_audit_command(self):
        self.run_cli(['init', '--dir', '.', '--force'])
        with open("schema.lds", "w") as f:
            f.write("""
ENTITY: Test
ATTRIBUTES:
  - id (String, PK)
""")

        self.run_cli(['broker', 'deliver'])
        success, output = self.run_cli(['broker', 'export-audit', '--out', 'audit.json'])

        self.assertTrue(success)
        self.assertIn("Audit bundle", output)
        self.assertIn("SHA-256", output)
        self.assertIn("Signature: ed25519", output)
        self.assertIn("Signing key:", output)
        self.assertTrue(Path("audit.json").exists())

    def test_interview_command_init_check(self):
        # Test interview without init (should fail gracefully)
        # Manually remove .etg if it exists from previous tests
        if os.path.exists(".etg"):
            shutil.rmtree(".etg")
        if os.path.exists("interview_prompt.md"):
            os.remove("interview_prompt.md")

        with patch('builtins.input', return_value='y'):
            success, output = self.run_cli(['interview'])
            self.assertFalse(success)
            self.assertIn("Run 'etg init' first.", output)

    @patch('entigram.cli_runner.etg_cli.launch_agent')
    def test_interview_command_success(self, mock_launch):
        # Initialize
        self.run_cli(['init', '--dir', '.', '--force'])
        mock_launch.return_value = (True, "Mock Launch")
        
        with patch('builtins.input', return_value='y'):
            success, output = self.run_cli(['interview'])
            self.assertTrue(success)
            self.assertIn("Starting Autonomous Modeler Interview", output)
            mock_launch.assert_called_once()

    @patch('entigram.cli_runner.etg_cli.launch_agent')
    def test_agent_command_headless(self, mock_launch):
        self.run_cli(['init', '--dir', '.', '--force'])
        mock_launch.return_value = (True, "Mock Launch")
        
        with patch('builtins.input', return_value='y'):
            success, output = self.run_cli(['agent', '--headless'])
            self.assertTrue(success)
            self.assertIn("Launching AI Agent", output)
            # Check that launch_agent was called with headless=True
            args, kwargs = mock_launch.call_args
            self.assertTrue(kwargs.get('headless'))

    @patch('entigram.cli_runner.etg_cli.launch_agent')
    def test_interview_command_headless(self, mock_launch):
        self.run_cli(['init', '--dir', '.', '--force'])
        mock_launch.return_value = (True, "Mock Launch")
        
        with patch('builtins.input', return_value='y'):
            success, output = self.run_cli(['interview', '--headless'])
            self.assertTrue(success)
            self.assertIn("Starting Autonomous Modeler Interview", output)
            # Check that launch_agent was called with headless=True
            args, kwargs = mock_launch.call_args
            self.assertTrue(kwargs.get('headless'))

    def test_discover_command_empty_db(self):
        # Create an empty DB
        db_path = "empty.db"
        open(db_path, 'a').close()
        
        success, output = self.run_cli(['discover', '--db', db_path])
        self.assertTrue(success)
        self.assertEqual(output.strip(), "")

    @patch('entigram.cli_runner.etg_cli.launch_ui')
    def test_no_command_prints_help_without_launching_ui(self, mock_launch_ui):
        success, output = self.run_cli([])
        self.assertTrue(success)
        self.assertIn("Entigram Headless Compiler CLI", output)
        mock_launch_ui.assert_not_called()

    @patch('entigram.cli_runner.etg_cli.importlib.util.find_spec', return_value=None)
    def test_ui_command_reports_missing_streamlit(self, _mock_find_spec):
        success, output = self.run_cli(['ui'])
        self.assertFalse(success)
        self.assertIn("Streamlit is not installed", output)
        self.assertIn("headless by default", output)
        self.assertIn("pipx install 'entigram-ai[ui]'", output)
        self.assertIn("pipx inject entigram-ai streamlit", output)

if __name__ == "__main__":
    unittest.main()
