#!/usr/bin/env python3
"""Update a Homebrew formula from PyPI release metadata."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


FORMULA_SOURCE_RE = re.compile(
    r'(?m)^(  url ")[^"]+\.tar\.gz("\n  sha256 ")[0-9a-f]{64}(")$'
)
RESOURCE_RE = re.compile(r'^\s*resource "([^"]+)" do')
NATIVE_DEPENDENCY_BY_RESOURCE = {
    "cryptography": "cryptography",
    "cffi": "cffi",
    "pycparser": "pycparser",
    "pydantic": "pydantic",
    "pydantic-core": "pydantic",
    "pydantic_core": "pydantic",
    "annotated-types": "pydantic",
    "annotated_types": "pydantic",
    "rpds-py": "rpds-py",
    "rpds_py": "rpds-py",
}
DEPENDENCY_ORDER = ["cryptography", "cffi", "pycparser", "pydantic", "rpds-py"]


def load_pypi_release(
    package_name: str,
    version: str,
    *,
    attempts: int = 12,
    sleep_seconds: int = 10,
) -> dict[str, Any]:
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except Exception as exc:  # pragma: no cover - exercised in GitHub Actions
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds)

    raise RuntimeError(f"Could not load PyPI metadata for {package_name}=={version}: {last_error}")


def load_release_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def select_sdist(release: dict[str, Any]) -> tuple[str, str]:
    for file_info in release.get("urls", []):
        if file_info.get("packagetype") != "sdist":
            continue
        filename = file_info.get("filename", "")
        if not filename.endswith(".tar.gz"):
            continue
        sha256 = file_info.get("digests", {}).get("sha256")
        url = file_info.get("url")
        if url and sha256:
            return url, sha256

    raise RuntimeError("PyPI metadata did not include a source .tar.gz with a sha256 digest")


def update_formula_source(formula_path: Path, source_url: str, sha256: str) -> None:
    text = formula_path.read_text()

    def replacement(match: re.Match[str]) -> str:
        return f"{match.group(1)}{source_url}{match.group(2)}{sha256}{match.group(3)}"

    updated, count = FORMULA_SOURCE_RE.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not update top-level source URL/checksum in {formula_path}")

    formula_path.write_text(updated)


def filter_native_resources(resources_text: str) -> tuple[str, list[str]]:
    """
    Removes poet resource blocks that Homebrew should satisfy with bottled
    native formulas instead of source-building Rust/C extensions in the etg
    virtualenv.
    """
    filtered_lines = []
    native_deps = set()
    skip_mode = False

    for line in resources_text.splitlines():
        match = RESOURCE_RE.match(line)
        if match:
            resource_name = match.group(1)
            native_dep = NATIVE_DEPENDENCY_BY_RESOURCE.get(resource_name)
            if native_dep:
                native_deps.add(native_dep)
                skip_mode = True

        if not skip_mode:
            filtered_lines.append(line)

        if skip_mode and line.strip() == "end":
            skip_mode = False

    cleaned_resources_text = "\n".join(
        line for line in filtered_lines if line.strip() or line == ""
    )
    ordered_deps = [dep for dep in DEPENDENCY_ORDER if dep in native_deps]
    return cleaned_resources_text, ordered_deps


def render_dependency_block(native_deps: list[str], resources_text: str) -> str:
    depends_lines = [f'  depends_on "{dep}"' for dep in native_deps]
    indented_resources = [
        "  " + line if line else ""
        for line in resources_text.splitlines()
    ]
    sections = []
    if depends_lines:
        sections.append("\n".join(depends_lines))
    if indented_resources:
        sections.append("\n".join(indented_resources))
    return "\n" + "\n\n".join(sections) + "\n\n"


def update_resources(formula_path: Path, package_name: str, version: str) -> None:
    # Use poet to get the resources
    print("Installing package and poet in a temporary virtualenv...")
    subprocess.run([sys.executable, "-m", "venv", ".poet-venv"], check=True)
    # Install from the local repository root instead of PyPI to avoid race conditions
    repo_root = str(Path(__file__).resolve().parent.parent)
    subprocess.run([".poet-venv/bin/pip", "install", repo_root, "homebrew-pypi-poet", "setuptools<70"], check=True)
    
    print("Generating resources with poet...")
    result = subprocess.run([".poet-venv/bin/poet", package_name], capture_output=True, text=True, check=True)
    resources_text = result.stdout.strip()
    cleaned_resources_text, native_deps = filter_native_resources(resources_text)

    text = formula_path.read_text()

    # We want to replace everything between 'depends_on "python@3.12"' and 'def install'
    start_marker = 'depends_on "python@3.12"\n'
    end_marker = '  def install\n'
    
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        raise RuntimeError("Could not find markers to inject resources into formula")
        
    start_idx += len(start_marker)
    
    # Indent the resources text properly and inject Homebrew's bottled dependencies.
    indented_resources = render_dependency_block(native_deps, cleaned_resources_text)
    
    updated_text = text[:start_idx] + indented_resources + text[end_idx:]
    formula_path.write_text(updated_text)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update a Homebrew formula from PyPI metadata.")
    parser.add_argument("formula", type=Path)
    parser.add_argument("--package-name", default="entigram-ai")
    parser.add_argument("--version", required=True)
    parser.add_argument("--pypi-json", type=Path)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--sleep-seconds", type=int, default=10)
    args = parser.parse_args(argv)

    if args.pypi_json:
        release = load_release_json(args.pypi_json)
    else:
        release = load_pypi_release(
            args.package_name,
            args.version,
            attempts=args.attempts,
            sleep_seconds=args.sleep_seconds,
        )

    source_url, sha256 = select_sdist(release)
    update_formula_source(args.formula, source_url, sha256)
    update_resources(args.formula, args.package_name, args.version)
    print(f"Updated {args.formula} to {source_url}")
    print(f"SHA256: {sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
