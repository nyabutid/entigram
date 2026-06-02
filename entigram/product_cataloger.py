import sqlite3
from pathlib import Path
from typing import List, Dict

class ProductCataloger:
    """
    The Product Cataloger Agent.
    Responsibility: Maintain the canonical Product list and its association with suppliers.
    Protocol: Ensure every Product has a valid SKU and is linked to a valid Supplier.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.db_file = self.target_dir / ".etg" / "states" / "SupplyChain.db"
    
    def validate_catalog(self) -> List[Dict[str, str]]:
        """
        Validates that all products have a valid SKU and supplier association.
        Returns a list of violations.
        """
        if not self.db_file.exists():
            print(f"Database not found: {self.db_file}")
            return []
            
        violations = []
        conn = sqlite3.connect(self.db_file)
        try:
            cursor = conn.cursor()
            # Find the product table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('product', 'products', 'Product')")
            product_table_row = cursor.fetchone()
            if not product_table_row:
                print("Product table not found.")
                return []
            
            product_table = product_table_row[0]
            
            # Find the supplier table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('supplier', 'suppliers', 'Supplier')")
            supplier_table_row = cursor.fetchone()
            if not supplier_table_row:
                print("Supplier table not found.")
                return []
            
            supplier_table = supplier_table_row[0]
            
            # Ensure required columns exist
            cursor.execute(f"PRAGMA table_info({product_table})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "sku" not in columns:
                return [{"error": "sku column missing in product table"}]
            if "supplier_id" not in columns:
                return [{"error": "supplier_id column missing in product table"}]
                
            cursor.execute(f"SELECT id, name, sku, supplier_id FROM {product_table}")
            products = cursor.fetchall()
            
            cursor.execute(f"SELECT id FROM {supplier_table}")
            valid_suppliers = {row[0] for row in cursor.fetchall()}
            
            skus_seen = {} # sku -> id
            
            for row in products:
                prod_id, name, sku, supplier_id = row
                
                # Check SKU
                if not sku or str(sku).strip() == "":
                    violations.append({
                        "product_id": str(prod_id),
                        "name": str(name),
                        "error": "Missing SKU"
                    })
                elif sku in skus_seen:
                    violations.append({
                        "product_id": str(prod_id),
                        "name": str(name),
                        "error": f"Duplicate SKU: {sku} (already used by {skus_seen[sku]})"
                    })
                else:
                    skus_seen[sku] = prod_id
                
                # Check supplier association
                if not supplier_id or supplier_id not in valid_suppliers:
                    violations.append({
                        "product_id": str(prod_id),
                        "name": str(name),
                        "error": f"Invalid or missing supplier association: {supplier_id}"
                    })
                    
            if violations:
                print(f"🚨 Product Cataloger found {len(violations)} catalog violations!")
                for v in violations:
                    print(f"   - {v.get('name', 'Unknown')} ({v.get('product_id', 'Unknown')}): {v['error']}")
            else:
                print("✅ All products passed catalog validation.")
                
            return violations
        except sqlite3.Error as e:
            print(f"Database error during catalog audit: {e}")
            return []
        finally:
            conn.close()

if __name__ == "__main__":
    cataloger = ProductCataloger()
    cataloger.validate_catalog()