import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from entigram.broker import EntigramBroker
from entigram.injector import inject_entigram_manifest
from entigram.mcp_service import EntigramMCPService
from entigram.sqlite_ledger.manager import LedgerManager
from entigram.sqlite_ledger.paths import resolve_ledger_path


SCHEMA = """
ENTITY: Supplier {
  id UUID PK
  name String
  tax_id String
}

ENTITY: Account {
  id UUID PK
  owner_name String
}
"""


def main():
    workspace = Path(tempfile.mkdtemp(prefix="entigram-gate-demo-"))
    try:
        inject_entigram_manifest(str(workspace), ["Entigram Schemas"], "Codex")
        (workspace / "schema.lds").write_text(SCHEMA)

        service = EntigramMCPService(str(workspace))
        schemas = json.loads(service.get_schemas())
        invalid = json.loads(service.propose_alignment(json.dumps({
            "source_domain": "CRM",
            "target_domain": "ERP",
            "source_concept": "Ghost.name",
            "target_concept": "Supplier.name",
            "confidence": 0.9,
            "rationale": "This should be rejected.",
        })))
        valid = json.loads(service.propose_alignment(json.dumps({
            "source_domain": "CRM",
            "target_domain": "ERP",
            "source_concept": "Account.owner_name",
            "target_concept": "Supplier.name",
            "confidence": 0.91,
            "rationale": "Both fields identify the supplier-facing account owner.",
        })))
        conflict = json.loads(service.log_conflict(json.dumps({
            "conflict_id": "SupplierName_001",
            "entity_type": "Supplier",
            "agent_id": "DemoAgent",
            "proposed_states": {
                "DemoAgent": {"name": "Acme Corp"},
                "ERPAgent": {"name": "ACME Corporation"},
            },
        })))

        ledger = LedgerManager(str(resolve_ledger_path(str(workspace))))
        try:
            alignments = ledger.get_alignments()
            conflicts = ledger.get_pending_conflicts()
        finally:
            ledger.close()

        broker = EntigramBroker(str(workspace))
        delivery = broker.commission_and_record()
        status = broker.delivery_status()
        audit = broker.export_audit_bundle()
        broker.close()

        result = {
            "workspace": str(workspace),
            "schemas": [schema["path"] for schema in schemas["schemas"]],
            "invalid_alignment_code": invalid["error"]["code"],
            "valid_alignment": valid,
            "alignment_rows": len(alignments),
            "conflict": conflict,
            "conflict_rows": len(conflicts),
            "delivery_snapshot": delivery.get("snapshot_id"),
            "delivery_status": status["status"],
            "audit_sha256": audit["sha256"],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
    finally:
        shutil.rmtree(workspace)


if __name__ == "__main__":
    main()
