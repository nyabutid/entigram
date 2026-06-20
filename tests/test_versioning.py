import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "versioning.py"
SPEC = importlib.util.spec_from_file_location("versioning", SCRIPT_PATH)
versioning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(versioning)


class TestVersioning(unittest.TestCase):
    def test_set_version_allows_setup_py_shim(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "pyproject.toml").write_text(
                '[project]\nname = "entigram-ai"\nversion = "1.4.0"\n'
            )
            (project / "setup.py").write_text("from setuptools import setup\n\nsetup()\n")

            previous = os.getcwd()
            try:
                os.chdir(project)
                originals = versioning.set_version("1.4.1")
            finally:
                os.chdir(previous)

            self.assertIn('version = "1.4.1"', (project / "pyproject.toml").read_text())
            self.assertEqual("from setuptools import setup\n\nsetup()\n", (project / "setup.py").read_text())
            self.assertEqual({Path("pyproject.toml")}, set(originals))

    def test_set_version_updates_legacy_setup_py_when_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "pyproject.toml").write_text(
                '[project]\nname = "entigram-ai"\nversion = "1.4.0"\n'
            )
            (project / "setup.py").write_text('setup(name="entigram-ai", version="1.4.0")\n')

            previous = os.getcwd()
            try:
                os.chdir(project)
                originals = versioning.set_version("1.4.1")
            finally:
                os.chdir(previous)

            self.assertIn('version = "1.4.1"', (project / "pyproject.toml").read_text())
            self.assertIn('version="1.4.1"', (project / "setup.py").read_text())
            self.assertEqual({Path("pyproject.toml"), Path("setup.py")}, set(originals))


if __name__ == "__main__":
    unittest.main()
