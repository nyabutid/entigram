import unittest
from entigram.governance.negotiator import AlignmentNegotiator

class TestNegotiatorBlocking(unittest.TestCase):
    def setUp(self):
        self.negotiator = AlignmentNegotiator(threshold=0.4)

    def test_semantic_blocking_identity(self):
        source_schema = """
        ENTITY: Patient
        - .id (UUID)
        - name (String)
        """
        target_schema = """
        ENTITY: User
        - .id (UUID)
        - full_name (String)
        """
        # Both "Patient" and "User" contain keywords for the "identity" block
        proposals = self.negotiator.negotiate(source_schema, target_schema)
        
        # Check if Patient and User were matched
        match = next((p for p in proposals if p['source_concept'] == 'Patient' and p['target_concept'] == 'User'), None)
        self.assertIsNotNone(match)
        self.assertIn("Block Match [identity]", match['rationale'])

    def test_semantic_blocking_isolation(self):
        source_schema = """
        ENTITY: Patient
        - .id (UUID)
        """
        target_schema = """
        ENTITY: Product
        - .id (UUID)
        """
        # "Patient" is identity, "Product" is product. They should NOT match if blocks are disjoint.
        # Note: If fallback prefixes overlap, they might still compare, but here they are in different categories.
        proposals = self.negotiator.negotiate(source_schema, target_schema)
        
        match = next((p for p in proposals if p['source_concept'] == 'Patient' and p['target_concept'] == 'Product'), None)
        self.assertIsNone(match, "Patient and Product should be in different blocks and not compared/matched")

    def test_fallback_blocking(self):
        source_schema = """
        ENTITY: XrayScan
        - .id (UUID)
        """
        target_schema = """
        ENTITY: XrayImage
        - .id (UUID)
        """
        # Neither matches a category, so they fallback to prefix_xra
        proposals = self.negotiator.negotiate(source_schema, target_schema)
        
        match = next((p for p in proposals if p['source_concept'] == 'XrayScan' and p['target_concept'] == 'XrayImage'), None)
        self.assertIsNotNone(match)
        self.assertIn("Block Match [prefix_xra]", match['rationale'])

if __name__ == "__main__":
    unittest.main()
