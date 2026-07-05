import json
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import yaml

from entigram.cli_runner.etg_cli import main
from entigram.governance.warden import Warden
from entigram.injector import inject_entigram_manifest
from entigram.schema_compiler.merger import SchemaMerger
from entigram.sqlite_ledger.manager import LedgerManager
from entigram.sqlite_ledger.paths import resolve_ledger_path


LOCAL_SCHEMA = """ENTITY: Person
ATTRIBUTES:
  - .id (UUID)
  - name (String)
  - email (String)
"""


REMOTE_SCHEMA = """ENTITY: Person
ATTRIBUTES:
  - .id (UUID)
  - name (String)
  - phone (String)

ENTITY: Encounter
ATTRIBUTES:
  - .id (UUID)
  - date (DateTime)
"""


class TestSchemaMerge(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.local_schema = self.test_dir / "local.lds"
        self.remote_schema = self.test_dir / "remote.lds"
        self.local_schema.write_text(LOCAL_SCHEMA)
        self.remote_schema.write_text(REMOTE_SCHEMA)
        self.ledger = LedgerManager(":memory:")

    def tearDown(self):
        self.ledger.close()
        shutil.rmtree(self.test_dir)

    def merger(self):
        return SchemaMerger(str(self.local_schema), str(self.remote_schema), self.ledger)

    def test_clean_merge_no_conflicts(self):
        self.remote_schema.write_text("""ENTITY: Organization
ATTRIBUTES:
  - .id (UUID)
  - name (String)
""")

        diff = self.merger().diff()

        self.assertFalse(diff.has_conflicts)
        self.assertEqual([entity.name for entity in diff.added_entities], ["Organization"])

    def test_attribute_divergence_conflict(self):
        diff = self.merger().diff()

        self.assertTrue(diff.has_conflicts)
        self.assertEqual(diff.conflicts[0].entity_name, "Person")
        self.assertEqual(diff.conflicts[0].conflict_type, "attribute_divergence")

    def test_union_strategy(self):
        result = self.merger().merge(strategy="union")

        self.assertIn("phone (String)", result.merged_schema)
        self.assertIn("email (String)", result.merged_schema)
        self.assertIn("Encounter", result.merged_schema)

    def test_ours_strategy(self):
        result = self.merger().merge(strategy="ours")

        self.assertIn("email (String)", result.merged_schema)
        self.assertNotIn("phone (String)", result.merged_schema)

    def test_theirs_strategy(self):
        result = self.merger().merge(strategy="theirs")

        self.assertIn("phone (String)", result.merged_schema)
        self.assertNotIn("email (String)", result.merged_schema)

    def test_precedent_lookup(self):
        self.ledger.record_resolution(
            "MERGE-Person-attribute_divergence",
            "Person",
            json.dumps({"merge_strategy": "union"}),
            "is_precedent=true UNION",
        )

        diff = self.merger().diff()

        self.assertEqual(diff.conflicts[0].suggested_resolution, "union")


class TestLedgerMerge(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.local_db = self.test_dir / "local.db"
        self.remote_db = self.test_dir / "remote.db"
        self.local = LedgerManager(str(self.local_db))
        self.remote = LedgerManager(str(self.remote_db))
        schema = self.test_dir / "schema.lds"
        schema.write_text("ENTITY: Local\nATTRIBUTES:\n  - .id (UUID)\n")
        self.remote_schema = self.test_dir / "remote.lds"
        self.remote_schema.write_text("ENTITY: Remote\nATTRIBUTES:\n  - .id (UUID)\n")
        self.merger = SchemaMerger(str(schema), str(self.remote_schema), self.local)

    def tearDown(self):
        self.local.close()
        self.remote.close()
        shutil.rmtree(self.test_dir)

    def test_ledger_merge_semantic_alignments(self):
        self.remote.record_alignment(
            "CRM", "ERP", "Account.name", "Supplier.name", 0.9, "test"
        )
        stats = self.merger.merge_state_db(str(self.remote_db))

        self.assertEqual(stats["semantic_alignments"], 1)
        self.assertEqual(len(self.local.get_alignments()), 1)

    def test_ledger_merge_synonyms(self):
        self.remote.record_synonym("vendor", "supplier", 0.95)
        stats = self.merger.merge_state_db(str(self.remote_db))

        self.assertEqual(stats["synonyms"], 2)
        self.assertEqual(len(self.local.get_synonyms()), 2)


class TestMergeCLI(unittest.TestCase):
    def setUp(self):
        self.local_dir = Path(tempfile.mkdtemp())
        self.remote_dir = Path(tempfile.mkdtemp())
        inject_entigram_manifest(str(self.local_dir), ["Entigram Schemas"], "Codex")
        inject_entigram_manifest(str(self.remote_dir), ["Entigram Schemas"], "Codex")
        (self.local_dir / "schema.lds").write_text(LOCAL_SCHEMA)
        (self.remote_dir / "schema.lds").write_text(REMOTE_SCHEMA)
        LedgerManager(str(resolve_ledger_path(str(self.local_dir)))).close()
        LedgerManager(str(resolve_ledger_path(str(self.remote_dir)))).close()
        self.old_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.local_dir)
        shutil.rmtree(self.remote_dir)

    def run_cli(self, argv):
        with patch.object(sys, "argv", ["etg"] + argv):
            output = StringIO()
            with patch("sys.stdout", output):
                try:
                    main()
                    code = 0
                except SystemExit as exc:
                    code = int(exc.code or 0)
            return code, output.getvalue()

    def test_dry_run(self):
        os.chdir(self.local_dir)
        before = (self.local_dir / "schema.lds").read_text()

        code, output = self.run_cli(["merge", "--from", str(self.remote_dir), "--dry-run"])

        self.assertEqual(code, 0, output)
        self.assertIn("Schema Diff", output)
        self.assertFalse((self.local_dir / "draft_schema.lds").exists())
        self.assertEqual((self.local_dir / "schema.lds").read_text(), before)

    def test_warden_relock(self):
        os.chdir(self.local_dir)
        Warden(str(self.local_dir)).lock_fingerprint()
        before = yaml.safe_load((self.local_dir / ".etg" / "entigram.yaml").read_text())

        code, output = self.run_cli([
            "merge", "--from", str(self.remote_dir), "--strategy", "union", "--apply"
        ])
        after = yaml.safe_load((self.local_dir / ".etg" / "entigram.yaml").read_text())

        self.assertEqual(code, 0, output)
        self.assertIn("phone (String)", (self.local_dir / "schema.lds").read_text())
        self.assertNotEqual(
            before["integrity_fingerprint"]["schema_checksum"],
            after["integrity_fingerprint"]["schema_checksum"],
        )
        self.assertTrue(Warden(str(self.local_dir)).verify_integrity())


if __name__ == "__main__":
    unittest.main()
