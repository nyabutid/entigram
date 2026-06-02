import sqlite3
from pathlib import Path
from typing import List, Dict

class SupplierAuditor:
    """
    The Supplier Auditor Agent.
    Responsibility: Validate supplier credentials and track performance ratings.
    Protocol: Ensure every Supplier has a valid tax_id.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.db_file = self.target_dir / ".etg" / "states" / "SupplyChain.db"
    
    def validate_credentials(self) -> List[Dict[str, str]]:
        """
        Validates that all suppliers have a valid tax_id.
        Returns a list of violations.
        """
        if not self.db_file.exists():
            print(f"Database not found: {self.db_file}")
            return []
            
        violations = []
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            # The SQLite ledger injector creates tables based on the Schema. Let's look for 'supplier' or 'suppliers'
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('supplier', 'suppliers', 'Supplier')")
            table_row = cursor.fetchone()
            if not table_row:
                print("Supplier table not found.")
                return []
            
            table_name = table_row[0]
            
            # Ensure tax_id column exists
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "tax_id" not in columns:
                print(f"tax_id column missing in {table_name} table.")
                return [{"error": "tax_id column missing"}]

            cursor.execute(f"SELECT id, name, tax_id FROM {table_name}")
            for row in cursor.fetchall():
                supplier_id = row[0]
                name = row[1]
                tax_id = row[2]
                
                if not tax_id or str(tax_id).strip() == "":
                    violations.append({
                        "supplier_id": str(supplier_id),
                        "name": str(name),
                        "error": "Missing tax_id"
                    })
                # Basic tax_id validation protocol (e.g. requires prefix or certain length)
                elif not (str(tax_id).startswith("EIN-") or str(tax_id).startswith("TAX-") or str(tax_id).startswith("VAT-")):
                    violations.append({
                        "supplier_id": str(supplier_id),
                        "name": str(name),
                        "error": f"Invalid tax_id format: {tax_id}"
                    })
                    
            if violations:
                print(f"🚨 Supplier Auditor found {len(violations)} credential violations!")
                for v in violations:
                    print(f"   - {v.get('name', 'Unknown')} ({v.get('supplier_id', 'Unknown')}): {v['error']}")
            else:
                print("✅ All suppliers passed credential validation (tax_id protocol).")
                
            return violations
        except sqlite3.Error as e:
            print(f"Database error during audit: {e}")
            return []
        finally:
            conn.close()

if __name__ == "__main__":
    auditor = SupplierAuditor()
    auditor.validate_credentials()
