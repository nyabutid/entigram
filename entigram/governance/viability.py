from typing import List, Dict, Any
from entigram.schema_compiler.parser import SchemaParser

class MVDValidator:
    """
    Enforces Minimum Viable Domain (MVD) rules for Entigram logical models.
    Ensures that a schema is not just structurally sound, but semantically viable for federation.
    """
    def __init__(self, schema_text: str):
        self.parser = SchemaParser(schema_text)
        self.entities, self.relationships = self.parser.parse()

    def validate(self) -> List[Dict[str, str]]:
        """
        Runs MVD validation rules.
        Returns a list of issues (severity, message).
        """
        issues = []

        # Rule 1: Must contain at least one internal entity
        internal_entities = [name for name, ent in self.entities.items() if not ent.external_ref]
        if not internal_entities:
            issues.append({
                "severity": "ERROR",
                "code": "MVD-001",
                "message": "Minimum Viable Domain Failure: Schema must contain at least one internal (non-external) entity."
            })

        # Rule 2: Must define at least one RELATIONSHIP
        if not self.relationships:
            issues.append({
                "severity": "WARNING",
                "code": "MVD-002",
                "message": "Minimum Viable Domain Warning: No relationships defined. Isolated entities limit federation capabilities."
            })

        # Rule 3: Should contain at least one [EXTERNAL: ...] link or external entity
        has_external = any(ent.external_ref for ent in self.entities.values())
        if not has_external:
             # Check for attribute-level external links
             attr_external = False
             for ent in self.entities.values():
                 for attr in ent.attributes:
                     if attr.get("external_link"):
                         attr_external = True
                         break
                 if attr_external: break
             
             if not attr_external:
                issues.append({
                    "severity": "INFO",
                    "code": "MVD-003",
                    "message": "Federation Advisory: This schema contains no external links. It is a closed domain and cannot yet interoperate with the broader federation."
                })

        return issues
