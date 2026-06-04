import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from entigram.sqlite_ledger.manager import LedgerManager

STATUS_PASSED = "passed"
STATUS_NEEDS_PROOF = "needs_proof"
STATUS_BLOCKED = "blocked"  # infra failure: cannot run check, not just unproven

@dataclass
class DeveloperExpectation:
    """A modeled expectation that must be proven before agent handoff."""

    name: str
    developer_expectation: str
    implementation_rule: str
    validation_check: str
    proof: Optional[str] = None

    def to_checklist_item(
        self,
        provided_proofs: List[str] = None,
        blocked_checks: List[str] = None,
    ) -> Dict[str, Any]:
        provided_proofs = provided_proofs or []
        blocked_checks = blocked_checks or []
        expected_proof = self.proof or self.validation_check
        proof_text = "\n".join(provided_proofs).lower()

        is_blocked = any(
            bc.lower() in (self.validation_check or "").lower()
            for bc in blocked_checks
        )

        if is_blocked:
            status = STATUS_BLOCKED
        elif bool(provided_proofs) and (
            not expected_proof or expected_proof.lower() in proof_text
        ):
            status = STATUS_PASSED
        else:
            status = STATUS_NEEDS_PROOF

        return {
            "name": self.name,
            "developer_expectation": self.developer_expectation,
            "implementation_rule": self.implementation_rule,
            "validation_check": self.validation_check,
            "proof": self.proof,
            "status": status,
            "handoff_question": (
                f"You changed behavior related to '{self.name}'. "
                f"Prove this still holds: {self.validation_check}"
            ),
        }


class Commissioner:
    """
    Performs engineering-style commissioning for modeled expectations.

    Commissioner turns developer_expectation + implementation_rule +
    validation_check into a deterministic pre-handoff checklist.

    Supported schema syntax:

    EXPECTATION: Stable Jump Arc {
      developer_expectation: Player jumps should feel consistent.
      implementation_rule: Gameplay changes must not alter jump height.
      validation_check: tests/test_gameplay.py::test_jump_arc
      proof: tests/test_gameplay.py::test_jump_arc
    }

    Short keys are also accepted: expectation, rule, check.
    """

    EXPECTATION_BLOCK_PATTERN = r"EXPECTATION:?\s+([^\{\n]+)\s*\{([^}]*)\}"

    FIELD_ALIASES = {
        "developer_expectation": "developer_expectation",
        "expectation": "developer_expectation",
        "implementation_rule": "implementation_rule",
        "rule": "implementation_rule",
        "validation_check": "validation_check",
        "check": "validation_check",
        "proof": "proof",
    }

    def __init__(self, schema_text: str, ledger: "Optional[LedgerManager]" = None):
        self.schema_text = schema_text
        self.expectations = self._parse_expectations(schema_text)
        self.ledger = ledger

    @classmethod
    def from_workspace(
        cls,
        target_dir: str = ".",
        ledger: "Optional[LedgerManager]" = None,
    ) -> "Commissioner":
        target_path = Path(target_dir).expanduser().resolve()
        schema_path = target_path / "schema.lds"
        if not schema_path.exists():
            schema_path = target_path / "draft_schema.lds"

        if not schema_path.exists():
            return cls("", ledger=ledger)

        return cls(schema_path.read_text(), ledger=ledger)

    def build_checklist(
        self,
        proofs: List[str] = None,
        blocked_checks: List[str] = None,
        agent_id: Optional[str] = None,
        expectation_name: Optional[str] = None,
        persist_evidence: bool = True,
    ) -> Dict[str, Any]:
        proofs = proofs or []
        blocked_checks = blocked_checks or []
        expectations = self.expectations
        if expectation_name:
            expectations = [
                exp for exp in expectations
                if exp.name.lower() == expectation_name.lower()
            ]
            if not expectations:
                return {
                    "valid": False,
                    "expectation_count": 0,
                    "items": [],
                    "missing_proof_count": 0,
                    "blocked_count": 0,
                    "evidence_ids": [],
                    "error": f"Unknown expectation: {expectation_name}",
                }

        items = []
        for exp in expectations:
            ledger_evidence = self._passed_evidence_for(exp.name)
            ledger_proofs = self._proof_text_from_evidence(ledger_evidence)
            item = exp.to_checklist_item(proofs + ledger_proofs, blocked_checks)
            item["evidence_ids"] = [row["id"] for row in ledger_evidence]
            items.append(item)

        needs_proof = [
            item for item in items
            if item["status"] not in (STATUS_PASSED, STATUS_BLOCKED)
        ]
        blocked = [item for item in items if item["status"] == STATUS_BLOCKED]
        passed = [item for item in items if item["status"] == STATUS_PASSED]
        evidence_ids = sorted({
            evidence_id
            for item in passed
            for evidence_id in item.get("evidence_ids", [])
        })

        checklist = {
            "valid": not needs_proof and not blocked,
            "expectation_count": len(items),
            "items": items,
            "missing_proof_count": len(needs_proof),
            "blocked_count": len(blocked),
            "evidence_ids": evidence_ids,
        }

        # Persist evidence when all expectations pass
        if persist_evidence and checklist["valid"] and self.ledger and passed:
            for item in passed:
                evidence_id = self.ledger.record_delivery_evidence(
                    evidence_type="commission_pass",
                    artifact_ref="commissioner_checklist",
                    expectation_name=item["name"],
                    command=item.get("validation_check"),
                    result_summary=f"Commissioner: {item['name']} passed",
                    passed=True,
                    agent_id=agent_id,
                )
                if evidence_id:
                    item.setdefault("evidence_ids", []).append(evidence_id)
                    checklist["evidence_ids"].append(evidence_id)

        return checklist

    def format_checklist(self, checklist: Dict[str, Any]) -> str:
        if checklist.get("error"):
            return f"Commissioner: {checklist['error']}"
        if checklist["expectation_count"] == 0:
            return "Commissioner: no modeled expectations found."

        lines = [
            f"Commissioner: {checklist['expectation_count']} modeled expectations",
        ]
        for item in checklist["items"]:
            if item["status"] == STATUS_PASSED:
                marker = "PASS"
            elif item["status"] == STATUS_BLOCKED:
                marker = "BLOCKED"
            else:
                marker = "TODO"
            lines.extend(
                [
                    f"{marker} {item['name']}",
                    f"  Developer expectation: {item['developer_expectation']}",
                    f"  Implementation rule: {item['implementation_rule']}",
                    f"  Validation check: {item['validation_check']}",
                ]
            )
            if item.get("proof"):
                lines.append(f"  Expected proof: {item['proof']}")
            if item["status"] == STATUS_BLOCKED:
                lines.append(f"  ⚠ Blocked: validation check cannot run (infra or environment issue)")
            elif item["status"] != STATUS_PASSED:
                lines.append(f"  Handoff gate: {item['handoff_question']}")

        blocked_count = checklist.get("blocked_count", 0)
        artifact_errors = checklist.get("artifact_errors") or []
        if artifact_errors:
            lines.extend(f"Artifact anchor error: {error}" for error in artifact_errors)
            lines.append("Commissioner: delivery artifacts must be readable before handoff.")
        elif checklist["valid"]:
            lines.append("Commissioner: all modeled expectations have proof.")
        elif blocked_count:
            lines.append(
                f"Commissioner: {checklist['missing_proof_count']} need proof, "
                f"{blocked_count} blocked (cannot run)."
            )
        else:
            lines.append(
                f"Commissioner: {checklist['missing_proof_count']} expectations need proof before handoff."
            )
        return "\n".join(lines)

    def to_json(self, checklist: Dict[str, Any]) -> str:
        return json.dumps(checklist, indent=2)

    def _passed_evidence_for(self, expectation_name: str) -> List[Dict[str, Any]]:
        if not self.ledger:
            return []
        return self.ledger.get_delivery_evidence(
            expectation_name=expectation_name,
            passed_only=True,
        )

    def _proof_text_from_evidence(self, evidence_rows: List[Dict[str, Any]]) -> List[str]:
        proof_texts = []
        for row in evidence_rows:
            proof_texts.append(
                "\n".join(
                    str(part)
                    for part in [
                        row.get("artifact_ref"),
                        row.get("command"),
                        row.get("result_summary"),
                    ]
                    if part
                )
            )
        return proof_texts

    def _parse_expectations(self, text: str) -> List[DeveloperExpectation]:
        line_text = re.sub(self.EXPECTATION_BLOCK_PATTERN, "", text, flags=re.DOTALL | re.IGNORECASE)
        return self._parse_block_expectations(text) + self._parse_line_expectations(line_text)

    def _parse_block_expectations(self, text: str) -> List[DeveloperExpectation]:
        expectations = []
        for match in re.finditer(self.EXPECTATION_BLOCK_PATTERN, text, re.DOTALL | re.IGNORECASE):
            name = match.group(1).strip()
            fields = self._parse_fields(match.group(2))
            expectation = self._build_expectation(name, fields)
            if expectation:
                expectations.append(expectation)
        return expectations

    def _parse_line_expectations(self, text: str) -> List[DeveloperExpectation]:
        expectations = []
        current_name = None
        fields = {}

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if "{" in line or "}" in line:
                continue

            header = re.match(r"EXPECTATION:?\s+(.+)$", line, re.IGNORECASE)
            if header:
                expectation = self._build_expectation(current_name, fields)
                if expectation:
                    expectations.append(expectation)
                current_name = header.group(1).strip()
                fields = {}
                continue

            field_match = re.match(r"([a-zA-Z_]+):\s*(.+)$", line)
            if field_match:
                field_name = field_match.group(1).lower()
                canonical = self.FIELD_ALIASES.get(field_name)
                if canonical:
                    fields[canonical] = field_match.group(2).strip()

        expectation = self._build_expectation(current_name, fields)
        if expectation:
            expectations.append(expectation)
        return expectations

    def _parse_fields(self, body: str) -> Dict[str, str]:
        fields = {}
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            field_match = re.match(r"([a-zA-Z_]+):\s*(.+)$", line)
            if not field_match:
                continue
            canonical = self.FIELD_ALIASES.get(field_match.group(1).lower())
            if canonical:
                value = field_match.group(2).strip()
                if (
                    (value.startswith('"') and value.endswith('"'))
                    or (value.startswith("'") and value.endswith("'"))
                ):
                    value = value[1:-1]
                fields[canonical] = value
        return fields

    def _build_expectation(self, name: Optional[str], fields: Dict[str, str]) -> Optional[DeveloperExpectation]:
        if not name and not fields:
            return None
        if not all(fields.get(key) for key in ["developer_expectation", "implementation_rule", "validation_check"]):
            return None
        return DeveloperExpectation(
            name=name or fields["developer_expectation"],
            developer_expectation=fields["developer_expectation"],
            implementation_rule=fields["implementation_rule"],
            validation_check=fields["validation_check"],
            proof=fields.get("proof"),
        )
