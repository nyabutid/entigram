import sys
import argparse
import os
import json
import importlib.util
import shutil
import yaml
from pathlib import Path
from datetime import datetime
from entigram.injector import inject_entigram_manifest
from entigram.schema_compiler import compile_schema_file
from entigram.package_builder import PackageBuilder
from entigram.cli_runner.runner import launch_agent
from entigram.utils import find_project_root

def get_default_engine():
    """Probes the system for available AI agents (Antigravity, Claude, or Codex)."""
    if shutil.which("agy"):
        return "Antigravity"
    if shutil.which("claude"):
        return "Claude Code"
    if shutil.which("ollama"):
        return "Ollama"
    if shutil.which("codex"):
        return "Codex"
    return "Antigravity"

def load_plugins(subparsers):
    """Loads custom CLI commands from the user's .etg/plugins directory."""
    plugins_dir = Path(".etg/plugins")
    if not plugins_dir.exists():
        return

    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name == "__init__.py":
            continue
            
        module_name = f"entigram_plugin_{plugin_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
                if hasattr(module, 'register_command'):
                    module.register_command(subparsers)
            except Exception as e:
                print(f"Failed to load plugin {plugin_file.name}: {e}")

def get_hydration_vector(target_path: Path, compact: bool = False) -> str:
    """Deterministic boot sequence to align LLM state vector by flattening ledger and Schema."""
    entigram_dir = target_path / ".etg"
    manifest_path = entigram_dir / "entigram.yaml"
    ledger_path = entigram_dir / "entigram_state.db"

    if not manifest_path.exists():
        return f"❌ Error: Not an Entigram workspace (missing {manifest_path})"

    # 1. Load Manifest
    with open(manifest_path, "r") as f:
        manifest = yaml.safe_load(f)

    # 2. Extract state from ledger
    alignments = []
    resolutions = []
    delivery_evidence = []
    delivery_artifacts = []
    improvement_proposals = []
    latest_delivery_snapshot = None
    current_delivery_status = None
    if ledger_path.exists():
        from entigram.sqlite_ledger.manager import LedgerManager
        manager = LedgerManager(str(ledger_path))
        conn = manager._get_connection()
        try:
            # Fetch alignments
            cursor = conn.execute("SELECT source_domain, target_domain, source_concept, target_concept FROM semantic_alignments WHERE status='approved'")
            alignments = [{"src_dom": r[0], "tgt_dom": r[1], "src_con": r[2], "tgt_con": r[3]} for r in cursor.fetchall()]
            
            # Fetch recent resolutions
            cursor = conn.execute("SELECT conflict_id, entity_type, resolved_state FROM human_resolutions ORDER BY timestamp DESC LIMIT 10")
            resolutions = [{"id": r[0], "type": r[1], "state": r[2]} for r in cursor.fetchall()]

            delivery_evidence = manager.get_delivery_evidence(passed_only=True, limit=10)
            delivery_artifacts = manager.get_delivery_artifacts(limit=10)
            improvement_proposals = manager.get_improvement_proposals(limit=10)
            latest_delivery_snapshot = manager.get_latest_snapshot()
            if latest_delivery_snapshot:
                from entigram.broker import EntigramBroker
                current_delivery_status = EntigramBroker(
                    str(target_path),
                    ledger=manager,
                    seed_synonyms=False,
                ).delivery_status()
        except Exception:
            pass
        finally:
            if not manager.db_path == ":memory:":
                conn.close()

    # 3. Load Schema (Schema)
    schema_path = target_path / "schema.lds"
    schema_content = ""
    if schema_path.exists():
        schema_content = schema_path.read_text()

    commissioner_checklist = {"expectation_count": 0, "items": []}
    if schema_content:
        from entigram.governance.commissioner import Commissioner
        commissioner_checklist = Commissioner(schema_content).build_checklist()

    # 4. Flatten to High-Density String
    boot_payload = {
        "ENTIGRAM_BOOT_VECTOR": {
            "version": manifest.get("entigram_version"),
            "packages": list(manifest.get("packages", {}).keys()),
            "physical_laws": schema_content,
            "commissioner": commissioner_checklist,
            "semantic_alignments": alignments,
            "settled_decisions": resolutions,
            "delivery_evidence": delivery_evidence,
            "delivery_artifacts": delivery_artifacts,
            "improvement_proposals": improvement_proposals,
            "latest_delivery_snapshot": latest_delivery_snapshot,
            "current_delivery_status": current_delivery_status,
            "timestamp": datetime.now().isoformat()
        }
    }

    output = f"--- ENTIGRAM HYDRATION SEQUENCE ---\n"
    if compact:
        output += json.dumps(boot_payload, separators=(',', ':'))
    else:
        output += json.dumps(boot_payload, indent=2)
    output += f"\n--- SEQUENCE COMPLETE ---"
    return output

def launch_ui(target_dir=None):
    """Launches the Streamlit UI dashboard."""
    import subprocess
    ui_path = Path(__file__).parent.parent / "ui" / "app.py"
    print(f"🚀 Launching Entigram Visual Dashboard...")
    try:
        # Pass the directory to the UI via environment variable
        env = os.environ.copy()
        
        # Resolve target directory (search upwards if not provided)
        if not target_dir:
            root = find_project_root(os.getcwd())
            target_dir = str(root) if root else os.getcwd()
        
        env["ENTIGRAM_PROJECT_DIR"] = str(Path(target_dir).expanduser().resolve())
        
        # Invoke streamlit via the current python interpreter to ensure it works in venvs (like Brew)
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(ui_path)], env=env, check=True)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped.")
    except Exception as e:
        print(f"❌ Failed to launch dashboard: {e}")

def main():
    parser = argparse.ArgumentParser(description="Entigram Headless Compiler CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Load user plugins
    load_plugins(subparsers)

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a workspace")
    init_parser.add_argument("--dir", help="Target directory (defaults to current directory)")
    init_parser.add_argument("--packages", default="Entigram Schemas", help="Comma separated packages")
    default_engine = get_default_engine()
    init_parser.add_argument("--engine", default=default_engine, help=f"CLI Engine (Detected: {default_engine})")
    init_parser.add_argument("--force", action="store_true", help="Force initialization even if workspace exists")

    # config command
    config_parser = subparsers.add_parser("config", help="Manage workspace configuration")
    config_parser.add_argument("--dir", default=".", help="Target directory")
    config_parser.add_argument("--engine", help="Update the default CLI engine")
    config_parser.add_argument("--list", action="store_true", help="List current configuration")

    # warden command
    warden_parser = subparsers.add_parser("warden", help="Manage schema contract integrity (The Warden)")
    warden_subparsers = warden_parser.add_subparsers(dest="warden_command", help="Warden commands")
    warden_parser.add_argument("--dir", default=".", help="Target directory")
    
    warden_subparsers.add_parser("lock", help="Lock the current Schema and Ontology via cryptographic checksum")
    warden_subparsers.add_parser("unlock", help="Unlock the domain for authorized modifications")
    warden_subparsers.add_parser("check", help="Verify the current integrity state")

    # build command
    build_parser = subparsers.add_parser("build", help="Build models from Schema")
    build_parser.add_argument("--dir", help="Target directory (defaults to current directory)")
    build_parser.add_argument("--format", choices=["sql", "ttl", "mermaid"], default="sql", help="Output format")

    # discover command
    discover_parser = subparsers.add_parser("discover", help="Reverse-engineer a Schema from an existing SQLite database")
    discover_parser.add_argument("--db", required=True, help="Path to the SQLite database file (.db or .sqlite)")
    discover_parser.add_argument("--out", help="Output Schema file (prints to stdout if omitted)")

    # package command
    pkg_parser = subparsers.add_parser("package", help="Package management")
    pkg_subparsers = pkg_parser.add_subparsers(dest="pkg_command", help="Package commands")
    
    create_pkg_parser = pkg_subparsers.add_parser("create", help="Create a new package")
    create_pkg_parser.add_argument("--name", required=True, help="Package name")
    create_pkg_parser.add_argument("--out", default="packages", help="Output directory")
    create_pkg_parser.add_argument("--skill", help="Base skill to inherit from")
    create_pkg_parser.add_argument("--depends", help="Dependency skill")

    create_from_schema_parser = pkg_subparsers.add_parser("import", help="Import an existing Schema into a package")
    create_from_schema_parser.add_argument("--schema", required=True, help="Path to Schema file")
    create_from_schema_parser.add_argument("--name", help="Package name")
    create_from_schema_parser.add_argument("--out", default=".etg/packages", help="Output directory")

    install_pkg_parser = pkg_subparsers.add_parser("install", help="Install a package from a registered remote repository")
    install_pkg_parser.add_argument("--name", required=True, help="Package name")
    install_pkg_parser.add_argument("--dir", default=".", help="Target directory")

    # registry command
    registry_parser = subparsers.add_parser("registry", help="Manage package registries")
    registry_subparsers = registry_parser.add_subparsers(dest="registry_command", help="Registry commands")
    
    add_reg_parser = registry_subparsers.add_parser("add", help="Add a remote git repository as a package registry")
    add_reg_parser.add_argument("--url", required=True, help="Git URL of the registry")
    add_reg_parser.add_argument("--dir", default=".", help="Target directory")
    
    list_reg_parser = registry_subparsers.add_parser("list", help="List configured registries")
    list_reg_parser.add_argument("--dir", default=".", help="Target directory")

    # inject command
    inject_parser = subparsers.add_parser("inject", help="Inject compiled SQLite databases for active domains")
    inject_parser.add_argument("--dir", default=".", help="Target directory")
    inject_parser.add_argument("--crsqlite", action="store_true", help="Enable CR-SQLite Conflict-free Replicated Relations")

    # query command
    query_parser = subparsers.add_parser("query", help="Execute a GraphQL-LD federated query")
    query_parser.add_argument("--dir", default=".", help="Target directory")
    query_parser.add_argument("--graphql", required=True, help="GraphQL query string")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Launch the Entigram Federated GraphQL Hub (API Server)")
    serve_parser.add_argument("--dir", default=".", help="Target directory")
    serve_parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")

    # ui command
    ui_parser = subparsers.add_parser("ui", help="Launch the Entigram Visual Dashboard")
    ui_parser.add_argument("--dir", default=".", help="Target directory")

    # agent command
    agent_launch_parser = subparsers.add_parser("agent", help="Launch your configured AI agent in the current workspace")
    agent_launch_parser.add_argument("--dir", help="Target directory")
    agent_launch_parser.add_argument("--engine", help="Override CLI Engine (Claude Code, Antigravity, Codex, Ollama)")
    agent_launch_parser.add_argument("--model", help="Specify model (e.g., qwen2.5, claude-3-opus)")
    agent_launch_parser.add_argument("--ollama-launch-option", help="Ollama launch target (e.g., claude, codex)")
    agent_launch_parser.add_argument("--headless", action="store_true", help="Run headlessly using stdin piping (Antigravity only)")

    # interview command
    interview_parser = subparsers.add_parser("interview", help="Launch an autonomous agent to model your domain")
    interview_parser.add_argument("--dir", help="Target directory")
    interview_parser.add_argument("--engine", help="Override CLI Engine (Claude Code, Antigravity, Codex, Ollama)")
    interview_parser.add_argument("--model", help="Specify model")
    interview_parser.add_argument("--ollama-launch-option", help="Ollama launch target (e.g., claude, codex)")
    interview_parser.add_argument("--headless", action="store_true", help="Run headlessly using stdin piping (Antigravity only)")

    # model command (One-shot headless modeling)
    model_parser = subparsers.add_parser("model", help="One-shot autonomous domain modeling using headless agent")
    model_parser.add_argument("description", help="Natural language description of the domain to model")
    model_parser.add_argument("--dir", help="Target directory")
    model_parser.add_argument("--engine", help="Override CLI Engine")
    model_parser.add_argument("--append", action="store_true", help="Append to draft_schema.lds instead of printing only")

    # cloud command
    cloud_parser = subparsers.add_parser("cloud", help="Entigram Cloud Managed Services")
    cloud_subparsers = cloud_parser.add_subparsers(dest="cloud_command", help="Cloud commands")
    
    login_parser = cloud_subparsers.add_parser("login", help="Login to Entigram Cloud")
    login_parser.add_argument("--token", required=True, help="API Token")
    
    sync_cloud_parser = cloud_subparsers.add_parser("sync", help="Synchronize local ledger with Entigram Cloud")
    sync_cloud_parser.add_argument("--dir", default=".", help="Target directory")
    sync_cloud_parser.add_argument("--endpoint", default="https://api.entigram.ai/v1", help="Cloud endpoint")

    # broker command
    broker_parser = subparsers.add_parser("broker", help="Agent orchestration broker")
    broker_subparsers = broker_parser.add_subparsers(dest="broker_command", help="Broker commands")
    broker_parser.add_argument("--dir", default=".", help="Target directory")

    decide_parser = broker_subparsers.add_parser("decide", help="Record a proposed decision")
    decide_parser.add_argument("--id", required=True, help="Conflict ID")
    decide_parser.add_argument("--type", required=True, help="Entity Type")
    decide_parser.add_argument("--state", required=True, help="Resolved State")
    decide_parser.add_argument("--rationale", required=True, help="Rationale")

    conflict_parser = broker_subparsers.add_parser("conflict", help="Report a contradiction")
    conflict_parser.add_argument("--id", required=True, help="Conflict ID")
    conflict_parser.add_argument("--type", required=True, help="Entity Type")
    conflict_parser.add_argument("--states", required=True, help="Proposed States (JSON)")
    conflict_parser.add_argument("--agent", required=True, help="Agent ID")

    check_parser = broker_subparsers.add_parser("check", help="Check for an existing decision")
    check_parser.add_argument("--id", required=True, help="Conflict ID")

    broker_subparsers.add_parser("conflicts", help="List all pending conflicts")
    broker_subparsers.add_parser("resolutions", help="List all settled resolutions")
    broker_subparsers.add_parser("validate", help="Validate current Schema model")

    commission_parser = broker_subparsers.add_parser(
        "commission",
        aliases=["commissioner"],
        help="Run the Commissioner pre-handoff expectation checklist",
    )
    commission_parser.add_argument(
        "--proof",
        action="append",
        default=[],
        help="Proof text or artifact reference that satisfies a validation_check",
    )
    commission_parser.add_argument("--json", action="store_true", dest="json_output", help="Print checklist as JSON")
    commission_parser.add_argument("--agent", help="Agent ID to attribute evidence to")
    commission_parser.add_argument(
        "--blocked",
        action="append",
        default=[],
        metavar="CHECK",
        help="Mark a validation_check as Blocked (infra failure, not a proof gap)",
    )

    deliver_parser = broker_subparsers.add_parser(
        "deliver",
        help="Run commissioner + write a delivery snapshot (deterministic handoff gate)",
    )
    deliver_parser.add_argument(
        "--expectation",
        help="Filter to a specific expectation name",
    )
    deliver_parser.add_argument(
        "--proof",
        action="append",
        default=[],
        help="Proof text or artifact reference",
    )
    deliver_parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Local artifact path to hash and attach to the delivery snapshot",
    )
    deliver_parser.add_argument(
        "--artifact-role",
        default="delivery_artifact",
        help="Role to apply to --artifact entries",
    )
    deliver_parser.add_argument(
        "--blocked",
        action="append",
        default=[],
        metavar="CHECK",
        help="Mark a validation_check as Blocked",
    )
    deliver_parser.add_argument("--agent", help="Agent ID to attribute this delivery to")
    deliver_parser.add_argument("--json", action="store_true", dest="json_output", help="Print result as JSON")

    status_parser = broker_subparsers.add_parser(
        "status",
        aliases=["diff"],
        help="Compare current expectations and artifacts against the latest delivery snapshot",
    )
    status_parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Local artifact path expected to be included in the delivery anchor",
    )
    status_parser.add_argument(
        "--artifact-role",
        default="delivery_artifact",
        help="Role to apply to --artifact entries",
    )
    status_parser.add_argument("--json", action="store_true", dest="json_output", help="Print result as JSON")

    resolve_parser = broker_subparsers.add_parser(
        "resolve",
        help="Run missing proof commands and record evidence (exit commissioner blocked state)",
    )
    resolve_parser.add_argument(
        "--run-missing-proofs",
        action="store_true",
        help="Attempt to run all validation_check commands and record the outcomes",
    )
    resolve_parser.add_argument("--agent", help="Agent ID to attribute evidence to")
    resolve_parser.add_argument("--json", action="store_true", dest="json_output", help="Print result as JSON")

    add_package_parser = broker_subparsers.add_parser("add-package", help="Add a package to the manifest")
    add_package_parser.add_argument("--name", required=True, help="Package name")

    broker_subparsers.add_parser("sense", help="Scan active domains for contradictions")
    broker_subparsers.add_parser("sync", help="Propagate human resolutions to domain states")

    # improve command (improvement proposal lifecycle)
    improve_parser = subparsers.add_parser("improve", help="Manage Entigram improvement proposals")
    improve_subparsers = improve_parser.add_subparsers(dest="improve_command", help="Improve commands")
    improve_parser.add_argument("--dir", default=".", help="Target directory")

    propose_parser = improve_subparsers.add_parser("propose", help="Record a new improvement proposal")
    propose_parser.add_argument("--title", required=True, help="Short title for the proposal")
    propose_parser.add_argument("--model", required=True, help="Affected model or entity name")
    propose_parser.add_argument("--rationale", required=True, help="Why this improvement is needed")
    propose_parser.add_argument("--change", required=True, help="Proposed change description (plain text or JSON)")
    propose_parser.add_argument("--benefit", help="Expected benefit")
    propose_parser.add_argument("--by", help="Agent or author ID")
    propose_parser.add_argument(
        "--status",
        default="Proposed",
        help="Lifecycle status: Proposed (default), Reviewed, Implemented, Rejected",
    )

    list_proposals_parser = improve_subparsers.add_parser("list", help="List improvement proposals")
    list_proposals_parser.add_argument(
        "--status",
        default=None,
        help="Filter by lifecycle status (Proposed, Reviewed, Implemented, Rejected)",
    )
    list_proposals_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # learn command (Entigram_Lesson operational path)
    learn_parser = subparsers.add_parser("learn", help="Record and retrieve reusable lessons from deliveries")
    learn_subparsers = learn_parser.add_subparsers(dest="learn_command", help="Learn commands")
    learn_parser.add_argument("--dir", default=".", help="Target directory")

    learn_record_parser = learn_subparsers.add_parser("record", help="Persist a new lesson to the ledger")
    learn_record_parser.add_argument("--lesson", required=True, help="The lesson learned (plain language)")
    learn_record_parser.add_argument("--task", help="Source task or session context")
    learn_record_parser.add_argument("--rule", help="Reusable rule derived from the lesson")
    learn_record_parser.add_argument("--confidence", type=float, default=1.0, help="Confidence 0.0-1.0 (default 1.0)")
    learn_record_parser.add_argument("--by", help="Agent ID")

    learn_list_parser = learn_subparsers.add_parser("list", help="List recorded lessons")
    learn_list_parser.add_argument("--status", default=None, help="Filter by lifecycle (Active, Archived)")
    learn_list_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    # hydrate / boot command
    hydrate_parser = subparsers.add_parser("hydrate", help="Deterministic boot sequence to align LLM state vector")
    hydrate_parser.add_argument("--dir", help="Target directory (defaults to current directory)")
    hydrate_parser.add_argument("--compact", action="store_true", help="Minimize whitespace for extreme token efficiency")
    hydrate_parser.add_argument("--out", help="Save the hydration vector to a file instead of printing")

    boot_parser = subparsers.add_parser("boot", help="Alias for 'hydrate'")
    boot_parser.add_argument("--dir", help="Target directory (defaults to current directory)")
    boot_parser.add_argument("--compact", action="store_true", help="Minimize whitespace for extreme token efficiency")
    boot_parser.add_argument("--out", help="Save the hydration vector to a file instead of printing")

    align_parser = broker_subparsers.add_parser("align", help="Authorize semantic alignment")
    align_parser.add_argument("--src_dom", required=True)
    align_parser.add_argument("--tgt_dom", required=True)
    align_parser.add_argument("--src_con", required=True)
    align_parser.add_argument("--tgt_con", required=True)
    align_parser.add_argument("--conf", type=float, default=1.0)
    align_parser.add_argument("--rat", required=True)

    synonym_parser = broker_subparsers.add_parser("synonym", help="Manage persistent synonyms for semantic reconciliation")
    synonym_parser.add_argument("--add", help="Add a synonym pair (format: 'term,synonym')")
    synonym_parser.add_argument("--conf", type=float, default=1.0, help="Confidence score")
    synonym_parser.add_argument("--list", action="store_true", help="List all synonyms")

    export_align_parser = broker_subparsers.add_parser("export-alignments", help="Export alignments to EXMO Align API format")
    export_align_parser.add_argument("--domain", help="Filter by source domain")

    import_align_parser = broker_subparsers.add_parser("import-alignments", help="Import alignments from EXMO Align API XML file")
    import_align_parser.add_argument("--file", required=True, help="Path to XML file")

    negotiate_parser = broker_subparsers.add_parser("negotiate", help="Propose alignments between two Schema files")
    negotiate_parser.add_argument("--src", required=True, help="Source Schema file")
    negotiate_parser.add_argument("--tgt", required=True, help="Target Schema file")
    negotiate_parser.add_argument("--threshold", type=float, default=0.6, help="Confidence threshold")

    negotiate_auto_parser = broker_subparsers.add_parser("negotiate-auto", help="Record high-confidence alignment proposals")
    negotiate_auto_parser.add_argument("--src", required=True, help="Source Schema file")
    negotiate_auto_parser.add_argument("--tgt", required=True, help="Target Schema file")
    negotiate_auto_parser.add_argument("--src_dom", required=True, help="Source Domain Name")
    negotiate_auto_parser.add_argument("--tgt_dom", required=True, help="Target Domain Name")
    negotiate_auto_parser.add_argument("--threshold", type=float, default=0.8, help="Proposal confidence threshold")

    scan_parser = broker_subparsers.add_parser("scan", help="Run Sentinel package vulnerability scanner")
    scan_parser.add_argument("--package", help="Specific package to scan (scans all if omitted)")

    bypass_parser = broker_subparsers.add_parser("bypass", help="Authorize a bypass for a Sentinel vulnerability (Custom Packages Only)")
    bypass_parser.add_argument("--package", required=True, help="Target package name")
    bypass_parser.add_argument("--id", required=True, help="Vulnerability ID (e.g., SNTNL-CUST-001)")
    bypass_parser.add_argument("--rationale", required=True, help="Reason for bypass")

    mesh_parser = broker_subparsers.add_parser("mesh", help="Automate multi-partner ingestion and alignment")
    mesh_parser.add_argument("--data", required=True, help="Directory containing partner CSV/JSON files")
    mesh_parser.add_argument("--threshold", type=float, default=0.8, help="Auto-alignment confidence threshold")

    args = parser.parse_args()

    if not args.command:
        launch_ui()
    elif hasattr(args, 'func'):
        args.func(args)
    elif args.command == "init":
        target_dir = args.dir
        if not target_dir:
            confirm = input(f"📂 No --dir provided. Initialize in current directory ({os.getcwd()})? [Y/n]: ").strip().lower()
            if confirm and confirm != 'y':
                print("Aborted.")
                sys.exit(0)
            target_dir = "."
        
        # Safety Check: Does workspace already exist?
        manifest_path = Path(target_dir) / ".etg" / "entigram.yaml"
        if manifest_path.exists() and not args.force:
            confirm = input(f"⚠️  Workspace already exists at {target_dir}. Overwrite configuration? [y/N]: ").strip().lower()
            if confirm != 'y':
                print("Aborted. Use --force to override.")
                sys.exit(0)

        packages = [p.strip() for p in args.packages.split(",")]
        success = inject_entigram_manifest(target_dir, packages, args.engine)
        if success:
            print(f"✅ Workspace initialized at {target_dir}")
        else:
            print(f"❌ Failed to initialize workspace.")
            sys.exit(1)

    elif args.command == "config":
        target_dir = args.dir
        manifest_path = Path(target_dir) / ".etg" / "entigram.yaml"
        
        if not manifest_path.exists():
            print(f"❌ No workspace found at {target_dir}. Did you run 'etg init'?")
            sys.exit(1)
            
        try:
            with open(manifest_path, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"❌ Failed to read config: {e}")
            sys.exit(1)
            
        if args.list:
            print(f"--- Entigram Workspace Config ({target_dir}) ---")
            for k, v in config.items():
                print(f"{k}: {v}")
            return

        if args.engine:
            config['cli_engine'] = args.engine
            config['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(manifest_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            print(f"✅ Default engine updated to: {args.engine}")
        else:
            print("No changes requested. Use --engine to update settings or --list to view them.")

    elif args.command == "warden":
        from entigram.governance.warden import Warden
        warden = Warden(args.dir)
        if args.warden_command == "lock":
            warden.lock_fingerprint()
        elif args.warden_command == "unlock":
            warden.unlock()
        elif args.warden_command == "check":
            if warden.verify_integrity():
                print("🛡️  [WARDEN] Schema contracts are intact and verified.")
            else:
                sys.exit(1)
        else:
            warden_parser.print_help()

    elif args.command == "build":
        target_dir = args.dir
        if not target_dir:
            root = find_project_root(os.getcwd())
            if root:
                target_dir = str(root)
            else:
                confirm = input(f"🏗️  No --dir provided and no .etg found. Build from current directory ({os.getcwd()})? [Y/n]: ").strip().lower()
                if confirm and confirm != 'y':
                    print("Aborted.")
                    sys.exit(0)
                target_dir = "."
            
        schema_file = Path(target_dir) / "schema.lds"
        if not schema_file.exists():
            print(f"❌ schema.lds not found in {target_dir}")
            sys.exit(1)
        
        try:
            output = compile_schema_file(str(schema_file), output_format=args.format)
            print(output)
            
            # Lock the Schema Contracts after a successful build
            from entigram.governance.warden import Warden
            Warden(target_dir).lock_fingerprint()
            
        except Exception as e:
            print(f"❌ Build failed: {e}")
            sys.exit(1)
    
    elif args.command == "discover":
        from entigram.schema_compiler.discoverer import DomainDiscoverer
        try:
            discoverer = DomainDiscoverer(args.db)
            schema_content = discoverer.discover_schema()
            if args.out:
                with open(args.out, 'w') as f:
                    f.write(schema_content)
                print(f"✅ Discovered Schema saved to {args.out}")
            else:
                print(schema_content)
        except Exception as e:
            print(str(e))
            sys.exit(1)
    
    elif args.command == "registry":
        from entigram.registry import EntigramRegistry
        registry = EntigramRegistry(args.dir)
        if args.registry_command == "add":
            if registry.add_registry(args.url):
                print(f"✅ Added registry: {args.url}")
            else:
                sys.exit(1)
        elif args.registry_command == "list":
            regs = registry.get_registries()
            print("Configured Registries:")
            for r in regs:
                print(f" - {r}")
                
    elif args.command == "package":
        if args.pkg_command == "create":
            builder = PackageBuilder()
            pkg_path = builder.create_package(
                name=args.name,
                output_dir=args.out,
                base_skill=args.skill,
                depends_on=args.depends
            )
            print(f"✅ Package '{args.name}' created at {pkg_path}")
        elif args.pkg_command == "import":
            builder = PackageBuilder()
            pkg_path = builder.create_package_from_schema(
                schema_path=args.schema,
                name=args.name,
                output_dir=args.out
            )
            print(f"✅ Package imported at {pkg_path}")
        elif args.pkg_command == "install":
            from entigram.registry import EntigramRegistry
            registry = EntigramRegistry(args.dir)
            if not registry.install_package(args.name):
                sys.exit(1)
        else:
            pkg_parser.print_help()

    elif args.command == "inject":
        from entigram.sqlite_ledger.injector import DomainSQLiteInjector
        injector = DomainSQLiteInjector(args.dir)
        successful = injector.inject_all_active(enable_crsqlite=args.crsqlite)
        if successful:
            print(f"✅ Successfully injected SQLite databases for: {', '.join(successful)}")
        else:
            print("⚠️  No domain databases injected.")

    elif args.command == "query":
        target_dir = args.dir
        if not target_dir:
            root = find_project_root(os.getcwd())
            target_dir = str(root) if root else os.getcwd()

        from entigram.governance.warden import Warden
        if not Warden(target_dir).verify_integrity():
            sys.exit(1)

        from entigram.federated_router import FederatedRouter
        router = FederatedRouter(target_dir)
        results = router.execute(args.graphql)
        print(json.dumps(results, indent=2))
    elif args.command == "serve":
        target_dir = args.dir
        if not target_dir:
            root = find_project_root(os.getcwd())
            target_dir = str(root) if root else os.getcwd()

        from entigram.governance.warden import Warden
        if not Warden(target_dir).verify_integrity():
            sys.exit(1)
            
        from entigram.server import run_server
        run_server(port=args.port, project_dir=target_dir)

    elif args.command == "boot" or args.command == "hydrate":
        # Resolve target directory
        if not args.dir:
            root = find_project_root(os.getcwd())
            target_path = Path(root) if root else Path.cwd()
        else:
            target_path = Path(args.dir).expanduser().resolve()

        vector = get_hydration_vector(target_path, compact=getattr(args, "compact", False))
        
        if getattr(args, "out", None):
            with open(args.out, "w") as f:
                f.write(vector)
            print(f"✅ Hydration vector saved to {args.out}")
        else:
            print(vector)

    elif args.command == "ui":
        launch_ui(args.dir)

    elif args.command == "agent":
        target_dir = args.dir
        if not target_dir:
            root = find_project_root(os.getcwd())
            if root:
                target_dir = str(root)
            else:
                confirm = input(f"🤖 No --dir provided and no .etg found. Launch agent in current directory ({os.getcwd()})? [Y/n]: ").strip().lower()
                if confirm and confirm != 'y':
                    print("Aborted.")
                    sys.exit(0)
                target_dir = "."
        
        # Verify Integrity: Prevent agent from starting if schema contracts have been tampered with
        from entigram.governance.warden import Warden
        if not Warden(target_dir).verify_integrity():
            sys.exit(1)
        
        # Load engine from manifest
        engine = get_default_engine()
        manifest_path = Path(target_dir) / ".etg" / "entigram.yaml"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f)
                    engine = manifest.get('cli_engine', engine)
            except: pass
            
        # Override if provided
        if args.engine:
            engine = args.engine

        print(f"🤖 Launching AI Agent ({engine})...")
        
        # ACTIVE HYDRATION: Force the LLM state vector to align with the local ontology
        # OPTIMIZATION: Use a temporary boot file for long vectors
        hydration_vector = get_hydration_vector(Path(target_dir), compact=True)
        
        boot_file = Path(target_dir) / ".etg" / "boot.json"
        with open(boot_file, "w") as f:
            f.write(hydration_vector)
            
        launch_agent(
            target_dir,
            engine,
            model=getattr(args, "model", None),
            ollama_launch_option=getattr(args, "ollama_launch_option", None),
            initial_prompt=f"Initialize from {boot_file}. Silent boot. Ready.",
            headless=args.headless,
        )

    elif args.command == "interview":
        target_dir = args.dir
        if not target_dir:
            root = find_project_root(os.getcwd())
            if root:
                target_dir = str(root)
            else:
                confirm = input(f"🎤 No --dir provided and no .etg found. Start interview in current directory ({os.getcwd()})? [Y/n]: ").strip().lower()
                if confirm and confirm != 'y':
                    print("Aborted.")
                    sys.exit(0)
                target_dir = "."

        # 1. Verify workspace is initialized
        if not (Path(target_dir) / ".etg" / "entigram.yaml").exists():
            print(f"❌ Error: Workspace not initialized in {target_dir}. Run 'etg init' first.")
            sys.exit(1)
            
        # 2. Load engine from manifest
        engine = get_default_engine()
        manifest_path = Path(target_dir) / ".etg" / "entigram.yaml"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f)
                    engine = manifest.get('cli_engine', engine)
            except: pass
            
        # Override if provided
        if args.engine:
            engine = args.engine

        print(f"🎤 Starting Autonomous Modeler Interview ({engine})...")

        # ACTIVE HYDRATION: Force the LLM state vector to align with the local ontology
        # OPTIMIZATION: Use a temporary boot file for long vectors
        hydration_vector = get_hydration_vector(Path(target_dir), compact=True)
        
        boot_file = Path(target_dir) / ".etg" / "boot.json"
        with open(boot_file, "w") as f:
            f.write(hydration_vector)
            
        launch_agent(
            target_dir,
            engine,
            model=getattr(args, "model", None),
            ollama_launch_option=getattr(args, "ollama_launch_option", None),
            initial_prompt=f"Initialize from {boot_file}. Silent boot. Ready.",
            headless=args.headless,
        )

    elif args.command == "model":
        target_dir = args.dir
        if not target_dir:
            root = find_project_root(os.getcwd())
            target_dir = str(root) if root else os.getcwd()

        # 1. Load engine
        engine = get_default_engine()
        manifest_path = Path(target_dir) / ".etg" / "entigram.yaml"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f)
                    engine = manifest.get('cli_engine', engine)
            except: pass
        if args.engine: engine = args.engine

        # 2. Construct Prompt
        # ACTIVE HYDRATION: Force the LLM state vector to align with the local ontology
        # OPTIMIZATION: Use a temporary boot file for long vectors
        hydration_vector = get_hydration_vector(Path(target_dir), compact=True)
        boot_file = Path(target_dir) / ".etg" / "boot.json"
        with open(boot_file, "w") as f:
            f.write(hydration_vector)

        # We instruct the agent to return ONLY the Schema block.
        system_prompt = f"""Initialize from {boot_file}. Silent boot.

You are the Entigram Domain Modeler. Your goal is to translate a natural language description into a strict Entigram Schema.
Return ONLY the ENTITY and RELATIONSHIP blocks. Do not include any conversational filler.
Format:
ENTITY: Name
ATTRIBUTES:
  - .id (UUID)
  - attribute_name (Type)

RELATIONSHIPS:
- EntityA (1) [MUST] --- [MAY] (MANY) EntityB
"""
        full_prompt = f"{system_prompt}\n\nDOMAIN DESCRIPTION: {args.description}\n\nSCHEMA PAYLOAD:"

        # 3. Headless Execution (Intercepting the Payload)
        print(f"🧠 Intercepting domain payload from {engine}...")
        from entigram.cli_runner.runner import execute_headless_agy
        
        payload = execute_headless_agy(full_prompt, target_dir=target_dir)
        
        if not payload:
            print("❌ Failed to intercept payload.")
            sys.exit(1)

        print("\n--- INTERCEPTED PAYLOAD ---")
        print(payload)
        print("---------------------------\n")

        # 4. Validation & Enforcement
        from entigram.schema_compiler.parser import SchemaParser
        try:
            parser = SchemaParser(payload)
            entities, rels = parser.parse()
            if not entities:
                print("⚠️  Warning: No entities detected in payload.")
            else:
                print(f"✅ Validated: {len(entities)} entities and {len(rels)} relationships found.")
                
                if args.append:
                    draft_path = Path(target_dir) / "draft_schema.lds"
                    with open(draft_path, "a") as f:
                        f.write(f"\n\n/* Autonomous model added on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} */\n")
                        f.write(payload)
                    print(f"📝 Appended to {draft_path}")
                    
                    # Auto-sync ontology
                    from entigram.broker import EntigramBroker
                    EntigramBroker(target_dir).sync_all_ontologies()
                    print("🛡️  Ontology synchronized.")
        except Exception as e:
            print(f"❌ Failed to parse or enforce payload: {e}")
            sys.exit(1)

    elif args.command == "cloud":
        if args.cloud_command == "login":
            creds_dir = Path.home() / ".etg"
            creds_dir.mkdir(parents=True, exist_ok=True)
            (creds_dir / "credentials").write_text(f"token: {args.token}")
            print("✅ Successfully logged into Entigram Cloud.")
        elif args.cloud_command == "sync":
            from entigram.broker import EntigramBroker
            broker = EntigramBroker(args.dir)
            
            token = "anonymous"
            creds_file = Path.home() / ".etg" / "credentials"
            if creds_file.exists():
                try:
                    token = creds_file.read_text().split("token: ")[1].strip()
                except: pass
            
            broker.ledger.sync_with_cloud(args.endpoint, token)

    elif args.command == "broker":
        from entigram.broker import EntigramBroker
        broker = EntigramBroker(args.dir)
        
        if args.broker_command == "decide":
            if broker.propose_resolution(args.id, args.type, args.state, args.rationale):
                print(f"✅ Decision '{args.id}' recorded.")
            else:
                sys.exit(1)
        elif args.broker_command == "conflict":
            states = json.loads(args.states)
            result = broker.report_conflict(args.id, args.type, states, args.agent)
            if result:
                # The broker might have auto-resolved it
                decision = broker.check_decision(args.id)
                if decision and "Auto-resolved" in decision.get('rationale', ''):
                    print(f"✅ Conflict '{args.id}' was auto-resolved by Policy.")
                else:
                    print(f"✅ Conflict '{args.id}' reported and logged for review.")
            else:
                sys.exit(1)
        elif args.broker_command == "check":
            decision = broker.check_decision(args.id)
            if decision:
                print(f"FOUND: {decision['state']} (Rationale: {decision['rationale']})")
            else:
                print("NOT_FOUND")
        elif args.broker_command == "conflicts":
            conflicts = broker.ledger.get_pending_conflicts()
            if not conflicts:
                print("No pending conflicts.")
            for c in conflicts:
                print(f"[{c['timestamp']}] ID: {c['conflict_id']} | Type: {c['entity_type']} | Agents: {c['source_agents']}")
                print(f"  Proposed States: {c['proposed_states']}")
        elif args.broker_command == "resolutions":
            resolutions = broker.ledger.get_all_resolutions()
            if not resolutions:
                print("No resolutions found.")
            for r in resolutions:
                print(f"[{r['timestamp']}] ID: {r['conflict_id']} (v{r['version']}) | State: {r['state']}")
                print(f"  Rationale: {r['rationale']}")
        elif args.broker_command == "validate":
            result = broker.validate_model()
            if result['valid']:
                e_warns = result.get("expectation_warnings", [])
                print(f"✅ Model valid: {result['entity_count']} entities, {result['relationship_count']} rels.")
                if e_warns:
                    print(f"⚠️  {len(e_warns)} expectation-to-test mapping warning(s):")
                    for w in e_warns:
                        print(f"   [{w['code']}] {w['message']}")
                elif result.get("expectation_count", 0) == 0 or not result.get("expectation_warnings"):
                    print("   ✅ All modeled expectations have resolvable validation_check paths.")
            else:
                print(f"❌ Model invalid: {result['error']}")
                sys.exit(1)
        elif args.broker_command in ("commission", "commissioner"):
            result = broker.commission(
                proofs=args.proof,
                blocked_checks=getattr(args, "blocked", []),
                agent_id=getattr(args, "agent", None),
            )
            if args.json_output:
                print(json.dumps(result, indent=2))
            else:
                print(broker.format_commission(result))
            if not result["valid"]:
                sys.exit(1)
        elif args.broker_command == "deliver":
            result = broker.commission_and_record(
                proofs=args.proof,
                blocked_checks=getattr(args, "blocked", []),
                agent_id=getattr(args, "agent", None),
                expectation_name=getattr(args, "expectation", None),
                artifact_paths=getattr(args, "artifact", []),
                artifact_role=getattr(args, "artifact_role", "delivery_artifact"),
            )
            if args.json_output:
                print(json.dumps(result, indent=2))
            else:
                print(broker.format_commission(result))
                if result["valid"]:
                    snap = result.get("snapshot_id", "unknown")
                    ts = result.get("trust_score", {})
                    grade = ts.get("grade", "?")
                    score = ts.get("score", 0.0)
                    print(f"\n📦 Delivery snapshot: {snap}")
                    print(f"🎯 Trust score: {score:.0%} (Grade {grade})")
                    bkd = ts.get("breakdown", {})
                    for k, v in bkd.items():
                        print(f"   {k}: {v:.0%}")
                    print("✅ Handoff gate: PASSED. This delivery is anchored.")
                else:
                    ts = result.get("trust_score", {})
                    if ts:
                        print(f"\n🎯 Trust score: {ts.get('score', 0):.0%} (Grade {ts.get('grade', 'F')})")
                    print("\n❌ Handoff gate: FAILED. Resolve missing proofs before delivering.")
            if not result["valid"]:
                sys.exit(1)
        elif args.broker_command in ("status", "diff"):
            result = broker.delivery_status(
                artifact_paths=getattr(args, "artifact", []),
                artifact_role=getattr(args, "artifact_role", "delivery_artifact"),
            )
            if args.json_output:
                print(json.dumps(result, indent=2))
            else:
                print(broker.format_delivery_status(result))
            if result.get("needs_recommission"):
                sys.exit(1)
        elif args.broker_command == "resolve":
            # Run missing proof commands and record outcomes
            checklist = broker.commission()
            if checklist["valid"]:
                print("✅ Commissioner: all expectations already have proof. Nothing to resolve.")
            else:
                missing = [
                    item for item in checklist["items"]
                    if item["status"] not in ("passed", "blocked")
                ]
                agent_id = getattr(args, "agent", None)
                if getattr(args, "run_missing_proofs", False):
                    import subprocess
                    import shlex
                    results = []
                    for item in missing:
                        cmd = item.get("validation_check", "")
                        if not cmd:
                            continue
                        print(f"▶ Running: {cmd}")
                        try:
                            try:
                                cmd_args = shlex.split(cmd)
                            except ValueError as e:
                                broker.ledger.record_delivery_evidence(
                                    evidence_type="test_run",
                                    artifact_ref=cmd,
                                    expectation_name=item["name"],
                                    command=cmd,
                                    result_summary=f"Invalid validation command: {e}",
                                    passed=False,
                                    agent_id=agent_id,
                                )
                                results.append({"name": item["name"], "passed": False, "command": cmd})
                                print(f"  ❌ INVALID COMMAND: {item['name']} ({e})")
                                continue
                            if not cmd_args:
                                continue
                            proc = subprocess.run(
                                cmd_args,
                                capture_output=True,
                                text=True,
                                timeout=120,
                                cwd=str(broker.target_dir),
                            )
                            passed = proc.returncode == 0
                            summary = (proc.stdout + proc.stderr).strip()[:500]
                            broker.ledger.record_delivery_evidence(
                                evidence_type="test_run",
                                artifact_ref=cmd,
                                expectation_name=item["name"],
                                command=cmd,
                                result_summary=summary,
                                passed=passed,
                                agent_id=agent_id,
                            )
                            status = "✅ PASS" if passed else "❌ FAIL"
                            print(f"  {status}: {item['name']}")
                            results.append({"name": item["name"], "passed": passed, "command": cmd})
                        except FileNotFoundError as e:
                            print(f"  ❌ COMMAND NOT FOUND: {item['name']} ({cmd})")
                            broker.ledger.record_delivery_evidence(
                                evidence_type="test_run",
                                artifact_ref=cmd,
                                expectation_name=item["name"],
                                command=cmd,
                                result_summary=str(e),
                                passed=False,
                                agent_id=agent_id,
                            )
                            results.append({"name": item["name"], "passed": False, "command": cmd})
                        except subprocess.TimeoutExpired:
                            print(f"  ⏰ TIMEOUT: {item['name']} ({cmd})")
                            broker.ledger.record_delivery_evidence(
                                evidence_type="test_run",
                                artifact_ref=cmd,
                                expectation_name=item["name"],
                                command=cmd,
                                result_summary="Timeout after 120s",
                                passed=False,
                                agent_id=agent_id,
                            )
                            results.append({"name": item["name"], "passed": False, "command": cmd})
                    all_passed = all(r["passed"] for r in results) if results else False
                    if all_passed:
                        print("\n✅ All missing proofs resolved. Run 'etg broker deliver' to anchor this delivery.")
                    else:
                        print("\n⚠️  Some proofs failed. Address failures before delivering.")
                        if args.json_output:
                            print(json.dumps(results, indent=2))
                        sys.exit(1)
                else:
                    print(f"Commissioner: {len(missing)} expectation(s) need proof:")
                    for item in missing:
                        print(f"  TODO {item['name']}: {item['validation_check']}")
                    print("\nRun with --run-missing-proofs to execute and record them.")
                    sys.exit(1)
        elif args.broker_command == "add-package":
            if broker.add_package(args.name):
                print(f"✅ Package '{args.name}' added to manifest.")
            else:
                sys.exit(1)
        elif args.broker_command == "sense":
            conflicts = broker.sense_all()
            if not conflicts:
                print("✅ No cross-domain contradictions detected.")
            else:
                print(f"⚠️  Detected {len(conflicts)} contradictions:")
                for c in conflicts:
                    print(f" - {c['id']}: {c['rationale']}")
                    print(f"   States: {c['proposed_states']}")
        elif args.broker_command == "sync":
            broker.sync_resolutions()
            print("✅ Domain states synchronized with human resolutions.")
        elif args.broker_command == "align":
            if broker.authorize_alignment(args.src_dom, args.tgt_dom, args.src_con, args.tgt_con, args.conf, args.rat):
                print(f"✅ Alignment Authorized.")
            else:
                sys.exit(1)
        elif args.broker_command == "synonym":
            if args.add:
                try:
                    term, synonym = args.add.split(",")
                    if broker.ledger.record_synonym(term, synonym, args.conf):
                        print(f"✅ Synonym added: {term} <-> {synonym} ({args.conf})")
                    else:
                        sys.exit(1)
                except ValueError:
                    print("❌ Invalid format for --add. Use 'term,synonym'.")
                    sys.exit(1)
            elif args.list:
                syns = broker.ledger.get_synonyms()
                if not syns:
                    print("No synonyms recorded.")
                else:
                    print("Global Synonym Ledger:")
                    for s in syns:
                        print(f" - {s['term']} <-> {s['synonym']} ({s['confidence']})")
            else:
                synonym_parser.print_help()
        elif args.broker_command == "export-alignments":
            output = broker.export_alignments(args.domain)
            if output:
                print(output)
            else:
                print("No alignments found.")
        elif args.broker_command == "import-alignments":
            count = broker.import_alignments(args.file)
            print(f"✅ Successfully imported and authorized {count} alignments from {args.file}")
        elif args.broker_command == "negotiate":
            proposals = broker.negotiate_alignments(args.src, args.tgt, args.threshold)
            if not proposals:
                print("No alignment proposals found above threshold.")
            else:
                print(f"Found {len(proposals)} alignment proposals:")
                for p in proposals:
                    print(f" - [{p['confidence']}] {p['source_concept']} <-> {p['target_concept']}")
                    print(f"   Rationale: {p['rationale']}")
        elif args.broker_command == "negotiate-auto":
            proposals = broker.negotiate_alignments(args.src, args.tgt, args.threshold)
            count = 0
            for p in proposals:
                if broker.propose_alignment(
                    source_domain=args.src_dom,
                    target_domain=args.tgt_dom,
                    source_concept=p['source_concept'],
                    target_concept=p['target_concept'],
                    confidence=p['confidence'],
                    rationale=f"Negotiated proposal: {p['rationale']}",
                    source_artifact=f"{args.src}::{args.tgt}",
                ):
                    print(f"✅ Proposed: {p['source_concept']} <-> {p['target_concept']} ({p['confidence']})")
                    count += 1
            print(f"\n✅ Recorded {count} alignment proposals between {args.src_dom} and {args.tgt_dom}.")
        elif args.broker_command == "mesh":
            from entigram.sensing.partner_mesh import PartnerMesh
            mesh = PartnerMesh(args.dir)
            results = mesh.mesh_directory(args.data, auto_align_threshold=args.threshold)
            print(json.dumps(results, indent=2))
        elif args.broker_command == "scan":
            from entigram.governance.sentinel import SentinelScanner
            scanner = SentinelScanner(args.dir)
            if args.package:
                results = {args.package: scanner.scan_package(args.package)}
            else:
                results = scanner.scan_all()
            
            if "status" in results and results["status"] == "no_packages_found":
                print("No packages found to scan.")
            else:
                total_vulns = 0
                for pkg, result in results.items():
                    vulns = result.get("vulnerabilities", [])
                    total_vulns += len(vulns)
                    if vulns:
                        pkg_type = "Standard" if result["is_standard"] else "Custom"
                        print(f"\n🛡️  Sentinel Scan: {pkg} ({pkg_type} Package)")
                        for v in vulns:
                            print(f"  [{v['severity']}] {v['id']}: {v['description']}")
                
                if total_vulns == 0:
                    print("✅ Sentinel Scan Complete: No active vulnerabilities found.")
                else:
                    print(f"\n⚠️  Sentinel Scan Complete: Found {total_vulns} active vulnerabilities.")
                    print("   To bypass custom package warnings, use: broker bypass --package <pkg> --id <id> --rationale \"<reason>\"")
        
        elif args.broker_command == "bypass":
            from entigram.governance.sentinel import SentinelScanner
            scanner = SentinelScanner(args.dir)
            if not scanner.authorize_bypass(args.package, args.id, args.rationale):
                sys.exit(1)
    
    elif args.command == "improve":
        from entigram.broker import EntigramBroker
        broker = EntigramBroker(args.dir)
        if args.improve_command == "propose":
            try:
                import json as _json
                change = _json.loads(args.change)
            except (ValueError, TypeError):
                change = {"description": args.change}
            proposal_id = broker.record_improvement_proposal(
                title=args.title,
                affected_model=args.model,
                proposed_change=change,
                rationale=args.rationale,
                expected_benefit=getattr(args, "benefit", None),
                created_by=getattr(args, "by", None),
                lifecycle_status=getattr(args, "status", "Proposed"),
            )
            if proposal_id:
                status_label = getattr(args, "status", "Proposed")
                print(f"✅ Improvement proposal #{proposal_id} recorded: '{args.title}'")
                print(f"   Affected model: {args.model}")
                print(f"   Lifecycle: {status_label}")
                if status_label == "Proposed":
                    print("   Advance with: etg improve list --status Proposed")
            else:
                print("❌ Failed to record proposal.")
                sys.exit(1)
        elif args.improve_command == "list":
            proposals = broker.ledger.get_improvement_proposals(
                lifecycle_status=getattr(args, "status", None)
            )
            if not proposals:
                status_filter = getattr(args, "status", None)
                label = f" (status: {status_filter})" if status_filter else ""
                print(f"No improvement proposals found{label}.")
            elif getattr(args, "json_output", False):
                print(json.dumps(proposals, indent=2))
            else:
                print(f"Improvement Proposals ({len(proposals)} found):")
                for p in proposals:
                    icon = {"Proposed": "🔵", "Reviewed": "🟡", "Implemented": "🟢", "Rejected": "🔴"}.get(
                        p["lifecycle_status"], "⚪"
                    )
                    print(f"  {icon} [{p['lifecycle_status']}] #{p['id']} {p['title']}")
                    print(f"    Model: {p['affected_model']}")
                    print(f"    Rationale: {p['rationale']}")
                    if p.get("expected_benefit"):
                        print(f"    Benefit: {p['expected_benefit']}")
                    print(f"    Created: {p['created_at']} by {p.get('created_by', 'unknown')}")
        else:
            improve_parser.print_help()

    elif args.command == "learn":
        from entigram.broker import EntigramBroker
        broker = EntigramBroker(args.dir)
        if args.learn_command == "record":
            lesson_id = broker.record_lesson(
                lesson=args.lesson,
                source_task=getattr(args, "task", None),
                reusable_rule=getattr(args, "rule", None),
                confidence=getattr(args, "confidence", 1.0),
                agent_id=getattr(args, "by", None),
            )
            if lesson_id:
                print(f"✅ Lesson #{lesson_id} recorded.")
                if getattr(args, "rule", None):
                    print(f"   Rule: {args.rule}")
                print("   View with: etg learn list")
            else:
                print("❌ Failed to record lesson.")
                sys.exit(1)
        elif args.learn_command == "list":
            lessons = broker.ledger.get_lessons(
                lifecycle_status=getattr(args, "status", None)
            )
            if not lessons:
                print("No lessons recorded yet.")
            elif getattr(args, "json_output", False):
                print(json.dumps(lessons, indent=2))
            else:
                print(f"Lessons ({len(lessons)} found):")
                for l in lessons:
                    print(f"  [{l['lifecycle_status']}] #{l['id']} {l['lesson'][:80]}")
                    if l.get("reusable_rule"):
                        print(f"    Rule: {l['reusable_rule']}")
                    if l.get("source_task"):
                        print(f"    Task: {l['source_task']}")
                    conf = l.get("confidence", 1.0)
                    print(f"    Confidence: {conf:.0%} | Agent: {l.get('agent_id', 'unknown')} | {l['observed_at']}")
        else:
            learn_parser.print_help()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
