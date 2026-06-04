import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from entigram.broker import EntigramBroker
from entigram.cli_runner.etg_cli import get_hydration_vector, main
from entigram.governance.commissioner import Commissioner
from entigram.injector import inject_entigram_manifest
from entigram.sqlite_ledger.manager import LedgerManager


EXPECTATION_SCHEMA = """
ENTITY: Player {
  id UUID PK
}

EXPECTATION: Stable Jump Arc {
  developer_expectation: Player jumps keep the same readable arc.
  implementation_rule: Gameplay changes must not alter jump height without an explicit model update.
  validation_check: tests/test_gameplay.py::test_jump_arc
  proof: tests/test_gameplay.py::test_jump_arc
}
"""


def command_expectation_schema(command: str) -> str:
    return f"""
ENTITY: Player {{
  id UUID PK
}}

EXPECTATION: Runnable Proof {{
  developer_expectation: Runnable checks should become durable delivery proof.
  implementation_rule: Resolve records successful proof that deliver can reuse.
  validation_check: {command}
  proof: {command}
}}
"""


class TestCommissioner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        inject_entigram_manifest(self.test_dir, ["Entigram Schemas"], "Codex")
        Path(self.test_dir, "schema.lds").write_text(EXPECTATION_SCHEMA)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_builds_pre_handoff_checklist_from_expectation_block(self):
        checklist = Commissioner(EXPECTATION_SCHEMA).build_checklist()

        self.assertFalse(checklist["valid"])
        self.assertEqual(checklist["expectation_count"], 1)
        self.assertEqual(checklist["missing_proof_count"], 1)
        self.assertEqual(checklist["items"][0]["name"], "Stable Jump Arc")
        self.assertIn("Prove this still holds", checklist["items"][0]["handoff_question"])

    def test_marks_expectation_passed_when_expected_proof_is_provided(self):
        checklist = Commissioner(EXPECTATION_SCHEMA).build_checklist(
            proofs=["python -m pytest tests/test_gameplay.py::test_jump_arc passed"]
        )

        self.assertTrue(checklist["valid"])
        self.assertEqual(checklist["missing_proof_count"], 0)
        self.assertEqual(checklist["items"][0]["status"], "passed")

    def test_accepts_line_style_expectations(self):
        schema = """
        EXPECTATION: Enemy Spawn Budget
        developer_expectation: Enemy spawns remain fair.
        implementation_rule: Spawn count must stay below the screen budget.
        validation_check: tests/test_spawns.py::test_spawn_budget
        """

        checklist = Commissioner(schema).build_checklist()

        self.assertEqual(checklist["expectation_count"], 1)
        self.assertEqual(checklist["items"][0]["name"], "Enemy Spawn Budget")

    def test_broker_commission_loads_workspace_schema(self):
        broker = EntigramBroker(self.test_dir)

        checklist = broker.commission(proofs=["tests/test_gameplay.py::test_jump_arc"])

        self.assertTrue(checklist["valid"])
        self.assertEqual(checklist["expectation_count"], 1)

    def test_cli_commission_fails_without_proof_and_passes_with_proof(self):
        old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            failed, failed_output = self._run_cli(["broker", "commission"])
            passed, passed_output = self._run_cli(
                ["broker", "commission", "--proof", "tests/test_gameplay.py::test_jump_arc"]
            )
        finally:
            os.chdir(old_cwd)

        self.assertFalse(failed)
        self.assertIn("need proof before handoff", failed_output)
        self.assertTrue(passed)
        self.assertIn("all modeled expectations have proof", passed_output)

    def test_hydration_vector_includes_commissioner_expectations(self):
        output = get_hydration_vector(Path(self.test_dir))

        self.assertIn('"commissioner"', output)
        self.assertIn("Stable Jump Arc", output)
        self.assertIn("tests/test_gameplay.py::test_jump_arc", output)
        self.assertIn('"delivery_evidence"', output)
        self.assertIn('"delivery_artifacts"', output)
        self.assertIn('"improvement_proposals"', output)
        self.assertIn('"latest_delivery_snapshot"', output)
        self.assertIn('"current_delivery_status"', output)

    def test_cli_deliver_records_explicit_artifact_anchor(self):
        artifact_path = Path(self.test_dir, "local-result.txt")
        artifact_path.write_text("delivery output")

        delivered, deliver_output = self._run_cli(
            [
                "broker",
                "--dir",
                self.test_dir,
                "deliver",
                "--proof",
                "tests/test_gameplay.py::test_jump_arc",
                "--artifact",
                "local-result.txt",
            ]
        )

        self.assertTrue(delivered, deliver_output)
        ledger = LedgerManager(str(Path(self.test_dir, ".etg", "entigram_state.db")))
        try:
            artifacts = ledger.get_delivery_artifacts()
            snapshot = ledger.get_latest_snapshot()
        finally:
            ledger.close()

        explicit = [
            artifact for artifact in artifacts
            if artifact["path"] == "local-result.txt"
        ]
        self.assertTrue(explicit)
        self.assertEqual(explicit[0]["artifact_role"], "delivery_artifact")
        self.assertIn(explicit[0]["id"], snapshot["artifact_ids"])

    def test_cli_status_reports_artifact_drift_after_delivery(self):
        artifact_path = Path(self.test_dir, "local-result.txt")
        artifact_path.write_text("delivery output")

        delivered, deliver_output = self._run_cli(
            [
                "broker",
                "--dir",
                self.test_dir,
                "deliver",
                "--proof",
                "tests/test_gameplay.py::test_jump_arc",
                "--artifact",
                "local-result.txt",
            ]
        )
        current, current_output = self._run_cli(
            ["broker", "--dir", self.test_dir, "status"]
        )
        artifact_path.write_text("changed output")
        drifted, drifted_output = self._run_cli(
            ["broker", "--dir", self.test_dir, "status"]
        )

        self.assertTrue(delivered, deliver_output)
        self.assertTrue(current, current_output)
        self.assertIn("Delivery status: current", current_output)
        self.assertFalse(drifted)
        self.assertIn("recommission required", drifted_output)
        self.assertIn("changed: local-result.txt", drifted_output)

    def test_cli_resolve_evidence_allows_deliver_without_repeating_proof(self):
        command = f'{sys.executable} -c "import sys; sys.exit(0)"'
        Path(self.test_dir, "schema.lds").write_text(command_expectation_schema(command))

        resolved, resolve_output = self._run_cli(
            ["broker", "--dir", self.test_dir, "resolve", "--run-missing-proofs"]
        )
        delivered, deliver_output = self._run_cli(
            ["broker", "--dir", self.test_dir, "deliver"]
        )

        self.assertTrue(resolved, resolve_output)
        self.assertIn("All missing proofs resolved", resolve_output)
        self.assertTrue(delivered, deliver_output)
        self.assertIn("Handoff gate: PASSED", deliver_output)

    def test_cli_deliver_unknown_expectation_fails(self):
        delivered, deliver_output = self._run_cli(
            [
                "broker",
                "--dir",
                self.test_dir,
                "deliver",
                "--expectation",
                "No Such Expectation",
                "--proof",
                "tests/test_gameplay.py::test_jump_arc",
            ]
        )

        self.assertFalse(delivered)
        self.assertIn("Unknown expectation", deliver_output)

    def _run_cli(self, args):
        captured_output = StringIO()
        with patch.object(sys, "argv", ["etg"] + args), patch("sys.stdout", captured_output):
            try:
                main()
                return True, captured_output.getvalue()
            except SystemExit as e:
                return e.code == 0, captured_output.getvalue()


if __name__ == "__main__":
    unittest.main()
