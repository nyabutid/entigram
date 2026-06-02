import unittest
import os
from entigram.schema_compiler.parser import SchemaParser
from entigram.schema_compiler.compiler import SchemaCompiler

class TestSchemaCompiler(unittest.TestCase):
    def test_basic_compilation(self):
        text = """
ENTITY: User
ATTRIBUTES:
  - id (UUID, PK)
  - username (String)

ENTITY: Post
ATTRIBUTES:
  - id (UUID, PK)
  - title (String)
  - content (String)

RELATIONSHIP: User (1) [MUST] --- [MAY] (MANY) Post
"""
        parser = SchemaParser(text)
        entities, relationships = parser.parse()
        
        self.assertIn("User", entities)
        self.assertIn("Post", entities)
        self.assertEqual(len(relationships), 1)
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        
        self.assertIn("CREATE TABLE IF NOT EXISTS users", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS posts", sql)
        self.assertIn("user_id TEXT", sql)
        self.assertIn("FOREIGN KEY (user_id) REFERENCES users(id)", sql)

    def test_one_to_one_compilation(self):
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
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        
        self.assertIn("CREATE TABLE IF NOT EXISTS profiles", sql)
        self.assertIn("user_id TEXT UNIQUE", sql)
        self.assertIn("FOREIGN KEY (user_id) REFERENCES users(id)", sql)

    def test_composite_pk_compilation(self):
        text = """
ENTITY: OrderItem
ATTRIBUTES:
  - .order_id (UUID)
  - .item_id (UUID)
  - quantity (Integer)
"""
        parser = SchemaParser(text)
        entities, relationships = parser.parse()
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        
        self.assertNotIn("order_id TEXT PRIMARY KEY", sql)
        self.assertNotIn("item_id TEXT PRIMARY KEY", sql)
        self.assertIn("PRIMARY KEY (order_id, item_id)", sql)

    def test_validation_errors(self):
        # 1. Duplicate Attribute
        text = """
ENTITY: Duplicate
ATTRIBUTES:
  - id (UUID, PK)
  - name (String)
  - name (Text)
"""
        parser = SchemaParser(text)
        ents, rels = parser.parse()
        compiler = SchemaCompiler(ents, rels)
        sql = compiler.compile()
        self.assertIn("-- Schema Compilation Failed", sql)
        self.assertIn("duplicate attributes: name", sql)

        # 2. Missing Entity in Relationship
        text = """
ENTITY: A
ATTRIBUTES:
  - id (UUID, PK)
RELATIONSHIP: A (1) [MUST] --- [MAY] (MANY) B
"""
        parser = SchemaParser(text)
        ents, rels = parser.parse()
        compiler = SchemaCompiler(ents, rels)
        sql = compiler.compile()
        self.assertIn("refers to non-existent entity 'B'", sql)

    def test_recursive_relationship(self):
        text = """
ENTITY: Employee
ATTRIBUTES:
  - .id (UUID)
  - name (String)

RELATIONSHIP: Employee (1) [MAY] --- [MAY] (MANY) Employee
"""
        parser = SchemaParser(text)
        entities, relationships = parser.parse()
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        
        self.assertIn("employee_id TEXT", sql)
        self.assertIn("FOREIGN KEY (employee_id) REFERENCES employees(id)", sql)

if __name__ == "__main__":
    unittest.main()
