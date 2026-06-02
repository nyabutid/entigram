import os
import re
from pathlib import Path
from typing import List, Dict

class AgentInventory:
    """
    Parses SKILL.md files within packages to catalog active agents and their capabilities.
    """
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.etg_dir = self.target_dir / ".etg"

    def get_inventory(self) -> List[Dict[str, str]]:
        """Traverses packages to find and parse SKILL.md files."""
        inventory = []
        
        # 1. Check Standard Packages
        # We assume they are either in packages/ or in the registry cache
        standard_pkg_dir = Path(__file__).parent.parent / "packages"
        if standard_pkg_dir.exists():
            inventory.extend(self._scan_dir(standard_pkg_dir, "Standard"))

        # 2. Check Custom Packages (.etg/packages/)
        custom_pkg_dir = self.etg_dir / "packages"
        if custom_pkg_dir.exists():
            inventory.extend(self._scan_dir(custom_pkg_dir, "Custom"))

        return inventory

    def _scan_dir(self, directory: Path, pkg_type: str) -> List[Dict[str, str]]:
        agents = []
        # Support namespaces (@namespace/package)
        for item in directory.rglob("SKILL.md"):
            pkg_path = item.parent
            pkg_name = pkg_path.name
            
            # If parent is a namespace, include it
            if pkg_path.parent.name.startswith("@"):
                pkg_name = f"{pkg_path.parent.name}/{pkg_name}"
            
            skill_content = item.read_text()
            metadata = self._parse_skill_md(skill_content)
            metadata["package"] = pkg_name
            metadata["type"] = pkg_type
            metadata["path"] = str(item)
            agents.append(metadata)
            
        return agents

    def _parse_skill_md(self, content: str) -> Dict[str, str]:
        """Extracts Role, Constraints, and Primary Directives from SKILL.md."""
        metadata = {
            "role": "Unknown Agent",
            "constraints": "No constraints defined.",
            "directives": "No directives defined."
        }

        # Simple regex/line-based parsing for standard SKILL.md sections
        role_match = re.search(r'# (.*?)\s*(\n|$)', content)
        if role_match:
            metadata["role"] = role_match.group(1).strip()

        # Extract sections by header
        sections = re.split(r'##\s*', content)
        for section in sections:
            if section.lower().startswith("constraints"):
                # Take everything until the next major block or end
                metadata["constraints"] = section[len("constraints"):].strip()
            elif section.lower().startswith("primary directives"):
                metadata["directives"] = section[len("primary directives"):].strip()
            elif section.lower().startswith("directives"):
                 metadata["directives"] = section[len("directives"):].strip()

        return metadata
