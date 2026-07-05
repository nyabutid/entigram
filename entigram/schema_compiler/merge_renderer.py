import json

from entigram.schema_compiler.merger import MergeConflict, MergeDiff, MergeResult


class MergeRenderer:
    """Terminal UI for interactive merge conflict resolution."""

    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"

    def render_diff(self, diff: MergeDiff) -> None:
        """Print colorized diff summary to stdout."""
        print("📊 Schema Diff:")
        print(self._line(self.GREEN, "+", f"{len(diff.added_entities)} entities added ({self._names([e.name for e in diff.added_entities])})"))
        print(self._line(self.YELLOW, "~", f"{len(diff.modified_entities)} entities modified ({self._names([e[0].name for e in diff.modified_entities])})"))
        print(self._line(self.RED, "-", f"{len(diff.removed_entities)} entities removed ({self._names([e.name for e in diff.removed_entities])})"))
        print(self._line(self.GREEN, "+", f"{len(diff.added_relationships)} relationships added"))
        print(self._line(self.RED, "-", f"{len(diff.removed_relationships)} relationships removed"))
        if diff.conflicts:
            print()
            print(f"⚠️  {len(diff.conflicts)} conflicts detected:")

    def prompt_conflict(self, conflict: MergeConflict) -> str:
        """Interactive prompt for a single conflict."""
        print()
        print(f"Entity '{conflict.entity_name}' — {conflict.conflict_type.replace('_', ' ')}")
        print(f"┌─ LOCAL:  {self._attribute_summary(conflict.local_state)}")
        print(f"└─ REMOTE: {self._attribute_summary(conflict.remote_state)}")
        if conflict.suggested_resolution:
            print(f"💡 Precedent found: {conflict.suggested_resolution.upper()} strategy")
        print()
        print("Resolution: (1) Union  (2) Accept local  (3) Accept remote  (4) Manual edit")
        choice = input("> ").strip()
        return {
            "1": "union",
            "2": "ours",
            "3": "theirs",
            "4": "manual",
        }.get(choice, "union")

    def render_result(self, result: MergeResult) -> None:
        """Print final merge summary with stats."""
        stats = result.ledger_stats or {}
        print()
        print("📝 Merge Results:")
        print(f"   ✅ {result.entities_added + result.entities_resolved} entities merged ({result.entities_added} added, {result.entities_resolved} resolved)")
        print(f"   ✅ {result.relationships_added} relationships added")
        print(f"   ✅ {stats.get('semantic_alignments', 0)} semantic alignments imported")
        print(f"   ✅ {stats.get('synonyms', 0)} synonyms imported")
        if stats.get("human_resolutions", 0):
            print(f"   ✅ {stats.get('human_resolutions', 0)} remote resolutions imported")
        if result.warden_locked:
            print("   🔒 Warden fingerprint updated")
        if result.output_path:
            print(f"   📝 Merged schema written to {result.output_path}")
        print()
        print("   Decisions recorded to .etg/state.db (immutable ledger)")

    def _line(self, color: str, marker: str, text: str) -> str:
        return f"   {color}{marker}{self.RESET} {text}"

    def _names(self, names) -> str:
        return ", ".join(names) if names else "none"

    def _attribute_summary(self, state: dict) -> str:
        attrs = state.get("attributes", [])
        return "[" + ", ".join(
            f"{attr.get('name')} ({attr.get('type', 'String')})"
            for attr in attrs
        ) + "]"

    def _json(self, value) -> str:
        return json.dumps(value, indent=2, sort_keys=True)
