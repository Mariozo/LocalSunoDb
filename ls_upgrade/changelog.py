"""Canonical cumulative LocalSunoDb Upgrade changelog support."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .package import manifest_upgrade_points

CHANGELOG_NAME = "LS_CHANGELOG.md"
TITLE = "# LocalSunoDb — Izmaiņu žurnāls"
_MONTHS = ["jan.", "feb.", "mar.", "apr.", "mai.", "jūn.", "jūl.", "aug.", "sep.", "okt.", "nov.", "dec."]


def display_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{1,2}\.[A-Za-zĀ-ž]+\.\d{4}", text):
        return text
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return f"{parsed.day:02d}.{_MONTHS[parsed.month - 1]}{parsed.year}"
    except Exception:
        return text


def _version_present(text: str, version: str) -> bool:
    pattern = re.compile(rf"(?m)^\s*(?:##\s+)?{re.escape(version)}\s+(?:—|-)\s+")
    return bool(pattern.search(str(text or "")))


def _clean_lines(lines: Sequence[str]) -> list[str]:
    clean: list[str] = []
    for line in lines:
        text = str(line or "").strip().lstrip("•*-–— ").strip()
        if text:
            clean.append(text)
    return clean


def _atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def read_changelog_markdown(base_dir: Path) -> str:
    path = Path(base_dir) / CHANGELOG_NAME
    if path.is_file():
        return path.read_text(encoding="utf-8-sig")
    return TITLE + "\n\n*Izmaiņu žurnālā vēl nav ierakstu.*\n"


def prepend_release_changelog(path: Path, version: str, published_at: str, lines: Sequence[str]) -> bool:
    path = Path(path)
    version = str(version or "").strip()
    if not version:
        raise ValueError("Changelog version is required")
    existing = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    if _version_present(existing, version):
        return False
    clean_lines = _clean_lines(lines)
    date = display_date(published_at)
    if path.suffix.casefold() == ".md":
        heading = f"## {version} — {date}" if date else f"## {version}"
    else:
        heading = f"{version} — {date}" if date else version
    block = heading + "\n"
    if clean_lines:
        block += "\n".join(f"- {line}" for line in clean_lines) + "\n\n"
    else:
        block += "- Izmaiņu apraksts nav norādīts.\n\n"
    if path.suffix.casefold() == ".md":
        current = existing.lstrip("\ufeff\r\n")
        if current.startswith(TITLE):
            remainder = current[len(TITLE):].lstrip("\r\n")
        else:
            remainder = current
        text = TITLE + "\n\n" + block
        if remainder:
            text += remainder.rstrip() + "\n"
    else:
        text = block + existing.lstrip("\ufeff\r\n")
    _atomic_write(path, text)
    return True


def append_verified_upgrade_changelog(base_dir: Path, manifest: dict[str, Any]) -> bool:
    if not isinstance(manifest, dict):
        raise ValueError("Upgrade changelog manifest must be an object")
    version = str(manifest.get("version") or "").strip()
    if not version:
        raise ValueError("Upgrade changelog manifest version is required")
    base = Path(base_dir)
    path = base / CHANGELOG_NAME
    if not path.is_file():
        _atomic_write(path, TITLE + "\n")
    return prepend_release_changelog(
        path, version,
        str(manifest.get("created_at") or manifest.get("published_at") or ""),
        manifest_upgrade_points(manifest),
    )


def capture_changelog_snapshot(base_dir: Path, transaction_dir: Path) -> dict[str, Any]:
    base = Path(base_dir).resolve()
    path = base / CHANGELOG_NAME
    tx_dir = Path(transaction_dir).resolve()
    tx_dir.mkdir(parents=True, exist_ok=True)
    existed = path.is_file()
    backup = tx_dir / "ls_changelog_before.bin"
    sha256 = ""
    if existed:
        data = path.read_bytes()
        backup.write_bytes(data)
        sha256 = hashlib.sha256(data).hexdigest()
    elif backup.exists():
        backup.unlink()
    return {"existed_before": existed, "backup_path": str(backup), "sha256": sha256}


def restore_changelog_snapshot(base_dir: Path, snapshot: dict[str, Any]) -> None:
    base = Path(base_dir).resolve()
    path = base / CHANGELOG_NAME
    existed = bool((snapshot or {}).get("existed_before"))
    if not existed:
        if path.exists():
            if not path.is_file():
                raise ValueError("LS changelog rollback target is not a file")
            path.unlink()
        return
    backup = Path(str((snapshot or {}).get("backup_path") or "")).resolve()
    if not backup.is_file():
        raise ValueError("LS changelog rollback backup is missing")
    data = backup.read_bytes()
    expected = str((snapshot or {}).get("sha256") or "")
    if expected and hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("LS changelog rollback backup hash mismatch")
    temporary = path.with_name(path.name + ".rollback.tmp")
    shutil.copy2(backup, temporary)
    os.replace(temporary, path)
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("LS changelog rollback restore hash mismatch")
