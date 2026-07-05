import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from entigram.governance.policy_engine import PolicyEngine
from entigram.schema_compiler.parser import SchemaEntity, SchemaParser, SchemaRelationship
from entigram.sqlite_ledger.manager import LedgerManager


@dataclass
class MergeConflict:
    entity_name: str
    conflict_type: str
    local_state: dict
    remote_state: dict
    suggested_resolution: Optional[str] = None


@dataclass
class MergeDiff:
    added_entities: List[SchemaEntity]
    removed_entities: List[SchemaEntity]
    modified_entities: List[tuple]
    added_relationships: List[SchemaRelationship]
    removed_relationships: List[SchemaRelationship]
    conflicts: List[MergeConflict]

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    def summary(self) -> str:
        lines = [
            "Schema Diff:",
            f"   + {len(self.added_entities)} entities added ({_format_names([e.name for e in self.added_entities])})",
            f"   ~ {len(self.modified_entities)} entities modified ({_format_names([e[0].name for e in self.modified_entities])})",
            f"   - {len(self.removed_entities)} entities removed ({_format_names([e.name for e in self.removed_entities])})",
            f"   + {len(self.added_relationships)} relationships added",
            f"   - {len(self.removed_relationships)} relationships removed",
        ]
        if self.conflicts:
            lines.append(f"   ! {len(self.conflicts)} conflicts detected")
        return "\n".join(lines)


@dataclass
class MergeResult:
    merged_schema: str
    output_path: Optional[str] = None
    diff: Optional[MergeDiff] = None
    resolved_conflicts: List[MergeConflict] = field(default_factory=list)
    ledger_stats: Dict[str, int] = field(default_factory=dict)
    warden_locked: bool = False
    strategy: str = "interactive"

    @property
    def entities_added(self) -> int:
        return len(self.diff.added_entities) if self.diff else 0

    @property
    def entities_resolved(self) -> int:
        return len(self.resolved_conflicts)

    @property
    def relationships_added(self) -> int:
        return len(self.diff.added_relationships) if self.diff else 0


class SchemaMerger:
    """Performs structural diff and merge of two LDS schemas using the conflict resolution engine."""

    def __init__(self, local_schema_path: str, remote_schema_path: str, ledger: LedgerManager):
        self.local_schema_path = Path(local_schema_path).expanduser().resolve()
        self.remote_schema_path = Path(remote_schema_path).expanduser().resolve()
        self.local_parser = SchemaParser(self.local_schema_path.read_text())
        self.remote_parser = SchemaParser(self.remote_schema_path.read_text())
        self.ledger = ledger
        self.local_entities, self.local_relationships = self.local_parser.parse()
        self.remote_entities, self.remote_relationships = self.remote_parser.parse()
        self.local_entities = self._normalize_entities(self.local_entities)
        self.remote_entities = self._normalize_entities(self.remote_entities)
        self.local_relationships = self._dedupe_relationships(self.local_relationships)
        self.remote_relationships = self._dedupe_relationships(self.remote_relationships)
        self._last_resolution_strategies: Dict[str, str] = {}
        self._last_diff: Optional[MergeDiff] = None

    def diff(self) -> MergeDiff:
        """Compare two parsed schemas structurally."""
        local_names = set(self.local_entities)
        remote_names = set(self.remote_entities)

        added_entities = [
            self.remote_entities[name] for name in sorted(remote_names - local_names)
        ]
        removed_entities = [
            self.local_entities[name] for name in sorted(local_names - remote_names)
        ]
        modified_entities = []
        conflicts = []

        for name in sorted(local_names & remote_names):
            local_entity = self.local_entities[name]
            remote_entity = self.remote_entities[name]
            attr_diffs = self._attribute_diffs(local_entity, remote_entity)
            if attr_diffs:
                modified_entities.append((local_entity, remote_entity, attr_diffs))
                conflict_type = (
                    "type_mismatch"
                    if any(diff["kind"] == "type_mismatch" for diff in attr_diffs)
                    else "attribute_divergence"
                )
                conflicts.append(MergeConflict(
                    entity_name=name,
                    conflict_type=conflict_type,
                    local_state=self._entity_to_state(local_entity),
                    remote_state=self._entity_to_state(remote_entity),
                    suggested_resolution=self._check_precedent(name),
                ))

        local_rels = {self._relationship_key(rel): rel for rel in self.local_relationships}
        remote_rels = {self._relationship_key(rel): rel for rel in self.remote_relationships}
        added_relationships = [
            remote_rels[key] for key in sorted(set(remote_rels) - set(local_rels))
        ]
        removed_relationships = [
            local_rels[key] for key in sorted(set(local_rels) - set(remote_rels))
        ]

        self._last_diff = MergeDiff(
            added_entities=added_entities,
            removed_entities=removed_entities,
            modified_entities=modified_entities,
            added_relationships=added_relationships,
            removed_relationships=removed_relationships,
            conflicts=conflicts,
        )
        return self._last_diff

    def merge(self, strategy: str = "interactive") -> MergeResult:
        """Execute the merge."""
        if strategy not in {"interactive", "union", "ours", "theirs", "auto"}:
            raise ValueError(f"Unsupported merge strategy: {strategy}")

        diff = self._last_diff or self.diff()
        merged_entities = dict(self.local_entities)
        resolved_conflicts = []
        self._last_resolution_strategies = {}

        for entity in diff.added_entities:
            merged_entities[entity.name] = entity

        for conflict in diff.conflicts:
            resolution_strategy = self._resolve_strategy(conflict, strategy)
            resolved_entity = self._resolve_entity(conflict, resolution_strategy)
            merged_entities[conflict.entity_name] = resolved_entity
            self._record_merge_decision(conflict, resolved_entity, resolution_strategy)
            self._last_resolution_strategies[conflict.entity_name] = resolution_strategy
            resolved_conflicts.append(conflict)

        merged_relationships = self._dedupe_relationships(
            list(self.local_relationships) + list(diff.added_relationships)
        )
        merged_schema = self.render_schema(merged_entities, merged_relationships)

        return MergeResult(
            merged_schema=merged_schema,
            diff=diff,
            resolved_conflicts=resolved_conflicts,
            strategy=strategy,
        )

    def merge_state_db(self, remote_db_path: str) -> Dict[str, int]:
        remote_path = Path(remote_db_path).expanduser().resolve()
        if not remote_path.exists():
            return {
                "semantic_alignments": 0,
                "synonyms": 0,
                "human_resolutions": 0,
                "improvement_proposals": 0,
                "lessons": 0,
            }

        remote_manager = LedgerManager(str(remote_path))
        remote_manager.close()

        conn = self.ledger._get_connection()
        stats = {}
        try:
            conn.execute("ATTACH DATABASE ? AS remote_db", (str(remote_path),))
            try:
                conn.execute("BEGIN")
                stats["semantic_alignments"] = self._merge_table(
                    conn,
                    "semantic_alignments",
                    [
                        "source_domain", "target_domain", "source_concept", "target_concept",
                        "relation", "confidence", "rationale", "status", "lifecycle_status",
                        "evidence_type", "source_artifact", "verified", "verified_by", "verified_at",
                        "semantic_confidence", "schema_confidence", "data_confidence",
                        "human_review_confidence", "runtime_observation_confidence", "timestamp",
                    ],
                    """
                    NOT EXISTS (
                        SELECT 1 FROM semantic_alignments local
                        WHERE local.source_domain = remote.source_domain
                          AND local.target_domain = remote.target_domain
                          AND local.source_concept = remote.source_concept
                          AND local.target_concept = remote.target_concept
                    )
                    """,
                )
                stats["synonyms"] = self._merge_table(
                    conn,
                    "synonyms",
                    ["term", "synonym", "confidence", "timestamp"],
                    """
                    NOT EXISTS (
                        SELECT 1 FROM synonyms local
                        WHERE local.term = remote.term
                          AND local.synonym = remote.synonym
                    )
                    """,
                )
                stats["human_resolutions"] = self._merge_table(
                    conn,
                    "human_resolutions",
                    ["conflict_id", "entity_type", "resolved_state", "rationale", "version", "timestamp"],
                    """
                    NOT EXISTS (
                        SELECT 1 FROM human_resolutions local
                        WHERE local.conflict_id = remote.conflict_id
                          AND COALESCE(local.version, -1) = COALESCE(remote.version, -1)
                    )
                    """,
                )
                stats["improvement_proposals"] = self._merge_table(
                    conn,
                    "improvement_proposals",
                    [
                        "title", "affected_model", "proposed_change", "rationale",
                        "expected_benefit", "lifecycle_status", "created_by", "created_at",
                    ],
                    """
                    remote.lifecycle_status = 'Proposed'
                    AND NOT EXISTS (
                        SELECT 1 FROM improvement_proposals local
                        WHERE local.title = remote.title
                          AND local.affected_model = remote.affected_model
                          AND local.created_at = remote.created_at
                    )
                    """,
                )
                stats["lessons"] = self._merge_table(
                    conn,
                    "lessons",
                    [
                        "source_task", "lesson", "reusable_rule", "confidence",
                        "lifecycle_status", "agent_id", "observed_at",
                    ],
                    """
                    remote.lifecycle_status = 'Active'
                    AND NOT EXISTS (
                        SELECT 1 FROM lessons local
                        WHERE COALESCE(local.source_task, '') = COALESCE(remote.source_task, '')
                          AND local.lesson = remote.lesson
                          AND COALESCE(local.reusable_rule, '') = COALESCE(remote.reusable_rule, '')
                    )
                    """,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.execute("DETACH DATABASE remote_db")
        finally:
            if self.ledger.db_path != ":memory:":
                conn.close()
        return stats

    def _check_precedent(self, entity_type: str) -> Optional[str]:
        """Query human_resolutions for past decisions on this entity_type."""
        for resolution in self.ledger.get_all_resolutions():
            if resolution.get("entity_type") != entity_type:
                continue
            strategy = self._strategy_from_resolution(resolution)
            if strategy:
                return strategy
        return None

    def _resolve_strategy(self, conflict: MergeConflict, strategy: str) -> str:
        if strategy in {"union", "ours", "theirs"}:
            return strategy
        if strategy == "auto":
            policy_resolution = PolicyEngine().evaluate_conflict(
                self._conflict_id(conflict),
                conflict.entity_name,
                {"local": conflict.local_state, "remote": conflict.remote_state},
            )
            if policy_resolution:
                resolved_state = policy_resolution.get("resolved_state")
                if resolved_state == conflict.remote_state:
                    return "theirs"
                if resolved_state == conflict.local_state:
                    return "ours"
                return "union"
            if conflict.suggested_resolution:
                return conflict.suggested_resolution
        if conflict.suggested_resolution:
            return conflict.suggested_resolution

        from entigram.schema_compiler.merge_renderer import MergeRenderer

        return MergeRenderer().prompt_conflict(conflict)

    def _resolve_entity(self, conflict: MergeConflict, strategy: str) -> SchemaEntity:
        if strategy == "ours":
            return self._state_to_entity(conflict.local_state)
        if strategy == "theirs":
            return self._state_to_entity(conflict.remote_state)
        if strategy == "manual":
            return self._manual_resolve(conflict)
        return self._union_entities(
            self._state_to_entity(conflict.local_state),
            self._state_to_entity(conflict.remote_state),
        )

    def _manual_resolve(self, conflict: MergeConflict) -> SchemaEntity:
        import os
        import subprocess
        import tempfile

        initial = json.dumps(conflict.local_state, indent=2, sort_keys=True)
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp:
            tmp.write(initial)
            tmp_path = tmp.name
        editor = os.environ.get("EDITOR", "vi")
        try:
            subprocess.run([editor, tmp_path], check=True)
            state = json.loads(Path(tmp_path).read_text())
            return self._state_to_entity(state)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _record_merge_decision(
        self,
        conflict: MergeConflict,
        resolved_entity: SchemaEntity,
        strategy: str,
    ) -> None:
        conflict_id = self._conflict_id(conflict)
        proposed = json.dumps({
            "local": conflict.local_state,
            "remote": conflict.remote_state,
        }, sort_keys=True)
        self.ledger.record_conflict(
            conflict_id,
            conflict.entity_name,
            proposed,
            json.dumps(["local", "remote"]),
        )
        self.ledger.record_resolution(
            conflict_id,
            conflict.entity_name,
            json.dumps({
                "entity": self._entity_to_state(resolved_entity),
                "merge_strategy": strategy,
            }, sort_keys=True),
            f"Schema merge resolved with {strategy.upper()} strategy; is_precedent=true",
        )

    def _merge_table(
        self,
        conn: sqlite3.Connection,
        table: str,
        columns: List[str],
        where_clause: str,
    ) -> int:
        if not self._remote_table_exists(conn, table):
            return 0
        column_csv = ", ".join(columns)
        remote_column_csv = ", ".join(f"remote.{col}" for col in columns)
        before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.execute(
            f"""
            INSERT OR IGNORE INTO {table} ({column_csv})
            SELECT {remote_column_csv}
            FROM remote_db.{table} remote
            WHERE {where_clause}
            """
        )
        after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return after - before

    def _remote_table_exists(self, conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT 1 FROM remote_db.sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    def _attribute_diffs(self, local: SchemaEntity, remote: SchemaEntity) -> List[dict]:
        local_attrs = {attr["name"]: attr for attr in local.attributes}
        remote_attrs = {attr["name"]: attr for attr in remote.attributes}
        diffs = []
        for name in sorted(set(remote_attrs) - set(local_attrs)):
            diffs.append({"kind": "added_attribute", "name": name, "remote": remote_attrs[name]})
        for name in sorted(set(local_attrs) - set(remote_attrs)):
            diffs.append({"kind": "removed_attribute", "name": name, "local": local_attrs[name]})
        for name in sorted(set(local_attrs) & set(remote_attrs)):
            if self._attribute_key(local_attrs[name]) != self._attribute_key(remote_attrs[name]):
                diffs.append({
                    "kind": "type_mismatch",
                    "name": name,
                    "local": local_attrs[name],
                    "remote": remote_attrs[name],
                })
        return diffs

    def _union_entities(self, local: SchemaEntity, remote: SchemaEntity) -> SchemaEntity:
        entity = SchemaEntity(local.name)
        entity.external_ref = local.external_ref or remote.external_ref
        attrs = {attr["name"]: attr for attr in local.attributes}
        for attr in remote.attributes:
            attrs.setdefault(attr["name"], attr)
        for attr in sorted(attrs.values(), key=lambda item: (not item.get("pk", False), item["name"])):
            self._add_attr_dict(entity, attr)
        return entity

    def _normalize_entities(self, entities: Dict[str, SchemaEntity]) -> Dict[str, SchemaEntity]:
        normalized = {}
        for name, entity in entities.items():
            clean = SchemaEntity(name)
            clean.external_ref = entity.external_ref
            attrs = {}
            for attr in entity.attributes:
                attrs.setdefault(attr["name"], attr)
            for attr in sorted(attrs.values(), key=lambda item: (not item.get("pk", False), item["name"])):
                self._add_attr_dict(clean, attr)
            normalized[name] = clean
        return normalized

    def _dedupe_relationships(self, relationships: List[SchemaRelationship]) -> List[SchemaRelationship]:
        rels = {}
        for relationship in relationships:
            rels.setdefault(self._relationship_key(relationship), relationship)
        return [rels[key] for key in sorted(rels)]

    def _entity_to_state(self, entity: SchemaEntity) -> dict:
        return {
            "name": entity.name,
            "external_ref": entity.external_ref,
            "attributes": [dict(attr) for attr in entity.attributes],
        }

    def _state_to_entity(self, state: dict) -> SchemaEntity:
        entity_state = state.get("entity", state)
        entity = SchemaEntity(entity_state["name"])
        entity.external_ref = entity_state.get("external_ref")
        for attr in entity_state.get("attributes", []):
            self._add_attr_dict(entity, attr)
        return entity

    def _add_attr_dict(self, entity: SchemaEntity, attr: dict) -> None:
        entity.add_attribute(
            attr["name"],
            attr.get("type", "String"),
            bool(attr.get("pk", False)),
            bool(attr.get("edge", False)),
            list(attr.get("constraints") or []),
            external_link=attr.get("external_link"),
        )

    def _attribute_key(self, attr: dict) -> Tuple[Any, ...]:
        return (
            attr.get("name"),
            attr.get("type"),
            bool(attr.get("pk")),
            bool(attr.get("edge")),
            tuple(attr.get("constraints") or []),
            attr.get("external_link"),
        )

    def _relationship_key(self, rel: SchemaRelationship) -> Tuple[str, str, str, str, str, str]:
        return (
            rel.entity_a,
            rel.degree_a,
            rel.part_a,
            rel.entity_b,
            rel.degree_b,
            rel.part_b,
        )

    def _conflict_id(self, conflict: MergeConflict) -> str:
        return f"MERGE-{conflict.entity_name}-{conflict.conflict_type}"

    def _strategy_from_resolution(self, resolution: dict) -> Optional[str]:
        text = f"{resolution.get('state', '')} {resolution.get('rationale', '')}".lower()
        for strategy in ("union", "ours", "theirs"):
            if strategy in text:
                return strategy
        try:
            state = json.loads(resolution.get("state") or "{}")
        except (TypeError, ValueError):
            return None
        strategy = state.get("merge_strategy") or state.get("strategy")
        return strategy if strategy in {"union", "ours", "theirs"} else None

    def render_schema(
        self,
        entities: Dict[str, SchemaEntity],
        relationships: List[SchemaRelationship],
    ) -> str:
        sections = ["/* Merged by etg merge. */", ""]
        for name in sorted(entities):
            entity = entities[name]
            sections.append(f"ENTITY: {entity.name}")
            sections.append("ATTRIBUTES:")
            for attr in entity.attributes:
                sections.append(f"  - {self._render_attribute(attr)}")
            sections.append("")
        if relationships:
            sections.append("RELATIONSHIPS:")
            for rel in relationships:
                sections.append(
                    f"- {rel.entity_a} ({rel.degree_a}) [{rel.part_a}] --- "
                    f"[{rel.part_b}] ({rel.degree_b}) {rel.entity_b}"
                )
            sections.append("")
        return "\n".join(sections)

    def _render_attribute(self, attr: dict) -> str:
        name = f".{attr['name']}" if attr.get("pk") else attr["name"]
        parts = [attr.get("type", "String")]
        parts.extend(attr.get("constraints") or [])
        if attr.get("pk") and "PK" not in [part.upper() for part in parts]:
            parts.append("PK")
        rendered = f"{name} ({', '.join(parts)})"
        if attr.get("external_link"):
            rendered += f" [EXTERNAL: {attr['external_link']}]"
        return rendered


def _format_names(names: List[str]) -> str:
    return ", ".join(names) if names else "none"
