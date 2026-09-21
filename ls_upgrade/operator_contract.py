"""Direct-entrypoint Upgrade receipt for the clean flat LS repository.

The runnable application entrypoint lives directly in the repository root.
Upgrade may publish ``LS_VERSION.json`` as a receipt, but it never creates a
CMD launcher, wrapper script, or managed application subdirectory.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

ROOT_RECEIPT_NAME = "LS_VERSION.json"
ROOT_ENTRYPOINT_RE = re.compile(r"LocalSunoDb\.py\Z", re.IGNORECASE)
SNAPSHOT_DIR_NAME = "_operator_contract"
SNAPSHOT_METADATA_NAME = "snapshot.json"


def _validated_entrypoint_name(value: str) -> str:
    name = str(value or "").strip()
    if Path(name).name != name or not ROOT_ENTRYPOINT_RE.fullmatch(name):
        raise ValueError(f"Invalid LocalSunoDb entrypoint name: {value!r}")
    return name


def _atomic_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".ls-operator-{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temporary, path)


def _atomic_text(path: Path, text: str) -> None:
    _atomic_bytes(Path(path), str(text).replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def capture_operator_launch_contract(host_root: Path, transaction_dir: Path, target_root_entrypoint_name: str) -> dict[str, Any]:
    root = Path(host_root).resolve()
    transaction = Path(transaction_dir).resolve()
    target_name = _validated_entrypoint_name(target_root_entrypoint_name)
    target_entrypoint = root / target_name
    if not target_entrypoint.is_file():
        raise FileNotFoundError(f"Verified LocalSunoDb entrypoint is missing: {target_entrypoint}")

    backup_root = transaction / "backup" / SNAPSHOT_DIR_NAME
    metadata_path = backup_root / SNAPSHOT_METADATA_NAME
    if metadata_path.is_file():
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("target_root_entrypoint") == target_name:
            return payload
        raise ValueError("Operator receipt snapshot already exists for a different target")

    backup_root.mkdir(parents=True, exist_ok=True)
    receipt_path = root / ROOT_RECEIPT_NAME
    existed = receipt_path.is_file()
    backup_name = "receipt-before.json" if existed else ""
    if existed:
        shutil.copy2(receipt_path, backup_root / backup_name)
    snapshot = {
        "schema_version": 2,
        "target_root_entrypoint": target_name,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "receipt_existed_before": existed,
        "receipt_backup_name": backup_name,
    }
    _atomic_text(metadata_path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    return snapshot


def publish_operator_launch_contract(
    host_root: Path,
    *,
    internal_entrypoint_name: str,
    version: str,
    based_on: str,
    package_id: str,
    package_sha256: str,
    source_name: str,
) -> dict[str, Any]:
    root = Path(host_root).resolve()
    entrypoint_name = _validated_entrypoint_name(internal_entrypoint_name)
    entrypoint = root / entrypoint_name
    if not entrypoint.is_file():
        raise FileNotFoundError(f"Verified LocalSunoDb entrypoint is missing: {entrypoint}")
    receipt_path = root / ROOT_RECEIPT_NAME
    receipt = {
        "version": str(version),
        "based_on": str(based_on),
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "package_sha256": str(package_sha256 or ""),
        "package_id": str(package_id or ""),
        "source": str(source_name or ""),
        "entrypoint": entrypoint_name,
        "launch": "python-entrypoint",
    }
    _atomic_text(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return {
        "version": str(version),
        "entrypoint": str(entrypoint),
        "receipt": str(receipt_path),
        "launcher": "",
    }


def restore_operator_launch_contract(host_root: Path, transaction_dir: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    root = Path(host_root).resolve()
    transaction = Path(transaction_dir).resolve()
    payload = dict(snapshot or {})
    target_name = _validated_entrypoint_name(str(payload.get("target_root_entrypoint") or ""))
    receipt_path = root / ROOT_RECEIPT_NAME
    if bool(payload.get("receipt_existed_before")):
        backup_name = str(payload.get("receipt_backup_name") or "")
        backup = transaction / "backup" / SNAPSHOT_DIR_NAME / backup_name
        if not backup.is_file():
            raise FileNotFoundError(f"Operator receipt backup is missing: {backup}")
        _atomic_bytes(receipt_path, backup.read_bytes())
    elif receipt_path.exists():
        if not receipt_path.is_file():
            raise ValueError(f"Operator receipt target is not a file: {receipt_path}")
        receipt_path.unlink()
    return {"restored": True, "target_root_entrypoint": target_name}
