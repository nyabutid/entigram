import re
from typing import List, Dict, Any

class SchemaEntity:
    def __init__(self, name: str):
        self.name = name
        self.attributes = []
        self.external_ref = None # e.g. "SupplyChain::Supplier"

    def add_attribute(self, name: str, attr_type: str, is_pk: bool, is_edge: bool, constraints: List[str] = None, external_link: str = None):
        self.attributes.append({
            "name": name,
            "type": attr_type,
            "pk": is_pk,
            "edge": is_edge,
            "constraints": constraints or [],
            "external_link": external_link # e.g. "SupplyChain::Supplier.id"
        })

class SchemaRelationship:
    def __init__(self, entity_a: str, degree_a: str, part_a: str, 
                 entity_b: str, degree_b: str, part_b: str):
        self.entity_a = entity_a
        self.degree_a = degree_a
        self.part_a = part_a
        self.entity_b = entity_b
        self.degree_b = degree_b
        self.part_b = part_b

class SchemaParser:
    def __init__(self, text: str):
        self.text = self._strip_comments(text)
        self.entities = {}
        self.relationships = []

    def _strip_comments(self, text: str) -> str:
        # Remove multi-line comments /* ... */
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        # Remove single-line comments # or //
        lines = []
        for line in text.split('\n'):
            line = re.sub(r'(#|//).*$', '', line)
            lines.append(line)
        return '\n'.join(lines)

    def parse(self):
        # 0. Handle EXTERNAL_ENTITY Package::Entity { ... }
        ext_block_pattern = r'EXTERNAL_ENTITY:?\s+([@\w/-]+)::(\w+)\s*\{([^}]*)\}'
        for match in re.finditer(ext_block_pattern, self.text, re.DOTALL | re.IGNORECASE):
            pkg_name = match.group(1)
            ent_name = match.group(2)
            content = match.group(3)
            
            entity = SchemaEntity(ent_name)
            entity.external_ref = f"{pkg_name}::{ent_name}"
            self._parse_block_content(entity, content)
            self.entities[ent_name] = entity
        
        # 1. Handle Block-style syntax: ENTITY Name [ANNOTATION] { ... }
        block_pattern = r'(?<!EXTERNAL_)ENTITY:?\s+(\w+)(?:\s+\[[^\]]+\])?\s*\{([^}]*)\}'
        for match in re.finditer(block_pattern, self.text, re.DOTALL | re.IGNORECASE):
            entity_name = match.group(1)
            content = match.group(2)
            
            if entity_name in self.entities: continue # Skip if already handled as external

            entity = SchemaEntity(entity_name)
            self._parse_block_content(entity, content)
            self.entities[entity_name] = entity

        # Now handle the traditional bulleted/line-based syntax
        lines = self.text.split('\n')
        current_entity = None
        in_relationships_block = False
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith("/*") or line.startswith("EXTERNAL_ENTITY") or "{" in line:
                continue
            
            # Start of relationships block
            if line.upper().startswith("RELATIONSHIPS:"):
                in_relationships_block = True
                continue

            # Entity matching
            if line.upper().startswith("ENTITY:") and "{" not in line:
                in_relationships_block = False
                entity_name = line[len("ENTITY:"):].strip()
                if "::" in entity_name:
                    pkg, ent = entity_name.split("::")
                    entity_name = ent
                    if entity_name not in self.entities:
                        current_entity = SchemaEntity(entity_name)
                        current_entity.external_ref = f"{pkg}::{ent}"
                        self.entities[entity_name] = current_entity
                    else:
                        current_entity = self.entities[entity_name]
                
                elif entity_name not in self.entities:
                    current_entity = SchemaEntity(entity_name)
                    self.entities[entity_name] = current_entity
                else:
                    current_entity = self.entities[entity_name]
            
            # Skip ATTRIBUTES: header if present
            elif line.upper().startswith("ATTRIBUTES:"):
                continue
                
            # Attribute matching (traditional style)
            elif (line.startswith("-") or line.startswith(".")) and current_entity and not in_relationships_block:
                is_pk = "PK" in line.upper() or "IDENTIFIER" in line.upper() or line.startswith(".")
                is_edge = "[EDGE_BOUNDARY]" in line.upper()
                
                # Check for [EXTERNAL: Package::Entity.Attr]
                ext_link = None
                ext_match = re.search(r'\[EXTERNAL:\s*([^\]]+)\]', line, re.IGNORECASE)
                if ext_match:
                    ext_link = ext_match.group(1).strip()

                match = re.search(r'[-.]\s*(\.?)([^\s\(]+)\s*(?:\(([^\)]+)\))?', line)
                if match:
                    prefix = match.group(1)
                    attr_name = match.group(2).strip()
                    if prefix == ".":
                        is_pk = True
                        
                    attr_info = match.group(3) if match.group(3) else "String"
                    parts = [p.strip() for p in attr_info.split(',')]
                    attr_type = parts[0]
                    
                    constraints = []
                    for p in parts[1:]:
                        p_upper = p.upper()
                        if p_upper in ["UNIQUE", "MUST", "NOT NULL", "MAY"]:
                            constraints.append(p_upper)
                        elif p_upper in ["PK", "IDENTIFIER"]:
                            is_pk = True

                    current_entity.add_attribute(attr_name, attr_type, is_pk, is_edge, constraints, external_link=ext_link)

            # Relationship matching (Strict Format or Bulleted)
            elif (line.upper().startswith("RELATIONSHIP") or 
                  (line.startswith("-") and in_relationships_block)):
                
                # Strip leading dash and "RELATIONSHIP" (with optional colon)
                clean_line = re.sub(r'^-|RELATIONSHIP:?\s*', '', line, flags=re.IGNORECASE).strip()
                
                # Regex for: EntityA (Degree) [Part] --- [Part] (Degree) EntityB
                # Matches: Entigram_Project (1) [MUST] --- [MAY] (MANY) Entigram_Package
                # Also matches shorthand: Idea (1) --- (1) Partner_Organization
                rel_match = re.search(r'(\w+)\s*[\(\[]?(1|ONE|MANY)[\)\]]?\s*(?:[\(\[]?(MUST|MAY)[\)\]]?)?\s*---\s*(?:[\(\[]?(MUST|MAY)[\)\]]?)?\s*[\(\[]?(1|ONE|MANY)[\)\]]?\s*(\w+)', clean_line, re.IGNORECASE)
                
                if rel_match:
                    self.relationships.append(self._create_rel(
                        rel_match.group(1), rel_match.group(2), rel_match.group(3), 
                        rel_match.group(4), rel_match.group(5), rel_match.group(6)
                    ))
                
                # If it's a bullet but didn't match the strict format, try natural language fallback
                elif line.startswith("-") and in_relationships_block:
                    rel = None
                    # Pattern: EntityA has many EntityB
                    nl_match = re.search(r'-\s+(\w+)\s+has\s+many\s+(\w+)', line, re.IGNORECASE)
                    if nl_match:
                        rel = self._create_rel(nl_match.group(1), "1", "MUST", "MAY", "MANY", nl_match.group(2))
                    else:
                        # Pattern: EntityA belongs to one EntityB
                        nl_match_2 = re.search(r'-\s+(\w+)\s+(?:must|may)?\s*belong\s+to\s+(?:one|1)\s+(\w+)', line, re.IGNORECASE)
                        if nl_match_2:
                            part = "MUST" if "must" in line.lower() else "MAY"
                            rel = self._create_rel(nl_match_2.group(2), "1", "MUST", part, "MANY", nl_match_2.group(1))
                    
                    if rel:
                        # Deduplication: Check if this pair already has a relationship recorded
                        is_duplicate = False
                        for existing in self.relationships:
                            pair_a = {existing.entity_a.lower(), existing.entity_b.lower()}
                            pair_b = {rel.entity_a.lower(), rel.entity_b.lower()}
                            if pair_a == pair_b:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            self.relationships.append(rel)
        
        return self.entities, self.relationships

    def _parse_block_content(self, entity, content):
        for attr_line in content.split('\n'):
            attr_line = attr_line.strip()
            if not attr_line: continue
            
            ext_link = None
            ext_match = re.search(r'\[EXTERNAL:\s*([^\]]+)\]', attr_line, re.IGNORECASE)
            if ext_match:
                ext_link = ext_match.group(1).strip()

            parts = attr_line.split()
            if len(parts) >= 2:
                attr_name = parts[0]
                attr_type = parts[1]
                is_pk = "PK" in [p.upper() for p in parts[2:]]
                
                if attr_name.startswith("."):
                    attr_name = attr_name[1:]
                    is_pk = True
                    
                entity.add_attribute(attr_name, attr_type, is_pk, False, [p.upper() for p in parts[2:] if p.upper() not in ["PK"]], external_link=ext_link)

    def _create_rel(self, ent_a, deg_a, part_a, part_b, deg_b, ent_b):
        def normalize_card(c):
            c = str(c).strip().upper()
            return "1" if c in ["1", "ONE"] else "MANY"
            
        # Smart Matching against existing entities (handles case and plural/singular)
        def find_entity(name):
            n = name.lower()
            for existing in self.entities.keys():
                ext = existing.lower()
                # Exact match or simple plural match (e.g., 'Shoes' -> 'Shoe')
                if n == ext or n == ext + "s" or ext == n + "s":
                    return existing
            return name # Fallback to original if no match found

        ent_a = find_entity(ent_a)
        ent_b = find_entity(ent_b)
            
        return SchemaRelationship(
            entity_a=ent_a,
            degree_a=normalize_card(deg_a),
            part_a=part_a.upper() if part_a else "MAY",
            part_b=part_b.upper() if part_b else "MAY",
            degree_b=normalize_card(deg_b),
            entity_b=ent_b
        )
