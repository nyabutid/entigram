import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from entigram.registry import _safe_extract


class TestSafeTarExtract(unittest.TestCase):
    def _make_tar(self, members):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for name, data in members:
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        buf.seek(0)
        return tarfile.open(fileobj=buf, mode="r:gz")

    def test_safe_extract_rejects_parent_traversal(self):
        tar = self._make_tar([("../evil.txt", b"pwned")])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                _safe_extract(tar, Path(tmp))

    def test_safe_extract_rejects_absolute_path(self):
        tar = self._make_tar([("/etc/evil.txt", b"pwned")])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                _safe_extract(tar, Path(tmp))

    def test_safe_extract_rejects_symlink(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="link.txt")
            info.type = tarfile.SYMTYPE
            info.linkname = "../evil.txt"
            tar.addfile(info)
        buf.seek(0)
        tar = tarfile.open(fileobj=buf, mode="r:gz")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                _safe_extract(tar, Path(tmp))

    def test_safe_extract_allows_legitimate_files(self):
        tar = self._make_tar([
            ("pkg/file.txt", b"hello"),
            ("pkg/.etg/entigram.yaml", b"version: 1.0"),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            _safe_extract(tar, Path(tmp))
            self.assertTrue((Path(tmp) / "pkg" / "file.txt").exists())
            self.assertTrue((Path(tmp) / "pkg" / ".etg" / "entigram.yaml").exists())


if __name__ == "__main__":
    unittest.main()
