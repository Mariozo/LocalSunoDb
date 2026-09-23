"""Flat-root runtime helpers for the clean LS repository.

The repository root is the application root. Runtime data folders live beside
the stable ``LocalSunoDb.py`` entrypoint; no managed application
subdirectory or launcher migration is used.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def resolve_host_root(app_dir: Path) -> Path:
    return Path(app_dir).resolve()


def organize_ls_root(
    *,
    host_root: Path,
    app_dir: Path,
    data_dir: Path,
    logs_dir: Path,
    reports_dir: Path,
    backup_dir: Path,
    temp_dir: Path,
    tools_dir: Path,
    probe_mode: bool = False,
) -> dict[str, Any]:
    """Keep the clean repository flat and create only runtime directories."""
    root = Path(host_root).resolve()
    app = Path(app_dir).resolve()
    if root != app:
        raise ValueError(f"LS flat-root contract mismatch: app={app} root={root}")
    moved = []
    duplicates_removed = []
    if not probe_mode:
        for folder in (data_dir, logs_dir, reports_dir, backup_dir, temp_dir, tools_dir):
            Path(folder).mkdir(parents=True, exist_ok=True)

        package_notes_dir = Path(reports_dir) / "PackageNotes"
        generated_note_patterns = (
            "README_PATCH.txt",
            "README_v*.txt",
            "SHA256SUMS.txt",
        )
        generated_notes = []
        for pattern in generated_note_patterns:
            generated_notes.extend(root.glob(pattern))

        for source in sorted({path.resolve() for path in generated_notes}):
            source = Path(source)
            if not source.is_file() or source.parent != root:
                continue
            package_notes_dir.mkdir(parents=True, exist_ok=True)
            target = package_notes_dir / source.name

            if target.exists():
                try:
                    if source.read_bytes() == target.read_bytes():
                        source.unlink()
                        duplicates_removed.append(str(source))
                        continue
                except OSError:
                    pass

                index = 2
                while True:
                    candidate = target.with_name(
                        f"{target.stem}.{index}{target.suffix}"
                    )
                    if not candidate.exists():
                        target = candidate
                        break
                    index += 1

            source.replace(target)
            moved.append({
                "source": str(source),
                "target": str(target),
            })

    return {
        "ok": True,
        "flat_root": str(root),
        "moved": moved,
        "duplicates_removed": duplicates_removed,
        "conflicts_quarantined": [],
        "copied_for_rollback": [],
        "kept": [],
        "warnings": [],
    }
