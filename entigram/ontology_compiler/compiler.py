from typing import List, Dict
from entigram.schema_compiler.parser import SchemaEntity, SchemaRelationship
from datetime import datetime

class OntologyCompiler:
    def __init__(self, entities: Dict[str, SchemaEntity], relationships: List[SchemaRelationship]):
        self.entities = entities
        self.relationships = relationships
        self.base_uri = "http://entigram.ai/ontology/custom#"

    def compile(self) -> str:
        """
        Translates the Schema into a formal Turtle (TTL) RDF ontology.
        """
        ttl_lines = [
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            f"@prefix mk: <{self.base_uri}> .",
            "",
            "mk:Ontology a owl:Ontology ;",
            f"    rdfs:label \"Entigram Generated Ontology\" ;",
            f"    mk:generatedAt \"{datetime.now().isoformat()}\" .\n"
        ]

        # 1. Classes (Entities)
        for name in self.entities.keys():
            ttl_lines.append(f"mk:{name} a owl:Class ;")
            ttl_lines.append(f"    rdfs:label \"{name}\" .\n")

        # 2. Datatype Properties (Attributes)
        for ent_name, entity in self.entities.items():
            for attr in entity.attributes:
                prop_name = f"{ent_name}_{attr['name']}"
                xsd_type = self._map_to_xsd(attr['type'])
                
                ttl_lines.append(f"mk:{prop_name} a owl:DatatypeProperty ;")
                ttl_lines.append(f"    rdfs:domain mk:{ent_name} ;")
                ttl_lines.append(f"    rdfs:range {xsd_type} ;")
                ttl_lines.append(f"    rdfs:label \"{attr['name']}\" .\n")

        # 3. Object Properties (Relationships)
        for rel in self.relationships:
            prop_name = f"relates_{rel.entity_a}_to_{rel.entity_b}"
            ttl_lines.append(f"mk:{prop_name} a owl:ObjectProperty ;")
            ttl_lines.append(f"    rdfs:domain mk:{rel.entity_a} ;")
            ttl_lines.append(f"    rdfs:range mk:{rel.entity_b} ;")
            ttl_lines.append(f"    rdfs:label \"relates\" .\n")

            # Cardinality Restrictions for Entity A -> Entity B
            # (Based on Degree B and Part B)
            res_a = self._generate_restriction(rel.entity_a, prop_name, rel.degree_b, rel.part_b)
            if res_a: ttl_lines.append(res_a)

            # Inverse Relationship and Restrictions for Entity B -> Entity A
            # (Based on Degree A and Part A)
            inv_prop = f"relates_{rel.entity_b}_to_{rel.entity_a}"
            ttl_lines.append(f"mk:{inv_prop} a owl:ObjectProperty ;")
            ttl_lines.append(f"    owl:inverseOf mk:{prop_name} ;")
            ttl_lines.append(f"    rdfs:domain mk:{rel.entity_b} ;")
            ttl_lines.append(f"    rdfs:range mk:{rel.entity_a} ;")
            ttl_lines.append(f"    rdfs:label \"inverse_relates\" .\n")

            res_b = self._generate_restriction(rel.entity_b, inv_prop, rel.degree_a, rel.part_a)
            if res_b: ttl_lines.append(res_b)

        return "\n".join(ttl_lines)

    def _generate_restriction(self, domain_entity: str, prop_name: str, degree: str, participation: str) -> str:
        """Generates OWL restrictions based on Schema cardinality."""
        restrictions = []
        if degree == '1':
            restrictions.append("        a owl:Restriction ;")
            restrictions.append(f"        owl:onProperty mk:{prop_name} ;")
            restrictions.append("        owl:maxCardinality 1")
            if participation == 'MUST':
                restrictions.append("    ] , [")
                restrictions.append("        a owl:Restriction ;")
                restrictions.append(f"        owl:onProperty mk:{prop_name} ;")
                restrictions.append("        owl:minCardinality 1")
        elif participation == 'MUST':
            # MANY MUST
            restrictions.append("        a owl:Restriction ;")
            restrictions.append(f"        owl:onProperty mk:{prop_name} ;")
            restrictions.append("        owl:minCardinality 1")
        
        if not restrictions:
            return ""

        ttl = f"mk:{domain_entity} rdfs:subClassOf [\n"
        ttl += "\n".join(restrictions)
        ttl += "\n    ] .\n"
        return ttl

    def _map_to_xsd(self, attr_type: str) -> str:
        t = attr_type.lower()
        if "string" in t: return "xsd:string"
        if "uuid" in t: return "xsd:string"
        if "int" in t: return "xsd:integer"
        if "decimal" in t: return "xsd:decimal"
        if "date" in t: return "xsd:dateTime"
        if "bool" in t: return "xsd:boolean"
        return "xsd:string"
