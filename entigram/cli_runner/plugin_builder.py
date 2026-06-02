import os
import argparse
import importlib.util
from pathlib import Path
from typing import List, Dict

def generate_plugin_boilerplate(plugin_name: str, target_dir: str):
    """Scaffolds a new Entigram CLI plugin."""
    plugins_dir = os.path.join(target_dir, ".etg", "plugins")
    os.makedirs(plugins_dir, exist_ok=True)

    plugin_file = os.path.join(plugins_dir, f"{plugin_name}.py")
    
    content = f"""import argparse

def {plugin_name}_handler(args):
    \"\"\"Handler for the {plugin_name} command.\"\"\"
    print(f"Executing custom plugin '{plugin_name}'...")
    # Add your custom logic here

def register_command(subparsers):
    \"\"\"Registers the '{plugin_name}' command with the Entigram CLI.\"\"\"
    parser = subparsers.add_parser("{plugin_name}", help="Custom plugin for {plugin_name}")
    # Add your arguments here, e.g.:
    # parser.add_argument("--example", help="An example argument")
    parser.set_defaults(func={plugin_name}_handler)
"""
    with open(plugin_file, "w") as f:
        f.write(content)

    print(f"✅ Successfully bootstrapped plugin '{plugin_name}' at {plugin_file}")

def get_plugins(target_dir: str) -> List[Dict[str, str]]:
    """Lists all valid Entigram CLI plugins in the workspace."""
    plugins_dir = Path(target_dir) / ".etg" / "plugins"
    plugins = []
    
    if not plugins_dir.exists():
        return []

    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name == "__init__.py":
            continue
            
        plugin_info = {
            "name": plugin_file.stem,
            "path": str(plugin_file),
            "valid": False,
            "description": "No register_command found."
        }
        
        # Try to peek into the file for a description or just verify it's a real plugin
        try:
            with open(plugin_file, 'r') as f:
                content = f.read()
                if "def register_command" in content:
                    plugin_info["valid"] = True
                    plugin_info["description"] = f"Entigram CLI Extension: {plugin_file.stem}"
        except: pass
        
        plugins.append(plugin_info)
        
    return plugins

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entigram Plugin Scaffolder")
    parser.add_argument("name", help="Name of the custom plugin")
    parser.add_argument("--dir", default=".", help="Target directory (workspace root)")
    args = parser.parse_args()
    
    generate_plugin_boilerplate(args.name, args.dir)
