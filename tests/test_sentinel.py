import unittest
import shutil
from pathlib import Path
from entigram.governance.sentinel import SentinelScanner

class TestSentinelScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("test_sentinel_workspace")
        self.packages_dir = self.test_dir / "packages"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.packages_dir.mkdir(parents=True)
        
        # 1. Setup a standard package with a known vulnerability
        aws_dir = self.packages_dir / "AWS"
        aws_dir.mkdir()
        (aws_dir / "schema.lds").write_text("ENTITY Bucket { id UUID }")
        
        # 2. Setup a custom package with a heuristic vulnerability
        custom_dir = self.packages_dir / "MyCustomAuth"
        custom_dir.mkdir()
        (custom_dir / "schema.lds").write_text("ENTITY User { id UUID, password String }")
        
        self.scanner = SentinelScanner(str(self.test_dir))

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_scan_standard_package(self):
        self.scanner.vulnerability_db["AWS"] = [{"id": "CVE-TEST-001", "severity": "HIGH", "description": "Test"}]
        results = self.scanner.scan_package("AWS")
        self.assertTrue(results["is_standard"])
        vulns = results["vulnerabilities"]
        self.assertTrue(any(v["id"] == "CVE-TEST-001" for v in vulns))

    def test_scan_custom_package(self):
        results = self.scanner.scan_package("MyCustomAuth")
        self.assertFalse(results["is_standard"])
        vulns = results["vulnerabilities"]
        self.assertTrue(any(v["id"] == "SNTNL-CUST-001" for v in vulns))

    def test_bypass_custom_package(self):
        # Authorize bypass
        success = self.scanner.authorize_bypass("MyCustomAuth", "SNTNL-CUST-001", "It is hashed in application layer")
        self.assertTrue(success)
        
        # Rescan
        results = self.scanner.scan_package("MyCustomAuth")
        vulns = results["vulnerabilities"]
        self.assertFalse(any(v["id"] == "SNTNL-CUST-001" for v in vulns))
        self.assertIn("SNTNL-CUST-001", results["bypassed"])

    def test_reject_bypass_standard_package(self):
        self.scanner.vulnerability_db["AWS"] = [{"id": "CVE-TEST-001", "severity": "HIGH", "description": "Test"}]
        success = self.scanner.authorize_bypass("AWS", "CVE-TEST-001", "I don't care about encryption")
        self.assertFalse(success)
        
        results = self.scanner.scan_package("AWS")
        self.assertTrue(any(v["id"] == "CVE-TEST-001" for v in results["vulnerabilities"]))

if __name__ == "__main__":
    unittest.main()
