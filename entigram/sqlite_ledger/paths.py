from pathlib import Path
from typing import Optional

import yaml


CANONICAL_LEDGER_NAME = "state.db"
LEGACY_LEDGER_NAME = "entigram_state.db"


def resolve_ledger_path(target_dir: str, *, create_default: bool = True) -> Path:
    """
    Returns the workspace ledger path.

    New workspaces use .etg/state.db. Existing workspaces that explicitly
    reference or only contain .etg/entigram_state.db continue to work.
    """
    target_path = Path(target_dir).expanduser().resolve()
    etg_dir = target_path / ".etg"
    manifest_path = etg_dir / "entigram.yaml"

    manifest_ledger = _manifest_ledger_path(manifest_path)
    if manifest_ledger is not None:
        resolved = manifest_ledger if manifest_ledger.is_absolute() else (target_path / manifest_ledger).resolve()
        legacy = etg_dir / LEGACY_LEDGER_NAME
        if not resolved.exists() and resolved.name == CANONICAL_LEDGER_NAME and legacy.exists():
            return legacy
        return resolved

    canonical = etg_dir / CANONICAL_LEDGER_NAME
    legacy = etg_dir / LEGACY_LEDGER_NAME

    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical if create_default else legacy


def _manifest_ledger_path(manifest_path: Path) -> Optional[Path]:
    if not manifest_path.exists():
        return None
    try:
        manifest = yaml.safe_load(manifest_path.read_text()) or {}
    except Exception:
        return None

    value = manifest.get("state_ledger")
    if not value:
        return None
    return Path(value).expanduser()
