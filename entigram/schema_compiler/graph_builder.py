import networkx as nx
from typing import List, Dict
from .parser import SchemaEntity, SchemaRelationship

class SchemaGraphBuilder:
    def __init__(self, entities: Dict[str, SchemaEntity], relationships: List[SchemaRelationship]):
        self.entities = entities
        self.relationships = relationships
        self.graph = nx.MultiDiGraph()

    def build(self) -> nx.MultiDiGraph:
        """
        Builds a directed graph where nodes are entities and edges are relationships.
        Edges carry metadata about cardinality and participation.
        """
        # Add nodes
        for name, entity in self.entities.items():
            self.graph.add_node(name, attributes=entity.attributes)

        # Add edges
        for rel in self.relationships:
            # We add two edges for each relationship to represent the bidirectional nature
            # or just one if we want to represent the "owner" direction.
            # In Schema, it's usually better to represent the structural dependency.
            self.graph.add_edge(
                rel.entity_a, 
                rel.entity_b, 
                degree=rel.degree_b, 
                participation=rel.part_b,
                label=f"{rel.degree_a}:{rel.degree_b}"
            )
            self.graph.add_edge(
                rel.entity_b, 
                rel.entity_a, 
                degree=rel.degree_a, 
                participation=rel.part_a,
                label=f"{rel.degree_b}:{rel.degree_a}"
            )
            
        return self.graph

    def to_mermaid(self) -> str:
        """
        Generates a Mermaid ER Diagram string representing the Schema.
        Uses a highly defensive syntax for compatibility with Mermaid 11+.
        """
        lines = ["erDiagram"]

        def sanitize(name):
            # Mermaid entities must be alphanumeric
            import re
            return re.sub(r'[^a-zA-Z0-9]', '_', name)

        # Entities
        for name, entity in self.entities.items():
            s_name = sanitize(name)
            lines.append(f"    {s_name} {{")
            for attr in entity.attributes:
                # Format: type name PK "comment"
                pk_tag = " PK" if attr['pk'] else ""
                # Use quoted comments for any metadata
                comment = ""
                if attr['edge']:
                    comment = ' "[EDGE]"'
                elif attr.get('external_link'):
                    comment = f' "[EXTERNAL: {attr["external_link"]}]"'

                # Ensure type and name are single words
                safe_type = sanitize(attr['type']) if attr['type'] else "string"
                safe_name = sanitize(attr['name'])

                lines.append(f"        {safe_type} {safe_name}{pk_tag}{comment}")
            lines.append("    }")

        # Relationships
        for rel in self.relationships:
            s1_ent = sanitize(rel.entity_a)
            s2_ent = sanitize(rel.entity_b)

            # Symbols
            if rel.degree_a == "1":
                s1 = "||" if rel.part_a == "MUST" else "|o"
            else:
                s1 = "}|" if rel.part_a == "MUST" else "}o"

            if rel.degree_b == "1":
                s2 = "||" if rel.part_b == "MUST" else "o|"
            else:
                s2 = "|{" if rel.part_b == "MUST" else "o{"

            # Quoted label for maximum safety
            lines.append(f"    {s1_ent} {s1}--{s2} {s2_ent} : \"relates\"")

        return "\n".join(lines)
