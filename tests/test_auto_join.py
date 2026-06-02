import unittest
import os
import shutil
import sqlite3
from pathlib import Path
from entigram.federated_router import FederatedRouter
from entigram.broker import EntigramBroker
from entigram.injector import inject_entigram_manifest
from entigram.sqlite_ledger.injector import DomainSQLiteInjector

class TestAutoJoinDiscovery(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_workspace_autojoin")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()

        # Domains: Customer -> Order
        packages = ["Banking", "SupplyChain"]
        inject_entigram_manifest(str(self.test_dir), packages, "Antigravity")
        
        # Setup Schema with clear but un-mapped FK: Order.customer_ref -> Customer.id
        # Banking Domain
        pkg_dir = self.test_dir / ".etg" / "packages" / "Banking"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        schema = "ENTITY Customer { id UUID PK \n name String }"
        (pkg_dir / "schema.lds").write_text(schema)

        # SupplyChain Domain
        pkg_dir = self.test_dir / ".etg" / "packages" / "SupplyChain"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        schema = "ENTITY Order { id UUID PK \n amount Decimal \n customer_ref UUID }"
        (pkg_dir / "schema.lds").write_text(schema)

        injector = DomainSQLiteInjector(str(self.test_dir))
        injector.inject_all_active()

        # Populate Data
        conn = sqlite3.connect(self.test_dir / ".etg" / "states" / "Banking.db")
        conn.execute("INSERT INTO customers (id, name) VALUES ('c-1', 'Alice')")
        conn.commit()
        conn.close()

        conn = sqlite3.connect(self.test_dir / ".etg" / "states" / "SupplyChain.db")
        conn.execute("INSERT INTO orders (id, amount, customer_ref) VALUES ('o-1', 99.99, 'c-1')")
        conn.commit()
        conn.close()

        self.router = FederatedRouter(str(self.test_dir))
        self.broker = EntigramBroker(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_auto_join_discovery_on_query(self):
        # We do NOT authorize any alignment here.
        # The router should discover Order.customer_ref -> Customer.id automatically.
        
        graphql = """
        {
          Customer {
            name
            Order {
              amount
            }
          }
        }
        """
        # Trigger query
        results = self.router.execute(graphql)
        
        self.assertEqual(len(results), 1)
        alice = results[0]
        self.assertEqual(alice['name'], 'Alice')
        
        self.assertIn('Order', alice)
        order = alice['Order']
        self.assertIsNotNone(order)
        self.assertEqual(order['amount'], 99.99)
        
        # Verify that an alignment was actually recorded in the ledger
        alignments = self.broker.ledger.get_alignments()
        found = False
        for aln in alignments:
            if "Order.customer_ref" in aln['source_concept'] or "Order.customer_ref" in aln['target_concept']:
                found = True
                self.assertIn("Auto-Discovered", aln['rationale'])
        self.assertTrue(found, "Router should have recorded an auto-discovered alignment")

if __name__ == "__main__":
    unittest.main()
