import os
import argparse

def generate_agent_boilerplate(agent_name: str, target_dir: str):
    """Scaffolds a new Entigram edge-agent pre-wired to the SQLite ledger."""
    agent_path = os.path.join(target_dir, f"{agent_name}_edge")
    os.makedirs(agent_path, exist_ok=True)

    # 1. The Skill Definition (The Agent's Contract)
    skill_content = f"""# Edge Agent: {agent_name.capitalize()}
## Role
You are a localized edge-agent responsible for parsing {agent_name} data into the local Entigram Schema.

## Ledger Constraint (CRITICAL)
If you detect a state contradiction between {agent_name} and the local Schema, you MUST halt execution. Do not hallucinate a resolution.
You must invoke the `request_human_tiebreaker` function to log the conflict to the Entigram state ledger and await human input.
"""
    with open(os.path.join(agent_path, "SKILL.md"), "w") as f:
        f.write(skill_content)

    # 2. The Ledger Hook (The Python Integration)
    hook_content = f"""import sqlite3
import json

def request_human_tiebreaker(conflict_id: str, conflicting_state: dict, rationale: str):
    \"\"\"
    Halts agent execution and writes the conflict to the Entigram deterministic ledger.
    \"\"\"
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
        print(f"[ENTIGRAM LEDGER] Conflict {{conflict_id}} logged. Awaiting human resolution.")
    except Exception as e:
        print(f"Ledger connection failed: {{e}}")
    finally:
        if conn:
            conn.close()
"""
    with open(os.path.join(agent_path, "ledger_hook.py"), "w") as f:
        f.write(hook_content)

    print(f"Successfully bootstrapped {agent_name} agent at {agent_path}")
    print("Boilerplate includes SKILL.md and pre-wired ledger_hook.py")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entigram Agent Scaffolder")
    parser.add_argument("name", help="Name of the edge agent (e.g., stripe, salesforce)")
    parser.add_argument("--dir", default="./templates", help="Target directory for the scaffold")
    args = parser.parse_args()
    
    generate_agent_boilerplate(args.name, args.dir)
