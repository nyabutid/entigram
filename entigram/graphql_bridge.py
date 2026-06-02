import re
from typing import Dict, List, Optional

class GraphQLBridge:
    """
    Translates GraphQL-LD queries into SPARQL algebra.
    Follows the 'Semantic Governance' principle of keeping query algebra local to the federated context.
    """
    def __init__(self, context: Dict[str, str], prefixes: Optional[Dict[str, str]] = None):
        self.context = context
        self.prefixes = prefixes or {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "mk": "http://entigram.ai/ontology/core#"
        }

    def _generate_prefixes(self) -> str:
        return "\n".join([f"PREFIX {k}: <{v}>" for k, v in self.prefixes.items()])

    def translate(self, graphql_query: str) -> str:
        # 1. Normalize and tokenize
        tokens = re.findall(r'\w+|[{}()]|[:,]', graphql_query)
        if not tokens:
            return "# Error: Empty query"

        if tokens[0] == "query":
            tokens.pop(0)

        # 2. Parse root
        if tokens[0] != "{":
            return "# Error: Missing starting brace"
        tokens.pop(0)

        root_entity = tokens.pop(0)
        args = {}
        if tokens[0] == "(":
            tokens.pop(0)
            while tokens[0] != ")":
                key = tokens.pop(0)
                if tokens[0] == ":": tokens.pop(0)
                val = tokens.pop(0)
                args[key] = val
                if tokens[0] == ",": tokens.pop(0)
            tokens.pop(0)

        if tokens[0] != "{":
            return "# Error: Expected { after entity"
        tokens.pop(0)

        # 3. Recursive field parsing
        select_vars = set()
        where_clauses = []
        
        def parse_fields(current_subject, current_tokens):
            while current_tokens and current_tokens[0] != "}":
                field = current_tokens.pop(0)
                
                # Check for nested block
                if current_tokens and current_tokens[0] == "{":
                    current_tokens.pop(0)
                    nested_subject = f"?{field}"
                    
                    field_uri = self.context.get(field, f"mk:{field}")
                    field_pred = f"<{field_uri}>" if field_uri.startswith("http") else field_uri
                    where_clauses.append(f"  {current_subject} {field_pred} {nested_subject} .")
                    
                    parse_fields(nested_subject, current_tokens)
                    if current_tokens: current_tokens.pop(0) # pop }
                else:
                    # Leaf field
                    select_vars.add(f"?{field}")
                    field_uri = self.context.get(field, f"mk:{field}")
                    field_pred = f"<{field_uri}>" if field_uri.startswith("http") else field_uri
                    where_clauses.append(f"  OPTIONAL {{ {current_subject} {field_pred} ?{field} }}")

        root_uri = self.context.get(root_entity, f"mk:{root_entity}")
        root_pred = f"<{root_uri}>" if root_uri.startswith("http") else root_uri
        where_clauses.append(f"  ?subject a {root_pred} .")
        
        parse_fields("?subject", tokens)

        # 4. Construct SPARQL
        sparql = self._generate_prefixes() + "\n"
        sparql += f"SELECT {' '.join(sorted(list(select_vars)))}\n"
        sparql += "WHERE {\n"
        sparql += "\n".join(where_clauses)
        sparql += "\n}"
        
        if "first" in args:
            sparql += f"\nLIMIT {args['first']}"
        if "offset" in args:
            sparql += f"\nOFFSET {args['offset']}"
            
        return sparql
