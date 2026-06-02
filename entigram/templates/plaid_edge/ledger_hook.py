import sqlite3
import json

def request_human_tiebreaker(conflict_id: str, conflicting_state: dict, rationale: str):
    """
    Halts agent execution and writes the conflict to the Entigram deterministic ledger.
    """
    # In a production environment, this path is resolved via the Entigram config
    db_path = '../../entigram/sqlite_ledger/entigram_state.db' 
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO human_resolutions (conflict_id, resolved_state, rationale) 
               VALUES (?, ?, ?)''',
            (conflict_id, json.dumps(conflicting_state), rationale)
        )
        conn.commit()
        print(f"[ENTIGRAM LEDGER] Conflict {conflict_id} logged. Awaiting human resolution.")
    except Exception as e:
        print(f"Ledger connection failed: {e}")
    finally:
        if conn:
            conn.close()
