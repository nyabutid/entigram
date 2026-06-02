import unittest
import os
from pathlib import Path
from entigram.governance.negotiator import AlignmentNegotiator

class TestAlignmentNegotiator(unittest.TestCase):
    def test_negotiate_simple(self):
        source_schema = """
        ENTITY Patient {
            id UUID PK
            full_name String
            birth_date Date
        }
        """
        target_schema = """
        ENTITY Client {
            id UUID PK
            name String
            dob Date
        }
        """
        
        negotiator = AlignmentNegotiator(threshold=0.3)
        proposals = negotiator.negotiate(source_schema, target_schema)
        
        # Check if Patient and Client are matched (low but should be there)
        entity_matches = [p for p in proposals if '.' not in p['source_concept']]
        self.assertTrue(any(p['source_concept'] == 'Patient' and p['target_concept'] == 'Client' for p in entity_matches))
        
        # Check if attributes are matched
        prop_matches = [p for p in proposals if '.' in p['source_concept']]
        # Patient.id <-> Client.id should be an exact match
        self.assertTrue(any(p['source_concept'] == 'Patient.id' and p['target_concept'] == 'Client.id' for p in prop_matches))

if __name__ == "__main__":
    unittest.main()
