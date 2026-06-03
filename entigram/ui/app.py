import streamlit as st
import os
import sys
import yaml
import base64
import json
import shutil
from pathlib import Path
from datetime import datetime
try:
    from importlib.metadata import version
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import version

# Add project root to path so we can import entigram
sys.path.append(str(Path(__file__).parent.parent.parent))
from entigram.injector import inject_entigram_manifest
from entigram.schema_compiler import compile_schema_file, SchemaParser
from entigram.schema_compiler.graph_builder import SchemaGraphBuilder
from entigram.sqlite_ledger import LedgerManager
from entigram.cli_runner.runner import launch_agent
from entigram.project_history import get_project_history, add_project_to_history
from entigram.ontology_compiler import OntologyCompiler
from entigram.utils import find_project_root

# Favicon path
favicon_path = os.path.join(os.path.dirname(__file__), "media", "favicon.svg")
logo_path = os.path.join(os.path.dirname(__file__), "media", "logo.svg")

st.set_page_config(
    page_title="Entigram Compiler", 
    page_icon=favicon_path if os.path.exists(favicon_path) else "⚙️", 
    layout="wide"
)

# --- STABLE STATE INITIALIZATION ---
if 'active_project' not in st.session_state:
    # 1. Check if a directory was passed via environment variable (from CLI)
    env_dir = os.environ.get("ENTIGRAM_PROJECT_DIR")
    if env_dir and os.path.exists(os.path.join(env_dir, ".etg", "entigram.yaml")):
        st.session_state.active_project = env_dir
        add_project_to_history(env_dir)
    else:
        # 2. Fallback: Search for Entigram project root starting from current directory
        root = find_project_root(os.getcwd())
        if root:
            root_str = str(root)
            st.session_state.active_project = root_str
            add_project_to_history(root_str)
        else:
            st.session_state.active_project = ""
if 'last_synced_project' not in st.session_state:
    st.session_state.last_synced_project = None

def resolve_namespace_path(nav_target: str) -> str:
    """Resolves a namespace string (e.g. @entigram/GCP) to an absolute path in the registry cache."""
    if not nav_target.startswith("@"):
        return nav_target
    
    potential_cache = Path.home() / ".etg" / "registry_cache"
    if potential_cache.exists():
        for repo in potential_cache.iterdir():
            if repo.is_dir():
                clean_target = nav_target.split("/")[-2:]
                if len(clean_target) == 2:
                    cache_path = repo / clean_target[0] / clean_target[1]
                    if cache_path.exists():
                        return str(cache_path)
    return nav_target

# --- NAVIGATION ROUTING VIA QUERY PARAMS ---
query_params = st.query_params
if "nav" in query_params:
    nav_target = query_params["nav"]
    # Clear the query param so we don't get stuck in a loop
    st.query_params.clear()

    # Simulate a click on the sidebar project by setting the active project
    # Resolve the namespace to a real path so the UI works
    resolved_path = resolve_namespace_path(nav_target)
    st.session_state.active_project = resolved_path
    
    # Only add to history if it's a real path
    if os.path.exists(resolved_path):
        add_project_to_history(resolved_path)
        
    st.rerun()

# --- MAIN UI ---
from entigram.cli_runner.etg_cli import get_hydration_vector

# Pinned Header CSS
st.markdown("""
    <style>
    /* Aggressively remove top padding/margin for main content */
    .main .block-container {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }
    /* Reduce top padding for sidebar */
    [data-testid="stSidebarNav"] {
        padding-top: 0rem !important;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem !important;
    }
    /* Make Tabs Sticky */
    div[data-testid="stTabBlock"] {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: white;
        padding-top: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid #eee;
    }
    /* ROBUST SIDEBAR CSS - Strict Left Align */
    [data-testid="stSidebar"] button {
        justify-content: flex-start !important;
        text-align: left !important;
        width: 100% !important;
        display: flex !important;
    }
    [data-testid="stSidebar"] button > div:first-child {
        justify-content: flex-start !important;
        text-align: left !important;
        width: 100% !important;
        display: flex !important;
        gap: 8px !important;
    }
    [data-testid="stSidebar"] button p {
        text-align: left !important;
        margin-left: 0 !important;
    }
    </style>
""", unsafe_allow_html=True)

target_dir = st.session_state.active_project

with st.sidebar:
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    st.header("Projects")
    try:
        app_version = version("entigram-ai")
        st.caption(f"v{app_version}")
    except Exception:
        st.caption("v0.0.1 (dev)")
    
    # 1. Project Search
    proj_search = st.text_input("Search Projects...", key="proj_search", label_visibility="collapsed", placeholder="Find project...")
    
    history = get_project_history()
    for path in history:
        folder_name = os.path.basename(path.rstrip('/'))
        
        # Apply filter
        if proj_search and proj_search.lower() not in folder_name.lower() and proj_search.lower() not in path.lower():
            continue
            
        is_active = (path == target_dir)
        if st.button(
            folder_name, 
            key=f"btn_{path}", 
            icon=":material/folder:",
            width='stretch', 
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_project = path
            add_project_to_history(path)
            st.rerun()
    
    st.divider()
    st.header("Active Packages")
    if target_dir:
        from entigram.broker import EntigramBroker
        broker = EntigramBroker(target_dir)
        pkgs = broker.get_active_packages()
        for p in pkgs:
            # Heuristic to find package source (Standard or .etg/packages)
            pkg_slug = p.replace(" ", "")
            # Try sibling directory first (as per user's recent move)
            sibling_registry = Path(__file__).parent.parent.parent / "entigram-standard-packages"
            potential_paths = [
                sibling_registry / pkg_slug,
                Path(target_dir) / ".etg" / "packages" / pkg_slug
            ]
            
            # If namespaced, it might be in sibling
            if "/" in pkg_slug:
                potential_paths.insert(0, sibling_registry / pkg_slug)
            else:
                # Legacy check for standard packages that moved to @entigram
                potential_paths.insert(0, sibling_registry / "@entigram" / pkg_slug)
            
            pkg_path = None
            for path in potential_paths:
                if path.exists():
                    pkg_path = str(path)
                    break
            
            if pkg_path:
                if st.button(p, key=f"pkg_btn_{p}", icon=":material/extension:", width='stretch'):
                    st.session_state.active_project = pkg_path
                    add_project_to_history(pkg_path)
                    st.rerun()
            else:
                st.write(f"○ {p} (Local)")

    st.divider()
    new_path = st.text_input("Manual Path Entry", value=st.session_state.active_project, placeholder="/Users/... or @namespace/pkg")
    if new_path != st.session_state.active_project:
        resolved_new_path = resolve_namespace_path(new_path)
        if resolved_new_path != new_path:
             st.session_state.active_project = resolved_new_path
        else:
             st.session_state.active_project = str(Path(new_path).expanduser().resolve()) if new_path else ""
        st.rerun()

# --- SYNC SETTINGS FROM MANIFEST ---
if target_dir and os.path.exists(target_dir):
    entigram_dir = os.path.join(target_dir, ".etg")
    manifest_path = os.path.join(entigram_dir, "entigram.yaml")
    
    if os.path.exists(manifest_path):
        if st.session_state.last_synced_project != target_dir:
            try:
                with open(manifest_path, 'r') as f:
                    m = yaml.safe_load(f)

                # Handle backwards compatibility (list vs dict)
                raw_pkgs = m.get('packages', [])
                if isinstance(raw_pkgs, dict):
                    raw_pkgs = list(raw_pkgs.keys())

                st.session_state.selected_packages = [p for p in raw_pkgs if p != "Entigram Schemas"]
                st.session_state.cli_engine = m.get('cli_engine', "Antigravity")
                st.session_state.last_synced_project = target_dir
            except: pass
        
        with st.sidebar:
            st.success(f"Active: {os.path.basename(target_dir)}")
            from entigram.broker import EntigramBroker
            broker = EntigramBroker(target_dir)
            health = broker.validate_model()
            if health['valid']: st.success(f"Broker: {health['entity_count']} Entities")
            else: st.warning(f"Broker: {health['error']}")

            # Warden Status
            from entigram.governance.warden import Warden
            warden = Warden(target_dir)
            if not warden.verify_integrity():
                st.error("Integrity: TAINTED", icon=":material/gpp_bad:")
                st.caption("The schema contracts (Schema/Ontology) have been modified since the last lock. Agents are halted.")
            else:
                with open(manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f) or {}
                if "integrity_fingerprint" in manifest:
                    st.success("Integrity: PROTECTED", icon=":material/enhanced_encryption:")
                    st.caption("The schema contracts are locked and verified via Checksum.")
                else:
                    st.info("Integrity: UNPROTECTED", icon=":material/no_encryption:")
                    st.caption("The schema contracts are not yet locked. Run 'Lock Schema Contracts' to protect the domain.")
            
            st.divider()
            from entigram.registry import EntigramRegistry
            registry = EntigramRegistry(target_dir)
            
            if st.button("Check for Package Updates", icon=":material/update:", width='stretch'):
                with st.spinner("Checking registries..."):
                    updates = registry.check_for_updates()
                    if updates:
                        st.session_state.pending_updates = updates
                    else:
                        st.toast("All packages are up to date!")
            
            if 'pending_updates' in st.session_state and st.session_state.pending_updates:
                for pkg, vers in st.session_state.pending_updates.items():
                    st.warning(f"**{pkg}**: {vers['current']} ➡️ {vers['latest']}")
                    if st.button(f"Upgrade {pkg}", key=f"upg_{pkg}", type="primary"):
                        if registry.install_package(pkg):
                            st.toast(f"Upgraded {pkg}!")
                            del st.session_state.pending_updates[pkg]
                            st.rerun()

# --- MAIN WORKSPACE (Redesigned with Top Bar) ---
if not target_dir:
    st.divider()
    st.info("👈 Select or enter a project path to begin.")
    st.stop()

# Task-Focused Navigation Bar
tabs = st.tabs([":material/home: Workspace", ":material/psychology: Model Engineering", ":material/language: Federated Query", ":material/link: Alignments", ":material/extension: Extensions", ":material/security: Sentinel", ":material/science: Simulator"])

# 1. WORKSPACE TAB (Setup & Agent Control)
with tabs[0]:
    col_left, col_right = st.columns([1, 1.2])
    with col_left:
        st.subheader("Package Selection")
        # Dynamically load available packages
        available_packages = set()
        cache_dir = Path.home() / ".etg" / "registry_cache"
        if cache_dir.exists():
            for repo in cache_dir.iterdir():
                if repo.is_dir():
                    for item in repo.iterdir():
                        if item.is_dir() and item.name.startswith("@"):
                            for pkg in item.iterdir():
                                if pkg.is_dir() and not pkg.name.startswith("."):
                                    available_packages.add(f"{item.name}/{pkg.name}")
                        elif item.is_dir() and not item.name.startswith("."):
                            available_packages.add(item.name)
        
        if target_dir:
            local_pkg_dir = Path(target_dir) / ".etg" / "packages"
            if local_pkg_dir.exists():
                for item in local_pkg_dir.iterdir():
                    if item.is_dir() and item.name.startswith("@"):
                        for pkg in item.iterdir():
                            if pkg.is_dir() and not pkg.name.startswith("."):
                                available_packages.add(f"{item.name}/{pkg.name}")
                    elif item.is_dir() and not item.name.startswith("."):
                        available_packages.add(item.name)

        available_packages = sorted(list(available_packages))
        pkg_search = st.text_input("Search Registry", placeholder="e.g., SupplyChain...", label_visibility="collapsed")
        if pkg_search:
            available_packages = [p for p in available_packages if pkg_search.lower() in p.lower()]

        selected_packages = st.multiselect("Select Optional Packages", available_packages, key="selected_packages")
        packages_to_inject = ["Entigram Schemas"] + selected_packages

        st.subheader("Engine Configuration")
        # Probe for available CLI engines
        all_engines = {
            "Antigravity": "agy",
            "Claude Code": "claude",
            "Ollama": "ollama",
            "Codex": "codex"
        }
        
        available_engines = [name for name, cmd in all_engines.items() if shutil.which(cmd)]
        
        if not available_engines:
            st.warning("No supported CLI engines detected on your system.")
            st.info("Please install at least one of the following:")
            st.markdown("- [Antigravity](https://github.com/nyabutid/antigravity)")
            st.markdown("- [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code)")
            st.markdown("- [Ollama](https://ollama.com/)")
            st.markdown("- [Codex](https://github.com/nyabutid/codex)")
            engines = ["None"]
        else:
            engines = sorted(available_engines)

        cli_engine = st.selectbox("CLI Engine", engines, key="cli_engine")
        
        if available_engines:
             st.caption("Available engines detected automatically.")
             with st.expander("Installation Links", icon=":material/link:"):
                st.markdown("- [Antigravity](https://antigravity.google/cli)")
                st.markdown("- [Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code)")
                st.markdown("- [Ollama](https://ollama.com/)")
                st.markdown("- [Codex](https://openai.com/codex)")

        if not os.path.exists(os.path.join(target_dir, ".etg", "entigram.yaml")):
            if st.button("Initialize Workspace", icon=":material/add_circle:", type="primary", width='stretch'):
                if inject_entigram_manifest(target_dir, packages_to_inject, cli_engine): st.rerun()
        else:
            if st.button("Sync / Update Packages", icon=":material/sync:", type="primary", width='stretch'):
                if inject_entigram_manifest(target_dir, packages_to_inject, cli_engine): 
                    st.toast("Synced!")
                    st.rerun()

    with col_right:
        st.subheader("Agent Control")
        custom_prompt = st.text_input("Prompt Override (Optional)")
        c1, c2, c3 = st.columns(3)
        with c1: 
            if st.button("Run Agent", icon=":material/play_arrow:", width='stretch'):
                # ACTIVE HYDRATION: Force LLM state alignment via boot file
                hydration_vector = get_hydration_vector(Path(target_dir), compact=True)
                boot_file = Path(target_dir) / ".etg" / "boot.json"
                with open(boot_file, "w") as f:
                    f.write(hydration_vector)
                
                p = custom_prompt if custom_prompt else f"Initialize from {boot_file}. Silent boot. Ready."
                success, msg = launch_agent(target_dir, cli_engine, initial_prompt=p)
                if success: st.success(msg)
                else: st.error(msg)
        with c2:
            if st.button("YOLO Mode", icon=":material/bolt:", width='stretch'):
                # ACTIVE HYDRATION: Force LLM state alignment via boot file
                hydration_vector = get_hydration_vector(Path(target_dir), compact=True)
                boot_file = Path(target_dir) / ".etg" / "boot.json"
                with open(boot_file, "w") as f:
                    f.write(hydration_vector)
                
                p = custom_prompt if custom_prompt else f"Initialize from {boot_file}. Silent boot. Ready."
                launch_agent(target_dir, engine=cli_engine, yolo=True, initial_prompt=p)
        with c3:
            if st.button("Interview", icon=":material/mic:", width='stretch'): 
                # ACTIVE HYDRATION: Force LLM state alignment via boot file
                hydration_vector = get_hydration_vector(Path(target_dir), compact=True)
                boot_file = Path(target_dir) / ".etg" / "boot.json"
                with open(boot_file, "w") as f:
                    f.write(hydration_vector)
                
                p = f"Initialize from {boot_file}. Silent boot. Ready."
                success, msg = launch_agent(target_dir, cli_engine, initial_prompt=p)
                if success: st.success(msg)
                else: st.error(msg)

        with st.expander("Manual Hydration Fallback", icon=":material/terminal:"):
            st.info("If the agent does not automatically boot, copy and paste this command into the terminal:")
            st.code("Initialize from .etg/boot.json. Silent boot. Ready.")

        with st.expander("Scaffold Custom Edge-Agent", icon=":material/handyman:"):
            new_agent_name = st.text_input("Agent Name", placeholder="stripe, plaid...")
            if st.button("Scaffold", type="primary", icon=":material/construction:"):
                if new_agent_name:
                    from entigram.cli_runner.agent_builder import generate_agent_boilerplate
                    generate_agent_boilerplate(new_agent_name, os.path.join(target_dir, "agents"))
                    st.success(f"Scaffolded at `agents/{new_agent_name}_edge`")

        st.divider()
        st.subheader("Agent Inventory")
        from entigram.agent_inventory import AgentInventory
        inventory = AgentInventory(target_dir).get_inventory()
        if not inventory:
            st.info("No agents with active skills found.")
        else:
            for agent in inventory:
                with st.expander(f"🤖 {agent['role']} ({agent['package']})", icon=":material/smart_toy:"):
                    st.write(f"**Type:** {agent['type']}")
                    st.write(f"**Constraints:**\n{agent['constraints']}")
                    st.write(f"**Primary Directives:**\n{agent['directives']}")
                    st.caption(f"Source: `{agent['path']}`")

# 2. MODEL ENGINEERING TAB
with tabs[1]:
    st.subheader("Entigram Schema")
    # Entity Search
    schema_file = Path(target_dir) / "schema.lds"
    if schema_file.exists():
        with open(schema_file, 'r') as f: 
            ents, _ = SchemaParser(f.read()).parse()
            if ents:
                selected_entity = st.selectbox("Find Entity", [""] + sorted(list(ents.keys())), index=0)
                if selected_entity:
                    ent = ents[selected_entity]
                    st.info(f"**{selected_entity}**" + (f" `[{ent.external_ref}]`" if ent.external_ref else ""))
                    for a in ent.attributes:
                        st.write(f"- {a['name']} ({a['type']})" + (" 🔑" if a['pk'] else "") + (f" 🔗 {a['external_link']}" if a.get('external_link') else ""))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Discover Model", icon=":material/search:", width='stretch'):
            dp = "Scan files and identify core entities for schema.lds."
            success, msg = launch_agent(target_dir, cli_engine, initial_prompt=dp)
            if success: st.success(msg)
    with col2:
        if st.button("Build SQL", icon=":material/build:", width='stretch'):
            if schema_file.exists():
                sql = compile_schema_file(str(schema_file))
                m_dir = Path(target_dir) / "migrations"
                m_dir.mkdir(parents=True, exist_ok=True)
                with open(m_dir / f"V{datetime.now().strftime('%Y.%m.%d.%H%M')}__update.sql", "w") as f: f.write(sql)
                st.session_state.last_build_sql = sql
                st.success("SQL Generated!")
    with col3:
        if st.button("Visualize Model", icon=":material/visibility:", width='stretch'):
            l_f = schema_file if schema_file.exists() else Path(target_dir) / "draft_schema.lds"
            if l_f.exists():
                e, r = SchemaParser(l_f.read_text()).parse()
                st.session_state.current_viz = SchemaGraphBuilder(e, r).to_mermaid()
                st.rerun()
    with col4:
        if st.button("Export Ontology", icon=":material/hub:", width='stretch'):
            if schema_file.exists():
                e, r = SchemaParser(schema_file.read_text()).parse()
                ttl = OntologyCompiler(e, r).compile()
                st.session_state.last_ontology_ttl = ttl
                st.success("Ontology Exported!")

    st.divider()
    from entigram.governance.warden import Warden
    warden = Warden(target_dir)
    is_protected = False
    with open(manifest_path, 'r') as f:
        manifest = yaml.safe_load(f) or {}
        is_protected = "integrity_fingerprint" in manifest

    if is_protected:
        if st.button("Unlock Schema Contracts", icon=":material/lock_open:", width='stretch'):
            warden.unlock()
            st.toast("Schema contracts unlocked.")
            st.rerun()
    else:
        if st.button("Lock Schema Contracts (Warden)", icon=":material/lock:", type="primary", width='stretch'):
            warden.lock_fingerprint()
            st.toast("Schema contracts locked via checksum integrity.")
            st.rerun()

# 3. FEDERATED QUERY TAB
with tabs[2]:
    st.subheader("GraphQL-LD Execution")
    # Dynamic default query logic
    default_q = "{\n  # Enter query\n}"
    if schema_file.exists():
        try:
            ents, _ = SchemaParser(schema_file.read_text()).parse()
            if ents:
                r_ent = next((n for n, e in ents.items() if not e.external_ref), list(ents.keys())[0])
                default_q = "{\n  " + r_ent + " {\n" + "\n".join([f"    {a['name']}" for a in ents[r_ent].attributes[:3]]) + "\n  }\n}"
        except: pass
    
    q_in = st.text_area("GraphQL", value=default_q, height=200, label_visibility="collapsed")
    if st.button("Run Federated Query", type="primary", icon=":material/database:"):
        from entigram.federated_router import FederatedRouter
        try: st.json(FederatedRouter(target_dir).execute(q_in))
        except Exception as e: st.error(f"Error: {e}")

# 4. ALIGNMENTS TAB
with tabs[3]:
    st.subheader("Semantic Reconciliation")
    from entigram.broker import EntigramBroker
    broker = EntigramBroker(target_dir)
    alns = broker.ledger.get_alignments()
    if alns: st.dataframe(alns, width='stretch')
    else: st.info("No authorized alignments.")
    
    with st.expander("Negotiate New Alignments", icon=":material/handshake:"):
        src = st.text_input("Source Schema", value="schema.lds")
        tgt = st.text_input("Target Schema", placeholder="PackageName/schema.lds")
        if st.button("Propose", icon=":material/lightbulb:"):
            s_p, t_p = Path(target_dir) / src, Path(target_dir) / ".etg" / "packages" / tgt
            if s_p.exists() and t_p.exists():
                props = broker.negotiate_alignments(str(s_p), str(t_p))
                if props: st.session_state.alignment_proposals = props; st.rerun()

# 5. EXTENSIONS TAB
with tabs[4]:
    st.subheader("CLI Extensions Registry")
    from entigram.cli_runner.plugin_builder import get_plugins, generate_plugin_boilerplate
    plugins = get_plugins(target_dir)
    
    if not plugins:
        st.info("No custom CLI extensions found in `.etg/plugins/`.")
    else:
        for p in plugins:
            with st.container(border=True):
                c1, c2 = st.columns([0.1, 0.9])
                with c1:
                    st.write("✅" if p['valid'] else "❌")
                with c2:
                    st.write(f"**{p['name']}**")
                    st.caption(p['description'])
                    st.code(f"python3 -m entigram.cli_runner.etg_cli {p['name']} --help")

    st.divider()
    with st.expander("Scaffold New CLI Plugin", icon=":material/add_circle:"):
        new_plugin_name = st.text_input("Plugin Name", placeholder="my_custom_tool")
        if st.button("Generate Plugin", type="primary"):
            if new_plugin_name:
                generate_plugin_boilerplate(new_plugin_name, target_dir)
                st.success(f"Plugin `{new_plugin_name}` scaffolded in `.etg/plugins/`.")
                st.rerun()

# 6. SENTINEL TAB
with tabs[5]:
    st.subheader("Governance & Security")
    if st.button("Run Sentinel Scan", icon=":material/security:", type="primary"):
        from entigram.governance.sentinel import SentinelScanner
        st.session_state.sentinel_results = SentinelScanner(target_dir).scan_all()
        st.rerun()
    
    if 'sentinel_results' in st.session_state:
        res = st.session_state.sentinel_results
        
        # Calculate global health
        total_issues = sum(len(r.get("vulnerabilities", [])) for r in res.values()) if isinstance(res, dict) else 0
        
        if total_issues == 0:
            st.success("✅ All packages are compliant with Semantic Governance rules.")
        else:
            st.error(f"🚨 Found {total_issues} security/structural issues across packages.")

        # Display package results, sorted by issues count
        sorted_pkgs = sorted(res.items(), key=lambda x: len(x[1].get("vulnerabilities", [])), reverse=True)
        
        for p, r in sorted_pkgs:
            vs = r.get("vulnerabilities", [])
            issue_count = len(vs)
            
            # Highlight failures with an icon and warning color
            label = f"{p} - {issue_count} issues"
            if issue_count > 0:
                with st.expander(f"⚠️ {label}", expanded=True):
                    for v in vs: 
                        st.warning(f"**[{v['severity']}]** {v['id']}: {v['description']}")
            else:
                with st.expander(f"✅ {p} (Passed)"):
                    st.write("No issues detected.")

# 7. SIMULATOR TAB
with tabs[6]:
    st.subheader("Conflict Simulation Sandbox")
    st.write("Test agent arbitration logic using an isolated, in-memory ledger.")
    
    with st.container(border=True):
        # Dynamically load entities for the simulator
        sim_entities = ["Supplier"] # Default fallback
        ents_dict = {}
        if schema_file.exists():
            try:
                ents_dict, _ = SchemaParser(schema_file.read_text()).parse()
                if ents_dict:
                    sim_entities = sorted(list(ents_dict.keys()))
            except: pass
        elif (Path(target_dir) / "draft_schema.lds").exists():
            try:
                ents_dict, _ = SchemaParser((Path(target_dir) / "draft_schema.lds").read_text()).parse()
                if ents_dict:
                    sim_entities = sorted(list(ents_dict.keys()))
            except: pass

        sim_entity = st.selectbox("Entity Type", sim_entities)
        
        # Generate a default JSON structure based on entity attributes
        default_state_a = '{"rating": 4.8}'
        default_state_b = '{"rating": 4.5}'
        if sim_entity in ents_dict:
            ent = ents_dict[sim_entity]
            sample_state = {}
            for attr in ent.attributes:
                if attr['type'] in ['String', 'Text', 'UUID']:
                    sample_state[attr['name']] = f"sample_{attr['name']}"
                elif attr['type'] in ['Integer', 'Int']:
                    sample_state[attr['name']] = 1
                elif attr['type'] in ['Decimal', 'Float']:
                    sample_state[attr['name']] = 1.0
                elif attr['type'] in ['Boolean']:
                    sample_state[attr['name']] = True
                else:
                     sample_state[attr['name']] = "value"
            
            default_state_a = json.dumps(sample_state, indent=2)
            # Create a slight variation for Agent B
            sample_state_b = sample_state.copy()
            if sample_state_b:
                first_key = list(sample_state_b.keys())[-1] # Pick the last one to change
                if isinstance(sample_state_b[first_key], (int, float)):
                     sample_state_b[first_key] += 1
                elif isinstance(sample_state_b[first_key], str):
                     sample_state_b[first_key] += "_alt"
                elif isinstance(sample_state_b[first_key], bool):
                     sample_state_b[first_key] = not sample_state_b[first_key]
            default_state_b = json.dumps(sample_state_b, indent=2)

        col_a, col_b = st.columns(2)
        with col_a:
            state_a = st.text_area("Agent A State (JSON)", value=default_state_a, height=200)
        with col_b:
            state_b = st.text_area("Agent B State (JSON)", value=default_state_b, height=200)

            
        if st.button("Run Simulation", type="primary", icon=":material/science:"):
            from entigram.simulator import EntigramSimulator
            try:
                sim = EntigramSimulator(target_dir)
                states = {
                    "Agent_A": json.loads(state_a),
                    "Agent_B": json.loads(state_b)
                }
                result = sim.run_conflict_scenario(sim_entity, states)
                
                st.divider()
                st.write(f"### Result: {result['status']}")
                if result['resolution']:
                    st.success(f"**Resolved State:** {result['resolution']['state']}")
                    st.caption(f"**Rationale:** {result['resolution']['rationale']}")
                else:
                    st.info("Conflict escalated to human operator (In-Memory Ledger).")
                
                with st.expander("Raw Simulator Log"):
                    st.json(result)
            except Exception as e:
                st.error(f"Simulation Error: {e}")

# --- FULL WIDTH OUTPUTS (Previewers & Visualizer) ---

if 'last_build_sql' in st.session_state:
    st.divider()
    st.subheader("SQL Migration Preview")
    st.code(st.session_state.last_build_sql, language="sql")
    if st.button("Close SQL Preview", icon=":material/close:"): del st.session_state.last_build_sql; st.rerun()

if 'last_ontology_ttl' in st.session_state:
    st.divider()
    st.subheader("Ontology Preview (Turtle)")
    st.code(st.session_state.last_ontology_ttl, language="turtle")
    st.download_button("Download schema.ttl", st.session_state.last_ontology_ttl, file_name="schema.ttl", mime="text/turtle")
    if st.button("Close Ontology Preview", icon=":material/close:"): del st.session_state.last_ontology_ttl; st.rerun()

if 'current_viz' in st.session_state:
    st.divider()
    st.subheader("Model Visualizer")
    # (Visualizer logic remains same, but integrated into full width flow)
    import streamlit.components.v1 as components
    import base64
    import json
    m_code = st.session_state.current_viz
    ext_links = {}
    if schema_file.exists():
        e, _ = SchemaParser(schema_file.read_text()).parse()
        for n, ent in e.items():
            if ent.external_ref: ext_links[n] = ent.external_ref.split("::")[0]
    
    links_json = json.dumps(ext_links)
    raw_h = f"""
    <!DOCTYPE html><html><head><style>
        body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: white; }}
        #container {{ width: 100%; height: 100%; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }}
        #mermaid-container {{ width: 100%; height: 100%; }}
    </style></head><body>
        <div id="container"><div id="mermaid-container" class="mermaid">{m_code}</div></div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
        <script>
            mermaid.initialize({{ startOnLoad: true, theme: 'base', securityLevel: 'loose' }});
            setTimeout(() => {{ 
                mermaid.init(undefined, document.querySelectorAll('.mermaid')); 
                var svgs = document.querySelectorAll('.mermaid svg');
                if (svgs.length > 0) {{
                    var svg = svgs[0]; svg.style.maxWidth = '100%'; svg.style.height = '100%';
                    svgPanZoom(svg, {{ zoomEnabled: true, controlIconsEnabled: true, fit: true, center: true, minZoom: 0.1 }});
                }}
            }}, 500);
        </script>
    </body></html>"""
    components.iframe(src=f"data:text/html;base64,{base64.b64encode(raw_h.encode('utf-8')).decode('utf-8')}", height=600)
    
    if ext_links:
        st.write("##### Connected Packages")
        c_links = st.columns(4)
        for i, (en, pt) in enumerate(ext_links.items()):
            with c_links[i % 4]:
                if st.button(en, key=f"nav_{en}", width='stretch'):
                    st.session_state.active_project = resolve_namespace_path(pt); del st.session_state.current_viz; st.rerun()

    if st.button("Close Visualizer", type="primary", icon=":material/close:"): del st.session_state.current_viz; st.rerun()

st.divider()
if target_dir:
    entigram_dir = os.path.join(target_dir, ".etg")
    if os.path.exists(entigram_dir):
        st.subheader("Decisions")
        ledger = LedgerManager(os.path.join(entigram_dir, "entigram_state.db"))
        res = ledger.get_all_resolutions()
        if res: st.dataframe(res, width='stretch')
        else: st.info("No decisions recorded.")
