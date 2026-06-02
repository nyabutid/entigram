import json
import sqlite3
from typing import List, Dict, Any
from entigram.broker import EntigramBroker
from entigram.sqlite_ledger.manager import LedgerManager

class EntigramSimulator:
    """
    Sandbox engine for testing agent workflows and conflict arbitration.
    Uses an in-memory SQLite ledger to prevent mutation of production state.
    """
    def __init__(self, target_dir: str):
        self.target_dir = target_dir
        self.ledger = LedgerManager(":memory:")
        self.broker = EntigramBroker(target_dir, ledger=self.ledger)

    def run_conflict_scenario(self, entity_type: str, states: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates a conflict report and captures the arbitration result.
        """
        conflict_id = f"SIM-CONFLICT-{entity_type}"
        agent_id = "Simulator-Agent"
        
        # 1. Report the conflict to our mock broker
        self.broker.report_conflict(conflict_id, entity_type, states, agent_id)
        
        # 2. Check for resolution (Auto-arbitrated or Escalated)
        resolution = self.ledger.get_resolution(conflict_id)
        pending = self.ledger.get_pending_conflicts()
        
        result = {
            "conflict_id": conflict_id,
            "status": "Escalated to Human" if not resolution else "Auto-Resolved",
            "resolution": resolution,
            "is_pending": any(c['conflict_id'] == conflict_id for c in pending)
        }
        
        return result

    def simulate_cross_domain_sensing(self, source_domain: str, target_domain: str, source_state: Dict[str, Any], target_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Simulates sensing between two domains with synthetic states.
        """
        # We need to temporarily inject some alignments into the in-memory ledger for this to work
        # Usually, the simulator would copy approved alignments from production to test them.
        real_broker = EntigramBroker(self.target_dir)
        approved_alignments = real_broker.ledger.get_alignments()
        
        for aln in approved_alignments:
            self.ledger.record_alignment(
                aln['source_domain'], aln['target_domain'],
                aln['source_concept'], aln['target_concept'],
                aln['confidence'], aln['rationale']
            )
            
        return self.broker.detect_cross_domain_conflict(source_domain, target_domain, source_state, target_state)
