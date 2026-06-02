import os
import sys
import shutil
import sqlite3
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from entigram.broker import EntigramBroker
from entigram.federated_router import FederatedRouter

def run_salesforce_supplychain_demo():
    demo_dir = Path("salesforce_supplychain_demo")
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir()

    print("🚀 Starting Salesforce-SupplyChain Federated Inventory Audit...")

    # 1. Setup Salesforce Domain (Sales Forecasts)
    print("\n☁️  Setting up Salesforce Domain (Sales Forecasts)...")
    sf_db_path = demo_dir / ".etg" / "states" / "Salesforce.db"
    sf_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sf_db_path)
    # SF_Product and SF_OpportunityLineItem (names must match pluralized entity names)
    # SF_Product -> sf_products
    # SF_OpportunityLineItem -> sf_opportunitylineitems
    conn.execute("CREATE TABLE sf_products (id TEXT PRIMARY KEY, name TEXT, product_code TEXT)")
    conn.execute("CREATE TABLE sf_opportunitylineitems (id TEXT PRIMARY KEY, product_id TEXT, quantity INTEGER)")
    
    # Data: Forecasted demand for 'Industrial Widget' is 100 units
    conn.execute("INSERT INTO sf_products (id, name, product_code) VALUES ('sf-p-001', 'Industrial Widget', 'WIDGET-X')")
    conn.execute("INSERT INTO sf_opportunitylineitems (id, product_id, quantity) VALUES ('sf-oli-501', 'sf-p-001', 100)")
    conn.commit()
    conn.close()

    # 2. Setup SupplyChain Domain (Inventory)
    print("📦 Setting up SupplyChain Domain (Inventory)...")
    sc_db_path = demo_dir / ".etg" / "states" / "SupplyChain.db"
    conn = sqlite3.connect(sc_db_path)
    # Product -> products
    # Inventory_Item -> inventory_items
    conn.execute("CREATE TABLE products (id TEXT PRIMARY KEY, sku TEXT, name TEXT)")
    conn.execute("CREATE TABLE inventory_items (id TEXT PRIMARY KEY, product_id TEXT, quantity INTEGER)")
    
    # Data: Current stock for 'WIDGET-X' is 45 units (LOW STOCK relative to 100 forecast)
    conn.execute("INSERT INTO products (id, sku, name) VALUES ('sc-p-101', 'WIDGET-X', 'Industrial Widget')")
    conn.execute("INSERT INTO inventory_items (id, product_id, quantity) VALUES ('sc-inv-901', 'sc-p-101', 45)")
    conn.commit()
    conn.close()

    # 3. Create Schema files
    sf_schema = """
ENTITY: SF_Product
ATTRIBUTES:
  . id (TEXT)
  - name (TEXT)
  - product_code (TEXT)

ENTITY: SF_OpportunityLineItem
ATTRIBUTES:
  . id (TEXT)
  - product_id (TEXT)
  - quantity (INTEGER)

RELATIONSHIP: SF_Product (1) [MUST] --- [MAY] (MANY) SF_OpportunityLineItem
"""
    sc_schema = """
ENTITY: Product
ATTRIBUTES:
  . id (TEXT)
  - sku (TEXT)
  - name (TEXT)

ENTITY: Inventory_Item
ATTRIBUTES:
  . id (TEXT)
  - product_id (TEXT)
  - quantity (INTEGER)

RELATIONSHIP: Product (1) [MUST] --- [MAY] (MANY) Inventory_Item
"""
    (demo_dir / "salesforce.lds").write_text(sf_schema)
    (demo_dir / "supplychain.lds").write_text(sc_schema)

    # 4. Initialize Entigram Infrastructure
    (demo_dir / ".etg" / "entigram.yaml").write_text("""
packages:
  - Salesforce
  - SupplyChain
cli_engine: Antigravity
""")

    # 5. Negotiate Alignment
    print("\n🤝 Negotiating Semantic Alignment...")
    broker = EntigramBroker(str(demo_dir))
    
    # Manually authorize the critical alignments for this demo
    # In a real scenario, broker.negotiate_alignments() would find these
    broker.authorize_alignment("Salesforce", "SupplyChain", "SF_Product", "Product", 0.95, "Fuzzy match on 'Product'")
    broker.authorize_alignment("Salesforce", "SupplyChain", "SF_Product.product_code", "Product.sku", 0.95, "Domain knowledge: Product Code == SKU")
    broker.authorize_alignment("Salesforce", "SupplyChain", "SF_OpportunityLineItem.quantity", "Inventory_Item.quantity", 0.85, "Quantity mapping")

    # 6. Execute Federated Audit Query
    print("\n🌐 Executing Federated Audit Query...")
    router = FederatedRouter(str(demo_dir))
    
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
    
    try:
        results = router.execute(query)
        print(f"Debug: Query returned {len(results)} results.")
        print("Audit Results:")
        for res in results:
            sku = res.get("sku", "UNKNOWN")
            name = res.get("name", "Unknown Product")
            
            # Inventory_Item is a nested dict or None (based on recursive SQL fallback)
            inv = res.get("Inventory_Item")
            stock = inv.get("quantity", 0) if isinstance(inv, dict) else 0
            
            # SF_Product is a nested dict or None
            sf_prod = res.get("SF_Product")
            forecast = 0
            if isinstance(sf_prod, dict):
                 oli = sf_prod.get("SF_OpportunityLineItem")
                 if isinstance(oli, dict):
                      forecast = oli.get("quantity", 0)
            
            print(f" - SKU: {sku} ({name}) | Stock: {stock} | Forecasted Demand: {forecast}")
            if stock < forecast:
                 print(f"   🚨 ALERT: Low stock detected for {sku}! Delta: {forecast - stock}")
            else:
                 print(f"   ✅ Stock level sufficient for {sku}.")

    except Exception as e:
        import traceback
        print(f"\n❌ Federated Audit Failed: {e}")
        traceback.print_exc()

    print("\n✅ Salesforce-SupplyChain Integration Demo Complete!")

if __name__ == "__main__":
    run_salesforce_supplychain_demo()
