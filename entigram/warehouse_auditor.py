import sqlite3
from pathlib import Path
from typing import List, Dict

class WarehouseAuditor:
    """
    The Warehouse Auditor Agent.
    Responsibility: Track storage capacity and constraints.
    Protocol: Ensure total Inventory_Item quantities in a Warehouse do not exceed its capacity.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.db_file = self.target_dir / ".etg" / "states" / "SupplyChain.db"
    
    def validate_capacity(self) -> List[Dict[str, str]]:
        """
        Validates that no warehouse exceeds its capacity.
        Returns a list of violations.
        """
        if not self.db_file.exists():
            print(f"Database not found: {self.db_file}")
            return []
            
        violations = []
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            
            # Find warehouse table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('warehouse', 'warehouses', 'Warehouse')")
            warehouse_table_row = cursor.fetchone()
            if not warehouse_table_row:
                print("Warehouse table not found.")
                return []
            warehouse_table = warehouse_table_row[0]
            
            # Find inventory item table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('inventory_item', 'inventory_items', 'Inventory_Item')")
            inventory_table_row = cursor.fetchone()
            if not inventory_table_row:
                print("Inventory_Item table not found.")
                return []
            inventory_table = inventory_table_row[0]
            
            # Ensure capacity and warehouse_id columns exist
            cursor.execute(f"PRAGMA table_info({warehouse_table})")
            wh_columns = [info[1] for info in cursor.fetchall()]
            
            cursor.execute(f"PRAGMA table_info({inventory_table})")
            inv_columns = [info[1] for info in cursor.fetchall()]
            
            if "capacity" not in wh_columns:
                return [{"error": f"capacity column missing in {warehouse_table}"}]
            
            # In many-to-one, inventory_item should have warehouse_id or similar
            warehouse_ref = next((c for c in inv_columns if c in ["warehouse_id", "warehouse_ref", "location_id"]), None)
            if not warehouse_ref:
                return [{"error": f"Warehouse reference column missing in {inventory_table}"}]

            # Query total quantity per warehouse
            query = f"""
            SELECT 
                w.id, 
                w.location_name, 
                w.capacity, 
                SUM(i.quantity) as total_quantity
            FROM {warehouse_table} w
            LEFT JOIN {inventory_table} i ON w.id = i.{warehouse_ref}
            GROUP BY w.id
            """
            
            cursor.execute(query)
            for row in cursor.fetchall():
                wh_id, name, capacity, total_quantity = row
                total_quantity = total_quantity or 0
                
                if capacity and total_quantity > capacity:
                    violations.append({
                        "warehouse_id": str(wh_id),
                        "name": str(name),
                        "capacity": str(capacity),
                        "total_quantity": str(total_quantity),
                        "error": f"Capacity exceeded: {total_quantity} > {capacity}"
                    })
                    
            if violations:
                print(f"🚨 Warehouse Auditor found {len(violations)} capacity violations!")
                for v in violations:
                    print(f"   - {v.get('name', 'Unknown')} ({v.get('warehouse_id', 'Unknown')}): {v['error']}")
            else:
                print("✅ All warehouses are within capacity limits.")
                
            return violations
        except sqlite3.Error as e:
            print(f"Database error during warehouse audit: {e}")
            return []
        finally:
            conn.close()

if __name__ == "__main__":
    auditor = WarehouseAuditor()
    auditor.validate_capacity()
