import os
import shutil
import subprocess
import hashlib
import yaml
from pathlib import Path
from typing import List, Optional

class EntigramRegistry:
    """
    Manages package registries, allowing Entigram to pull standard or custom 
    packages from remote Git repositories.
    """
    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir).expanduser().resolve()
        self.etg_dir = self.target_dir / ".etg"
        self.manifest_path = self.etg_dir / "entigram.yaml"
        self.global_cache_dir = Path.home() / ".etg" / "registry_cache"
        self.global_cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_registry = "git@github.com:nyabutid/entigram-standard-packages.git"

    def get_registries(self) -> List[str]:
        """Returns a list of all configured registries, including the default Cloud API."""
        # Primary: managed Entigram registry
        regs = ["https://api.entigram.ai/v1/registry"]
        
        # Secondary: Community Git Registry
        if self.default_registry not in regs:
            regs.append(self.default_registry)
            
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    manifest = yaml.safe_load(f) or {}
                for r in manifest.get('registries', []):
                    if r not in regs:
                        regs.append(r)
            except Exception as e:
                print(f"Warning: Could not read registries from manifest: {e}")
        return regs

    def add_registry(self, url: str) -> bool:
        """Adds a new remote Git URL to the project manifest."""
        if not self.manifest_path.exists():
            print("❌ Entigram workspace not initialized. Run 'etg init' first.")
            return False
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = yaml.safe_load(f) or {}
            regs = manifest.get('registries', [])
            if url not in regs:
                regs.append(url)
                manifest['registries'] = regs
                with open(self.manifest_path, 'w') as f:
                    yaml.dump(manifest, f, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error adding registry: {e}")
            return False

    def _get_auth_url(self, url: str) -> str:
        """Injects ENTIGRAM_GIT_TOKEN into HTTPS URLs if present."""
        token = os.environ.get("ENTIGRAM_GIT_TOKEN")
        if token and url.startswith("https://"):
            # Ensure we don't double-inject if it already has credentials
            if "@" not in url.split("://")[1]:
                return url.replace("https://", f"https://{token}@")
        return url

    def _fetch_registry(self, url: str) -> Optional[Path]:
        """Clones or pulls the latest version of the registry into the global cache."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_path = self.global_cache_dir / url_hash
        
        auth_url = self._get_auth_url(url)
        
        # Mask the URL for logging if it contains a token
        log_url = url
        if "@" in log_url and log_url.startswith("https://"):
             log_url = "https://***@" + log_url.split("@", 1)[1]
        elif "@" in auth_url and auth_url.startswith("https://"):
             log_url = "https://***@" + auth_url.split("@", 1)[1]
             
        try:
            if cache_path.exists():
                print(f"🔄 Updating registry cache: {log_url}")
                # We use --quiet to keep the CLI output clean
                # Set origin URL to auth URL before pulling, then revert
                subprocess.run(["git", "-C", str(cache_path), "remote", "set-url", "origin", auth_url], check=True)
                subprocess.run(["git", "-C", str(cache_path), "pull", "--quiet"], check=True)
                # Remove token from local git config
                subprocess.run(["git", "-C", str(cache_path), "remote", "set-url", "origin", url], check=True)
            else:
                print(f"📥 Cloning registry: {log_url}")
                subprocess.run(["git", "clone", "--quiet", auth_url, str(cache_path)], check=True)
                # Remove token from local git config
                subprocess.run(["git", "-C", str(cache_path), "remote", "set-url", "origin", url], check=True)
            return cache_path
        except subprocess.CalledProcessError as e:
            # Mask error message just in case the URL is included in the exception
            err_msg = str(e).replace(auth_url, log_url)
            print(f"❌ Failed to fetch registry {log_url}: {err_msg}")
            return None

    def _is_api_registry(self, url: str) -> bool:
        """Heuristic to check if the registry is a Entigram API endpoint vs a Git repo."""
        return url.startswith("http") and not url.endswith(".git") and "api.entigram.ai" in url

    def _fetch_api_package(self, api_url: str, package_name: str) -> Optional[Path]:
        """
        Simulates fetching a package from a Entigram API registry.
        In a production environment, this would download a signed tarball.
        """
        url_hash = hashlib.md5(f"{api_url}/{package_name}".encode()).hexdigest()
        cache_path = self.global_cache_dir / "api_cache" / url_hash
        
        # Managed delivery path for signed semantic mapping packages. 
        # Managed, high-availability delivery of semantic mappings.
        print(f"🌐 [ENTIGRAM CLOUD] Resolving '{package_name}' via API: {api_url}")
        
        # For now, we return None to fall back to Git if the API is 'offline' (not implemented)
        # but the infrastructure is now in place.
        return None

    def install_package(self, package_name: str) -> bool:
        """
        Searches all configured registries for a package and installs it 
        into the local .etg/packages directory. Locks the version.
        Supports namespaces e.g., @entigram/SupplyChain.
        """
        registries = self.get_registries()
        local_packages_dir = self.etg_dir / "packages"
        local_packages_dir.mkdir(parents=True, exist_ok=True)
        
        target_pkg_path = local_packages_dir / package_name
            
        for reg_url in registries:
            if self._is_api_registry(reg_url):
                cache_path = self._fetch_api_package(reg_url, package_name)
            else:
                cache_path = self._fetch_registry(reg_url)
                
            if not cache_path:
                continue
                
            source_pkg_path = cache_path / package_name
            
            # Legacy fallback: if package_name doesn't have a namespace, check @entigram/
            if not source_pkg_path.exists() and "/" not in package_name:
                source_pkg_path = cache_path / "@entigram" / package_name

            if source_pkg_path.exists() and source_pkg_path.is_dir():
                # Extract version from package's own manifest
                pkg_version = "latest"
                pkg_manifest = source_pkg_path / ".etg" / "entigram.yaml"
                if pkg_manifest.exists():
                    try:
                        with open(pkg_manifest, 'r') as f:
                            pm = yaml.safe_load(f) or {}
                            pkg_version = pm.get('version', '0.0.1')
                    except Exception as e:
                        print(f"Warning: Could not read package manifest for '{package_name}': {e}")

                if target_pkg_path.exists():
                    # If it exists, overwrite it (upgrade/reinstall)
                    shutil.rmtree(target_pkg_path)

                print(f"📦 Installing '{package_name}' (v{pkg_version}) from registry...")
                shutil.copytree(source_pkg_path, target_pkg_path)
                
                self._update_manifest(package_name, pkg_version)
                print(f"✅ Package '{package_name}' successfully locked to v{pkg_version}.")
                return True
        
        print(f"❌ Package '{package_name}' not found in any registered repositories.")
        return False
        
    def check_for_updates(self) -> dict:
        """
        Fetches the latest registries and compares remote package versions
        against the locked versions in the local manifest.
        Returns a dict of {package_name: {"current": v1, "latest": v2}}.
        """
        if not self.manifest_path.exists(): return {}
        
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = yaml.safe_load(f) or {}
            
            local_pkgs = manifest.get('packages', {})
            if isinstance(local_pkgs, list):
                local_pkgs = {p: "latest" for p in local_pkgs}
        except Exception as e:
            print(f"Warning: Could not read local manifest for update check: {e}")
            return {}

        updates_available = {}
        registries = self.get_registries()
        
        for reg_url in registries:
            cache_path = self._fetch_registry(reg_url)
            if not cache_path: continue
            
            for pkg_name, current_version in local_pkgs.items():
                if pkg_name in updates_available: continue # already found an update
                
                source_pkg_path = cache_path / pkg_name
                # Legacy fallback check
                if not source_pkg_path.exists() and "/" not in pkg_name:
                    source_pkg_path = cache_path / "@entigram" / pkg_name

                if source_pkg_path.exists() and source_pkg_path.is_dir():
                    pkg_manifest = source_pkg_path / ".etg" / "entigram.yaml"
                    if pkg_manifest.exists():
                        try:
                            with open(pkg_manifest, 'r') as f:
                                pm = yaml.safe_load(f) or {}
                                remote_version = pm.get('version', '0.0.1')
                                
                                if remote_version != current_version and remote_version != "latest":
                                    updates_available[pkg_name] = {
                                        "current": current_version,
                                        "latest": remote_version
                                    }
                        except Exception as e:
                            print(f"Warning: Could not read remote manifest for '{pkg_name}': {e}")

        return updates_available

    def _update_manifest(self, package_name: str, version: str):
        """Ensures the package is listed in the entigram.yaml packages dict."""
        if not self.manifest_path.exists(): return
        try:
            with open(self.manifest_path, 'r') as f:
                manifest = yaml.safe_load(f) or {}
            
            pkgs = manifest.get('packages', {})
            # Backwards compatibility: convert list to dict
            if isinstance(pkgs, list):
                pkgs = {p: "latest" for p in pkgs}
                
            pkgs[package_name] = version
            manifest['packages'] = pkgs
            
            with open(self.manifest_path, 'w') as f:
                yaml.dump(manifest, f, default_flow_style=False)
        except Exception as e:
            print(f"❌ Error updating manifest lockfile: {e}")
