import unittest
from pathlib import Path
from entigram.schema_compiler.parser import SchemaParser
from entigram.schema_compiler.compiler import SchemaCompiler

class TestBusinessEcosystem(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path(__file__).parent.parent
        self.templates_dir = self.workspace_root / "entigram" / "templates"
        
    def test_startup_founder_schema(self):
        schema_path = self.templates_dir / "startup_founder" / "schema.lds"
        self.assertTrue(schema_path.exists(), f"StartupFounder schema.lds is missing at {schema_path}")
        
        parser = SchemaParser(schema_path.read_text())
        entities, relationships = parser.parse()
        
        self.assertIn("Idea", entities)
        self.assertIn("Value_Proposition", entities)
        self.assertIn("Market_Segment", entities)
        self.assertIn("Competitor", entities)
        self.assertIn("User_Persona", entities)
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        self.assertIn("CREATE TABLE IF NOT EXISTS ideas", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS value_propositions", sql)
        
    def test_business_strategy_schema(self):
        schema_path = self.templates_dir / "business_strategy" / "schema.lds"
        self.assertTrue(schema_path.exists(), f"BusinessStrategy schema.lds is missing at {schema_path}")
        
        parser = SchemaParser(schema_path.read_text())
        entities, relationships = parser.parse()
        
        self.assertIn("Strategic_Goal", entities)
        self.assertIn("KPI", entities)
        self.assertIn("Revenue_Stream", entities)
        self.assertIn("Cost_Structure", entities)
        self.assertIn("Strategic_Initiative", entities)
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        self.assertIn("CREATE TABLE IF NOT EXISTS strategic_goals", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS kpis", sql)

if __name__ == '__main__':
    unittest.main()
