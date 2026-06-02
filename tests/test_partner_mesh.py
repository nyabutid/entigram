import unittest
import os
import shutil
import tempfile
import json
from pathlib import Path
from entigram.sensing.partner_mesh import PartnerMesh
from entigram.broker import EntigramBroker

class TestPartnerMesh(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.partner_data_dir = self.test_dir / "partner_data"
        self.partner_data_dir.mkdir()
        
        # Initialize Entigram workspace
        (self.test_dir / ".etg").mkdir()
        (self.test_dir / ".etg" / "entigram.yaml").write_text("packages: []\ncli_engine: Antigravity")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_mesh_directory(self):
        # 1. Create dummy partner data
        # Use semantic names like 'vendors' and 'suppliers' to ensure they fall into 'identity' block
        csv_content = "UID,Vendor_Name,EIN\nV-900,Global Fasteners,EIN-1122"
        (self.partner_data_dir / "TechCorp_Vendors.csv").write_text(csv_content)
        
        json_content = [
            {"id": "sup-101", "name": "Global Fasteners", "tax_id": "EIN-1122"}
        ]
        with open(self.partner_data_dir / "Internal_Suppliers.json", "w") as f:
            json.dump(json_content, f)

        # 2. Run Mesh
        mesh = PartnerMesh(str(self.test_dir))
        results = mesh.mesh_directory(str(self.partner_data_dir), auto_align_threshold=0.4)
        
        # 3. Verify
        self.assertIn("TechCorp_Vendors", results["ingested_domains"])
        self.assertIn("Internal_Suppliers", results["ingested_domains"])
        self.assertIn("TechCorp_Vendors", results["discovered_schema"])
        self.assertIn("Internal_Suppliers", results["discovered_schema"])
        self.assertEqual(results["alignments_count"], 0)
        self.assertGreater(results["proposals_count"], 0)
        
        # Verify alignments in ledger
        broker = EntigramBroker(str(self.test_dir))
        alignments = broker.ledger.get_alignments()
        self.assertGreater(len(alignments), 0)
        self.assertTrue(all(aln["lifecycle_status"] == "proposed" for aln in alignments))
        self.assertTrue(all(not aln["verified"] for aln in alignments))
        
        # Verify Schema files were created
        self.assertTrue((self.test_dir / ".etg" / "packages" / "TechCorp_Vendors" / "schema.lds").exists())
        self.assertTrue((self.test_dir / ".etg" / "packages" / "Internal_Suppliers" / "schema.lds").exists())

if __name__ == "__main__":
    unittest.main()
