import unittest
from pathlib import Path
from entigram.schema_compiler.parser import SchemaParser
from entigram.schema_compiler.compiler import SchemaCompiler

class TestNewDomains(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace_new_domains")
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        
    def tearDown(self):
        if self.test_dir.exists():
            import shutil
            shutil.rmtree(self.test_dir)

    def test_technical_due_diligence_schema(self):
        schema_path = self.test_dir / "TechnicalDueDiligence_schema.lds"
        schema_path.write_text("""
        ENTITY Target_Company { id UUID PK }
        ENTITY Architecture_Review { id UUID PK }
        ENTITY Code_Quality_Audit { id UUID PK }
        ENTITY Security_Assessment { id UUID PK }
        """)
        
        parser = SchemaParser(schema_path.read_text())
        entities, relationships = parser.parse()
        
        self.assertIn("Target_Company", entities)
        self.assertIn("Architecture_Review", entities)
        self.assertIn("Code_Quality_Audit", entities)
        self.assertIn("Security_Assessment", entities)
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        self.assertIn("CREATE TABLE IF NOT EXISTS target_companies", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS architecture_reviews", sql)
        
    def test_content_publishing_schema(self):
        schema_path = self.test_dir / "ContentPublishing_schema.lds"
        schema_path.write_text("""
        ENTITY Publication { id UUID PK }
        ENTITY Article { id UUID PK }
        ENTITY Concept_Reference { id UUID PK }
        ENTITY Subscriber_Metric { id UUID PK }
        """)
        
        parser = SchemaParser(schema_path.read_text())
        entities, relationships = parser.parse()
        
        self.assertIn("Publication", entities)
        self.assertIn("Article", entities)
        self.assertIn("Concept_Reference", entities)
        self.assertIn("Subscriber_Metric", entities)
        
        compiler = SchemaCompiler(entities, relationships)
        sql = compiler.compile()
        self.assertIn("CREATE TABLE IF NOT EXISTS publications", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS articles", sql)

if __name__ == '__main__':
    unittest.main()
