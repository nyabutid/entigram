import os
import json
import sqlite3
from itertools import combinations
from pathlib import Path
from typing import Optional, List, Dict, Any
from .sqlite_ledger.manager import LedgerManager
from datetime import datetime
from .governance.warden import Warden

class EntigramBroker:
    """
    The semantic governance broker that validates edge-agent state,
    records conflicts, and manages verified cross-domain alignments.
    """
    def __init__(self, target_dir: str, ledger: LedgerManager = None):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.etg_dir = self.target_dir / ".etg"
        self.ledger_path = self.etg_dir / "entigram_state.db"
        self.ledger = ledger if ledger is not None else LedgerManager(str(self.ledger_path))
        self.warden = Warden(str(self.target_dir))
        self._packages_cache = None
        
        # Seed initial synonyms if table is empty (Phase 3 Scalability)
        self._seed_synonyms()

    def _seed_synonyms(self):
        """Seeds the ledger with default synonyms if empty."""
        try:
            current_syns = self.ledger.get_synonyms()
            if not current_syns:
                from .governance.negotiator import _SYNONYMS
                for term, syns in _SYNONYMS.items():
                    for s in syns:
                        self.ledger.record_synonym(term, s, 0.95)
        except: pass

    def check_decision(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        """Checks if a decision has already been recorded for this conflict."""
        return self.ledger.get_resolution(conflict_id)

    def report_conflict(self, conflict_id: str, entity_type: str, proposed_states: Dict[str, Any], agent_id: str):
        """
        Reports a contradiction between agent states.
        Hardened with a Policy Engine to auto-arbitrate low-risk conflicts.
        """
        # Verify Integrity: Prevent reporting if schema contracts have been tampered with
        if not self.warden.verify_integrity():
            print(f"🚨 [SCHEMA_GUARD_HALT] Broker: Refusing to report conflict. Model integrity is compromised.")
            return None

        # Validate payloads against Schema
        for agent, state in proposed_states.items():
            if not self.warden.validate_payload(entity_type, state):
                print(f"🚨 [SCHEMA_GUARD_HALT] Broker: Agent '{agent}' proposed an invalid payload for '{entity_type}'.")
                return None

        from .governance.policy_engine import PolicyEngine
        policy = PolicyEngine()
        
        # 1. Attempt Auto-Arbitration (Tiered Oversight)
        resolution = policy.evaluate_conflict(conflict_id, entity_type, proposed_states)
        if resolution:
            print(f"[ENTIGRAM POLICY] Auto-resolving conflict {conflict_id}: {resolution['rationale']}")
            return self.ledger.record_resolution(
                conflict_id=conflict_id,
                entity_type=entity_type,
                state=json.dumps(resolution['resolved_state']),
                rationale=resolution['rationale']
            )

        # 2. Escalate to Human Ledger (Standard HITL)
        return self.ledger.record_conflict(
            conflict_id=conflict_id,
            entity_type=entity_type,
            proposed_states=json.dumps(proposed_states),
            source_agents=json.dumps([agent_id])
        )

    def propose_resolution(self, conflict_id: str, entity_type: str, proposed_state: str, rationale: str) -> bool:
        """
        Registers a proposed resolution. 
        Note: In Phase 2, this is appended to the ledger as a new version.
        """
        # Verify Integrity
        if not self.warden.verify_integrity():
            return False

        # Validate payload
        try:
            payload = json.loads(proposed_state)
            if not self.warden.validate_payload(entity_type, payload):
                return False
        except json.JSONDecodeError:
            pass # Not a JSON payload, skip attribute validation

        return self.ledger.record_resolution(conflict_id, entity_type, proposed_state, f"[AGENT] {rationale}")

    def get_active_packages(self) -> List[str]:
        """Reads the manifest to see what capabilities are active. Result is cached until add_package invalidates it."""
        if self._packages_cache is not None:
            return self._packages_cache
        import yaml
        manifest_path = self.etg_dir / "entigram.yaml"
        if not manifest_path.exists():
            return []
        try:
            with open(manifest_path, 'r') as f:
                manifest = yaml.safe_load(f) or {}
            self._packages_cache = manifest.get('packages', [])
            return self._packages_cache
        except Exception as e:
            print(f"Warning: Could not read manifest: {e}")
            return []

    def add_package(self, package_name: str) -> bool:
        """
        Adds a package to the project's entigram.yaml manifest.
        """
        import yaml
        manifest_path = self.etg_dir / "entigram.yaml"
        if not manifest_path.exists():
            return False

        try:
            with open(manifest_path, 'r') as f:
                manifest = yaml.safe_load(f) or {}

            packages = manifest.get('packages', [])
            
            # Handle both list and dict formats for backwards compatibility
            if isinstance(packages, list):
                if package_name not in packages:
                    packages.append(package_name)
                    manifest['packages'] = packages
                    manifest['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(manifest_path, 'w') as f:
                        yaml.dump(manifest, f, default_flow_style=False)
            elif isinstance(packages, dict):
                if package_name not in packages:
                    packages[package_name] = "latest"
                    manifest['packages'] = packages
                    manifest['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(manifest_path, 'w') as f:
                        yaml.dump(manifest, f, default_flow_style=False)

            self._packages_cache = None  # invalidate cache
            return True
        except Exception as e:
            print(f"Error adding package: {e}")
            return False

    def validate_model(self) -> Dict[str, Any]:
        """
        Performs a 'Semantic Governance' check on the logical models using the SchemaLinter.
        Also runs MVD (Minimum Viable Domain) semantic validation.
        Automatically updates the corresponding .ttl ontology.
        """
        from .schema_compiler.linter import SchemaLinter
        from .governance.viability import MVDValidator
        
        schema_path = self.target_dir / "schema.lds"
        if not schema_path.exists():
            schema_path = self.target_dir / "draft_schema.lds"
        
        if not schema_path.exists():
            return {"valid": False, "error": "Missing schema.lds or draft_schema.lds"}
        
        try:
            schema_text = schema_path.read_text()
            
            # 1. Structural Linting
            linter = SchemaLinter(schema_text)
            errors = linter.lint()
            
            # 2. Semantic MVD Validation
            mvd_validator = MVDValidator(schema_text)
            mvd_issues = mvd_validator.validate()
            
            all_issues = errors + mvd_issues
            
            # Filter for hard errors that block compilation
            critical_errors = [i for i in all_issues if i.get('severity') == 'ERROR' or 'code' not in i]
            
            if critical_errors:
                return {
                    "valid": False,
                    "error": critical_errors[0].get('message', str(critical_errors[0])),
                    "all_errors": all_issues
                }

            # If no critical errors, model is 'valid' but might have warnings
            entities, rels = linter.parser.parse()
            return {
                "valid": True, 
                "entity_count": len(entities), 
                "relationship_count": len(rels),
                "warnings": [i for i in mvd_issues if i.get('severity') != 'ERROR']
            }
        except Exception as e:
            import traceback
            print(f"validate_model raised unexpectedly:\n{traceback.format_exc()}")
            return {"valid": False, "error": str(e)}

    def authorize_alignment(self, source_domain: str, target_domain: str, source_concept: str, target_concept: str, confidence: float, rationale: str, _defer_sync: bool = False):
        """
        Authorizes a semantic alignment between two isolated domains.
        Pass _defer_sync=True when calling in a batch loop; call sync_all_ontologies() once after the loop.
        """
        result = self.ledger.record_alignment(
            source_domain,
            target_domain,
            source_concept,
            target_concept,
            confidence,
            rationale,
            evidence_type="human_review",
            human_review_confidence=confidence,
        )
        if result and not _defer_sync:
            self.sync_all_ontologies()
        return result

    def propose_alignment(self, source_domain: str, target_domain: str, source_concept: str, target_concept: str, confidence: float, rationale: str, source_artifact: str = None):
        """
        Records a non-operational alignment hypothesis. Proposed alignments are not used
        for closed-world routing until promoted through authorize_alignment().
        """
        return self.ledger.record_alignment_proposal(
            source_domain,
            target_domain,
            source_concept,
            target_concept,
            confidence,
            rationale,
            source_artifact=source_artifact,
        )

    def compile_ontology(self, schema_path: str):
        """Compiles a Schema file into a TTL ontology and saves it in the same directory."""
        from .schema_compiler import compile_schema_file
        try:
            ttl_content = compile_schema_file(schema_path, output_format="ttl")
            ttl_path = Path(schema_path).with_suffix(".ttl")
            ttl_path.write_text(ttl_content)
        except Exception as e:
            print(f"Warning: Failed to auto-sync ontology for {schema_path}: {e}")

    def sync_all_ontologies(self):
        """Synchronizes ontologies for the root domain and all active packages."""
        # 1. Root Domain
        for schema_name in ["schema.lds", "draft_schema.lds"]:
            root_schema = self.target_dir / schema_name
            if root_schema.exists():
                self.compile_ontology(str(root_schema))
        
        # 2. Active Packages
        packages = self.get_active_packages()
        for pkg in packages:
            # Check local packages folder
            pkg_schema = self.etg_dir / "packages" / pkg / "schema.lds"
            if pkg_schema.exists():
                self.compile_ontology(str(pkg_schema))
            else:
                # Fallback to root packages dir (legacy)
                pkg_schema = self.target_dir / "packages" / pkg / "schema.lds"
                if pkg_schema.exists():
                    self.compile_ontology(str(pkg_schema))

    def detect_cross_domain_conflict(self, 
                                     source_domain: str, 
                                     target_domain: str, 
                                     source_state: Dict[str, Any], 
                                     target_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Uses approved semantic alignments to sense contradictions between two domain states.
        """
        alignments = self.ledger.get_alignments(source_domain=source_domain, trusted_only=True)
        conflicts = []

        for alignment in alignments:
            if alignment['target_domain'] != target_domain:
                continue
            
            s_concept = alignment['source_concept']
            t_concept = alignment['target_concept']

            # Check if both states have the concept
            if s_concept in source_state and t_concept in target_state:
                s_val = source_state[s_concept]
                t_val = target_state[t_concept]

                if s_val != t_val:
                    conflict_id = f"CONFLICT-{source_domain}-{target_domain}-{s_concept}"
                    conflict = {
                        "id": conflict_id,
                        "entity_type": s_concept,
                        "proposed_states": {
                            source_domain: s_val,
                            target_domain: t_val
                        },
                        "rationale": f"Alignment mismatch: {s_concept} ({source_domain}) vs {t_concept} ({target_domain})"
                    }
                    conflicts.append(conflict)

        return conflicts

    def load_domain_state(self, domain_name: str) -> Dict[str, Any]:
        """
        Loads the current state of a domain from .etg/states/[domain].db
        For sensing purposes, we extract a flattened representation of key attributes.
        """
        db_file = self.etg_dir / "states" / f"{domain_name}.db"
        if not db_file.exists():
            return {}
        
        state = {}
        conn = None
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            # 1. Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cursor.fetchall()]

            for table in tables:
                # 2. Get table columns
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in cursor.fetchall()]

                # 3. Read the latest record (simplistic extraction for conflict sensing)
                cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 1")
                row = cursor.fetchone()

                if row:
                    for i, col in enumerate(cols):
                        state[f"{table}.{col}"] = row[i]
                        if col not in state:
                            state[col] = row[i]

            return state
        except Exception as e:
            print(f"Error loading state from {db_file}: {e}")
            return {}
        finally:
            if conn:
                conn.close()

    def update_domain_state(self, domain_name: str, updates: Dict[str, Any]):
        """
        Updates the domain state with the provided values in the SQLite database.
        """
        db_file = self.etg_dir / "states" / f"{domain_name}.db"
        if not db_file.exists():
            print(f"Cannot update state: {db_file} does not exist.")
            return

        conn = None
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            # Get all tables and their columns for whitelist validation
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cursor.fetchall()]

            # Build column whitelist per table to prevent SQL injection via concept names
            table_cols: Dict[str, set] = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                table_cols[table] = {r[1] for r in cursor.fetchall()}

            with conn:
                for key, value in updates.items():
                    if "." in key:
                        table, col = key.split(".", 1)
                        if table in table_cols and col in table_cols[table]:
                            cursor.execute(f"UPDATE {table} SET {col} = ?", (value,))
                        else:
                            print(f"Warning: Skipping unsafe update key '{key}' — not a valid table.column")
                    else:
                        for table in tables:
                            if key in table_cols[table]:
                                cursor.execute(f"UPDATE {table} SET {key} = ?", (value,))
        except Exception as e:
            print(f"Error updating state in {db_file}: {e}")
        finally:
            if conn:
                conn.close()

    def sync_resolutions(self):
        """
        Propagates human-approved resolutions back to the individual domain states.
        This closes the loop in the Federated Architecture.
        """
        resolutions = self.ledger.get_all_resolutions()
        alignments = self.ledger.get_alignments(trusted_only=True)
        
        for res in resolutions:
            target_concept = res['entity_type']
            resolved_val = res['state']
            
            # Find all domains linked to this concept via alignments
            affected_domains = {} # domain -> concept_name
            
            for aln in alignments:
                if aln['source_concept'] == target_concept:
                    affected_domains[aln['source_domain']] = aln['source_concept']
                    affected_domains[aln['target_domain']] = aln['target_concept']
                elif aln['target_concept'] == target_concept:
                    affected_domains[aln['source_domain']] = aln['source_concept']
                    affected_domains[aln['target_domain']] = aln['target_concept']

            # Apply updates
            for domain, concept in affected_domains.items():
                print(f"🔄 Syncing {domain}: setting {concept} = {resolved_val}")
                self.update_domain_state(domain, {concept: resolved_val})

    def negotiate_alignments(self, source_schema_path: str, target_schema_path: str, threshold: float = 0.6) -> List[Dict[str, Any]]:
        """
        Automatically proposes alignments between two Schema files.
        """
        from .governance.negotiator import AlignmentNegotiator
        
        with open(source_schema_path, 'r') as f:
            source_schema = f.read()
        with open(target_schema_path, 'r') as f:
            target_schema = f.read()
            
        negotiator = AlignmentNegotiator(threshold=threshold, ledger_path=str(self.ledger_path))
        return negotiator.negotiate(source_schema, target_schema)

    def export_alignments(self, source_domain: Optional[str] = None) -> str:
        """
        Exports all approved alignments in EXMO Align API (RDF/XML) format.
        """
        from .governance.alignment import AlignmentProtocol
        
        # We'll group alignments by pair of domains
        all_alignments = self.ledger.get_alignments(source_domain=source_domain, trusted_only=True)
        if not all_alignments:
            return ""

        # For the purpose of EXMO Align API, we usually export one file per domain pair.
        # Here we'll just aggregate them into a single protocol object for demonstration,
        # or we could return multiple. Let's simplify and aggregate.
        protocol = AlignmentProtocol("Entigram-Source-Collective", "Entigram-Target-Collective")
        for aln in all_alignments:
            protocol.mappings.append({
                "source": f"{aln['source_domain']}:{aln['source_concept']}",
                "target": f"{aln['target_domain']}:{aln['target_concept']}",
                "relation": aln['relation'],
                "confidence": aln['confidence']
            })
            
        return protocol.export_alignment_api()

    def import_alignments(self, xml_file_path: str) -> int:
        """
        Imports and authorizes alignments from an EXMO Align API XML file.
        Returns the number of authorized alignments.
        """
        from .governance.alignment import AlignmentProtocol
        
        with open(xml_file_path, 'r') as f:
            content = f.read()
            
        protocol = AlignmentProtocol("", "")
        protocol.import_alignment_api(content)
        
        count = 0
        for mapping in protocol.mappings:
            # Parse domain:concept from the resource strings
            # Expected format "Domain:Concept" or just "Concept"
            src = mapping['source']
            tgt = mapping['target']

            src_dom, src_con = src.split(":", 1) if ":" in src else ("External", src)
            tgt_dom, tgt_con = tgt.split(":", 1) if ":" in tgt else ("Internal", tgt)

            if self.authorize_alignment(
                source_domain=src_dom,
                target_domain=tgt_dom,
                source_concept=src_con,
                target_concept=tgt_con,
                confidence=mapping['confidence'],
                rationale=f"Imported from {xml_file_path} ({mapping['relation']})",
                _defer_sync=True,
            ):
                count += 1

        if count:
            self.sync_all_ontologies()  # single flush after batch
        return count

    def sense_all(self) -> List[Dict[str, Any]]:
        """
        Orchestrates cross-domain sensing across all active packages.
        """
        packages = self.get_active_packages()
        all_conflicts = []

        # Load states for all packages
        states = {pkg: self.load_domain_state(pkg) for pkg in packages}

        # Compare each unordered pair once (N*(N-1)/2 instead of N*(N-1))
        for src_pkg, tgt_pkg in combinations(packages, 2):
            conflicts = self.detect_cross_domain_conflict(
                src_pkg, tgt_pkg, states[src_pkg], states[tgt_pkg]
            )
            for conflict in conflicts:
                all_conflicts.append(conflict)
                self.report_conflict(conflict['id'], conflict['entity_type'], conflict['proposed_states'], "EntigramBroker-Sensor")

        return all_conflicts
