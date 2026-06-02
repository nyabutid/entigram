import sqlite3
import os
import inflect
from typing import Dict, List, Any
from entigram.schema_compiler.parser import SchemaEntity

p = inflect.engine()

class DomainDiscoverer:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_entity_name(self, table_name: str) -> str:
        singular = p.singular_noun(table_name)
        if not singular:
            singular = table_name
        return singular.capitalize()

    def discover_schema(self) -> str:
        """
        Reverse-engineers a SQLite database into a Schema string.
        """
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # 1. Get Tables
            # This is where 'file is not a database' will usually trigger
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'migrations' AND name NOT LIKE 'crsql_%';")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema_output = []
            for table in tables:
                entity_name = self._get_entity_name(table)
                schema_output.append(f"ENTITY: {entity_name}")
                schema_output.append("ATTRIBUTES:")
                
                cursor.execute(f"PRAGMA table_info({table});")
                cols = cursor.fetchall()
                for col in cols:
                    # cid, name, type, notnull, dflt_value, pk
                    name = col[1]
                    ctype = col[2]
                    is_pk = col[5] == 1
                    
                    prefix = "." if is_pk else "-"
                    attr_line = f"  {prefix} {name} ({ctype})"
                    schema_output.append(attr_line)
                schema_output.append("")

            # 2. Get Relationships (Foreign Keys)
            relationships = []
            for table in tables:
                cursor.execute(f"PRAGMA foreign_key_list({table});")
                fks = cursor.fetchall()
                for fk in fks:
                    # id, seq, table, from, to, on_update, on_delete, match
                    parent_table = fk[2]
                    
                    child_ent = self._get_entity_name(table)
                    parent_ent = self._get_entity_name(parent_table)
                    
                    # Carlis Schema usually expresses this as a relationship line
                    # We'll use a standard 1:MANY MUST/MAY assumption for recovery
                    relationships.append(f"RELATIONSHIP: {parent_ent} (1) [MUST] --- [MAY] (MANY) {child_ent}")

            if relationships:
                schema_output.append("RELATIONSHIPS:")
                # Deduplicate and add
                for rel in sorted(list(set(relationships))):
                    schema_output.append(f"- {rel.replace('RELATIONSHIP: ', '')}")

            conn.close()
            return "\n".join(schema_output)
            
        except sqlite3.DatabaseError as e:
            if "file is not a database" in str(e):
                raise ValueError(f"❌ Error: The file '{self.db_path}' is not a valid SQLite database.")
            raise e
        except Exception as e:
            raise e

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        discoverer = DomainDiscoverer(sys.argv[1])
        print(discoverer.discover_schema())
    else:
        print("Usage: python -m entigram.schema_compiler.discoverer <db_path>")
