import unittest
from entigram.graphql_bridge import GraphQLBridge

class TestGraphQLBridge(unittest.TestCase):
    def test_basic_translation(self):
        context = {
            "Patient": "http://hl7.org/fhir/Patient",
            "name": "http://hl7.org/fhir/Patient.name",
            "birthDate": "http://hl7.org/fhir/Patient.birthDate"
        }
        bridge = GraphQLBridge(context)
        
        graphql = """
        query {
          Patient {
            name
            birthDate
          }
        }
        """
        
        sparql = bridge.translate(graphql)
        
        # Check for variables in SELECT (order independent)
        self.assertIn("?name", sparql.split("WHERE")[0])
        self.assertIn("?birthDate", sparql.split("WHERE")[0])
        
        self.assertIn("?subject a <http://hl7.org/fhir/Patient>", sparql)
        self.assertIn("OPTIONAL { ?subject <http://hl7.org/fhir/Patient.name> ?name }", sparql)
        self.assertIn("OPTIONAL { ?subject <http://hl7.org/fhir/Patient.birthDate> ?birthDate }", sparql)

    def test_translation_without_query_keyword(self):
        context = {"Account": "mk:SalesforceAccount", "id": "mk:sf_id"}
        bridge = GraphQLBridge(context)
        
        graphql = "{ Account { id } }"
        sparql = bridge.translate(graphql)
        
        self.assertIn("SELECT ?id", sparql)
        self.assertIn("?subject a mk:SalesforceAccount", sparql)

if __name__ == "__main__":
    unittest.main()
