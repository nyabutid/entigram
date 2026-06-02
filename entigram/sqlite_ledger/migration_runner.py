import os
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

class MigrationRunner:
    def __init__(self, db_path: str, migrations_dir: str):
        self.db_path = Path(db_path).expanduser().resolve()
        self.migrations_dir = Path(migrations_dir).expanduser().resolve()
        self._ensure_migration_table()

    def _ensure_migration_table(self):
        """Ensures the migrations table exists in the target database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS migrations (
                        id INTEGER PRIMARY KEY,
                        filename TEXT UNIQUE,
                        executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
        finally:
            conn.close()

    def get_applied_migrations(self) -> List[str]:
        """Returns a list of filenames of migrations already applied."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT filename FROM migrations')
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_pending_migrations(self) -> List[Path]:
        """Returns a list of .sql files in the migrations directory not yet applied."""
        if not self.migrations_dir.exists():
            return []
            
        applied = self.get_applied_migrations()
        pending = []
        
        # Look for .sql files, sorted by name (standard versioning)
        for f in sorted(self.migrations_dir.glob("*.sql")):
            if f.name not in applied:
                pending.append(f)
        
        return pending

    def run_migrations(self) -> List[str]:
        """Executes all pending migrations."""
        pending = self.get_pending_migrations()
        executed = []
        
        if not pending:
            return executed

        conn = sqlite3.connect(self.db_path)
        try:
            for migration_file in pending:
                print(f"Applying migration: {migration_file.name}")
                with open(migration_file, 'r') as f:
                    sql = f.read()
                
                # Split by semicolon for execution, or use executescript
                # executescript handles multiple statements and wraps in transaction
                with conn:
                    conn.executescript(sql)
                    conn.execute('INSERT INTO migrations (filename) VALUES (?)', (migration_file.name,))
                
                executed.append(migration_file.name)
        except Exception as e:
            print(f"Error applying migration {migration_file.name}: {e}")
            raise
        finally:
            conn.close()
            
        return executed

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Entigram Migration Runner")
    parser.add_argument("--db", required=True, help="Path to the target SQLite database")
    parser.add_argument("--dir", required=True, help="Path to the migrations directory")
    
    args = parser.parse_args()
    
    runner = MigrationRunner(args.db, args.dir)
    try:
        applied = runner.run_migrations()
        if applied:
            print(f"Successfully applied {len(applied)} migrations.")
        else:
            print("No pending migrations.")
    except Exception as e:
        print(f"Migration failed: {e}")
        import sys
        sys.exit(1)
