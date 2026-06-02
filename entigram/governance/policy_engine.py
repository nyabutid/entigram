from typing import Dict, Any, List, Optional
import json

class PolicyEngine:
    """
    Tiered Agentic Oversight Policy Engine.
    Deterministically arbitrates low-risk contradictions to prevent 
    Queueing Theory collapse in the human-in-the-loop ledger.
    """
    def __init__(self):
        # Heuristic rules for auto-resolution
        self.rules = [
            self._rule_non_key_text_update,
            self._rule_deterministic_source_win
        ]

    def evaluate_conflict(self, conflict_id: str, entity_type: str, proposed_states: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluates a conflict against heuristic rules.
        Returns a resolution dict if auto-resolved, else None (Escalate to Human).
        """
        for rule in self.rules:
            resolution = rule(conflict_id, entity_type, proposed_states)
            if resolution:
                return resolution
        return None

    def _rule_non_key_text_update(self, conflict_id: str, entity_type: str, proposed_states: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Auto-resolves if the conflict only involves non-key, non-numeric text updates.
        Prioritizes the first agent's state as a stable default.
        """
        # In a real implementation, we'd compare the keys in proposed_states
        # For this hardening step, we'll implement a simple heuristic:
        # If any state change involves "description" or "note", it's low risk.
        
        # Simulating logic: if all agents agree on PK but disagree on 'description'
        states = list(proposed_states.values())
        if len(states) < 2: return None
        
        # Check for risky fields
        dangerous_fields = ['id', 'uuid', 'pk', 'amount', 'price', 'status', 'email']
        
        # Find differing keys
        all_keys = set()
        for s in states:
            if isinstance(s, dict):
                all_keys.update(s.keys())
            else:
                # If it's a scalar, we treat the key as the concept itself or a generic 'value'
                all_keys.add('value')
        
        diff_keys = []
        for k in all_keys:
            if k == 'value':
                # Only compare scalar states under the synthetic 'value' key
                vals = set(str(s) for s in states if not isinstance(s, dict))
            else:
                vals = set(str(s.get(k)) for s in states if isinstance(s, dict))

            if len(vals) > 1:
                diff_keys.append(k)

        # Identical states — nothing to resolve
        if not diff_keys:
            return None

        # If any diff key is dangerous, we must ESCALATE
        for dk in diff_keys:
            if any(df in dk.lower() for df in dangerous_fields):
                return None

        # All differences are in safe fields (e.g. description)
        # Auto-resolve by taking the most recent or first state
        return {
            "resolved_state": states[0],
            "rationale": f"Auto-resolved via Policy [Tier 1]: Conflict limited to low-risk text fields ({', '.join(diff_keys)})."
        }

    def _rule_deterministic_source_win(self, conflict_id: str, entity_type: str, proposed_states: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Placeholder for more complex source-of-truth rules
        return None
