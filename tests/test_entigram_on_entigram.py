import unittest
import os
import shutil
import subprocess
import sys
from pathlib import Path

class TestEntigramOnEntigram(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("bootstrap_test")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_self_bootstrap(self):
        # 1. Use Headless CLI to Initialize
        print("\n[Entigram on Entigram] Step 1: Initializing self...")
        cmd_init = [sys.executable, "-m", "entigram.cli_runner.etg_cli", "init", "--dir", str(self.test_dir)]
        result = subprocess.run(cmd_init, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.test_dir / ".etg" / "entigram.yaml").exists())

        # 2. Simulate Schema creation (Self-Discovery would happen here)
        print("[Entigram on Entigram] Step 2: Injecting self-model...")
        schema_content = """
ENTITY: Entigram_Project
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - path (String)

ENTITY: Entigram_Package
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - description (String)

RELATIONSHIP: Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Package
"""
        with open(self.test_dir / "schema.lds", "w") as f:
            f.write(schema_content)

        # 3. Use Headless CLI to Build
        print("[Entigram on Entigram] Step 3: Building models...")
        cmd_build = [sys.executable, "-m", "entigram.cli_runner.etg_cli", "build", "--dir", str(self.test_dir)]
        result = subprocess.run(cmd_build, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CREATE TABLE IF NOT EXISTS entigram_projects", result.stdout)
        self.assertIn("CREATE TABLE IF NOT EXISTS entigram_packages", result.stdout)

if __name__ == "__main__":
    unittest.main()
