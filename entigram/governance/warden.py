import hashlib
import os
from pathlib import Path
from typing import Dict, Optional, Any

class Warden:
    """
    Implements 'Semantic Governance' Integrity: Decouples schema contracts (Schema/Ontology) 
    from agent execution by enforcing cryptographic immutability.
    """
    def __init__(self, target_dir: str = "."):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.manifest_path = self.target_dir / ".etg" / "entigram.yaml"

    def calculate_checksum(self, file_path: str) -> str:
        """Calculates the SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def generate_fingerprint(self) -> Dict[str, str]:
        """Generates a fingerprint of the current governed domain (Schema and Ontology)."""
        fingerprint = {}
        schema_path = self.target_dir / "schema.lds"
        ttl_path = self.target_dir / "schema.ttl"

        if schema_path.exists():
            fingerprint["schema_checksum"] = self.calculate_checksum(str(schema_path))
        if ttl_path.exists():
            fingerprint["ontology_checksum"] = self.calculate_checksum(str(ttl_path))
            
        return fingerprint

    def verify_integrity(self) -> bool:
        """
        Validates the current files against the hashes stored in the manifest.
        Triggers SCHEMA_GUARD_HALT if a mismatch is detected.
        """
        import yaml
        if not self.manifest_path.exists():
            return True # Nothing to verify yet

        with open(self.manifest_path, "r") as f:
            manifest = yaml.safe_load(f) or {}

        stored_fingerprint = manifest.get("integrity_fingerprint", {})
        if not stored_fingerprint:
            return True # Not yet protected

        current_fingerprint = self.generate_fingerprint()

        for key, expected_hash in stored_fingerprint.items():
            actual_hash = current_fingerprint.get(key)
            if actual_hash != expected_hash:
                print(f"🚨 [SCHEMA_GUARD_HALT] Warden Integrity Violation Detected in {key}!")
                print(f"   Expected: {expected_hash}")
                print(f"   Actual:   {actual_hash}")
                print(f"   The model is attempting to alter the schema contracts of the system.")
                return False

        return True

    def lock_fingerprint(self):
        """Persists the current checksums into the manifest, locking the schema contracts."""
        import yaml
        from datetime import datetime
        
        fingerprint = self.generate_fingerprint()
        if not self.manifest_path.exists():
            return

        with open(self.manifest_path, "r") as f:
            manifest = yaml.safe_load(f) or {}

        manifest["integrity_fingerprint"] = fingerprint
        manifest["last_locked"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(self.manifest_path, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False)
        
        print(f"🔒 [WARDEN] Schema contracts locked via checksum integrity.")

    def unlock(self):
        """Removes the integrity fingerprint from the manifest, allowing modifications."""
        import yaml
        if not self.manifest_path.exists():
            return

        with open(self.manifest_path, "r") as f:
            manifest = yaml.safe_load(f) or {}

        if "integrity_fingerprint" in manifest:
            del manifest["integrity_fingerprint"]
            if "last_locked" in manifest:
                del manifest["last_locked"]

            with open(self.manifest_path, "w") as f:
                yaml.dump(manifest, f, default_flow_style=False)
            
            print(f"🔓 [WARDEN] Schema contracts UNLOCKED. The domain can now be modified.")
        else:
            print(f"ℹ️  [WARDEN] Domain was not locked.")

    def validate_payload(self, entity_name: str, payload: Dict[str, Any]) -> bool:
        """
        Deterministially validates an agent-proposed payload against the locked Schema.
        Prevents agents from inventing new attributes or drifting from strict types.
        """
        from ..schema_compiler.parser import SchemaParser
        
        schema_path = self.target_dir / "schema.lds"
        if not schema_path.exists():
            return True # No schema contracts to enforce

        parser = SchemaParser(schema_path.read_text())
        entities, _ = parser.parse()

        if entity_name not in entities:
            print(f"🚨 [SCHEMA_GUARD_HALT] Semantic Drift: Agent proposed unknown entity '{entity_name}'.")
            return False

        allowed_entity = entities[entity_name]
        allowed_attributes = [attr['name'] for attr in allowed_entity.attributes]

        for attr_name in payload.keys():
            if attr_name not in allowed_attributes:
                print(f"🚨 [SCHEMA_GUARD_HALT] Unauthorized Mutation: Agent attempted to invent attribute '{attr_name}' for '{entity_name}'.")
                return False

        return True
