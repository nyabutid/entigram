import unittest
import shutil
import subprocess
import sys
from pathlib import Path

class TestResearchPackages(unittest.TestCase):
    def setUp(self):
        self.startup_dir = Path("test_startup")
        self.strategy_dir = Path("test_strategy")
        for d in [self.startup_dir, self.strategy_dir]:
            if d.exists(): shutil.rmtree(d)
            
    def tearDown(self):
        for d in [self.startup_dir, self.strategy_dir]:
            if d.exists(): shutil.rmtree(d)

    def test_startup_founder_bootstrap(self):
        print("\n[Research Test] Bootstrapping Startup Founder...")
        cmd = [sys.executable, "-m", "entigram.cli_runner.etg_cli", "init", "--dir", str(self.startup_dir), "--packages", "Startup Founder"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        self.assertEqual(result.returncode, 0)
        
        # Verify specific Schema entities exist
        schema_text = (self.startup_dir / "schema.lds").read_text()
        self.assertIn("ENTITY: Idea", schema_text)
        self.assertIn("ENTITY: Value_Proposition", schema_text)
        
        # Verify Skill is injected
        self.assertTrue((self.startup_dir / "SKILL.md").exists())

    def test_business_strategy_bootstrap(self):
        print("[Research Test] Bootstrapping Business Strategy...")
        cmd = [sys.executable, "-m", "entigram.cli_runner.etg_cli", "init", "--dir", str(self.strategy_dir), "--packages", "Business Strategy"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        self.assertEqual(result.returncode, 0)
        
        # Verify specific Schema entities exist
        schema_text = (self.strategy_dir / "schema.lds").read_text()
        self.assertIn("ENTITY: Strategic_Goal", schema_text)
        self.assertIn("ENTITY: KPI", schema_text)

if __name__ == "__main__":
    unittest.main()
