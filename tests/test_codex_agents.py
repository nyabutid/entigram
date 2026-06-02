import unittest
import os
import shutil
import tempfile
from pathlib import Path
from entigram.injector import inject_entigram_manifest

class TestCodexAgents(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_codex_generates_agents_md(self):
        """Verifies that selecting the Codex engine generates an AGENTS.md file."""
        success = inject_entigram_manifest(self.test_dir, ["Banking"], "Codex")
        self.assertTrue(success)
        
        agents_path = Path(self.test_dir) / "AGENTS.md"
        self.assertTrue(agents_path.exists(), "AGENTS.md was not generated for Codex engine")
        
        content = agents_path.read_text()
        self.assertIn("# Entigram Agent Context", content)
        self.assertIn("## Workspace Context", content)
        self.assertIn("## Primary Directives", content)
        self.assertIn("- **Packages:** Banking", content)

if __name__ == "__main__":
    unittest.main()
