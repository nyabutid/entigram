import unittest
from entigram.graphql_bridge import GraphQLBridge

class TestGraphQLBridgeAdvanced(unittest.TestCase):
    def setUp(self):
        self.context = {
            "Patient": "http://hl7.org/fhir/Patient",
            "name": "http://hl7.org/fhir/Patient.name",
            "Observation": "http://hl7.org/fhir/Observation",
            "value": "http://hl7.org/fhir/Observation.value",
            "hasObservation": "mk:hasObservation"
        }
        self.bridge = GraphQLBridge(self.context)

    def test_nested_query(self):
        graphql = """
        query {
          Patient {
            name
            hasObservation {
              value
            }
          }
        }
        """
        sparql = self.bridge.translate(graphql)
        
        # Check for nested pattern
        # Prefixed names should not have <>, full URIs should.
        self.assertIn("?subject mk:hasObservation ?hasObservation", sparql)
        self.assertIn("?hasObservation <http://hl7.org/fhir/Observation.value> ?value", sparql)
        self.assertIn("SELECT ?name ?value", sparql)

    def test_pagination(self):
        graphql = """
        query {
          Patient(first: 10, offset: 20) {
            name
          }
        }
        """
        sparql = self.bridge.translate(graphql)
        self.assertIn("LIMIT 10", sparql)
        self.assertIn("OFFSET 20", sparql)

    def test_optional_fields(self):
        # By default, we should use OPTIONAL for attributes to avoid failing the whole query if one property is missing
        graphql = """
        {
          Patient {
            name
            birthDate
          }
        }
        """
        sparql = self.bridge.translate(graphql)
        self.assertIn("OPTIONAL { ?subject <http://hl7.org/fhir/Patient.name> ?name }", sparql)

if __name__ == "__main__":
    unittest.main()
