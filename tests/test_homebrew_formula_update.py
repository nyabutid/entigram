import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_homebrew_formula.py"
SPEC = importlib.util.spec_from_file_location("update_homebrew_formula", SCRIPT_PATH)
update_homebrew_formula = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_homebrew_formula)


class TestHomebrewFormulaUpdate(unittest.TestCase):
    def test_updates_only_top_level_source_checksum(self):
        old_sha = "0" * 64
        resource_sha = old_sha
        new_sha = "1" * 64
        new_url = "https://files.pythonhosted.org/packages/aa/bb/example/entigram_ai-1.3.2.tar.gz"
        formula = f'''class Etg < Formula
  include Language::Python::Virtualenv

  desc "Schema-first semantic governance layer for enterprise agents"
  homepage "https://api.entigram.ai"
  url "https://files.pythonhosted.org/packages/old/entigram_ai-1.3.1.tar.gz"
  sha256 "{old_sha}"
  license "Apache-2.0"

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/f3/certifi-2026.5.20.tar.gz"
    sha256 "{resource_sha}"
  end
end
'''

        with tempfile.TemporaryDirectory() as tmpdir:
            formula_path = Path(tmpdir) / "etg.rb"
            formula_path.write_text(formula)

            update_homebrew_formula.update_formula_source(formula_path, new_url, new_sha)

            updated = formula_path.read_text()

        self.assertIn(f'  url "{new_url}"', updated)
        self.assertIn(f'  sha256 "{new_sha}"', updated)
        self.assertIn(f'    sha256 "{resource_sha}"', updated)
        self.assertEqual(updated.count(new_sha), 1)

    def test_selects_source_distribution_from_pypi_metadata(self):
        release = {
            "urls": [
                {
                    "packagetype": "bdist_wheel",
                    "filename": "entigram_ai-1.3.2-py3-none-any.whl",
                    "digests": {"sha256": "wheel"},
                    "url": "https://example.test/wheel",
                },
                {
                    "packagetype": "sdist",
                    "filename": "entigram_ai-1.3.2.tar.gz",
                    "digests": {"sha256": "sdist"},
                    "url": "https://example.test/sdist",
                },
            ]
        }

        self.assertEqual(
            update_homebrew_formula.select_sdist(release),
            ("https://example.test/sdist", "sdist"),
        )


if __name__ == "__main__":
    unittest.main()
