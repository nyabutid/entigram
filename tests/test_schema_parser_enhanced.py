import unittest
from entigram.schema_compiler.parser import SchemaParser

class TestSchemaParserEnhanced(unittest.TestCase):
    def test_dot_pk_notation(self):
        text = """
        ENTITY: User
        ATTRIBUTES:
          - .id (UUID)
          - name (String)
        """
        parser = SchemaParser(text)
        entities, _ = parser.parse()
        self.assertIn("User", entities)
        attrs = entities["User"].attributes
        self.assertTrue(attrs[0]["pk"])
        self.assertEqual(attrs[0]["name"], "id")
        self.assertFalse(attrs[1]["pk"])

    def test_attributes_block_skip(self):
        text = """
        ENTITY: Task
        ATTRIBUTES:
          - id (UUID, PK)
          - title
        """
        parser = SchemaParser(text)
        entities, _ = parser.parse()
        self.assertIn("Task", entities)
        self.assertEqual(len(entities["Task"].attributes), 2)

    def test_relationship_parsing(self):
        text = """
        ENTITY: Project
        ENTITY: Task
        RELATIONSHIP: Project (1) [MUST] --- [MAY] (MANY) Task
        """
        parser = SchemaParser(text)
        entities, relationships = parser.parse()
        self.assertEqual(len(relationships), 1)
        rel = relationships[0]
        self.assertEqual(rel.entity_a, "Project")
        self.assertEqual(rel.entity_b, "Task")
        self.assertEqual(rel.degree_a, "1")
        self.assertEqual(rel.degree_b, "MANY")
        self.assertEqual(rel.part_a, "MUST")
        self.assertEqual(rel.part_b, "MAY")

if __name__ == "__main__":
    unittest.main()
