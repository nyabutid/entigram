import json
import shutil
import tempfile
import unittest
from pathlib import Path

from entigram.injector import inject_entigram_manifest
from entigram.mcp_service import EntigramMCPService
from entigram.sqlite_ledger.manager import LedgerManager
from entigram.sqlite_ledger.paths import resolve_ledger_path


SCHEMA = """
ENTITY: User {
  id UUID PK
  name String
}

ENTITY: Account {
  id UUID PK
  owner_name String
}
"""

PARENT_CHILD_SCHEMA = """
ENTITY: Parent {
  id UUID PK
  name String
}

ENTITY: Child {
  id UUID PK
  name String
}

RELATIONSHIPS:
- Parent (1) [MUST] --- [MAY] (MANY) Child
"""


class TestMCPService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        inject_entigram_manifest(self.test_dir, ["Entigram Schemas"], "Codex")
        Path(self.test_dir, "schema.lds").write_text(SCHEMA)
        self.service = EntigramMCPService(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_get_schemas_returns_lds_boundaries(self):
        output = json.loads(self.service.get_schemas())

        self.assertEqual(output["schemas"][0]["path"], "schema.lds")
        self.assertIn("User", output["schemas"][0]["entities"])
        self.assertIn("Account", output["schemas"][0]["entities"])

    def test_propose_alignment_validates_and_writes_proposal(self):
        result = json.loads(
            self.service.propose_alignment(
                json.dumps(
                    {
                        "source_domain": "CRM",
                        "target_domain": "Finance",
                        "source_concept": "User.name",
                        "target_concept": "Account.owner_name",
                        "confidence": 0.91,
                        "rationale": "Both values identify the account owner name.",
                    }
                )
            )
        )

        self.assertTrue(result["ok"])
        ledger = LedgerManager(str(resolve_ledger_path(self.test_dir)))
        try:
            alignments = ledger.get_alignments()
        finally:
            ledger.close()

        self.assertEqual(len(alignments), 1)
        self.assertEqual(alignments[0]["lifecycle_status"], "proposed")
        self.assertFalse(alignments[0]["verified"])

    def test_propose_alignment_rejects_unknown_entity_without_crashing(self):
        result = self.service.propose_alignment(
            json.dumps(
                {
                    "source_domain": "CRM",
                    "target_domain": "Finance",
                    "source_concept": "Ghost.name",
                    "target_concept": "Account.owner_name",
                    "confidence": 0.91,
                    "rationale": "Bad payload.",
                }
            )
        )

        self.assertIn("Error: Invalid Schema Alignment - Entity Ghost not found", result)
        ledger = LedgerManager(str(resolve_ledger_path(self.test_dir)))
        try:
            self.assertEqual(ledger.get_alignments(), [])
        finally:
            ledger.close()

    def test_propose_alignment_rejects_child_when_parent_alignment_is_only_proposed(self):
        Path(self.test_dir, "schema.lds").write_text(PARENT_CHILD_SCHEMA)

        parent_result = json.loads(
            self.service.propose_alignment(
                json.dumps(
                    {
                        "source_domain": "CRM",
                        "target_domain": "ERP",
                        "source_concept": "Parent.name",
                        "target_concept": "Parent.name",
                        "confidence": 0.91,
                        "rationale": "Proposed parent mapping.",
                    }
                )
            )
        )
        self.assertTrue(parent_result["ok"])

        child_result = self.service.propose_alignment(
            json.dumps(
                {
                    "source_domain": "CRM",
                    "target_domain": "ERP",
                    "source_concept": "Child.name",
                    "target_concept": "Child.name",
                    "confidence": 0.91,
                    "rationale": "Child mapping should wait for a verified parent.",
                }
            )
        )

        self.assertIn("RA Precedence Violation", child_result)

    def test_propose_alignment_allows_child_when_parent_alignment_is_trusted(self):
        Path(self.test_dir, "schema.lds").write_text(PARENT_CHILD_SCHEMA)
        ledger = LedgerManager(str(resolve_ledger_path(self.test_dir)))
        try:
            ledger.record_alignment(
                source_domain="CRM",
                target_domain="ERP",
                source_concept="Parent.name",
                target_concept="Parent.name",
                confidence=0.95,
                rationale="Verified parent mapping.",
            )
        finally:
            ledger.close()

        child_result = json.loads(
            self.service.propose_alignment(
                json.dumps(
                    {
                        "source_domain": "CRM",
                        "target_domain": "ERP",
                        "source_concept": "Child.name",
                        "target_concept": "Child.name",
                        "confidence": 0.91,
                        "rationale": "Child mapping follows verified parent.",
                    }
                )
            )
        )

        self.assertTrue(child_result["ok"])

    def test_log_conflict_rejects_unknown_attribute(self):
        result = self.service.log_conflict(
            json.dumps(
                {
                    "conflict_id": "Conflict_1",
                    "entity_type": "User",
                    "agent_id": "AgentA",
                    "proposed_states": {
                        "AgentA": {"invented": "x"},
                        "AgentB": {"name": "y"},
                    },
                }
            )
        )

        self.assertIn("Error: Invalid Conflict - Attribute invented not found on entity User", result)

    def test_log_conflict_validates_and_writes_conflict(self):
        result = json.loads(
            self.service.log_conflict(
                json.dumps(
                    {
                        "conflict_id": "Conflict_2",
                        "entity_type": "User",
                        "agent_id": "AgentA",
                        "proposed_states": {
                            "AgentA": {"name": "Alice"},
                            "AgentB": {"name": "Alicia"},
                        },
                    }
                )
            )
        )

        self.assertTrue(result["ok"])
        ledger = LedgerManager(str(resolve_ledger_path(self.test_dir)))
        try:
            conflicts = ledger.get_pending_conflicts()
        finally:
            ledger.close()

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["conflict_id"], "Conflict_2")

    def test_file_ledger_uses_wal_and_busy_timeout(self):
        ledger_path = resolve_ledger_path(self.test_dir)
        ledger = LedgerManager(str(ledger_path))
        conn = ledger._get_connection()
        try:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        finally:
            conn.close()
            ledger.close()

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(busy_timeout, 5000)
