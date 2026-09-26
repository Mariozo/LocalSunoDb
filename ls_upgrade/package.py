"""Manifest-based LocalSunoDb Upgrade package validation.

This module has no dependency on the main LocalSunoDb application module.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

MANIFEST_NAME = "ls_update_manifest.json"
MANIFEST_SCHEMA = 1
MAX_FILE_BYTES = 60 * 1024 * 1024
MAX_PACKAGE_BYTES = 60 * 1024 * 1024
MAX_FILE_COUNT = 1024
MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MAX_PATH_CHARS = 240
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul", "clock$",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}
PROTECTED_ROOT_NAMES = {
    ".ls_update_transaction",
    "backup",
    "data",
    "edit_cache",
    "exports",
    "logs",
    "reports",
    "ls_suno_token_bridge",
    "tools",
    "__pycache__",
    "suno_finder_v4.db",
    "suno_finder_v4.db-shm",
    "suno_finder_v4.db-wal",
    "suno_local_inventory.db",
    MANIFEST_NAME,
}
REQUIRED_MANIFEST_FIELDS = {
    "schema_version",
    "version",
    "based_on",
    "entrypoint",
    "package_id",
    "created_at",
    "files",
}
SOURCE_PATTERN = re.compile(r"^LocalSunoDb_v(?P<major>\d+)\.(?P<minor>\d+)\.zip$", re.I)
MEMBER_PATTERN = re.compile(r"^LocalSunoDb\.py$", re.I)
APP_VERSION_PATTERN = re.compile(
    r'''(?m)^APP_VERSION\s*=\s*["']v(?P<major>\d+)\.(?P<minor>\d+)["']\s*$'''
)
BASED_ON_PATTERN = re.compile(r"(?m)^# Based on:\s*(?P<version>v\d+\.\d+)\s*$")
PROBE_MARKER = "LS_UPDATE_PROBE_OK"


class NoUpdateCandidate(ValueError):
    """Downloads contains no newer installable Upgrade package."""


@dataclass(frozen=True)
class PackageFile:
    path: str
    action: str
    size: int
    sha256: str


@dataclass(frozen=True)
class UpgradePackage:
    source_path: Path
    source_name: str
    source_sha256: str
    source_size_bytes: int
    source_mtime_ns: int
    manifest: dict[str, Any]
    manifest_sha256: str
    version: str
    based_on: str
    entrypoint: str
    working_directory: str
    package_id: str
    created_at: str
    files: tuple[PackageFile, ...]
    signature: str

    def to_payload(self) -> dict[str, Any]:
        upgrade_points = manifest_upgrade_points(self.manifest)
        return {
            "ok": True,
            "available": True,
            "source_kind": "zip",
            "source_name": self.source_name,
            "zip_name": self.source_name,
            "source_sha256": self.source_sha256,
            "source_size_bytes": self.source_size_bytes,
            "source_mtime_ns": self.source_mtime_ns,
            "manifest_sha256": self.manifest_sha256,
            "version": self.version,
            "new_version": self.version,
            "based_on": self.based_on,
            "recovery_from": list(manifest_recovery_versions(self.manifest)),
            "entrypoint": self.entrypoint,
            "working_directory": self.working_directory,
            "package_id": self.package_id,
            "created_at": self.created_at,
            "file_count": len(self.files),
            "upgrade_points": upgrade_points,
            "files": [
                {
                    "path": item.path,
                    "action": item.action,
                    "size": item.size,
                    "sha256": item.sha256,
                }
                for item in self.files
            ],
            "signature": self.signature,
        }


def parse_version(value: Any) -> tuple[int, int]:
    """Return the stable release line for a release or visible test iteration.

    User-visible test builds may add a third numeric identity component
    (for example v2.27.1). Upgrade compatibility is intentionally decided
    by the stable major/minor release line, so v2.27.1 belongs to v2.27.
    """
    match = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.\d+)?", str(value or "").strip())
    if not match:
        raise ValueError(f"Invalid LS version: {value}")
    return int(match.group(1)), int(match.group(2))


def format_version(value: tuple[int, int]) -> str:
    return f"v{int(value[0])}.{int(value[1]):02d}"


def is_direct_successor(version: Any, running_version: Any) -> bool:
    candidate = parse_version(version)
    running = parse_version(running_version)
    return candidate[0] == running[0] and candidate[1] == running[1] + 1


def manifest_recovery_versions(manifest: dict[str, Any]) -> tuple[str, ...]:
    raw = manifest.get("recovery_from")
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("Upgrade manifest recovery_from must be a list")
    versions: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Upgrade manifest recovery_from must contain version strings")
        normalized = format_version(parse_version(item))
        if normalized in versions:
            raise ValueError("Upgrade manifest recovery_from contains a duplicate version")
        versions.append(normalized)
    return tuple(versions)


def manifest_upgrade_points(manifest: dict[str, Any]) -> list[str]:
    """Return a compact, safe list of user-facing Upgrade highlights."""
    raw: Any = manifest.get("upgrade_points")
    if raw in (None, "", []):
        raw = manifest.get("highlights")
    if raw in (None, "", []):
        raw = manifest.get("release_notes")

    if isinstance(raw, str):
        values = raw.replace("\r", "").split("\n")
    elif isinstance(raw, list):
        values = raw
    else:
        values = []

    points: list[str] = []
    for value in values:
        if not isinstance(value, (str, int, float)):
            continue
        text = str(value).strip()
        text = re.sub(r"^[\s•*\-–—]+", "", text).strip()
        if not text:
            continue
        if len(text) > 240:
            text = text[:237].rstrip() + "…"
        points.append(text)
        if len(points) >= 8:
            break
    return points


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member_name(value: Any) -> str:
    name = str(value or "").strip()
    if (
        not name
        or len(name) > MAX_PATH_CHARS
        or "\x00" in name
        or "\\" in name
        or ":" in name
    ):
        raise ValueError("The Upgrade ZIP contains an unsafe file path")
    path_obj = PurePosixPath(name)
    parts = path_obj.parts
    normalized = path_obj.as_posix()
    if (
        path_obj.is_absolute()
        or not parts
        or normalized != name
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("The Upgrade ZIP contains an unsafe file path")
    for part in parts:
        if part.endswith((" ", ".")):
            raise ValueError("The Upgrade ZIP path is not portable on Windows")
        stem = part.split(".", 1)[0].casefold()
        if stem in WINDOWS_RESERVED_NAMES:
            raise ValueError("The Upgrade ZIP uses a reserved Windows file name")
    return normalized


def windows_path_key(name: str) -> str:
    return "/".join(
        unicodedata.normalize("NFC", part).rstrip(" .").casefold()
        for part in PurePosixPath(name).parts
    )


def path_under(root: Path, relative_name: str) -> Path:
    root = Path(root).resolve()
    safe_name = safe_member_name(relative_name)
    candidate = (root / Path(*PurePosixPath(safe_name).parts)).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError(f"The Upgrade target is outside the LS folder: {safe_name}")
    return candidate


def member_allowed(name: str, entrypoint: str = "") -> bool:
    name = safe_member_name(name)
    root_name = PurePosixPath(name).parts[0].casefold()
    if root_name in PROTECTED_ROOT_NAMES:
        return False
    if name.casefold().endswith((".db", ".db-shm", ".db-wal")):
        return False
    return name != MANIFEST_NAME


def decode_text(data: bytes, label: str) -> str:
    try:
        return bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} is not UTF-8 text") from exc


def validate_entrypoint_source(source_text: str, source_name: str) -> dict[str, Any]:
    filename_match = MEMBER_PATTERN.fullmatch(Path(source_name).name)
    if not filename_match:
        raise ValueError("The Upgrade entrypoint must be named LocalSunoDb.py")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        compile(source_text, source_name, "exec")
    app_match = APP_VERSION_PATTERN.search(source_text)
    based_on_match = BASED_ON_PATTERN.search(source_text)
    if not app_match:
        raise ValueError("The Upgrade entrypoint has no APP_VERSION")
    if not based_on_match:
        raise ValueError("The Upgrade entrypoint has no Based on header")
    if PROBE_MARKER not in source_text or "--ls-update-probe" not in source_text:
        raise ValueError("The Upgrade entrypoint has no startup probe contract")
    version_tuple = (int(app_match.group("major")), int(app_match.group("minor")))
    return {
        "version_tuple": version_tuple,
        "version": format_version(version_tuple),
        "based_on": str(based_on_match.group("version") or "").strip(),
    }


def _read_manifest(archive: zipfile.ZipFile, members: dict[str, zipfile.ZipInfo]) -> tuple[dict[str, Any], str]:
    manifest_member = members.get(MANIFEST_NAME)
    if manifest_member is None:
        raise ValueError("Every LocalSunoDb Upgrade ZIP must contain ls_update_manifest.json")
    manifest_bytes = archive.read(manifest_member)
    manifest_sha = sha256_bytes(manifest_bytes)
    try:
        manifest = json.loads(decode_text(manifest_bytes, MANIFEST_NAME))
    except json.JSONDecodeError as exc:
        raise ValueError("The Upgrade manifest is not valid JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("The Upgrade manifest must be a JSON object")
    missing = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest))
    if missing:
        raise ValueError("The Upgrade manifest is missing: " + ", ".join(missing))
    if int(manifest.get("schema_version") or 0) != MANIFEST_SCHEMA:
        raise ValueError("Unsupported LS Upgrade manifest schema")
    return manifest, manifest_sha


def validate_zip(
    zip_path: Path,
    *,
    running_version: str,
    require_newer: bool = True,
    require_direct_successor: bool = False,
    allowed_recovery_bases: Iterable[str] = (),
) -> UpgradePackage:
    zip_path = Path(zip_path).resolve()
    if not zip_path.is_file() or zip_path.suffix.casefold() != ".zip":
        raise ValueError(f"Upgrade ZIP was not found: {zip_path}")
    source_match = SOURCE_PATTERN.fullmatch(zip_path.name)
    if not source_match:
        raise ValueError("The Upgrade ZIP name must be LocalSunoDb_vN.NN.zip")
    stat = zip_path.stat()
    if stat.st_size <= 0 or stat.st_size > MAX_PACKAGE_BYTES:
        raise ValueError("The Upgrade ZIP has an invalid size")

    source_sha = sha256_file(zip_path)
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            raw_members = [item for item in archive.infolist() if not item.is_dir()]
            if not raw_members:
                raise ValueError("The Upgrade ZIP is empty")
            if len(raw_members) > MAX_FILE_COUNT + 1:
                raise ValueError("The Upgrade ZIP contains too many files")
            total_uncompressed = sum(max(0, int(item.file_size)) for item in raw_members)
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("The Upgrade ZIP expands beyond the allowed total size")

            members: dict[str, zipfile.ZipInfo] = {}
            windows_keys: set[str] = set()
            for member in raw_members:
                name = safe_member_name(member.filename)
                key = windows_path_key(name)
                if name in members or key in windows_keys:
                    raise ValueError(f"The Upgrade ZIP repeats or collides on Windows: {name}")
                if member.file_size < 0 or member.file_size > MAX_FILE_BYTES:
                    raise ValueError(f"The Upgrade file has an invalid size: {name}")
                members[name] = member
                windows_keys.add(key)

            manifest, manifest_sha = _read_manifest(archive, members)
            version = str(manifest.get("version") or "").strip()
            based_on = str(manifest.get("based_on") or "").strip()
            package_id = str(manifest.get("package_id") or "").strip()
            created_at = str(manifest.get("created_at") or "").strip()
            entrypoint = safe_member_name(manifest.get("entrypoint"))
            working_value = str(manifest.get("working_directory") or ".").strip()
            working_directory = "" if working_value in {"", "."} else safe_member_name(working_value)
            if not package_id:
                raise ValueError("The Upgrade manifest has no package_id")
            if not created_at:
                raise ValueError("The Upgrade manifest has no created_at")

            version_tuple = parse_version(version)
            based_on_tuple = parse_version(based_on)
            running_tuple = parse_version(running_version)
            recovery_from = manifest_recovery_versions(manifest)
            recovery_from_tuples = {parse_version(item) for item in recovery_from}
            allowed_recovery_tuples = {parse_version(item) for item in allowed_recovery_bases}
            filename_tuple = (int(source_match.group("major")), int(source_match.group("minor")))
            if version_tuple != filename_tuple:
                raise ValueError("The ZIP filename version does not match the manifest")
            if require_newer and version_tuple <= running_tuple:
                raise NoUpdateCandidate("Downloads contains no newer LS Upgrade package")
            if based_on_tuple != running_tuple:
                recovery_allowed = (
                    is_direct_successor(version, running_version)
                    and running_tuple in recovery_from_tuples
                    and based_on_tuple in allowed_recovery_tuples
                )
                if not recovery_allowed:
                    raise ValueError(
                        f"The Upgrade is based on {based_on}, but {running_version} is running"
                    )
            # Failed/unused version numbers may be skipped. Safety is enforced
            # by newer-version, based_on, manifest, hashes and transaction checks.

            raw_files = manifest.get("files")
            if not isinstance(raw_files, list) or not raw_files:
                raise ValueError("The Upgrade manifest has no files list")
            if len(raw_files) > MAX_FILE_COUNT:
                raise ValueError("The Upgrade manifest declares too many files")

            declared_names: set[str] = set()
            declared_keys: set[str] = set()
            package_files: list[PackageFile] = []
            expected_members = {MANIFEST_NAME}
            entrypoint_bytes: bytes | None = None
            for item in raw_files:
                if not isinstance(item, dict):
                    raise ValueError("Each Upgrade manifest file must be an object")
                name = safe_member_name(item.get("path"))
                key = windows_path_key(name)
                if name in declared_names or key in declared_keys:
                    raise ValueError(f"The Upgrade manifest repeats or collides: {name}")
                declared_names.add(name)
                declared_keys.add(key)
                if not member_allowed(name, entrypoint):
                    raise ValueError(f"The Upgrade file is not allowed: {name}")

                action = str(item.get("action") or "replace").strip().casefold()
                if action not in {"new", "replace", "delete"}:
                    raise ValueError(f"Unsupported Upgrade action for {name}: {action}")
                expected_sha = str(item.get("sha256") or "").strip().casefold()
                expected_size = int(item.get("size") if item.get("size") is not None else -1)

                if action == "delete":
                    if name in members:
                        raise ValueError(f"A delete action must not include file bytes: {name}")
                    if expected_size not in {-1, 0}:
                        raise ValueError(f"A delete action must have size 0: {name}")
                    if expected_sha not in {"", "0" * 64}:
                        raise ValueError(f"A delete action must not declare a content hash: {name}")
                    package_files.append(PackageFile(name, action, 0, ""))
                    continue

                member = members.get(name)
                if member is None:
                    raise ValueError(f"The Upgrade ZIP is missing: {name}")
                data = archive.read(member)
                actual_sha = sha256_bytes(data)
                if expected_size != len(data):
                    raise ValueError(f"The Upgrade size does not match the manifest: {name}")
                if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or actual_sha != expected_sha:
                    raise ValueError(f"The Upgrade SHA-256 does not match the manifest: {name}")
                if name.casefold().endswith(".py"):
                    source_text = decode_text(data, name)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", SyntaxWarning)
                        compile(source_text, name, "exec")
                if name == entrypoint:
                    entrypoint_bytes = data
                expected_members.add(name)
                package_files.append(PackageFile(name, action, len(data), actual_sha))

            actual_names = set(members)
            if actual_names != expected_members:
                extras = sorted(actual_names - expected_members)
                missing = sorted(expected_members - actual_names)
                details = []
                if extras:
                    details.append("extra: " + ", ".join(extras))
                if missing:
                    details.append("missing: " + ", ".join(missing))
                raise ValueError("The Upgrade ZIP contents do not match the manifest (" + "; ".join(details) + ")")
            if entrypoint_bytes is None:
                raise ValueError("The Upgrade entrypoint is not installed by the package")

            source_info = validate_entrypoint_source(decode_text(entrypoint_bytes, entrypoint), entrypoint)
            if source_info["version"] != version:
                raise ValueError("The manifest version does not match APP_VERSION")
            if source_info["based_on"] != based_on:
                raise ValueError("The manifest based_on does not match the entrypoint header")

    except zipfile.BadZipFile as exc:
        raise ValueError("The downloaded Upgrade is not a valid ZIP file") from exc

    signature = "|".join((version, zip_path.name, source_sha, manifest_sha))
    return UpgradePackage(
        source_path=zip_path,
        source_name=zip_path.name,
        source_sha256=source_sha,
        source_size_bytes=stat.st_size,
        source_mtime_ns=stat.st_mtime_ns,
        manifest=manifest,
        manifest_sha256=manifest_sha,
        version=version,
        based_on=based_on,
        entrypoint=entrypoint,
        working_directory=working_directory,
        package_id=package_id,
        created_at=created_at,
        files=tuple(package_files),
        signature=signature,
    )


def iter_download_candidates(downloads_dir: Path) -> Iterable[Path]:
    directory = Path(downloads_dir)
    if not directory.is_dir():
        return ()
    return tuple(
        sorted(
            (path for path in directory.glob("LocalSunoDb_v*.zip") if path.is_file()),
            key=lambda item: (item.stat().st_mtime_ns, item.name.casefold()),
            reverse=True,
        )
    )
