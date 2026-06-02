import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..schema_compiler.parser import SchemaParser

class SentinelScanner:
    """
    Sentinel: The Entigram Package Vulnerability Scanner (Agentic SAST).
    Performs true AST-based static analysis on Schema models to enforce Semantic Governance,
    while also checking for traditional PII/Heuristic leaks.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        
        # Look in local project packages and the registry cache
        self.local_packages_dir = self.target_dir / ".etg" / "packages"
        self.global_registry_cache = Path.home() / ".etg" / "registry_cache"
        
        # Simulated vulnerability database for standard packages
        self.vulnerability_db = {
            "ContentPublishing": [],
            "AWS": []
        }
        
        # Heuristics for custom package vulnerabilities (Regex-based fallback)
        self.custom_heuristics = [
            {"id": "SNTNL-CUST-001", "severity": "MEDIUM", "trigger": "password", "description": "Plaintext password attribute detected in Schema"},
            {"id": "SNTNL-CUST-002", "severity": "HIGH", "trigger": "ssn", "description": "Social Security Number attribute without explicit encryption annotation"}
        ]

    def _is_standard_package(self, package_name: str) -> bool:
        """Determines if a package is standard by checking if it belongs to the @entigram namespace or standard list."""
        if package_name.startswith("@entigram/"):
            return True
            
        # Legacy fallback for projects initialized before namespaces
        standard_packages = [
            "Entigram Schemas",
            "AWS", "Azure", "GCP", "Banking", "BusinessStrategy", 
            "ClinicalValidation", "CompetitiveIntelligence", "ContentPublishing", 
            "EHRExtraction", "GoogleWorkspace", "HIPAACompliance", 
            "MarketingWebsite", "PartnerManagement", "PersonalFinance", 
            "Salesforce", "SpringBoot", "StartupFounder", "SupplyChain", 
            "TechnicalDueDiligence", "Terraform", "XWiki"
        ]
        return package_name in standard_packages

    def scan_all(self) -> Dict[str, Any]:
        """Scans all packages active in the current project's workspace."""
        manifest_path = self.target_dir / ".etg" / "entigram.yaml"
        schema_path = self.target_dir / "schema.lds"
        
        active_pkgs = set()

        # 1. Load packages from manifest
        if manifest_path.exists():
            import yaml
            try:
                with open(manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f) or {}
                
                raw_pkgs = manifest.get('packages', {})
                if isinstance(raw_pkgs, list):
                    for p in raw_pkgs: active_pkgs.add(p)
                else:
                    for p in raw_pkgs.keys(): active_pkgs.add(p)
            except Exception as e:
                print(f"Warning: Could not parse manifest for scan: {e}")

        # 2. Dynamically discover dependencies from Schema
        if schema_path.exists():
            try:
                parser = SchemaParser(schema_path.read_text())
                entities, _ = parser.parse()
                for ent in entities.values():
                    if ent.external_ref:
                        # Extract package name: @entigram/Salesforce::Account -> @entigram/Salesforce
                        pkg_name = ent.external_ref.split("::")[0]
                        active_pkgs.add(pkg_name)
            except Exception as e:
                print(f"Warning: Could not parse schema.lds for dependency discovery: {e}")

        if not active_pkgs:
            return {"status": "no_packages_found", "results": {}}

        results = {}
        for pkg in sorted(list(active_pkgs)):
            results[pkg] = self.scan_package(pkg)
            
        return results

    def _resolve_pkg_path(self, package_name: str) -> Optional[Path]:
        # 1. Foundation Package
        if package_name == "Entigram Schemas":
             return self.target_dir
             
        # 2. Standard Global Cache
        if self._is_standard_package(package_name) and self.global_registry_cache.exists():
             for repo in self.global_registry_cache.iterdir():
                 if repo.is_dir():
                     parts = package_name.split("/")
                     if len(parts) == 2:
                         # Handle explicit namespaces (e.g., @entigram/MonteCarlo)
                         potential_path = repo / parts[0] / parts[1]
                         if potential_path.exists(): return potential_path
                         # Legacy check
                         potential_path = repo / package_name
                         if potential_path.exists(): return potential_path
                     else:
                         # Legacy standard package fallback
                         potential_path = repo / "@entigram" / package_name
                         if potential_path.exists(): return potential_path

        # 3. Workspace 'packages/' folder (Legacy/Local/Test)
        root_pkg_path = self.target_dir / "packages" / package_name
        if root_pkg_path.exists():
            return root_pkg_path

        # 4. Local '.etg/packages/' folder (Locked/Custom)
        local_pkg_path = self.local_packages_dir / package_name
        if local_pkg_path.exists():
            return local_pkg_path

        return None

    def scan_package(self, package_name: str) -> Dict[str, Any]:
        """Performs static analysis on a specific package."""
        is_standard = self._is_standard_package(package_name)
        vulnerabilities = []

        # 1. Resolve Package Path
        pkg_path = self._resolve_pkg_path(package_name)
                 
        if not pkg_path:
             return {
                 "package": package_name,
                 "is_standard": is_standard,
                 "vulnerabilities": [{"id": "SNTNL-SYS-001", "severity": "HIGH", "description": f"Could not resolve package path for analysis."}],
                 "bypassed": []
             }

        # 2. Check Standard Vulnerability DB
        clean_name = package_name.split("/")[-1]
        if is_standard and clean_name in self.vulnerability_db:
             vulnerabilities.extend(self.vulnerability_db[clean_name])

        schema_path = pkg_path / "schema.lds"
        if schema_path.exists():
            schema_content = schema_path.read_text()
            
            # 3. AST-Based Static Analysis (Structural Integrity)
            try:
                parser = SchemaParser(schema_content)
                entities, relationships = parser.parse()
                
                for ent_name, entity in entities.items():
                    # Rule AST-001: Missing Primary Key
                    has_pk = any(attr.get('pk', False) for attr in entity.attributes)
                    if not has_pk and not entity.external_ref:
                        vulnerabilities.append({
                            "id": "SNTNL-AST-001",
                            "severity": "HIGH",
                            "description": f"Missing Primary Key: Entity '{ent_name}' lacks a PK attribute. This breaks federated GraphQL-LD routing."
                        })
                    
                    # Rule AST-002: Orphaned Entity (No relationships)
                    if not entity.external_ref:
                        is_related = False
                        for rel in relationships:
                            if rel.entity_a.lower() == ent_name.lower() or rel.entity_b.lower() == ent_name.lower():
                                is_related = True
                                break
                        if not is_related and len(entities) > 1:
                            vulnerabilities.append({
                                "id": "SNTNL-AST-002",
                                "severity": "MEDIUM",
                                "description": f"Orphaned Entity: '{ent_name}' has no relationships to other entities in the model."
                            })

            except Exception as e:
                vulnerabilities.append({
                    "id": "SNTNL-AST-000",
                    "severity": "CRITICAL",
                    "description": f"AST Parse Failure: The schema.lds is malformed and cannot be statically analyzed. Error: {str(e)}"
                })

            # 4. Regex-Based Heuristic Scan (PII / Pollution)
            schema_content_lower = schema_content.lower()
            
            if is_standard:
                pollution_pattern = re.compile(r'\b(acme|demo|my_?custom|test_?company|customer_?[a-z])\b', re.IGNORECASE)
                match = pollution_pattern.search(schema_content)
                if match:
                     vulnerabilities.append({
                         "id": "SNTNL-RULE-005",
                         "severity": "CRITICAL",
                         "description": f"Standard Package Pollution: Customer-specific term '{match.group(1)}' found. Specific implementations must be isolated."
                     })

            for heuristic in self.custom_heuristics:
                if heuristic["trigger"] in schema_content_lower:
                    vulnerabilities.append({
                        "id": heuristic["id"],
                        "severity": heuristic["severity"],
                        "description": heuristic["description"]
                    })

        # 5. Check for bypasses
        bypassed = self._get_bypassed_vulnerabilities(pkg_path)
        
        active_vulns = []
        for v in vulnerabilities:
             if v["id"] not in bypassed:
                  active_vulns.append(v)

        return {
            "package": package_name,
            "is_standard": is_standard,
            "vulnerabilities": active_vulns,
            "bypassed": bypassed
        }

    def _get_bypass_file_path(self, pkg_path: Path) -> Path:
        return pkg_path / ".sentinel-ignore"

    def _get_bypassed_vulnerabilities(self, pkg_path: Path) -> List[str]:
        """Reads the .sentinel-ignore file."""
        bypass_file = self._get_bypass_file_path(pkg_path)
        if bypass_file.exists():
            return [line.strip() for line in bypass_file.read_text().splitlines() if line.strip() and not line.startswith("#")]
        return []

    def authorize_bypass(self, package_name: str, vulnerability_id: str, rationale: str) -> bool:
        """
        Authorizes a bypass for a specific vulnerability.
        """
        if self._is_standard_package(package_name):
             print(f"❌ Sentinel Error: Cannot bypass vulnerabilities in standard package '{package_name}'. Please update the package.")
             return False

        pkg_path = self._resolve_pkg_path(package_name)
        if not pkg_path:
            print(f"❌ Sentinel Error: Package path not found.")
            return False

        bypass_file = self._get_bypass_file_path(pkg_path)
        current_bypasses = self._get_bypassed_vulnerabilities(pkg_path)
        
        if vulnerability_id in current_bypasses:
             print(f"ℹ️ Bypass already exists for {vulnerability_id} in {package_name}.")
             return True

        with open(bypass_file, "a") as f:
             f.write(f"\n# Bypass authorized: {rationale}\n")
             f.write(f"{vulnerability_id}\n")
        
        print(f"✅ Sentinel: Bypass authorized for {vulnerability_id} in custom package '{package_name}'.")
        return True
