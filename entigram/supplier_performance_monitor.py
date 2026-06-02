import sqlite3
from pathlib import Path
from typing import List, Dict

class SupplierPerformanceMonitor:
    """
    The Supplier Performance Monitor Agent.
    Responsibility: Track performance ratings and flag underperforming suppliers.
    Protocol: Flag suppliers with a rating below 3.0.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.db_file = self.target_dir / ".etg" / "states" / "SupplyChain.db"
    
    def check_performance(self, threshold: float = 3.0) -> List[Dict[str, str]]:
        """
        Flags suppliers with a rating below the threshold.
        Returns a list of warnings.
        """
        if not self.db_file.exists():
            print(f"Database not found: {self.db_file}")
            return []
            
        warnings = []
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            
            # Find supplier table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('supplier', 'suppliers', 'Supplier')")
            supplier_table_row = cursor.fetchone()
            if not supplier_table_row:
                print("Supplier table not found.")
                return []
            supplier_table = supplier_table_row[0]
            
            # Ensure rating column exists
            cursor.execute(f"PRAGMA table_info({supplier_table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "rating" not in columns:
                print(f"rating column missing in {supplier_table} table.")
                return []

            cursor.execute(f"SELECT id, name, rating FROM {supplier_table} WHERE rating < ?", (threshold,))
            for row in cursor.fetchall():
                supplier_id, name, rating = row
                
                warnings.append({
                    "supplier_id": str(supplier_id),
                    "name": str(name),
                    "rating": str(rating),
                    "error": f"Underperforming supplier: Rating {rating} is below threshold {threshold}"
                })
                    
            if warnings:
                print(f"🚨 Supplier Performance Monitor found {len(warnings)} underperforming suppliers!")
                for w in warnings:
                    print(f"   - {w.get('name', 'Unknown')} ({w.get('supplier_id', 'Unknown')}): {w['error']}")
            else:
                print(f"✅ All suppliers are above the performance threshold ({threshold}).")
                
            return warnings
        except sqlite3.Error as e:
            print(f"Database error during performance audit: {e}")
            return []
        finally:
            conn.close()

if __name__ == "__main__":
    monitor = SupplierPerformanceMonitor()
    monitor.check_performance()
