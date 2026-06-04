import os
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from .project_history import add_project_to_history

def inject_entigram_manifest(target_dir: str, selected_packages: list, cli_engine: str) -> bool:
    """
    Bootstraps a new Entigram workspace by injecting the YAML manifest 
    and the selected package template files. Uses a .etg subfolder for metadata.
    """
    target_path = Path(target_dir).expanduser().resolve()
    entigram_dir = target_path / ".etg"
    
    try:
        target_path.mkdir(parents=True, exist_ok=True)
        entigram_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {target_dir}: {e}")
        return False

    # 1. Generate entigram.yaml in .etg/
    # Convert list to initial dict for version tracking
    locked_packages = {pkg: "0.0.1" for pkg in selected_packages}
    
    manifest = {
        "entigram_version": "0.0.1",
        "packages": locked_packages,
        "cli_engine": cli_engine,
        "state_ledger": str(entigram_dir / "entigram_state.db"),
        "status": "initialized",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open(entigram_dir / "entigram.yaml", "w") as f:
        yaml.dump(manifest, f, default_flow_style=False)

    # 1.5 Generate/Append instruction file for agent awareness
    if cli_engine == "Antigravity":
        instruction_file = "AGY.md"
    elif cli_engine == "Claude Code":
        instruction_file = "CLAUDE.md"
    elif cli_engine == "Ollama":
        instruction_file = "OLLAMA.md"
    elif cli_engine == "Codex":
        instruction_file = "AGENTS.md"
    else:
        instruction_file = "AGENT_INSTRUCTIONS.md"
        
    instruction_path = target_path / instruction_file
    
    entigram_context = f"""
<!-- ENTIGRAM_START -->
# Entigram Agent Context
You are an edge-agent operating within a Entigram Federated Architecture.

## Workspace Context
- **Manifest:** You MUST read `.etg/entigram.yaml` (using your `read_file` tool) to understand project metadata and active packages.
- **Packages:** {", ".join(selected_packages)}
- **Decisions Ledger:** Contradictions must be resolved via the human tie-breaker ledger at `.etg/entigram_state.db`.

## Primary Directives
1. **Schema First:** Never generate code or ontologies before an Entigram Schema is explicitly defined in `schema.lds`.
2. **Persistence:** You MUST maintain the local `schema.lds` and `draft_schema.lds` files. Update them (using your `replace` or `write_file` tools) after EVERY turn where new domain information is established.
3. Broker Interaction: Use the Entigram CLI for cross-domain orchestration:
   - **Check Decisions:** `etg broker check --id [CONFLICT_ID]`
   - **Record Proposals:** `etg broker decide --id [ID] --type [ENTITY] --state [STATE] --rationale [WHY]`
   - **Report Conflicts:** `etg broker conflict --id [ID] --type [ENTITY] --states [JSON_STATES] --agent [AGENT_ID]`
   - **Align Domains:** `etg broker align --src_dom [DOM] --tgt_dom [DOM] --src_con [CON] --tgt_con [CON] --rat [WHY]`
   - **Validate Model:** `etg broker validate`
   - **Commission Handoff:** `etg broker commission --proof [VALIDATION_EVIDENCE]`

4. **Domain Isolation:** Treat external systems as black boxes.
5. **Schema Contract Enforcement (Execution Mode):** Once a build is finalized, the `schema.lds` and `schema.ttl` files represent the immutable schema contracts of this workspace. You are forbidden from attempting to rewrite or modify these files during data execution or orchestration. Any attempt to drift from the established schema will trigger a `SCHEMA_GUARD_HALT`.
6. **Initialization Step:** As your first action, read the project manifest and the local `schema.lds` to synchronize your mental model with the current authoritative state.
7. **Commissioner Pre-Handoff Gate:** If you changed implementation behavior, run `etg broker commission` and provide proof for each modeled `EXPECTATION` before handoff.

## Active Package Instructions
"""
    if "Entigram Schemas" in selected_packages:
        entigram_context += f"- **Schema Modeling:** Read `interview_prompt.md` and begin the domain modeling interview. Record your progress in `schema.lds`. (Note: For {'Antigravity' if cli_engine == 'Antigravity' else cli_engine}, ensure all turns are committed to state).\n"
    
    if len(selected_packages) > 0:
        entigram_context += "- **Package Skills:** You MUST read the `SKILL.md` file for each active package to understand your specific roles and protocols.\n"
    
    entigram_context += "<!-- ENTIGRAM_END -->\n"

    # Smart Injection: Append or Update instead of Overwrite
    if instruction_path.exists():
        with open(instruction_path, "r") as f:
            existing_content = f.read()
        
        if "<!-- ENTIGRAM_START -->" in existing_content:
            # Update existing Entigram block
            import re
            # Re-wrap in markers since we are replacing the whole block
            full_context = entigram_context.strip() + "\n"
            new_content = re.sub(r"<!-- ENTIGRAM_START -->.*?<!-- ENTIGRAM_END -->", full_context, existing_content, flags=re.DOTALL)
            with open(instruction_path, "w") as f:
                f.write(new_content)
        else:
            # Append to bottom
            with open(instruction_path, "a") as f:
                f.write("\n\n" + entigram_context)
    else:
        # Create new
        with open(instruction_path, "w") as f:
            f.write(entigram_context)

    # 1.6 Record in history
    try:
        add_project_to_history(target_dir)
    except Exception as e:
        print(f"Warning: Failed to record project history: {e}")

    # 2. Copy Templates (Keep templates in root for easy user access, or .etg?)
    # User wanted root for Schema, but manifest in .etg. Let's keep source files in root.
    # 2. Copy Templates
    # Use the internal templates directory within the package
    package_root = Path(__file__).parent
    local_packages_dir = target_path / ".etg" / "packages"

    template_map = {
        "Entigram Schemas": "schema_modeling",
        "Standard Personal Finance": "personal_finance",
        "Startup Founder": "startup_founder",
        "Business Strategy": "business_strategy"
    }

    for package in selected_packages:
        # 1. Check Standard Templates (Bundled)
        template_folder = template_map.get(package)
        src_path = None
        if template_folder:
            src_path = package_root / "templates" / template_folder

        # 2. Fallback to Local Packages (.etg/packages/)
        if (not src_path or not src_path.exists()) and local_packages_dir.exists():
            potential_local = local_packages_dir / package.replace(" ", "-")
            if potential_local.exists():
                src_path = potential_local
                
        # 3. Fallback to Registry if not found locally
        if not src_path or not src_path.exists():
            from entigram.registry import EntigramRegistry
            registry = EntigramRegistry(target_dir)
            if registry.install_package(package):
                potential_local = local_packages_dir / package.replace(" ", "-")
                if potential_local.exists():
                    src_path = potential_local

        if src_path and src_path.exists():
            for item in src_path.iterdir():
                if item.name == ".keep" or item.name == ".gitignore" or item.name == ".etg": continue

                target_file = target_path / item.name
                # NEVER overwrite the user's model files if they already exist
                if item.name in ["schema.lds", "draft_schema.lds"] and target_file.exists():
                    continue

                if item.is_file():
                    shutil.copy2(item, target_file)
                elif item.is_dir():
                    shutil.copytree(item, target_file, dirs_exist_ok=True)
    return True
