import inflect
from typing import List, Dict
from .parser import SchemaEntity, SchemaRelationship

p = inflect.engine()

class SchemaCompiler:
    def __init__(self, entities: Dict[str, SchemaEntity], relationships: List[SchemaRelationship]):
        self.entities = entities
        self.relationships = relationships
        self.type_map = {
            "UUID": "TEXT",
            "String": "TEXT",
            "Text": "TEXT",
            "Decimal": "REAL",
            "DateTime": "TEXT",
            "Date": "TEXT",
            "Integer": "INTEGER",
            "Int": "INTEGER",
            "Boolean": "INTEGER",
            "Float": "REAL",
            "JSON": "TEXT"
        }

    def _get_table_name(self, entity_name: str) -> str:
        plural = p.plural(entity_name.lower())
        return plural

    def _get_pk_name(self, entity_name: str) -> str:
        entity = self.entities.get(entity_name)
        if entity:
            for attr in entity.attributes:
                if attr["pk"]:
                    return attr["name"]
        return "id" # Default fallback

    def validate(self) -> List[str]:
        """
        Validates the Schema model for consistency and common errors.
        Returns a list of error messages.
        """
        errors = []
        
        # 1. Check for entities with no PK
        for name, entity in self.entities.items():
            pk_count = sum(1 for attr in entity.attributes if attr["pk"])
            if pk_count == 0:
                errors.append(f"Entity '{name}' has no primary key defined.")
            
            # 2. Check for duplicate attribute names
            attr_names = [attr["name"] for attr in entity.attributes]
            if len(attr_names) != len(set(attr_names)):
                duplicates = set([x for x in attr_names if attr_names.count(x) > 1])
                errors.append(f"Entity '{name}' has duplicate attributes: {', '.join(duplicates)}")

        # 3. Check relationships
        for rel in self.relationships:
            if rel.entity_a not in self.entities:
                errors.append(f"Relationship refers to non-existent entity '{rel.entity_a}'.")
            if rel.entity_b not in self.entities:
                errors.append(f"Relationship refers to non-existent entity '{rel.entity_b}'.")

        return errors

    def compile(self, enable_crsqlite: bool = False) -> str:
        errors = self.validate()
        if errors:
            error_str = "\n".join([f"-- ERROR: {e}" for e in errors])
            return f"-- Schema Compilation Failed\n{error_str}"

        sql_lines = [
            "-- Entigram Generated Schema",
            "-- Flyway Versioned Migration",
            "PRAGMA foreign_keys = ON;\n"
        ]
        
        # 1. Create Tables
        for entity_name, entity in self.entities.items():
            table_name = self._get_table_name(entity_name)
            cols = []
            fks = []
            pk_attrs = [attr["name"] for attr in entity.attributes if attr["pk"]]
            
            for attr in entity.attributes:
                sql_type = self.type_map.get(attr["type"], "TEXT")
                col_def = f"{attr['name']} {sql_type}"
                
                # If it's a single PK, we can keep it inline, but for composite we MUST use table constraint.
                # To be safe and consistent, let's use table constraint if pk_attrs > 1.
                if attr["pk"] and len(pk_attrs) == 1:
                    col_def += " PRIMARY KEY"
                
                # Apply constraints
                for const in attr.get("constraints", []):
                    if const == "UNIQUE":
                        col_def += " UNIQUE"
                    elif const in ["MUST", "NOT NULL"]:
                        col_def += " NOT NULL"
                
                cols.append(col_def)
            
            if len(pk_attrs) > 1:
                cols.append(f"PRIMARY KEY ({', '.join(pk_attrs)})")
            
            # Handle Foreign Keys (1:MANY and 1:1)
            for rel in self.relationships:
                # 1:MANY (FK goes to the MANY side)
                if rel.degree_a == '1' and rel.degree_b == 'MANY' and rel.entity_b == entity_name:
                    parent_pk = self._get_pk_name(rel.entity_a)
                    fk_col = f"{rel.entity_a.lower()}_{parent_pk}"
                    cols.append(f"{fk_col} TEXT")
                    fks.append(f"FOREIGN KEY ({fk_col}) REFERENCES {self._get_table_name(rel.entity_a)}({parent_pk})")
                elif rel.degree_b == '1' and rel.degree_a == 'MANY' and rel.entity_a == entity_name:
                    parent_pk = self._get_pk_name(rel.entity_b)
                    fk_col = f"{rel.entity_b.lower()}_{parent_pk}"
                    cols.append(f"{fk_col} TEXT")
                    fks.append(f"FOREIGN KEY ({fk_col}) REFERENCES {self._get_table_name(rel.entity_b)}({parent_pk})")
                
                # 1:1 (FK goes to the side that is 'MAY' if the other is 'MUST', else entity_b)
                elif rel.degree_a == '1' and rel.degree_b == '1':
                    if rel.entity_b == entity_name:
                        # Determine if this side should hold the FK
                        # Logic: If B is MAY and A is MUST, B holds the FK.
                        # If both are MAY or both are MUST, we pick B as the default.
                        if (rel.part_b == 'MAY' and rel.part_a == 'MUST') or (rel.part_a == rel.part_b):
                            parent_pk = self._get_pk_name(rel.entity_a)
                            fk_col = f"{rel.entity_a.lower()}_{parent_pk}"
                            cols.append(f"{fk_col} TEXT UNIQUE")
                            fks.append(f"FOREIGN KEY ({fk_col}) REFERENCES {self._get_table_name(rel.entity_a)}({parent_pk})")
                    elif rel.entity_a == entity_name:
                        # If A is MAY and B is MUST, A holds the FK.
                        if rel.part_a == 'MAY' and rel.part_b == 'MUST':
                            parent_pk = self._get_pk_name(rel.entity_b)
                            fk_col = f"{rel.entity_b.lower()}_{parent_pk}"
                            cols.append(f"{fk_col} TEXT UNIQUE")
                            fks.append(f"FOREIGN KEY ({fk_col}) REFERENCES {self._get_table_name(rel.entity_b)}({parent_pk})")

            all_defs = cols + fks
            create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n  " + ",\n  ".join(all_defs) + "\n);"
            sql_lines.append(create_sql)

        # 2. Handle Many-to-Many (Associative Tables)
        for rel in self.relationships:
            if rel.degree_a == 'MANY' and rel.degree_b == 'MANY':
                table_name = f"{rel.entity_a.lower()}_{rel.entity_b.lower()}"
                pk_a = self._get_pk_name(rel.entity_a)
                pk_b = self._get_pk_name(rel.entity_b)
                
                col_a = f"{rel.entity_a.lower()}_{pk_a}"
                col_b = f"{rel.entity_b.lower()}_{pk_b}"
                
                assoc_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
                assoc_sql += f"  {col_a} TEXT,\n"
                assoc_sql += f"  {col_b} TEXT,\n"
                assoc_sql += f"  PRIMARY KEY ({col_a}, {col_b}),\n"
                assoc_sql += f"  FOREIGN KEY ({col_a}) REFERENCES {self._get_table_name(rel.entity_a)}({pk_a}),\n"
                assoc_sql += f"  FOREIGN KEY ({col_b}) REFERENCES {self._get_table_name(rel.entity_b)}({pk_b})\n"
                assoc_sql += ");"
                sql_lines.append(assoc_sql)

        # 3. CR-SQLite Integration (Enable Conflict-free Replicated Relations)
        if enable_crsqlite:
            sql_lines.append("\n-- CR-SQLite Configuration")
            for entity_name in self.entities.keys():
                table_name = self._get_table_name(entity_name)
                sql_lines.append(f"SELECT crsql_as_crr('{table_name}');")
            
            for rel in self.relationships:
                if rel.degree_a == 'MANY' and rel.degree_b == 'MANY':
                    table_name = f"{rel.entity_a.lower()}_{rel.entity_b.lower()}"
                    sql_lines.append(f"SELECT crsql_as_crr('{table_name}');")
            
        return "\n\n".join(sql_lines)
