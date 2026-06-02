from pathlib import Path
from typing import List, Dict
from entigram.federated_router import FederatedRouter

class InventoryStrategist:
    """
    The Inventory Strategist Agent.
    Responsibility: Monitor Inventory_Item levels across all Warehouse locations.
    Protocol: Flag low stock levels based on integrated sales forecasts from the Salesforce domain.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        
    def check_inventory_levels(self) -> List[Dict[str, str]]:
        """
        Flags low stock levels by comparing recorded Inventory_Item.quantity
        against sales forecasts from Salesforce.
        """
        router = FederatedRouter(str(self.target_dir))
        
        # We want to find Products where Inventory < Forecast
        query = """
        {
          Product {
            sku
            name
            Inventory_Item {
              quantity
            }
            SF_Product {
              SF_OpportunityLineItem {
                quantity
              }
            }
          }
        }
        """
        
        violations = []
        try:
            results = router.execute(query)
            for res in results:
                sku = res.get("sku", "UNKNOWN")
                name = res.get("name", "Unknown Product")
                
                # Extract inventory quantity
                inv = res.get("Inventory_Item")
                stock = 0
                if isinstance(inv, dict):
                    stock = inv.get("quantity", 0)
                elif isinstance(inv, list):
                    stock = sum(item.get("quantity", 0) for item in inv)
                
                # Extract forecast quantity
                sf_prod = res.get("SF_Product")
                forecast = 0
                if isinstance(sf_prod, dict):
                     oli = sf_prod.get("SF_OpportunityLineItem")
                     if isinstance(oli, dict):
                          forecast = oli.get("quantity", 0)
                     elif isinstance(oli, list):
                          forecast = sum(item.get("quantity", 0) for item in oli)
                
                if stock < forecast:
                    violations.append({
                        "product_sku": str(sku),
                        "name": str(name),
                        "stock": str(stock),
                        "demand": str(forecast),
                        "error": f"Low stock detected for {sku}: {stock} < {forecast}"
                    })
                    
            if violations:
                print(f"🚨 Inventory Strategist found {len(violations)} low stock warnings!")
                for v in violations:
                    print(f"   - SKU {v.get('product_sku')}: {v['error']}")
            else:
                print("✅ Inventory levels are sufficient across all monitored items.")
                
            return violations
        except Exception as e:
            print(f"Federated query error: {e}")
            return []

if __name__ == "__main__":
    strategist = InventoryStrategist()
    strategist.check_inventory_levels()
