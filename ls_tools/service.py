import base64
import difflib
import hashlib
import importlib.util
import socket
import threading
import html
import json
import os
import shutil
import mimetypes
import re
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import warnings
import webbrowser
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from ls_core.runtime import *

LS_UPDATE_PY_GLOB = "LocalSunoDb.py"

LS_UPDATE_MEMBER_PATTERN = re.compile(r"^LocalSunoDb\.py$", re.IGNORECASE)

LS_UPDATE_APP_VERSION_PATTERN = re.compile(
    r'''(?m)^APP_VERSION\s*=\s*["\']v(?P<major>\d+)\.(?P<minor>\d+)["\']\s*$'''
)

LS_UPDATE_MAX_FILE_BYTES = 60 * 1024 * 1024

def parse_ls_version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)", str(value or "").strip())
    if not match:
        raise ValueError(f"Invalid LS version: {value}")
    return int(match.group(1)), int(match.group(2))

def format_ls_version(version_tuple):
    return f"v{int(version_tuple[0])}.{int(version_tuple[1]):02d}"

def format_ls_minor_version(value):
    try:
        return f"v1.{int(value):02d}"
    except Exception:
        return "v1.00"

def ls_version_minor_from_any(value, default=0):
    try:
        if isinstance(value, str) and value.strip().lower().startswith("v"):
            parsed = parse_ls_version(value)
            if parsed[0] == 1:
                return int(parsed[1])
        return int(value)
    except Exception:
        return int(default or 0)

def get_current_ls_minor():
    return ls_version_minor_from_any(APP_VERSION, 0)

def normalize_ls_rejected_versions(value):
    result = {int(item) for item in LS_VERSION_REJECTED_DEFAULTS}
    for item in value if isinstance(value, (list, tuple, set)) else []:
        minor = ls_version_minor_from_any(item, 0)
        if minor > 0:
            result.add(minor)
    return sorted(result)

def normalize_ls_installed_packages(value):
    raw_items = value if isinstance(value, list) else []
    result = []
    seen = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        version = str(item.get("version") or "").strip()
        identity = str(item.get("source_sha256") or item.get("package_id") or "").strip().lower()
        if not version or not identity or identity in seen:
            continue
        try:
            parse_ls_version(version)
        except ValueError:
            continue
        seen.add(identity)
        result.append(dict(item))
    return result[-64:]

def read_ls_version_registry():
    current_minor = get_current_ls_minor()
    default = {
        "highest_issued": max(LS_VERSION_BASE_MINOR, current_minor),
        "current_running": current_minor,
        "latest_stable": LS_VERSION_BASE_MINOR,
        "rejected_versions": list(LS_VERSION_REJECTED_DEFAULTS),
        "rollback_reason": LS_VERSION_ROLLBACK_REASON,
        "installed_packages": [],
    }
    try:
        if LS_VERSION_REGISTRY_PATH.is_file():
            loaded = json.loads(LS_VERSION_REGISTRY_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                default.update(loaded)
    except Exception:
        pass
    default["highest_issued"] = max(ls_version_minor_from_any(default.get("highest_issued"), current_minor), current_minor)
    default["current_running"] = current_minor
    default["latest_stable"] = ls_version_minor_from_any(default.get("latest_stable"), LS_VERSION_BASE_MINOR)
    default["rejected_versions"] = normalize_ls_rejected_versions(default.get("rejected_versions"))
    default["installed_packages"] = normalize_ls_installed_packages(default.get("installed_packages"))
    return default

def write_ls_version_registry(registry):
    payload = dict(registry or {})
    payload["updated_at"] = now_iso_local()
    payload["updated_by"] = APP_VERSION
    LS_VERSION_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = LS_VERSION_REGISTRY_PATH.with_suffix(LS_VERSION_REGISTRY_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, LS_VERSION_REGISTRY_PATH)
    return payload

def refresh_ls_version_registry():
    registry = read_ls_version_registry()
    registry["current_running"] = get_current_ls_minor()
    registry["highest_issued"] = max(int(registry.get("highest_issued") or 0), get_current_ls_minor())
    return write_ls_version_registry(registry)

def _ls_windows_powershell_path():
    candidates = [
        Path(os.environ.get("SystemRoot", r"C:\\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        Path("powershell.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file() or candidate.name.casefold() == "powershell.exe":
            return str(candidate)
    return "powershell.exe"

def send_ls_path_to_windows_recycle_bin(path_obj):
    """Move one history item to its drive's Recycle Bin without a shell process."""
    path_obj = Path(path_obj).resolve()
    if not path_obj.exists():
        return True
    if os.name != "nt":
        raise RuntimeError("Windows atkritne ir pieejama tikai Windows vidē")

    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_ALLOWUNDO = 0x0040
    FOF_NOERRORUI = 0x0400
    source_list = str(path_obj) + "\0\0"
    operation = SHFILEOPSTRUCTW(
        None,
        FO_DELETE,
        source_list,
        None,
        FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI,
        False,
        None,
        None,
    )
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0 or operation.fAnyOperationsAborted or path_obj.exists():
        raise RuntimeError(
            f"Failu neizdevās pārvietot uz Windows atkritni: {path_obj} "
            f"(SHFileOperation={result}, aborted={bool(operation.fAnyOperationsAborted)})"
        )
    return True

def prune_ls_comparison_history():
    """Keep at most the newest configured number of valid LS Python versions."""
    history_dir = LS_COMPARISON_HISTORY_DIR.resolve()
    if not history_dir.is_dir():
        return {"kept": 0, "recycled": 0, "failed": []}
    valid = []
    for path_obj in history_dir.glob(LS_UPDATE_PY_GLOB):
        try:
            item = _ls_comparison_candidate_from_path(path_obj)
        except Exception:
            continue
        valid.append(item)
    valid.sort(key=lambda item: (item["version_tuple"], item["mtime_ns"]), reverse=True)
    kept = valid[:LS_COMPARISON_HISTORY_LIMIT]
    recycled = 0
    failed = []
    for item in valid[LS_COMPARISON_HISTORY_LIMIT:]:
        try:
            send_ls_path_to_windows_recycle_bin(item["path"])
            recycled += 1
        except Exception as exc:
            failed.append({"path": str(item["path"]), "error": str(exc)})
            log_ls_exception(
                "comparison_history",
                "recycle_old_version",
                exc,
                context={"path": str(item["path"])},
                include_traceback=False,
            )
    return {"kept": len(kept), "recycled": recycled, "failed": failed}

def resolve_previous_ls_app_path_for_restart():
    """Use the handoff path, or the newest older root version for v5.354 migration."""
    explicit_path = get_command_line_value(LS_PREVIOUS_APP_PATH_FLAG)
    if explicit_path:
        return explicit_path
    current_version = parse_ls_version(APP_VERSION)
    candidates = []
    for search_root in (APP_DIR, HOST_ROOT):
        for path_obj in search_root.glob(LS_UPDATE_PY_GLOB):
            try:
                item = _ls_comparison_candidate_from_path(path_obj)
            except Exception:
                continue
            if item["version_tuple"] < current_version:
                candidates.append(item)
    if not candidates:
        return ""
    candidates.sort(
        key=lambda item: (item["version_tuple"], item["mtime_ns"]),
        reverse=True,
    )
    return str(candidates[0]["path"])

def archive_previous_ls_version(previous_app_path):
    """Move the just-replaced LS file from E: to short-term D: history."""
    previous_text = str(previous_app_path or "").strip()
    if not previous_text:
        return {"moved": False, "reason": "missing_previous_path"}
    previous_path = Path(previous_text).resolve()
    current_path = Path(APP_ENTRYPOINT_PATH).resolve()
    if previous_path == current_path:
        return {"moved": False, "reason": "same_as_current"}
    if previous_path.parent not in {HOST_ROOT.resolve(), APP_DIR.resolve()}:
        raise ValueError("Iepriekšējais LS fails neatrodas LocalSunoDb programmas mapē")
    if not previous_path.exists():
        result = prune_ls_comparison_history()
        return {"moved": False, "reason": "already_missing", **result}

    previous_item = _ls_comparison_candidate_from_path(previous_path)
    if previous_item["version_tuple"] >= parse_ls_version(APP_VERSION):
        raise ValueError("Iepriekšējā LS versija nav vecāka par pašreizējo")

    history_dir = LS_COMPARISON_HISTORY_DIR.resolve()
    history_dir.mkdir(parents=True, exist_ok=True)
    target_path = history_dir / previous_path.name
    if target_path.exists():
        if target_path.read_bytes() != previous_path.read_bytes():
            raise ValueError(
                f"CompareHistory jau ir cits fails ar nosaukumu {target_path.name}"
            )
        previous_path.unlink()
    else:
        shutil.move(str(previous_path), str(target_path))

    result = prune_ls_comparison_history()
    return {
        "moved": True,
        "source": str(previous_path),
        "target": str(target_path),
        **result,
    }

def _ls_comparison_candidate_from_path(path_obj):
    """Validate one legacy previous LS Python file without applying update-only rules."""
    path_obj = Path(path_obj).resolve()
    if not path_obj.is_file() or path_obj.suffix.lower() != ".py":
        raise ValueError("Salīdzināšanas avots nav Python fails")
    filename_match = LS_UPDATE_MEMBER_PATTERN.fullmatch(path_obj.name)
    if not filename_match:
        raise ValueError("Salīdzināšanas avotam ir nederīgs LS faila nosaukums")
    if path_obj.stat().st_size <= 0 or path_obj.stat().st_size > LS_UPDATE_MAX_FILE_BYTES:
        raise ValueError("Salīdzināšanas avotam ir nederīgs faila izmērs")
    source_text = path_obj.read_text(encoding="utf-8-sig")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        compile(source_text, path_obj.name, "exec")
    app_match = LS_UPDATE_APP_VERSION_PATTERN.search(source_text)
    if not app_match:
        raise ValueError("Salīdzināšanas avotā netika atrasts APP_VERSION")
    app_version = (
        int(app_match.group("major")),
        int(app_match.group("minor")),
    )
    return {
        "version_tuple": app_version,
        "version": format_ls_version(app_version),
        "path": path_obj,
        "entrypoint_path": path_obj,
        "entrypoint": path_obj.name,
        "filename": path_obj.name,
        "mtime_ns": int(path_obj.stat().st_mtime_ns),
        "legacy": True,
    }


def _ls_comparison_candidate_from_snapshot_dir(version_dir):
    version_dir = Path(version_dir).resolve()
    metadata_path = version_dir / "comparison_snapshot.json"
    app_dir = version_dir / "app"
    if not metadata_path.is_file() or not app_dir.is_dir():
        raise ValueError("Salīdzināšanas pilnā versijas kopija nav pilnīga")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    if not isinstance(metadata, dict):
        raise ValueError("Salīdzināšanas pilnās kopijas metadata nav derīga")
    version = str(metadata.get("version") or version_dir.name).strip()
    version_tuple = parse_ls_version(version)
    entrypoint = str(metadata.get("entrypoint") or "LocalSunoDb.py").strip()
    entrypoint_path = (app_dir / entrypoint).resolve()
    item = _ls_comparison_candidate_from_path(entrypoint_path)
    if item["version_tuple"] != version_tuple:
        raise ValueError("Salīdzināšanas pilnās kopijas versija neatbilst entrypoint")
    item.update({
        "app_dir": app_dir,
        "snapshot_dir": version_dir,
        "entrypoint": entrypoint,
        "entrypoint_path": entrypoint_path,
        "legacy": False,
        "mtime_ns": max(int(metadata_path.stat().st_mtime_ns), int(entrypoint_path.stat().st_mtime_ns)),
    })
    return item



def _ls_comparison_candidate_from_snapshot_zip(zip_path):
    zip_path = Path(zip_path).resolve()
    if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
        raise ValueError("Salīdzināšanas pilnās versijas ZIP nav atrasts")
    version = zip_path.stem.strip()
    version_tuple = parse_ls_version(version)
    entrypoint = "LocalSunoDb.py"
    entrypoint_member = entrypoint
    runtime_member = "ls_core/runtime.py"
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if entrypoint_member not in names or runtime_member not in names:
            raise ValueError("Salīdzināšanas pilnās versijas ZIP nav pilnīgs")
        source_text = archive.read(entrypoint_member).decode("utf-8-sig")
    app_match = LS_UPDATE_APP_VERSION_PATTERN.search(source_text)
    if not app_match:
        raise ValueError("Salīdzināšanas ZIP entrypoint nav APP_VERSION")
    app_version = (int(app_match.group("major")), int(app_match.group("minor")))
    if app_version != version_tuple:
        raise ValueError("Salīdzināšanas ZIP nosaukums neatbilst APP_VERSION")
    return {
        "version_tuple": version_tuple,
        "version": format_ls_version(version_tuple),
        "archive_path": zip_path,
        "entrypoint": entrypoint,
        "filename": entrypoint,
        "mtime_ns": int(zip_path.stat().st_mtime_ns),
        "legacy": False,
        "bundled": True,
    }

def get_ls_comparison_versions():
    """Return only runnable full-app previous versions from comparison history."""
    current_version = parse_ls_version(APP_VERSION)
    history_dir = LS_COMPARISON_HISTORY_DIR.resolve()
    by_version = {}
    if history_dir.is_dir():
        for version_dir in history_dir.iterdir():
            if not version_dir.is_dir():
                continue
            try:
                item = _ls_comparison_candidate_from_snapshot_dir(version_dir)
            except Exception:
                continue
            if item["version_tuple"] >= current_version:
                continue
            key = item["version_tuple"]
            previous = by_version.get(key)
            if previous is None or item["mtime_ns"] > previous["mtime_ns"]:
                by_version[key] = item

    bundled_dir = Path(LS_COMPARISON_BUNDLED_SNAPSHOT_DIR).resolve()
    if bundled_dir.is_dir():
        for zip_path in bundled_dir.glob("v*.zip"):
            try:
                item = _ls_comparison_candidate_from_snapshot_zip(zip_path)
            except Exception:
                continue
            if item["version_tuple"] >= current_version:
                continue
            by_version.setdefault(item["version_tuple"], item)

    result = []
    for version_tuple in sorted(by_version, reverse=True):
        item = by_version[version_tuple]
        result.append({
            "version": item["version"],
            "filename": item["entrypoint"],
            "location": "Bundled snapshot" if item.get("bundled") else "D: CompareHistory",
            "label": f"{item['version']} — pilna app kopija",
        })
    return result[:LS_COMPARISON_HISTORY_LIMIT]


def resolve_ls_comparison_version(version):
    requested = parse_ls_version(version)
    current = parse_ls_version(APP_VERSION)
    if requested >= current:
        raise ValueError("Izvēlies versiju, kas ir vecāka par pašlaik palaisto LS")
    history_dir = LS_COMPARISON_HISTORY_DIR.resolve()
    version_dir = history_dir / format_ls_version(requested)
    try:
        item = _ls_comparison_candidate_from_snapshot_dir(version_dir)
    except Exception:
        bundled_path = Path(LS_COMPARISON_BUNDLED_SNAPSHOT_DIR).resolve() / f"{format_ls_version(requested)}.zip"
        try:
            item = _ls_comparison_candidate_from_snapshot_zip(bundled_path)
        except Exception as exc:
            raise ValueError(
                f"LS {format_ls_version(requested)} pilnā app kopija netika atrasta CompareHistory "
                "vai komplektā iekļautajos Compare snapshotos"
            ) from exc
    if item["version_tuple"] != requested:
        raise ValueError("Salīdzināšanas pilnās kopijas versija neatbilst pieprasījumam")
    return item


def _copy_ls_comparison_support_file(source_path, destination_path):
    source_path = Path(source_path)
    if source_path.is_file():
        destination_path = Path(destination_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        return True
    return False


def _patch_ls_comparison_runtime(run_app_dir, port):
    run_app_dir = Path(run_app_dir)
    runtime_path = run_app_dir / "ls_core" / "runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8-sig")
    patched, count = re.subn(
        r"(?m)^PORT\s*=\s*\d+\s*$",
        f"PORT = {int(port)}",
        runtime_text,
        count=1,
    )
    if count != 1:
        raise ValueError("Salīdzināšanas app runtime PORT neizdevās izolēt")
    runtime_path.write_text(patched, encoding="utf-8")

    app_path = run_app_dir / "ls_web" / "app.py"
    if app_path.is_file():
        app_text = app_path.read_text(encoding="utf-8-sig")
        app_text = app_text.replace(
            '"Local\\\\Maris.LocalSunoDb.Server",',
            f'"Local\\\\Maris.LocalSunoDb.Server.Compare.{int(port)}",',
        )
        app_path.write_text(app_text, encoding="utf-8")

    launcher_path = run_app_dir / "ls_tools" / "launcher.py"
    if launcher_path.is_file():
        launcher_text = launcher_path.read_text(encoding="utf-8-sig")
        launcher_text += (
            "\n\n# Isolated Compare runtime: never rewrite the installed LS/PWA shortcuts.\n"
            "def sync_existing_localsunodb_shortcuts_to_pwa_identity(*args, **kwargs):\n"
            "    return {'ok': True, 'action': 'comparison_skipped'}\n"
        )
        launcher_path.write_text(launcher_text, encoding="utf-8")


def _extract_ls_comparison_snapshot_zip(zip_path, run_app_dir):
    zip_path = Path(zip_path).resolve()
    run_app_dir = Path(run_app_dir).resolve()
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if not members:
            raise ValueError("Salīdzināšanas pilnās versijas ZIP ir tukšs")
        for member in members:
            posix = PurePosixPath(member.filename)
            if posix.is_absolute() or ".." in posix.parts or not posix.parts:
                raise ValueError("Salīdzināšanas ZIP satur nedrošu ceļu")
            target = run_app_dir.joinpath(*posix.parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)

def create_ls_comparison_snapshot(candidate, port):
    """Create a runnable full-app copy with current DB/settings isolated from live LS."""
    if candidate.get("legacy") or not (candidate.get("app_dir") or candidate.get("archive_path")):
        raise ValueError("Šai LS versijai nav saglabāta pilna app kopija")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_version = str(candidate["version"]).replace(".", "_")
    run_root = LS_COMPARISON_ROOT / f"{safe_version}_{stamp}_{os.getpid()}"
    run_app_dir = run_root / "app"
    run_root.mkdir(parents=True, exist_ok=False)
    if candidate.get("app_dir"):
        shutil.copytree(
            candidate["app_dir"],
            run_app_dir,
            dirs_exist_ok=False,
            ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.pyo"),
        )
    else:
        _extract_ls_comparison_snapshot_zip(candidate["archive_path"], run_app_dir)

    from ls_data.repository import copy_sqlite_snapshot

    copy_sqlite_snapshot(DB_PATH, run_app_dir / DB_PATH.name)
    run_data_dir = run_app_dir / "Data"
    run_data_dir.mkdir(parents=True, exist_ok=True)
    copy_sqlite_snapshot(LOCAL_INVENTORY_DB_PATH, run_data_dir / LOCAL_INVENTORY_DB_PATH.name)

    data_files = (
        LS_VERSION_REGISTRY_PATH,
        DOWNLOADER_STATE_PATH,
        SUNO_METADATA_JOB_PATH,
        LAST_VIEW_STATE_PATH,
        VARIANT_COUNTERS_PATH,
        LOCAL_FAMILY_MAP_PATH,
        TAGS_FILE_PATH,
        HELP_MARKDOWN_PATH,
        HELP_LEGACY_TEXT_PATH,
    )
    for source_path in data_files:
        source_path = Path(source_path)
        if source_path.is_file():
            try:
                relative = source_path.resolve().relative_to(HOST_ROOT.resolve())
            except Exception:
                relative = Path("Data") / source_path.name
            _copy_ls_comparison_support_file(source_path, run_app_dir / relative)

    if SETTINGS_PATH.is_file():
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
            if not isinstance(settings, dict):
                settings = {}
        except Exception:
            settings = {}
        settings["ls_update_check_interval_seconds"] = 0
        run_settings = run_app_dir / "Data" / SETTINGS_PATH.name
        run_settings.parent.mkdir(parents=True, exist_ok=True)
        run_settings.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")

    for profile_path in PROFILE_IMAGE_CANDIDATES:
        profile_path = Path(profile_path)
        if not profile_path.is_file():
            continue
        try:
            relative = profile_path.resolve().relative_to(HOST_ROOT.resolve())
        except Exception:
            relative = Path(profile_path.name)
        if _copy_ls_comparison_support_file(profile_path, run_app_dir / relative):
            break

    _patch_ls_comparison_runtime(run_app_dir, port)
    run_entrypoint = run_app_dir / candidate["entrypoint"]
    if not run_entrypoint.is_file():
        raise ValueError("Salīdzināšanas pilnās app kopijas entrypoint nav atrasts")
    (run_root / "COMPARISON_ISOLATED.txt").write_text(
        "This folder is an isolated LocalSunoDb comparison run.\n"
        "The current main and local-inventory databases were copied before launch.\n"
        "Upgrade checks are disabled in this copy.\n",
        encoding="utf-8",
    )
    return run_root, run_entrypoint


def find_free_ls_comparison_port():
    for port in range(8766, 8800):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError("Diapazonā 8766–8799 netika atrasts brīvs LS salīdzināšanas ports")


LS_COMPARISON_PUBLIC_ERROR = "Salīdzinājumu neizdevās palaist. Diagnostika saglabāta LS žurnālā."


def _cleanup_ls_comparison_state(remove_snapshot=False, *, phase="idle", public_error="", version=""):
    process = LS_COMPARISON_STATE.get("process")
    snapshot_dir = str(LS_COMPARISON_STATE.get("snapshot_dir") or "")
    launch_id = int(LS_COMPARISON_STATE.get("launch_id") or 0)
    LS_COMPARISON_STATE.update({
        "process": None,
        "chrome_process": None,
        "version": str(version or ""),
        "port": 0,
        "url": "",
        "source_path": "",
        "snapshot_dir": "",
        "phase": str(phase or "idle"),
        "public_error": str(public_error or ""),
        "launch_id": launch_id,
    })
    if remove_snapshot and snapshot_dir:
        try:
            shutil.rmtree(snapshot_dir, ignore_errors=True)
        except Exception:
            pass
    return process


def get_ls_comparison_status():
    with LS_COMPARISON_LOCK:
        phase = str(LS_COMPARISON_STATE.get("phase") or "idle")
        version = str(LS_COMPARISON_STATE.get("version") or "")
        if phase == "starting":
            return {"active": False, "starting": True, "version": version}
        if phase == "error":
            return {
                "active": False,
                "starting": False,
                "version": version,
                "error": str(LS_COMPARISON_STATE.get("public_error") or LS_COMPARISON_PUBLIC_ERROR),
            }

        process = LS_COMPARISON_STATE.get("process")
        if process is not None and process.poll() is not None:
            _cleanup_ls_comparison_state(
                remove_snapshot=True,
                phase="error",
                public_error=LS_COMPARISON_PUBLIC_ERROR,
                version=version,
            )
            return {
                "active": False,
                "starting": False,
                "version": version,
                "error": LS_COMPARISON_PUBLIC_ERROR,
            }
        if process is None:
            return {"active": False, "starting": False}
        return {
            "active": True,
            "starting": False,
            "version": version,
            "port": int(LS_COMPARISON_STATE.get("port") or 0),
            "url": str(LS_COMPARISON_STATE.get("url") or ""),
            "process_id": int(process.pid),
        }


def stop_ls_comparison():
    with LS_COMPARISON_LOCK:
        LS_COMPARISON_STATE["launch_id"] = int(LS_COMPARISON_STATE.get("launch_id") or 0) + 1
        process = LS_COMPARISON_STATE.get("process")
        chrome_process = LS_COMPARISON_STATE.get("chrome_process")
        snapshot_dir = str(LS_COMPARISON_STATE.get("snapshot_dir") or "")
        if process is not None and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=3)
                except Exception:
                    pass
        if chrome_process is not None and getattr(chrome_process, "poll", lambda: 0)() is None:
            try:
                chrome_process.terminate()
            except Exception:
                pass
        _cleanup_ls_comparison_state(remove_snapshot=False)
        if snapshot_dir:
            try:
                shutil.rmtree(snapshot_dir, ignore_errors=True)
            except Exception:
                pass
        return {"active": False, "starting": False}


def _wait_for_ls_comparison_http(port, expected_version, timeout_seconds=25.0):
    deadline = time.time() + float(timeout_seconds)
    last_error = ""
    while time.time() < deadline:
        request = urllib.request.Request(
            f"http://{HOST}:{int(port)}/app-version?comparison_probe={time.time_ns()}",
            headers={"Cache-Control": "no-cache"},
        )
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            running = str(payload.get("app_version") or payload.get("version") or "")
            if running == str(expected_version):
                return True
            last_error = f"reported {running or 'unknown'}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(
        f"Salīdzināšanas process neuzsāka {expected_version}: {last_error or 'timeout'}"
    )


def _launch_ls_comparison_worker(candidate, port, launch_id):
    run_root = None
    process = None
    try:
        run_root, run_entrypoint = create_ls_comparison_snapshot(candidate, port=port)
        with LS_COMPARISON_LOCK:
            if int(LS_COMPARISON_STATE.get("launch_id") or 0) != int(launch_id):
                shutil.rmtree(run_root, ignore_errors=True)
                return

        log_path = run_root / "comparison.log"
        command = [sys.executable, str(run_entrypoint), "--ls-restarted"]
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000 | 0x00000200
        log_handle = log_path.open("a", encoding="utf-8")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(run_entrypoint.parent),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        finally:
            log_handle.close()

        url = f"http://{HOST}:{port}/"
        with LS_COMPARISON_LOCK:
            if int(LS_COMPARISON_STATE.get("launch_id") or 0) != int(launch_id):
                try:
                    process.terminate()
                except Exception:
                    pass
                shutil.rmtree(run_root, ignore_errors=True)
                return
            LS_COMPARISON_STATE.update({
                "process": process,
                "chrome_process": None,
                "port": port,
                "url": url,
                "source_path": str(candidate.get("snapshot_dir") or candidate.get("archive_path") or ""),
                "snapshot_dir": str(run_root),
            })

        _wait_for_ls_comparison_http(port, candidate["version"])
        from ls_tools.launcher import open_localsunodb_chrome_app
        chrome_result = open_localsunodb_chrome_app(url=url, force_app_url=True)
        with LS_COMPARISON_LOCK:
            if int(LS_COMPARISON_STATE.get("launch_id") or 0) != int(launch_id):
                return
            LS_COMPARISON_STATE["chrome_process"] = chrome_result.get("process")
            LS_COMPARISON_STATE["phase"] = "active"
            LS_COMPARISON_STATE["public_error"] = ""
    except Exception as exc:
        try:
            log_ls_exception(
                "comparison",
                "launch_worker",
                exc,
                context={"version": str(candidate.get("version") or "")},
                include_traceback=True,
            )
        except Exception:
            pass
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        if run_root is not None:
            try:
                shutil.rmtree(run_root, ignore_errors=True)
            except Exception:
                pass
        with LS_COMPARISON_LOCK:
            if int(LS_COMPARISON_STATE.get("launch_id") or 0) == int(launch_id):
                LS_COMPARISON_STATE.update({
                    "process": None,
                    "chrome_process": None,
                    "port": 0,
                    "url": "",
                    "snapshot_dir": "",
                    "phase": "error",
                    "public_error": LS_COMPARISON_PUBLIC_ERROR,
                })


def launch_ls_comparison(version):
    """Queue one isolated previous LS app without blocking the current UI request."""
    stop_ls_comparison()
    candidate = resolve_ls_comparison_version(version)
    port = find_free_ls_comparison_port()
    with LS_COMPARISON_LOCK:
        launch_id = int(LS_COMPARISON_STATE.get("launch_id") or 0) + 1
        LS_COMPARISON_STATE.update({
            "process": None,
            "chrome_process": None,
            "version": candidate["version"],
            "port": port,
            "url": "",
            "source_path": str(candidate.get("snapshot_dir") or candidate.get("archive_path") or ""),
            "snapshot_dir": "",
            "phase": "starting",
            "public_error": "",
            "launch_id": launch_id,
        })
        threading.Thread(
            target=_launch_ls_comparison_worker,
            args=(candidate, port, launch_id),
            name=f"LSCompare-{candidate['version']}",
            daemon=True,
        ).start()
    return get_ls_comparison_status()

def get_ls_comparison_payload():
    return {
        "ok": True,
        "current_version": APP_VERSION,
        "versions": get_ls_comparison_versions(),
        "running": get_ls_comparison_status(),
    }


def download_suno_audio_for_edit(track_id, audio_url, title=""):
    """Download the Suno audio URL into edit_cache and return the local file path."""
    track_id = str(track_id or "").strip()
    audio_url = str(audio_url or "").strip()
    title = str(title or "").strip()

    if not audio_url:
        raise ValueError("Missing Suno audio URL")

    EDIT_CACHE_DIR.mkdir(exist_ok=True)

    parsed = urllib.parse.urlparse(audio_url)
    ext = Path(parsed.path).suffix.lower()

    if ext not in [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"]:
        ext = ".mp3"

    name = safe_filename_part(title or track_id or "suno_audio")
    id_part = safe_filename_part(track_id[:8]) if track_id else "noid"
    local_path = EDIT_CACHE_DIR / f"{name}_{id_part}{ext}"

    if local_path.exists() and local_path.stat().st_size > 0:
        return local_path

    request = urllib.request.Request(
        audio_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "audio/*,*/*;q=0.8",
        },
    )

    temp_path = local_path.with_suffix(local_path.suffix + ".tmp")

    with urllib.request.urlopen(request, timeout=120) as response:
        with open(temp_path, "wb") as f:
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)

    if not temp_path.exists() or temp_path.stat().st_size == 0:
        raise RuntimeError("Downloaded Suno audio file is empty")

    temp_path.replace(local_path)
    return local_path


