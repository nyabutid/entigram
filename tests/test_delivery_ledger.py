"""
Tests for the durable delivery ledger:
- delivery_evidence (commissioner pass persistence)
- improvement_proposals (lifecycle tracking)
- delivery_snapshots (drift detection anchor)
"""
import unittest
from entigram.sqlite_ledger.manager import LedgerManager


class TestDeliveryEvidence(unittest.TestCase):
    def setUp(self):
        self.ledger = LedgerManager(":memory:")

    def test_record_and_retrieve_delivery_evidence(self):
        row_id = self.ledger.record_delivery_evidence(
            evidence_type="commission_pass",
            artifact_ref="commissioner_checklist",
            expectation_name="Stable Jump Arc",
            command="python -m pytest tests/test_gameplay.py",
            result_summary="3 passed in 0.1s",
            passed=True,
            agent_id="Antigravity",
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)

        records = self.ledger.get_delivery_evidence()
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["evidence_type"], "commission_pass")
        self.assertEqual(record["expectation_name"], "Stable Jump Arc")
        self.assertTrue(record["passed"])
        self.assertEqual(record["agent_id"], "Antigravity")

    def test_filter_by_expectation_name(self):
        self.ledger.record_delivery_evidence(
            evidence_type="commission_pass",
            artifact_ref="commissioner_checklist",
            expectation_name="Loop A",
            passed=True,
        )
        self.ledger.record_delivery_evidence(
            evidence_type="test_run",
            artifact_ref="tests/test_b.py",
            expectation_name="Loop B",
            passed=True,
        )
        results = self.ledger.get_delivery_evidence(expectation_name="Loop A")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["expectation_name"], "Loop A")

    def test_filter_passed_only(self):
        self.ledger.record_delivery_evidence(
            evidence_type="test_run", artifact_ref="tests/a.py", passed=True
        )
        self.ledger.record_delivery_evidence(
            evidence_type="test_run", artifact_ref="tests/b.py", passed=False
        )
        results = self.ledger.get_delivery_evidence(passed_only=True)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["passed"])


class TestImprovementProposals(unittest.TestCase):
    def setUp(self):
        self.ledger = LedgerManager(":memory:")

    def test_record_and_retrieve_proposal(self):
        row_id = self.ledger.record_improvement_proposal(
            title="Add Blocked expectation state",
            affected_model="Entigram_Expectation",
            proposed_change={"add_field": "lifecycle_status=Blocked"},
            rationale="Distinguish infra failures from proof gaps",
            expected_benefit="Clearer root cause in commissioner output",
            created_by="Antigravity",
        )
        self.assertIsNotNone(row_id)

        proposals = self.ledger.get_improvement_proposals()
        self.assertEqual(len(proposals), 1)
        p = proposals[0]
        self.assertEqual(p["title"], "Add Blocked expectation state")
        self.assertEqual(p["lifecycle_status"], "Proposed")
        self.assertEqual(p["created_by"], "Antigravity")
        self.assertIn("add_field", p["proposed_change"])

    def test_filter_by_lifecycle_status(self):
        self.ledger.record_improvement_proposal(
            title="Proposal A",
            affected_model="Model",
            proposed_change={},
            rationale="reason A",
            lifecycle_status="Proposed",
        )
        self.ledger.record_improvement_proposal(
            title="Proposal B",
            affected_model="Model",
            proposed_change={},
            rationale="reason B",
            lifecycle_status="Reviewed",
        )
        proposed = self.ledger.get_improvement_proposals(lifecycle_status="Proposed")
        self.assertEqual(len(proposed), 1)
        self.assertEqual(proposed[0]["title"], "Proposal A")

    def test_multiple_proposals_returned(self):
        for i in range(3):
            self.ledger.record_improvement_proposal(
                title=f"Proposal {i}",
                affected_model="Core",
                proposed_change={"index": i},
                rationale=f"reason {i}",
            )
        proposals = self.ledger.get_improvement_proposals()
        self.assertEqual(len(proposals), 3)


class TestDeliverySnapshots(unittest.TestCase):
    def setUp(self):
        self.ledger = LedgerManager(":memory:")

    def test_record_and_retrieve_snapshot(self):
        success = self.ledger.record_delivery_snapshot(
            snapshot_id="delivery-20260604T120000-Antigravity",
            expectation_count=2,
            missing_proof_count=0,
            schema_hash="abc123def456ab12",
            agent_id="Antigravity",
            warden_status="intact",
            evidence_ids=[1, 2],
            metadata={"proofs_provided": 2},
        )
        self.assertTrue(success)

        snap = self.ledger.get_latest_snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(snap["snapshot_id"], "delivery-20260604T120000-Antigravity")
        self.assertEqual(snap["expectation_count"], 2)
        self.assertEqual(snap["missing_proof_count"], 0)
        self.assertEqual(snap["schema_hash"], "abc123def456ab12")
        self.assertEqual(snap["warden_status"], "intact")
        self.assertEqual(snap["evidence_ids"], [1, 2])
        self.assertEqual(snap["metadata"]["proofs_provided"], 2)

    def test_get_latest_snapshot_returns_most_recent(self):
        self.ledger.record_delivery_snapshot(
            snapshot_id="snap-001", expectation_count=2, missing_proof_count=0
        )
        self.ledger.record_delivery_snapshot(
            snapshot_id="snap-002", expectation_count=3, missing_proof_count=0
        )
        snap = self.ledger.get_latest_snapshot()
        self.assertEqual(snap["snapshot_id"], "snap-002")

    def test_no_snapshot_returns_none(self):
        snap = self.ledger.get_latest_snapshot()
        self.assertIsNone(snap)


class TestCommissionerWritesEvidence(unittest.TestCase):
    """End-to-end: Commissioner pass should write to delivery_evidence in ledger."""

    SCHEMA = """
EXPECTATION: Stable Loop {
  developer_expectation: The loop must be stable.
  implementation_rule: Tests must not break the loop.
  validation_check: tests/test_loop.py
  proof: tests/test_loop.py
}
"""

    def test_commissioner_pass_writes_evidence_to_ledger(self):
        from entigram.governance.commissioner import Commissioner

        ledger = LedgerManager(":memory:")
        commissioner = Commissioner(self.SCHEMA, ledger=ledger)
        checklist = commissioner.build_checklist(
            proofs=["tests/test_loop.py passed 3 assertions"],
            agent_id="TestAgent",
        )

        self.assertTrue(checklist["valid"])

        # Verify evidence was written
        evidence = ledger.get_delivery_evidence(expectation_name="Stable Loop")
        self.assertEqual(len(evidence), 1)
        self.assertTrue(evidence[0]["passed"])
        self.assertEqual(evidence[0]["agent_id"], "TestAgent")
        self.assertEqual(evidence[0]["evidence_type"], "commission_pass")

    def test_commissioner_fail_does_not_write_evidence(self):
        from entigram.governance.commissioner import Commissioner

        ledger = LedgerManager(":memory:")
        commissioner = Commissioner(self.SCHEMA, ledger=ledger)
        checklist = commissioner.build_checklist(proofs=[], agent_id="TestAgent")

        self.assertFalse(checklist["valid"])
        evidence = ledger.get_delivery_evidence()
        self.assertEqual(len(evidence), 0)


if __name__ == "__main__":
    unittest.main()
