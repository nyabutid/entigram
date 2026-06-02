import os
import shutil
from pathlib import Path
from typing import List, Dict, Any
from ..sensing.partner_sensor import PartnerCSVSensor, PartnerJSONSensor
from ..schema_compiler.discoverer import DomainDiscoverer
from ..broker import EntigramBroker

class PartnerMesh:
    """
    Macro ingestion helper for Phase 3: Macro Deployment.
    Ingests partner datasets, discovers Schema files, and records alignment proposals.
    """
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.broker = EntigramBroker(str(self.target_dir))
        self.csv_sensor = PartnerCSVSensor(str(self.target_dir))
        self.json_sensor = PartnerJSONSensor(str(self.target_dir))

    def mesh_directory(self, partner_data_dir: str, auto_align_threshold: float = 0.8) -> Dict[str, Any]:
        """
        Scans a directory for CSV/JSON files, ingests them as domains, 
        discovers Schema, and records alignment proposals for review.
        """
        data_path = Path(partner_data_dir).expanduser().resolve()
        if not data_path.exists() or not data_path.is_dir():
            return {"success": False, "error": f"Directory not found: {partner_data_dir}"}

        results = {
            "ingested_domains": [],
            "discovered_schema": [],
            "alignments_count": 0,
            "proposals_count": 0,
            "errors": []
        }

        # 1. Ingest all files
        for file in data_path.iterdir():
            if file.name.startswith("."): continue
            
            domain_name = file.stem.replace(" ", "_")
            table_name = domain_name.lower() 
            
            success = False
            if file.suffix == ".csv":
                success = self.csv_sensor.ingest_csv(str(file), domain_name, table_name)
            elif file.suffix == ".json":
                success = self.json_sensor.ingest_json(str(file), domain_name, table_name)
            
            if success:
                results["ingested_domains"].append(domain_name)
                self.broker.add_package(domain_name)
            else:
                results["errors"].append(f"Failed to ingest {file.name}")

        # 2. Discover Schema for each domain
        schema_files = {} # domain_name -> path
        for domain in results["ingested_domains"]:
            db_path = self.target_dir / ".etg" / "states" / f"{domain}.db"
            if db_path.exists():
                discoverer = DomainDiscoverer(str(db_path))
                schema_content = discoverer.discover_schema()
                
                # Save Schema file
                schema_dir = self.target_dir / ".etg" / "packages" / domain
                schema_dir.mkdir(parents=True, exist_ok=True)
                schema_path = schema_dir / "schema.lds"
                schema_path.write_text(schema_content)
                
                results["discovered_schema"].append(domain)
                schema_files[domain] = str(schema_path)

        # 3. Propose alignments for all pairs. Discovery creates hypotheses;
        # it does not authorize operational cross-domain joins.
        domains = list(schema_files.keys())
        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                d1, d2 = domains[i], domains[j]
                proposals = self.broker.negotiate_alignments(schema_files[d1], schema_files[d2], threshold=auto_align_threshold)
                
                for p in proposals:
                    self.broker.propose_alignment(
                        d1, d2, 
                        p['source_concept'], p['target_concept'], 
                        p['confidence'], f"PartnerMesh proposal: {p['rationale']}",
                        source_artifact=f"{schema_files[d1]}::{schema_files[d2]}",
                    )
                    results["proposals_count"] += 1

        return results
