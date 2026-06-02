import unittest
from entigram.schema_compiler.parser import SchemaParser

class TestSchemaParserBlock(unittest.TestCase):
    def test_block_syntax(self):
        text = """
ENTITY User {
    id UUID PK
    username String UNIQUE
}

ENTITY Post {
    .id UUID
    title String MUST
    content Text
}

RELATIONSHIP: User (1) [MUST] --- [MAY] (MANY) Post
"""
        parser = SchemaParser(text)
        entities, relationships = parser.parse()
        
        self.assertIn("User", entities)
        self.assertIn("Post", entities)
        self.assertEqual(len(relationships), 1)
        
        user = entities["User"]
        self.assertEqual(user.attributes[0]["name"], "id")
        self.assertTrue(user.attributes[0]["pk"])
        self.assertEqual(user.attributes[1]["name"], "username")
        self.assertIn("UNIQUE", user.attributes[1]["constraints"])
        
        post = entities["Post"]
        self.assertEqual(post.attributes[0]["name"], "id")
        self.assertTrue(post.attributes[0]["pk"])
        self.assertIn("MUST", post.attributes[1]["constraints"])

if __name__ == "__main__":
    unittest.main()
