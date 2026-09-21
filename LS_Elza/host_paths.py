"""Host paths and rollback-safe runtime state migration for LS Elza."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
APP_ROOT = PACKAGE_DIR.parent
HOST_ROOT = APP_ROOT.parent if APP_ROOT.name.casefold() == "localsunodb_app" else APP_ROOT
DATA_DIR = HOST_ROOT / "Data" / "LS_Elza"
LOGS_DIR = HOST_ROOT / "Logs" / "LS_Elza"
LEGACY_PACKAGE_DIR = HOST_ROOT / "LS_Elza"
LEGACY_DATA_DIR = HOST_ROOT / "Data"
LEGACY_LOGS_DIR = HOST_ROOT / "Logs"


def ensure_runtime_dirs(probe_mode: bool = False) -> None:
    if probe_mode:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def copy_legacy_runtime_file(
    file_name: str,
    destination_dir: Path,
    source_dirs: tuple[Path, ...],
) -> bool:
    """Copy one legacy runtime file only when the new location is empty."""
    target = Path(destination_dir) / file_name
    if target.exists():
        return False
    for source_dir in source_dirs:
        source = Path(source_dir) / file_name
        if not source.is_file() or source.resolve() == target.resolve():
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".migration-copy.tmp")
            shutil.copy2(source, temp)
            os.replace(temp, target)
            return True
        except OSError:
            try:
                temp.unlink(missing_ok=True)
            except Exception:
                pass
    return False
