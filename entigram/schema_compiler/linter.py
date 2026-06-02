import re
from typing import List, Dict, Any
from .parser import SchemaParser

class SchemaLinter:
    """
    SchemaLinter: Provides deterministic error codes for Entigram Schema models.
    Designed to prevent infinite LLM retry loops by giving precise feedback.
    """
    def __init__(self, schema_text: str):
        self.schema_text = schema_text
        self.parser = SchemaParser(schema_text)

    def lint(self) -> List[Dict[str, str]]:
        """
        Runs a battery of structural checks on the Schema.
        Returns a list of errors with codes and actionable descriptions.
        """
        errors = []
        try:
            entities, relationships = self.parser.parse()
        except Exception as e:
            return [{"code": "Schema-000", "severity": "CRITICAL", "message": f"Syntax Error: {str(e)}"}]

        if not entities:
            errors.append({"code": "Schema-004", "severity": "HIGH", "message": "No entities found in the model."})
            return errors

        for ent_name, ent in entities.items():
            # Rule Schema-001: Missing Primary Key
            has_pk = any(attr['pk'] for attr in ent.attributes)
            if not has_pk and not ent.external_ref:
                errors.append({
                    "code": "Schema-001",
                    "severity": "HIGH",
                    "message": f"Entity '{ent_name}' is missing a Primary Key (PK). Use '.' prefix or '(..., PK)'."
                })

            # Rule Schema-002: Orphaned Entity
            if not ent.external_ref:
                is_connected = False
                for rel in relationships:
                    if rel.entity_a.lower() == ent_name.lower() or rel.entity_b.lower() == ent_name.lower():
                        is_connected = True
                        break
                if not is_connected and len(entities) > 1:
                    errors.append({
                        "code": "Schema-002",
                        "severity": "MEDIUM",
                        "message": f"Entity '{ent_name}' is orphaned (has no relationships to other entities)."
                    })

        # Rule Schema-003: Relationship Entity Match
        for rel in relationships:
            if rel.entity_a not in entities and not self._is_builtin_or_external(rel.entity_a):
                errors.append({
                    "code": "Schema-003",
                    "severity": "HIGH",
                    "message": f"Relationship refers to undefined entity '{rel.entity_a}'."
                })
            if rel.entity_b not in entities and not self._is_builtin_or_external(rel.entity_b):
                errors.append({
                    "code": "Schema-003",
                    "severity": "HIGH",
                    "message": f"Relationship refers to undefined entity '{rel.entity_b}'."
                })

        return errors

    def _is_builtin_or_external(self, name: str) -> bool:
        # Check if it looks like a namespaced external ref
        if "::" in name or name.startswith("@"):
            return True
        return False

    def format_errors_for_llm(self, errors: List[Dict[str, str]]) -> str:
        """Formats the errors into a prompt-friendly string."""
        if not errors: return "Model is valid."
        
        lines = ["The Schema you generated has the following structural errors:"]
        for err in errors:
            lines.append(f"- [{err['code']}] {err['message']}")
        lines.append("\nPlease correct these errors and regenerate the Schema.")
        return "\n".join(lines)
