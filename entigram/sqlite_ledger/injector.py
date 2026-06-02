import os
import sqlite3
from pathlib import Path
from typing import Optional
from entigram.schema_compiler import compile_schema_file

class DomainSQLiteInjector:
    """
    Injects a compiled Schema into a local SQLite database for a specific domain package.
    Transitions agent state from simple JSON files to robust, schema-enforced SQLite databases.
    """
    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir).expanduser().resolve()
        self.etg_dir = self.workspace_dir / ".etg"
        self.packages_dir = self.workspace_dir / "packages"
        self.states_dir = self.etg_dir / "states"
        
    def _get_pkg_path(self, pkg_name: str) -> Path:
        # Check workspace 'packages/' folder first (for tests and local overrides)
        pkg_root_path = self.workspace_dir / "packages" / pkg_name
        if (pkg_root_path / "schema.lds").exists():
            return pkg_root_path

        # Fallback to locked/registry packages in .etg/packages/
        user_pkg_path = self.etg_dir / "packages" / pkg_name
        if user_pkg_path.exists():
            return user_pkg_path
            
        # Fallback to the root packages dir (legacy/internal)
        return self.packages_dir / pkg_name

    def inject_domain(self, domain_name: str, enable_crsqlite: bool = False) -> bool:
        """
        Compiles the domain's Schema and injects it into a new SQLite database.
        """
        pkg_dir = self._get_pkg_path(domain_name)
        schema_file = pkg_dir / "schema.lds"
        
        if not schema_file.exists():
            print(f"Error: Schema file not found for domain '{domain_name}' at {schema_file}")
            return False
            
        # Compile Schema to SQL
        try:
            sql_script = compile_schema_file(str(schema_file), enable_crsqlite=enable_crsqlite)
        except Exception as e:
            print(f"Error compiling Schema for '{domain_name}': {e}")
            return False
            
        # Create SQLite database
        self.states_dir.mkdir(parents=True, exist_ok=True)
        db_path = self.states_dir / f"{domain_name}.db"
        
        conn = sqlite3.connect(db_path)
        try:
            with conn:
                # If CR-SQLite is requested, load the extension (assumes it is available in path)
                if enable_crsqlite:
                    try:
                        conn.enable_load_extension(True)
                        conn.load_extension("crsqlite")
                        conn.enable_load_extension(False)
                    except Exception as cr_err:
                        print(f"Warning: Failed to load CR-SQLite extension. Ensure it is installed. ({cr_err})")

                # Execute the generated SQL script
                conn.executescript(sql_script)
                print(f"✅ Successfully injected Schema into {db_path.name}")
            return True
        except Exception as e:
            print(f"Error executing SQL for '{domain_name}': {e}")
            return False
        finally:
            conn.close()

    def inject_all_active(self, enable_crsqlite: bool = False) -> list[str]:
        """
        Injects SQLite databases for all active packages defined in the manifest.
        """
        manifest_path = self.etg_dir / "entigram.yaml"
        if not manifest_path.exists():
            print("Error: entigram.yaml manifest not found.")
            return []
            
        import yaml
        with open(manifest_path, 'r') as f:
            manifest = yaml.safe_load(f)
            
        packages = manifest.get('packages', [])
        successful_injections = []
        
        for pkg in packages:
            if pkg == "Entigram Schemas": # Skip the root modeling package itself if listed
                continue
            if self.inject_domain(pkg, enable_crsqlite=enable_crsqlite):
                successful_injections.append(pkg)
                
        return successful_injections
