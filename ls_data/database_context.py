"""Database target registry and active-database connection context.

This module prepares LocalSunoDb for multiple interchangeable library databases
without changing the current product UI.  The canonical LocalSunoDb database
remains the built-in primary target.  Additional databases can be registered and
activated later by the UI once their schema contract is ready.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ls_core.runtime import DATA_DIR, DB_PATH


DATABASE_REGISTRY_PATH = DATA_DIR / "ls_database_registry.json"
DATABASE_REGISTRY_SCHEMA_VERSION = 1
PRIMARY_DATABASE_ID = "main"
PRIMARY_DATABASE_LABEL = "LocalSunoDb"

_REGISTRY_LOCK = threading.RLock()


def _primary_target():
    return {
        "id": PRIMARY_DATABASE_ID,
        "label": PRIMARY_DATABASE_LABEL,
        "path": str(DB_PATH),
        "kind": "suno",
        "built_in": True,
    }


def _clean_database_id(value):
    text = str(value or "").strip().lower()
    cleaned = []
    for char in text:
        if char.isalnum() or char in {"-", "_"}:
            cleaned.append(char)
    result = "".join(cleaned).strip("-_")
    if not result:
        raise ValueError("Database ID cannot be empty.")
    return result[:64]


def _clean_label(value, fallback):
    text = " ".join(str(value or "").split()).strip()
    return (text or str(fallback or "").strip())[:120]


def _normalise_path(value):
    text = str(value or "").strip().strip('"')
    if not text:
        raise ValueError("Database path cannot be empty.")
    return Path(text).expanduser()


def _default_payload():
    return {
        "schema_version": DATABASE_REGISTRY_SCHEMA_VERSION,
        "active_database_id": PRIMARY_DATABASE_ID,
        "databases": [],
    }


def _load_payload():
    payload = _default_payload()
    try:
        raw = json.loads(DATABASE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return payload

    if not isinstance(raw, dict):
        return payload

    active = str(raw.get("active_database_id") or PRIMARY_DATABASE_ID).strip().lower()
    try:
        payload["active_database_id"] = _clean_database_id(active)
    except ValueError:
        payload["active_database_id"] = PRIMARY_DATABASE_ID

    rows = raw.get("databases")
    if not isinstance(rows, list):
        return payload

    cleaned = []
    seen = {PRIMARY_DATABASE_ID}
    for item in rows:
        if not isinstance(item, dict):
            continue
        try:
            database_id = _clean_database_id(item.get("id"))
            if database_id in seen:
                continue
            path = _normalise_path(item.get("path"))
        except (TypeError, ValueError):
            continue
        seen.add(database_id)
        cleaned.append({
            "id": database_id,
            "label": _clean_label(item.get("label"), database_id),
            "path": str(path),
            "kind": _clean_label(item.get("kind"), "library").lower() or "library",
            "built_in": False,
        })
    payload["databases"] = cleaned
    return payload


def _save_payload(payload):
    DATABASE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        "schema_version": DATABASE_REGISTRY_SCHEMA_VERSION,
        "active_database_id": str(
            payload.get("active_database_id") or PRIMARY_DATABASE_ID
        ),
        "databases": [
            {
                "id": str(item["id"]),
                "label": str(item.get("label") or item["id"]),
                "path": str(item["path"]),
                "kind": str(item.get("kind") or "library"),
            }
            for item in payload.get("databases") or []
            if str(item.get("id") or "") != PRIMARY_DATABASE_ID
        ],
    }
    temp_path = DATABASE_REGISTRY_PATH.with_suffix(
        DATABASE_REGISTRY_PATH.suffix + ".tmp"
    )
    temp_path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(DATABASE_REGISTRY_PATH)


def list_database_targets():
    """Return the built-in primary DB plus all registered external DB targets."""
    with _REGISTRY_LOCK:
        payload = _load_payload()
        return [_primary_target(), *payload["databases"]]


def get_database_target(database_id):
    database_id = _clean_database_id(database_id)
    for item in list_database_targets():
        if item["id"] == database_id:
            return dict(item)
    raise KeyError(f"Unknown database ID: {database_id}")


def register_database_target(database_id, path, label="", kind="library"):
    """Register or update a non-primary DB path without opening or modifying it."""
    database_id = _clean_database_id(database_id)
    if database_id == PRIMARY_DATABASE_ID:
        raise ValueError("The built-in primary database cannot be replaced.")

    path_obj = _normalise_path(path)
    target = {
        "id": database_id,
        "label": _clean_label(label, database_id),
        "path": str(path_obj),
        "kind": _clean_label(kind, "library").lower() or "library",
        "built_in": False,
    }

    with _REGISTRY_LOCK:
        payload = _load_payload()
        rows = [
            item
            for item in payload["databases"]
            if item["id"] != database_id
        ]
        rows.append(target)
        rows.sort(key=lambda item: (item["label"].casefold(), item["id"]))
        payload["databases"] = rows
        _save_payload(payload)
    return dict(target)


def unregister_database_target(database_id):
    """Remove only the registry entry; never delete the database file itself."""
    database_id = _clean_database_id(database_id)
    if database_id == PRIMARY_DATABASE_ID:
        raise ValueError("The built-in primary database cannot be unregistered.")

    with _REGISTRY_LOCK:
        payload = _load_payload()
        before = len(payload["databases"])
        payload["databases"] = [
            item
            for item in payload["databases"]
            if item["id"] != database_id
        ]
        if len(payload["databases"]) == before:
            return False
        if payload["active_database_id"] == database_id:
            payload["active_database_id"] = PRIMARY_DATABASE_ID
        _save_payload(payload)
    return True


def get_configured_active_database_id():
    with _REGISTRY_LOCK:
        return str(_load_payload()["active_database_id"] or PRIMARY_DATABASE_ID)


def get_active_database_target():
    """Return the effective active target.

    If a previously selected external DB is unavailable, fall back to the
    canonical primary DB so LocalSunoDb still starts and user data is not
    modified.  The stored selection is preserved for later diagnostics/UI.
    """
    configured_id = get_configured_active_database_id()
    try:
        target = get_database_target(configured_id)
    except KeyError:
        target = _primary_target()

    if target["id"] != PRIMARY_DATABASE_ID:
        try:
            if not Path(target["path"]).is_file():
                return _primary_target()
        except OSError:
            return _primary_target()
    return target


def get_active_database_id():
    return str(get_active_database_target()["id"])


def get_active_database_path():
    return Path(get_active_database_target()["path"])


def resolve_database_path(database_id=None):
    if database_id is None or str(database_id or "").strip() == "":
        return get_active_database_path()
    return Path(get_database_target(database_id)["path"])


def set_active_database(database_id):
    """Select a registered DB.

    Non-primary targets must already exist.  Selecting a DB never creates,
    migrates, rewrites, or deletes it.
    """
    database_id = _clean_database_id(database_id)
    target = get_database_target(database_id)
    if database_id != PRIMARY_DATABASE_ID:
        path = Path(target["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Database file not found: {path}")

    with _REGISTRY_LOCK:
        payload = _load_payload()
        payload["active_database_id"] = database_id
        _save_payload(payload)
    return dict(target)


def get_database_registry_state():
    configured_id = get_configured_active_database_id()
    effective = get_active_database_target()
    return {
        "schema_version": DATABASE_REGISTRY_SCHEMA_VERSION,
        "configured_active_database_id": configured_id,
        "active_database_id": effective["id"],
        "active_database_path": effective["path"],
        "fell_back_to_primary": configured_id != effective["id"],
        "databases": list_database_targets(),
    }
