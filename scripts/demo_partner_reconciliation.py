import os
import sys
import shutil
import sqlite3
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from entigram.sensing.partner_sensor import PartnerCSVSensor
from entigram.schema_compiler.discoverer import DomainDiscoverer
from entigram.broker import EntigramBroker
from entigram.federated_router import FederatedRouter

def run_reconciliation_demo():
    demo_dir = Path("partner_reconciliation_demo")
    if demo_dir.exists():
        shutil.rmtree(demo_dir)
    demo_dir.mkdir()

    print("🚀 Starting Multi-Partner Semantic Reconciliation Demo...")

    # 1. Simulate External Partner Data (CSV)
    # Different headers: UID instead of id, Vendor_Name instead of name
    csv_content = """UID,Vendor_Name,EIN,Trust_Score
V-900,Global Fasteners,EIN-1122,0.88
V-901,Precision Parts,EIN-3344,0.92
"""
    csv_path = demo_dir / "techcorp_vendors.csv"
    csv_path.write_text(csv_content)

    # 2. Ingest Partner Data into a dedicated Domain
    sensor = PartnerCSVSensor(str(demo_dir))
    sensor.ingest_csv(str(csv_path), "TechCorp_Logistics", "vendors")

    # 3. Discover Schema from the ingested database
    print("\n🔍 Discovering Partner Schema...")
    db_path = demo_dir / ".etg" / "states" / "TechCorp_Logistics.db"
    discoverer = DomainDiscoverer(str(db_path))
    partner_schema_content = discoverer.discover_schema()
    
    partner_schema_path = demo_dir / "techcorp_logistics.lds"
    partner_schema_path.write_text(partner_schema_content)
    print(f"✅ Partner Schema Discovered:\n{partner_schema_content}")

    # 4. Setup our Internal Domain (SupplyChain)
    print("\n📦 Setting up Internal Domain (SupplyChain)...")
    # We'll just create the DB directly for this demo
    internal_db_path = demo_dir / ".etg" / "states" / "SupplyChain.db"
    conn = sqlite3.connect(internal_db_path)
    conn.execute("CREATE TABLE suppliers (id TEXT, name TEXT, tax_id TEXT, rating REAL)")
    conn.execute("INSERT INTO suppliers (id, name, tax_id, rating) VALUES ('sup-101', 'Global Fasteners', 'EIN-1122', 4.8)")
    conn.commit()
    conn.close()

    internal_schema_content = """ENTITY: Supplier
ATTRIBUTES:
  . id (TEXT)
  - name (TEXT)
  - tax_id (TEXT)
  - rating (REAL)
"""
    internal_schema_path = demo_dir / "internal_supply_chain.lds"
    internal_schema_path.write_text(internal_schema_content)

    # 5. Initialize Entigram Infrastructure
    # We need a entigram.yaml for the broker to work
    (demo_dir / ".etg" / "entigram.yaml").write_text("""
packages:
  - TechCorp_Logistics
  - SupplyChain
cli_engine: Antigravity
""")

    # 6. Negotiate Alignment
    print("\n🤝 Negotiating Semantic Alignment between TechCorp and Internal Supply Chain...")
    broker = EntigramBroker(str(demo_dir))
    proposals = broker.negotiate_alignments(str(partner_schema_path), str(internal_schema_path), threshold=0.4)
    
    print("Found Alignment Proposals:")
    for p in proposals:
        print(f" - [{p['confidence']}] {p['source_concept']} <-> {p['target_concept']} ({p['rationale']})")
        # Auto-authorize high confidence
        if p['confidence'] > 0.45: # Low threshold for demo fuzzy matching
            broker.authorize_alignment(
                "TechCorp_Logistics", "SupplyChain", 
                p['source_concept'], p['target_concept'], 
                p['confidence'], p['rationale']
            )

    # 7. Execute Federated Query
    print("\n🌐 Executing Federated Query across aligned domains...")
    router = FederatedRouter(str(demo_dir))
    
    query = """
    {
      Supplier {
        name
        tax_id
        Vendor {
          Vendor_Name
          Trust_Score
        }
      }
    }
    """
    
    try:
        results = router.execute(query)
        print("Federated Query Results:")
        print(json.dumps(results, indent=2))
        
        # Verify join success
        if results and "Vendor" in results[0] and results[0]["Vendor"]:
             print("\n✅ SUCCESS: Federated join executed via semantic alignment!")
        else:
             print("\n⚠️ WARNING: Federated join returned no nested data. Check alignment logic.")
    except Exception as e:
        print(f"\n❌ Federated Query Failed: {e}")

    print("\n✅ Multi-Partner Reconciliation Demo Complete!")
    print(f"Workspace: {demo_dir.absolute()}")

if __name__ == "__main__":
    run_reconciliation_demo()
