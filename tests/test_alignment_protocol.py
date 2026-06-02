import unittest
from entigram.governance.alignment import AlignmentProtocol

class TestAlignmentProtocol(unittest.TestCase):
    def test_export_alignment_api(self):
        protocol = AlignmentProtocol("finance.ttl", "startup.ttl")
        protocol.propose_alignment("finance:Account", "startup:BankAccount", confidence=0.95)
        
        xml_output = protocol.export_alignment_api()
        self.assertIn('<?xml version="1.0"', xml_output)
        self.assertIn('<Alignment>', xml_output)
        self.assertIn('<entity1 rdf:resource="finance:Account"/>', xml_output)
        self.assertIn('<entity2 rdf:resource="startup:BankAccount"/>', xml_output)
        self.assertIn('<measure rdf:datatype="http://www.w3.org/2001/XMLSchema#float">0.95</measure>', xml_output)

    def test_alignment_proposals_are_unverified_by_default(self):
        protocol = AlignmentProtocol("finance.ttl", "startup.ttl")
        mapping = protocol.propose_alignment("finance:balance", "startup:cash_on_hand")

        self.assertEqual(mapping["lifecycle_status"], "proposed")
        self.assertFalse(mapping["verified"])
        self.assertEqual(mapping["evidence_type"], "schema_match")

    def test_approve_alignment_promotes_to_verified(self):
        protocol = AlignmentProtocol("finance.ttl", "startup.ttl")
        protocol.propose_alignment("finance:balance", "startup:cash_on_hand")

        mapping = protocol.approve_alignment(
            "finance:balance",
            "startup:cash_on_hand",
            verified_by="test-reviewer",
            evidence_type="human_review",
        )

        self.assertEqual(mapping["lifecycle_status"], "verified")
        self.assertTrue(mapping["verified"])
        self.assertEqual(mapping["verified_by"], "test-reviewer")

if __name__ == "__main__":
    unittest.main()
