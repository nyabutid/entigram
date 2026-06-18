import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .commissioner import Commissioner, STATUS_BLOCKED, STATUS_PASSED

if TYPE_CHECKING:
    from entigram.sqlite_ledger.manager import LedgerManager


class ExpectationGuard:
    """
    Runs modeled expectations as a pre-handoff verification gate.

    The guard is the agent-facing wrapper around Commissioner: it turns each
    developer expectation, implementation rule, and validation_check into a
    single pass/fail verdict, running unresolved checks when possible.
    """

    def __init__(
        self,
        target_dir: str = ".",
        ledger: "Optional[LedgerManager]" = None,
    ):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.ledger = ledger
        self.commissioner = Commissioner.from_workspace(
            str(self.target_dir),
            ledger=ledger,
        )

    def verify(
        self,
        proofs: Optional[List[str]] = None,
        blocked_checks: Optional[List[str]] = None,
        agent_id: Optional[str] = None,
        expectation_name: Optional[str] = None,
        run_validation_checks: bool = True,
        timeout: int = 120,
    ) -> Dict[str, Any]:
        proofs = proofs or []
        blocked_checks = blocked_checks or []

        initial = self.commissioner.build_checklist(
            proofs=proofs,
            blocked_checks=blocked_checks,
            agent_id=agent_id,
            expectation_name=expectation_name,
            persist_evidence=False,
        )
        if initial.get("error"):
            initial["guard"] = {
                "valid": False,
                "ran_validation_checks": False,
                "verification_results": [],
                "handoff_verdict": "FAILED",
            }
            return initial

        verification_results: List[Dict[str, Any]] = []
        if run_validation_checks:
            missing = [
                item for item in initial.get("items", [])
                if item.get("status") not in (STATUS_PASSED, STATUS_BLOCKED)
            ]
            for item in missing:
                result = self._run_validation_check(
                    item,
                    agent_id=agent_id,
                    timeout=timeout,
                )
                verification_results.append(result)

        final = self.commissioner.build_checklist(
            proofs=proofs,
            blocked_checks=blocked_checks,
            agent_id=agent_id,
            expectation_name=expectation_name,
            persist_evidence=True,
        )
        final["guard"] = {
            "valid": final.get("valid", False),
            "ran_validation_checks": run_validation_checks,
            "verification_results": verification_results,
            "handoff_verdict": "PASSED" if final.get("valid") else "FAILED",
        }
        return final

    def format_result(self, result: Dict[str, Any]) -> str:
        lines = [self.commissioner.format_checklist(result)]
        guard = result.get("guard") or {}
        verification_results = guard.get("verification_results") or []

        if verification_results:
            lines.append("")
            lines.append("Expectation guard verification:")
            for check in verification_results:
                marker = "PASS" if check.get("passed") else "FAIL"
                lines.append(
                    f"{marker} {check.get('expectation_name')}: {check.get('command')}"
                )
                summary = check.get("result_summary")
                if summary:
                    lines.append(f"  {summary}")

        verdict = guard.get("handoff_verdict", "PASSED" if result.get("valid") else "FAILED")
        lines.append("")
        lines.append(f"Expectation guard: {verdict}")
        return "\n".join(lines)

    def _run_validation_check(
        self,
        item: Dict[str, Any],
        *,
        agent_id: Optional[str],
        timeout: int,
    ) -> Dict[str, Any]:
        command = (item.get("validation_check") or "").strip()
        expectation_name = item.get("name")
        if not command:
            return self._record_check_result(
                expectation_name=expectation_name,
                command=command,
                passed=False,
                result_summary="Missing validation_check",
                agent_id=agent_id,
            )

        try:
            cmd_args = shlex.split(command)
        except ValueError as exc:
            return self._record_check_result(
                expectation_name=expectation_name,
                command=command,
                passed=False,
                result_summary=f"Invalid validation command: {exc}",
                agent_id=agent_id,
            )

        if not cmd_args:
            return self._record_check_result(
                expectation_name=expectation_name,
                command=command,
                passed=False,
                result_summary="Empty validation command",
                agent_id=agent_id,
            )
        cmd_args = self._normalize_command(cmd_args)

        try:
            proc = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.target_dir),
            )
            output = (proc.stdout + proc.stderr).strip()
            summary = output[:500] if output else f"Exit code {proc.returncode}"
            return self._record_check_result(
                expectation_name=expectation_name,
                command=command,
                passed=proc.returncode == 0,
                result_summary=summary,
                agent_id=agent_id,
                return_code=proc.returncode,
            )
        except FileNotFoundError as exc:
            return self._record_check_result(
                expectation_name=expectation_name,
                command=command,
                passed=False,
                result_summary=str(exc),
                agent_id=agent_id,
            )
        except subprocess.TimeoutExpired:
            return self._record_check_result(
                expectation_name=expectation_name,
                command=command,
                passed=False,
                result_summary=f"Timeout after {timeout}s",
                agent_id=agent_id,
            )

    def _record_check_result(
        self,
        *,
        expectation_name: Optional[str],
        command: str,
        passed: bool,
        result_summary: str,
        agent_id: Optional[str],
        return_code: Optional[int] = None,
    ) -> Dict[str, Any]:
        evidence_id = None
        if self.ledger:
            evidence_id = self.ledger.record_delivery_evidence(
                evidence_type="test_run",
                artifact_ref=command or "validation_check",
                expectation_name=expectation_name,
                command=command,
                result_summary=result_summary,
                passed=passed,
                agent_id=agent_id,
            )
        return {
            "expectation_name": expectation_name,
            "command": command,
            "passed": passed,
            "return_code": return_code,
            "result_summary": result_summary,
            "evidence_id": evidence_id,
        }

    def _normalize_command(self, cmd_args: List[str]) -> List[str]:
        if cmd_args and cmd_args[0] in {"python", "python3"}:
            return [sys.executable] + cmd_args[1:]
        if cmd_args and self._looks_like_python_check(cmd_args[0]):
            if "::" in cmd_args[0]:
                return [sys.executable, "-m", "pytest"] + cmd_args
            return [sys.executable] + cmd_args
        return cmd_args

    def _looks_like_python_check(self, value: str) -> bool:
        check_file = value.split("::", 1)[0]
        return (
            check_file.endswith(".py")
            or check_file.startswith("tests/")
            or check_file.startswith("test_")
        )
