import unittest
from entigram.schema_compiler.parser import SchemaParser
from entigram.ontology_compiler.compiler import OntologyCompiler

class TestOntologyCompiler(unittest.TestCase):
    def test_ontology_generation(self):
        text = """
ENTITY: User
ATTRIBUTES:
  - id (UUID, PK)
  - username (String)

ENTITY: Profile
ATTRIBUTES:
  - id (UUID, PK)
  - bio (Text)

RELATIONSHIP: User (1) [MUST] --- [MAY] (1) Profile
"""
        parser = SchemaParser(text)
        entities, relationships = parser.parse()
        
        compiler = OntologyCompiler(entities, relationships)
        ttl = compiler.compile()
        
        # Check for classes
        self.assertIn("mk:User a owl:Class", ttl)
        self.assertIn("mk:Profile a owl:Class", ttl)
        
        # Check for properties
        self.assertIn("mk:User_username a owl:DatatypeProperty", ttl)
        
        # Check for restrictions (1:1 MAY)
        # Profile should have maxCardinality 1 on its relationship to User
        self.assertIn("owl:maxCardinality 1", ttl)
        self.assertIn("owl:inverseOf", ttl)
        
        # User (MUST) relates to Profile (MAY) (1)
        # Profile (MAY) relates to User (MUST) (1)
        # Profile -> User should have minCardinality 1
        self.assertIn("owl:minCardinality 1", ttl)

if __name__ == "__main__":
    unittest.main()
