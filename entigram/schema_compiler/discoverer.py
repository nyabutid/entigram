import csv
import importlib.util
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type

import inflect

p = inflect.engine()


def _title_entity_name(raw_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", raw_name).strip("_")
    if not cleaned:
        return "DiscoveredEntity"
    singular = p.singular_noun(cleaned) or cleaned
    parts = [part for part in re.split(r"[_\s]+", singular) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def _quote_sqlite_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


@dataclass
class DiscoveryAttribute:
    name: str
    type: str = "String"
    primary_key: bool = False
    required: bool = False
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        prefix = "." if self.primary_key else "-"
        constraints = []
        if self.required and not self.primary_key:
            constraints.append("MUST")
        type_expr = self.type
        if constraints:
            type_expr = f"{type_expr}, {', '.join(constraints)}"
        return f"  {prefix} {self.name} ({type_expr})"


@dataclass
class DiscoveryEntity:
    name: str
    attributes: List[DiscoveryAttribute] = field(default_factory=list)
    source_name: Optional[str] = None
    confidence: float = 1.0
    evidence: Dict[str, Any] = field(default_factory=dict)

    def render(self) -> List[str]:
        lines = [f"ENTITY: {self.name}", "ATTRIBUTES:"]
        lines.extend(attr.render() for attr in self.attributes)
        return lines


@dataclass
class DiscoveryRelationship:
    parent_entity: str
    child_entity: str
    confidence: float = 0.7
    evidence: Dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        return f"- {self.parent_entity} (1) [MUST] --- [MAY] (MANY) {self.child_entity}"


@dataclass
class DiscoveryFinding:
    code: str
    severity: str
    message: str
    entity: Optional[str] = None
    attribute: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    confidence: float = 1.0


@dataclass
class DiscoveryResult:
    adapter: str
    source_ref: str
    entities: List[DiscoveryEntity] = field(default_factory=list)
    relationships: List[DiscoveryRelationship] = field(default_factory=list)
    findings: List[DiscoveryFinding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_schema(self, include_metadata_comment: bool = False) -> str:
        lines = []
        if include_metadata_comment:
            lines.extend([
                "/*",
                f" * Discovered by Entigram adapter: {self.adapter}",
                f" * Source: {self.source_ref}",
                " * Status: discovery output is a draft and must be reviewed before promotion.",
                " */",
                "",
            ])

        for entity in self.entities:
            lines.extend(entity.render())
            lines.append("")

        if self.relationships:
            lines.append("RELATIONSHIPS:")
            for relationship in sorted({rel.render() for rel in self.relationships}):
                lines.append(relationship)

        return "\n".join(lines).rstrip()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter": self.adapter,
            "source_ref": self.source_ref,
            "entities": [
                {
                    "name": entity.name,
                    "source_name": entity.source_name,
                    "confidence": entity.confidence,
                    "evidence": entity.evidence,
                    "attributes": [
                        {
                            "name": attr.name,
                            "type": attr.type,
                            "primary_key": attr.primary_key,
                            "required": attr.required,
                            "confidence": attr.confidence,
                            "evidence": attr.evidence,
                        }
                        for attr in entity.attributes
                    ],
                }
                for entity in self.entities
            ],
            "relationships": [
                {
                    "parent_entity": rel.parent_entity,
                    "child_entity": rel.child_entity,
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                }
                for rel in self.relationships
            ],
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                    "entity": finding.entity,
                    "attribute": finding.attribute,
                    "evidence": finding.evidence,
                    "recommendation": finding.recommendation,
                    "confidence": finding.confidence,
                }
                for finding in self.findings
            ],
            "metadata": self.metadata,
        }


class SourceDiscoveryAdapter:
    name = "base"

    def discover(self) -> DiscoveryResult:
        raise NotImplementedError


class SQLiteSourceAdapter(SourceDiscoveryAdapter):
    name = "sqlite"

    def __init__(self, db_path: str, normalize_types: bool = False):
        self.db_path = str(db_path)
        self.normalize_types = normalize_types

    def discover(self) -> DiscoveryResult:
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' "
                    "AND name NOT LIKE 'migrations' "
                    "AND name NOT LIKE 'crsql_%';"
                )
                tables = [row[0] for row in cursor.fetchall()]

                entities = []
                table_to_entity = {}
                for table in tables:
                    entity_name = _title_entity_name(table)
                    table_to_entity[table] = entity_name
                    cursor.execute(f"PRAGMA table_info({_quote_sqlite_identifier(table)});")
                    cols = cursor.fetchall()
                    attributes = []
                    for col in cols:
                        name = col[1]
                        storage_type = col[2] or "String"
                        pk_position = int(col[5] or 0)
                        required = bool(col[3])
                        attr_type = _normalize_sql_type(storage_type) if self.normalize_types else storage_type
                        attributes.append(
                            DiscoveryAttribute(
                                name=name,
                                type=attr_type,
                                primary_key=pk_position > 0,
                                required=required,
                                evidence={
                                    "source_table": table,
                                    "source_type": storage_type,
                                    "not_null": required,
                                    "primary_key": pk_position > 0,
                                    "pk_position": pk_position,
                                },
                            )
                        )
                    entities.append(
                        DiscoveryEntity(
                            name=entity_name,
                            source_name=table,
                            attributes=attributes,
                            evidence={"source_table": table, "column_count": len(cols)},
                        )
                    )

                relationships = []
                for table in tables:
                    cursor.execute(f"PRAGMA foreign_key_list({_quote_sqlite_identifier(table)});")
                    for fk in cursor.fetchall():
                        parent_table = fk[2]
                        if parent_table not in table_to_entity:
                            continue
                        relationships.append(
                            DiscoveryRelationship(
                                parent_entity=table_to_entity[parent_table],
                                child_entity=table_to_entity[table],
                                evidence={
                                    "source_table": table,
                                    "parent_table": parent_table,
                                    "from_column": fk[3],
                                    "to_column": fk[4],
                                    "evidence_type": "foreign_key",
                                },
                            )
                        )

                return DiscoveryResult(
                    adapter=self.name,
                    source_ref=self.db_path,
                    entities=entities,
                    relationships=relationships,
                    metadata={"table_count": len(tables), "trusted": False},
                )
        except sqlite3.DatabaseError as e:
            if "file is not a database" in str(e):
                raise ValueError(f"Error: The file '{self.db_path}' is not a valid SQLite database.")
            raise
        finally:
            if conn is not None:
                conn.close()


class CSVSourceAdapter(SourceDiscoveryAdapter):
    name = "csv"

    def __init__(self, file_path: str, domain_name: Optional[str] = None, sample_size: int = 100):
        self.file_path = str(file_path)
        self.domain_name = domain_name
        self.sample_size = sample_size

    def discover(self) -> DiscoveryResult:
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            rows = []
            for index, row in enumerate(reader):
                if index >= self.sample_size:
                    break
                rows.append(row)

        entity_name = _title_entity_name(self.domain_name or path.stem)
        attributes = [
            _attribute_from_samples(
                header,
                [row.get(header) for row in rows],
                source={"source_file": str(path), "sample_rows": len(rows)},
            )
            for header in headers
        ]
        return DiscoveryResult(
            adapter=self.name,
            source_ref=str(path),
            entities=[
                DiscoveryEntity(
                    name=entity_name,
                    source_name=path.name,
                    attributes=attributes,
                    confidence=0.8,
                    evidence={"source_file": str(path), "sample_rows": len(rows)},
                )
            ] if headers else [],
            metadata={"row_sample_count": len(rows), "trusted": False},
        )


class JSONSourceAdapter(SourceDiscoveryAdapter):
    name = "json"

    def __init__(self, file_path: str, domain_name: Optional[str] = None, sample_size: int = 100):
        self.file_path = str(file_path)
        self.domain_name = domain_name
        self.sample_size = sample_size

    def discover(self) -> DiscoveryResult:
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {self.file_path}")

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        rows = _coerce_json_rows(payload)[: self.sample_size]
        headers = _ordered_keys(rows)
        entity_name = _title_entity_name(self.domain_name or path.stem)
        attributes = [
            _attribute_from_samples(
                header,
                [row.get(header) for row in rows],
                source={"source_file": str(path), "sample_rows": len(rows)},
            )
            for header in headers
        ]
        return DiscoveryResult(
            adapter=self.name,
            source_ref=str(path),
            entities=[
                DiscoveryEntity(
                    name=entity_name,
                    source_name=path.name,
                    attributes=attributes,
                    confidence=0.8,
                    evidence={"source_file": str(path), "sample_rows": len(rows)},
                )
            ] if headers else [],
            metadata={"row_sample_count": len(rows), "trusted": False},
        )


_ADAPTERS: Dict[str, Type[SourceDiscoveryAdapter]] = {
    SQLiteSourceAdapter.name: SQLiteSourceAdapter,
    CSVSourceAdapter.name: CSVSourceAdapter,
    JSONSourceAdapter.name: JSONSourceAdapter,
}


def register_discovery_adapter(name: str, adapter_cls: Type[SourceDiscoveryAdapter]) -> None:
    if not name or not re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", name):
        raise ValueError("adapter name must be a non-empty identifier")
    if not issubclass(adapter_cls, SourceDiscoveryAdapter):
        raise TypeError("adapter_cls must inherit SourceDiscoveryAdapter")
    _ADAPTERS[name] = adapter_cls


def load_discovery_adapter_module(module_path: str) -> List[str]:
    path = Path(module_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"discovery adapter module not found: {module_path}")

    module_name = f"entigram_dynamic_discovery_adapter_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load discovery adapter module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "register"):
        raise ValueError("discovery adapter module must define register(register_discovery_adapter)")

    before = set(_ADAPTERS)
    module.register(register_discovery_adapter)
    registered = sorted(set(_ADAPTERS) - before)
    if not registered:
        raise ValueError("discovery adapter module did not register any adapters")
    return registered


def available_discovery_adapters() -> List[str]:
    return sorted(_ADAPTERS)


def discover_source(
    source_path: str,
    source: str = "auto",
    domain_name: Optional[str] = None,
    normalize_types: bool = False,
) -> DiscoveryResult:
    adapter_name = _infer_adapter_name(source_path) if source == "auto" else source
    adapter_cls = _ADAPTERS.get(adapter_name)
    if adapter_cls is None:
        raise ValueError(f"Unknown discovery source adapter: {source}")
    if adapter_name == "sqlite":
        return review_discovery_result(adapter_cls(source_path, normalize_types=normalize_types).discover())
    return review_discovery_result(adapter_cls(source_path, domain_name=domain_name).discover())


def discover_schema_from_source(
    source_path: str,
    source: str = "auto",
    domain_name: Optional[str] = None,
    include_metadata_comment: bool = False,
    normalize_types: bool = False,
) -> str:
    return discover_source(
        source_path,
        source=source,
        domain_name=domain_name,
        normalize_types=normalize_types,
    ).to_schema(include_metadata_comment=include_metadata_comment)


class DomainDiscoverer:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_entity_name(self, table_name: str) -> str:
        return _title_entity_name(table_name)

    def discover(self) -> DiscoveryResult:
        return review_discovery_result(SQLiteSourceAdapter(self.db_path).discover())

    def discover_schema(self) -> str:
        """
        Reverse-engineers a SQLite database into a Schema string.

        Kept as the compatibility API for existing callers. New discovery
        sources should use discover_source() through the adapter registry.
        """
        return self.discover().to_schema()


def _infer_adapter_name(source_path: str) -> str:
    suffix = Path(source_path).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    if suffix in {".db", ".sqlite", ".sqlite3"} or not suffix:
        return "sqlite"
    raise ValueError(f"Could not infer discovery source adapter for {source_path}")


def review_discovery_result(result: DiscoveryResult) -> DiscoveryResult:
    existing = list(result.findings)
    result.findings = []
    result.findings.extend(existing)
    result.findings.extend(_review_entity_keys(result))
    result.findings.extend(_review_relationships(result))
    result.findings.extend(_review_attribute_shapes(result))
    result.metadata["finding_count"] = len(result.findings)
    severities = {}
    for finding in result.findings:
        severities[finding.severity] = severities.get(finding.severity, 0) + 1
    result.metadata["finding_severity_counts"] = severities
    return result


def _review_entity_keys(result: DiscoveryResult) -> List[DiscoveryFinding]:
    findings = []
    for entity in result.entities:
        if not entity.attributes:
            continue
        primary_keys = [attr for attr in entity.attributes if attr.primary_key]
        if not primary_keys:
            findings.append(DiscoveryFinding(
                code="NO_PRIMARY_KEY",
                severity="warning",
                entity=entity.name,
                message=f"{entity.name} has no discovered primary key.",
                evidence={"source_name": entity.source_name, "attribute_count": len(entity.attributes)},
                recommendation="Add or identify a stable primary key before promoting this draft model.",
                confidence=0.95,
            ))
        elif len(primary_keys) > 1:
            findings.append(DiscoveryFinding(
                code="MULTIPLE_PRIMARY_KEY_COLUMNS",
                severity="warning",
                entity=entity.name,
                message=f"{entity.name} uses a composite or multi-column primary key.",
                evidence={"primary_key_attributes": [attr.name for attr in primary_keys]},
                recommendation="Review whether the composite key should remain as-is or be modeled with a surrogate identifier plus uniqueness constraints.",
                confidence=0.9,
            ))
    return findings


def _review_relationships(result: DiscoveryResult) -> List[DiscoveryFinding]:
    findings = []
    relationship_columns = {
        (rel.evidence.get("source_table"), rel.evidence.get("from_column"))
        for rel in result.relationships
        if rel.evidence.get("source_table") and rel.evidence.get("from_column")
    }
    if len(result.entities) > 1 and not result.relationships:
        findings.append(DiscoveryFinding(
            code="NO_FOREIGN_KEYS_IN_MULTI_ENTITY_SOURCE",
            severity="warning",
            message="Multiple entities were discovered, but no relationships were found.",
            evidence={"entity_count": len(result.entities)},
            recommendation="Review the source for missing foreign key constraints or add relationships explicitly during model promotion.",
            confidence=0.8,
        ))

    for entity in result.entities:
        for attr in entity.attributes:
            if attr.primary_key:
                continue
            attr_name = attr.name.lower()
            if attr_name in {"id", "uuid"}:
                continue
            if not (attr_name.endswith("_id") or attr_name.endswith("_uuid")):
                continue
            source_table = attr.evidence.get("source_table")
            if (source_table, attr.name) in relationship_columns:
                continue
            findings.append(DiscoveryFinding(
                code="FK_LIKE_COLUMN_WITHOUT_CONSTRAINT",
                severity="warning",
                entity=entity.name,
                attribute=attr.name,
                message=f"{entity.name}.{attr.name} looks like a foreign key, but no relationship constraint was discovered.",
                evidence={"source_table": source_table, "source_type": attr.evidence.get("source_type")},
                recommendation="Confirm whether this field should reference another entity and add a relationship if appropriate.",
                confidence=0.75,
            ))
    return findings


def _review_attribute_shapes(result: DiscoveryResult) -> List[DiscoveryFinding]:
    findings = []
    for entity in result.entities:
        if not entity.attributes:
            continue
        non_key_attributes = [attr for attr in entity.attributes if not attr.primary_key]
        required_non_key = [attr for attr in non_key_attributes if attr.required]
        if len(non_key_attributes) >= 2 and not required_non_key:
            findings.append(DiscoveryFinding(
                code="ALL_NON_KEY_COLUMNS_NULLABLE",
                severity="info",
                entity=entity.name,
                message=f"{entity.name} has no required non-key attributes.",
                evidence={"nullable_non_key_attributes": [attr.name for attr in non_key_attributes]},
                recommendation="Review whether important fields should be marked required in the promoted model.",
                confidence=0.7,
            ))
        if len(entity.attributes) >= 30:
            findings.append(DiscoveryFinding(
                code="WIDE_ENTITY",
                severity="info",
                entity=entity.name,
                message=f"{entity.name} has {len(entity.attributes)} attributes.",
                evidence={"attribute_count": len(entity.attributes)},
                recommendation="Review for denormalized groups or embedded concepts that should become separate entities.",
                confidence=0.65,
            ))

        repeated_groups = _find_repeating_column_groups([attr.name for attr in entity.attributes])
        for base_name, names in repeated_groups.items():
            findings.append(DiscoveryFinding(
                code="REPEATING_COLUMN_GROUP",
                severity="warning",
                entity=entity.name,
                message=f"{entity.name} has repeated columns that look like a repeating group: {', '.join(names)}.",
                evidence={"base_name": base_name, "attributes": names},
                recommendation="Consider normalizing this into a child entity or repeated relationship.",
                confidence=0.8,
            ))

        for attr in entity.attributes:
            source_type = str(attr.evidence.get("source_type", attr.type)).upper()
            if attr.type.upper() == "JSON" or "JSON" in source_type:
                findings.append(DiscoveryFinding(
                    code="JSON_BLOB_COLUMN",
                    severity="info",
                    entity=entity.name,
                    attribute=attr.name,
                    message=f"{entity.name}.{attr.name} stores JSON-like structured data.",
                    evidence={"source_type": attr.evidence.get("source_type"), "type": attr.type},
                    recommendation="Review whether nested fields should be modeled explicitly or left as opaque JSON.",
                    confidence=0.8,
                ))
            if attr.confidence < 0.75:
                findings.append(DiscoveryFinding(
                    code="LOW_CONFIDENCE_ATTRIBUTE_INFERENCE",
                    severity="info",
                    entity=entity.name,
                    attribute=attr.name,
                    message=f"{entity.name}.{attr.name} was inferred with low confidence.",
                    evidence=attr.evidence,
                    recommendation="Review sample coverage or provide a stronger source adapter before promotion.",
                    confidence=attr.confidence,
                ))
            unique_count = attr.evidence.get("unique_non_empty_sample_count")
            sample_count = attr.evidence.get("non_empty_samples")
            if (
                not attr.primary_key
                and attr.type == "String"
                and isinstance(unique_count, int)
                and isinstance(sample_count, int)
                and sample_count >= 5
                and 1 < unique_count <= 10
            ):
                findings.append(DiscoveryFinding(
                    code="LOW_CARDINALITY_STRING",
                    severity="info",
                    entity=entity.name,
                    attribute=attr.name,
                    message=f"{entity.name}.{attr.name} has a small set of repeated string values.",
                    evidence={
                        "non_empty_samples": sample_count,
                        "unique_non_empty_sample_count": unique_count,
                        "sample_values": attr.evidence.get("unique_non_empty_sample_values", []),
                    },
                    recommendation="Consider whether this should be modeled as an enum, controlled vocabulary, or reference data.",
                    confidence=0.7,
                ))
    return findings


def _find_repeating_column_groups(names: List[str]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for name in names:
        match = re.fullmatch(r"(.+?)[_-]?\d+", name)
        if not match:
            continue
        base = match.group(1).rstrip("_-").lower()
        if len(base) < 2:
            continue
        groups.setdefault(base, []).append(name)
    return {
        base: sorted(group_names)
        for base, group_names in groups.items()
        if len(group_names) >= 2
    }


def _normalize_sql_type(storage_type: str) -> str:
    upper = storage_type.upper()
    if any(token in upper for token in ("INT", "SERIAL")):
        return "Integer"
    if any(token in upper for token in ("REAL", "FLOA", "DOUB", "DEC", "NUM")):
        return "Decimal"
    if "BOOL" in upper:
        return "Boolean"
    if any(token in upper for token in ("DATE", "TIME")):
        return "DateTime"
    if any(token in upper for token in ("BLOB", "BINARY")):
        return "Blob"
    if "JSON" in upper:
        return "JSON"
    return "String"


def _attribute_from_samples(name: str, values: Iterable[Any], source: Dict[str, Any]) -> DiscoveryAttribute:
    samples = list(values)
    non_empty = [value for value in samples if not _is_empty(value)]
    unique_values = sorted({str(value) for value in non_empty})
    logical_type = _infer_values_type(non_empty)
    primary_key = name.lower() in {"id", "uuid"}
    required = bool(samples) and len(non_empty) == len(samples)
    confidence = 0.95 if non_empty else 0.5
    return DiscoveryAttribute(
        name=name,
        type=logical_type,
        primary_key=primary_key,
        required=required,
        confidence=confidence,
        evidence={
            **source,
            "non_empty_samples": len(non_empty),
            "unique_non_empty_sample_count": len(unique_values),
            "unique_non_empty_sample_values": unique_values[:10],
            "inferred_from_values": True,
        },
    )


def _infer_values_type(values: List[Any]) -> str:
    if not values:
        return "String"
    if all(isinstance(value, bool) or _is_bool_string(value) for value in values):
        return "Boolean"
    if all(isinstance(value, int) and not isinstance(value, bool) or _is_int_string(value) for value in values):
        return "Integer"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool) or _is_decimal_string(value) for value in values):
        return "Decimal"
    if all(isinstance(value, (dict, list)) or _is_json_string(value) for value in values):
        return "JSON"
    if all(_is_datetime_string(value) for value in values):
        return "DateTime"
    return "String"


def _coerce_json_rows(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ValueError("JSON discovery requires a list of objects")
        return payload
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value
        return [payload]
    raise ValueError("JSON discovery requires an object or a list of objects")


def _ordered_keys(rows: Iterable[Dict[str, Any]]) -> List[str]:
    keys = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


def _is_empty(value: Any) -> bool:
    return value is None or value == ""


def _is_bool_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in {"true", "false", "yes", "no", "0", "1"}


def _is_int_string(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[-+]?\d+", value.strip()))


def _is_decimal_string(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[-+]?(?:\d+\.\d+|\d+)", value.strip()))


def _is_json_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return False
    try:
        json.loads(stripped)
        return True
    except ValueError:
        return False


def _is_datetime_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return bool(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[-+]\d{2}:?\d{2})?", stripped)
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(discover_schema_from_source(sys.argv[1]))
    else:
        print("Usage: python -m entigram.schema_compiler.discoverer <source_path>")
