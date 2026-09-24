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

from ls_core.root_hygiene import organize_ls_root, resolve_host_root


LS_UPDATE_PROBE_MARKER = "LS_UPDATE_PROBE_OK"
LS_UPDATE_PROBE_MODE = "--ls-update-probe" in sys.argv
APP_VERSION = "v2.18"
APP_BASED_ON = "v2.17"
APP_DIR = Path(__file__).resolve().parent.parent
HOST_ROOT = APP_DIR
# Compatibility alias: BASE_DIR means the user-facing LocalSunoDb host root.
BASE_DIR = HOST_ROOT
APP_ENTRYPOINT_PATH = APP_DIR / "LocalSunoDb.py"
DATA_DIR = HOST_ROOT / "Data"
LOGS_DIR = HOST_ROOT / "Logs"
REPORTS_DIR = HOST_ROOT / "Reports"
BACKUP_DIR = HOST_ROOT / "Backup"
TEMP_DIR = HOST_ROOT / "Temp"
TOOLS_DIR = HOST_ROOT / "Tools"
EXPORTS_DIR = HOST_ROOT / "exports"
LS_RUNTIME_STATE_PATH = DATA_DIR / "ls_runtime_state.json"

# External adapters are wired explicitly by ls_web.app; imports stay side-effect free.
def render_ls_elza_assets(*_args, **_kwargs): return ""
def render_ls_elza_button(*_args, **_kwargs): return ""
def configure_ls_elza_app_source(*_args, **_kwargs): return None
ls_elza_error_payload = None
handle_ls_elza_action = None
ls_elza_append_chat_exchange = None
LS_ELZA_SERVICE_IMPORT_ERROR = ""

def initialize_runtime_environment():
    """Create runtime folders and migrate legacy files only during explicit startup."""
    if LS_UPDATE_PROBE_MODE:
        return
    for folder in (APP_DIR, DATA_DIR, LOGS_DIR, REPORTS_DIR, BACKUP_DIR, TEMP_DIR, TOOLS_DIR, EXPORTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    organize_ls_root(
        host_root=HOST_ROOT,
        app_dir=APP_DIR,
        data_dir=DATA_DIR,
        logs_dir=LOGS_DIR,
        reports_dir=REPORTS_DIR,
        backup_dir=BACKUP_DIR,
        temp_dir=TEMP_DIR,
        tools_dir=TOOLS_DIR,
        probe_mode=LS_UPDATE_PROBE_MODE,
    )
    for name in (
        "localsunodb_settings.json", "ls_version_registry.json", "suno_downloader_state.json",
        "suno_metadata_backfill_job.json", "suno_last_view.json", "suno_variant_counters.json",
        "suno_local_family_map.json", "localsunodb_tags.txt", "suno_profile.png", "suno_profile.jpg",
        "suno_profile.jpeg", "suno_profile.webp", "profile.png", "profile.jpg", "profile.jpeg",
        "profile.webp", "avatar.png", "avatar.jpg", "avatar.jpeg", "avatar.webp",
    ):
        _ls_migrate_legacy_runtime_file(name, DATA_DIR)
    for name in (
        "ls_error_log.jsonl", "ls_error_log.previous.jsonl", "ls_upgrade_audit.jsonl",
        "ls_upgrade_audit.previous.jsonl", "ls_upgrade_error_log.jsonl",
        "ls_upgrade_error_log.previous.jsonl",
    ):
        _ls_migrate_legacy_runtime_file(name, LOGS_DIR)

LS_UPDATE_PROBE_MARKER = "LS_UPDATE_PROBE_OK"

LEGACY_DB_PATH = HOST_ROOT / "suno_finder_v4.db"
DB_PATH = DATA_DIR / "local_suno.db"

LOCAL_INVENTORY_DB_PATH = DATA_DIR / "suno_local_inventory.db"

WAVEFORM_MEMORY_CACHE = {}

EDIT_CACHE_DIR = TEMP_DIR / "edit_cache"

REFRESH_SCRIPT = TOOLS_DIR / "refresh_db.py"

REFRESH_SUMMARY_PATH = REPORTS_DIR / "refresh_summary.txt"

SETTINGS_PATH = DATA_DIR / "localsunodb_settings.json"

LS_VERSION_REGISTRY_PATH = DATA_DIR / "ls_version_registry.json"

DOWNLOADER_STATE_PATH = DATA_DIR / "suno_downloader_state.json"

SUNO_METADATA_JOB_PATH = DATA_DIR / "suno_metadata_backfill_job.json"

LAST_VIEW_STATE_PATH = DATA_DIR / "suno_last_view.json"

VARIANT_COUNTERS_PATH = DATA_DIR / "suno_variant_counters.json"

LOCAL_FAMILY_MAP_PATH = DATA_DIR / "suno_local_family_map.json"

TOKEN_BRIDGE_DIR = APP_DIR / "LS_Suno_TokenBridge"

LS_UPDATE_DOWNLOADS_DIR = Path.home() / "Downloads"

LS_UPDATE_TRANSACTION_ROOT = DATA_DIR / "UpgradeTransactions"

LS_VERSION_BASE_MINOR = 4

LS_VERSION_REJECTED_DEFAULTS = []

LS_VERSION_ROLLBACK_REASON = ""

LS_COMPARISON_HISTORY_DIR = Path(r"D:\LocalSunoDb\CompareHistory")

LS_COMPARISON_BUNDLED_SNAPSHOT_DIR = APP_DIR / "ls_compare_snapshots"

LS_COMPARISON_HISTORY_LIMIT = 15

HELP_MARKDOWN_PATH = DATA_DIR / "Help_LocalSunoDb.md"

HELP_LEGACY_TEXT_PATH = DATA_DIR / "Help_LocalSunoDb.txt"

TAGS_FILE_PATH = DATA_DIR / "localsunodb_tags.txt"

LS_ERROR_LOG_PATH = LOGS_DIR / "ls_error_log.jsonl"

LS_ERROR_LOG_PREVIOUS_PATH = LOGS_DIR / "ls_error_log.previous.jsonl"

LS_ERROR_LOG_MAX_BYTES = 5 * 1024 * 1024

LS_UPGRADE_AUDIT_LOG_PATH = LOGS_DIR / "ls_upgrade_audit.jsonl"

LS_UPGRADE_AUDIT_LOG_PREVIOUS_PATH = LOGS_DIR / "ls_upgrade_audit.previous.jsonl"

LS_UPGRADE_ERROR_LOG_PATH = LOGS_DIR / "ls_upgrade_error_log.jsonl"

LS_UPGRADE_ERROR_LOG_PREVIOUS_PATH = LOGS_DIR / "ls_upgrade_error_log.previous.jsonl"

LS_UPGRADE_LOG_MAX_BYTES = 5 * 1024 * 1024

PROFILE_IMAGE_CANDIDATES = [
    DATA_DIR / "suno_profile.png",
    DATA_DIR / "suno_profile.jpg",
    DATA_DIR / "suno_profile.jpeg",
    DATA_DIR / "suno_profile.webp",
    DATA_DIR / "profile.png",
    DATA_DIR / "profile.jpg",
    DATA_DIR / "profile.jpeg",
    DATA_DIR / "profile.webp",
    DATA_DIR / "avatar.png",
    DATA_DIR / "avatar.jpg",
    DATA_DIR / "avatar.jpeg",
    DATA_DIR / "avatar.webp",
    BASE_DIR / "suno_profile.png",
    BASE_DIR / "suno_profile.jpg",
    BASE_DIR / "suno_profile.jpeg",
    BASE_DIR / "suno_profile.webp",
    BASE_DIR / "profile.png",
    BASE_DIR / "profile.jpg",
    BASE_DIR / "profile.jpeg",
    BASE_DIR / "profile.webp",
    BASE_DIR / "avatar.png",
    BASE_DIR / "avatar.jpg",
    BASE_DIR / "avatar.jpeg",
    BASE_DIR / "avatar.webp",
]

SUNO_CREDITS_API_URL = "https://studio-api-prod.suno.com/api/billing/info/"

SUNO_CREDITS_CACHE_SECONDS = 300

AUDIO_EDITOR_CANDIDATES = [
    Path(r"C:\Program Files\Audacity\Audacity.exe"),
    Path(r"C:\Program Files (x86)\Audacity\Audacity.exe"),
]

FFMPEG_CANDIDATES = [
    Path(r"E:\Audio Soft\ffmpe\ffmpeg-2026-05-11-git-17bc88e67f-essentials_build\bin\ffmpeg.exe"),
    Path(r"C:\VBProjekti\Music\!!Ffmpeg\bin\ffmpeg.exe"),
    Path("ffmpeg"),
]

HOST = "127.0.0.1"

PORT = 8765

LS_ERROR_LOG_LOCK = threading.Lock()

LS_UPGRADE_AUDIT_LOG_LOCK = threading.Lock()

LS_PREVIOUS_APP_PATH_FLAG = "--ls-previous-app-path"

SUNO_METADATA_JOB_LOCK = threading.RLock()

LS_STRUCTURED_REPAIR_LOCK = threading.Lock()

LS_INTENT_AUDIT_LOCK = threading.Lock()

LS_CATEGORY_ASSIGNMENT_LOCK = threading.Lock()

SUNO_CREDITS_LOCK = threading.Lock()

LS_AUDIO_OUTPUT_LOCK = threading.RLock()

LS_AUDIO_OUTPUT_HELPER_PATH = (
    Path(tempfile.gettempdir()) / "LocalSunoDb_audio_output_v4.ps1"
)

LS_AUDIO_OUTPUT_CACHE = {
    "updated_at": 0.0,
    "payload": None,
}

LS_COMPARISON_LOCK = threading.RLock()

LS_COMPARISON_RUNNER_FLAG = "--ls-comparison-runner"

LS_COMPARISON_PORT_FLAG = "--ls-comparison-port"

LS_COMPARISON_PARENT_PID_FLAG = "--ls-comparison-parent-pid"

LS_COMPARISON_ROOT = Path(tempfile.gettempdir()) / "LocalSunoDbCompare"

LS_COMPARISON_STATE = {
    "process": None,
    "chrome_process": None,
    "version": "",
    "port": 0,
    "url": "",
    "source_path": "",
    "snapshot_dir": "",
    "phase": "idle",
    "public_error": "",
    "launch_id": 0,
}

TOKEN_BRIDGE_LOCK = threading.Lock()

TOKEN_BRIDGE_STATE = {
    "last_seen": "",
    "last_token_at": "",
    "last_error": "",
    "extension_version": "",
    "last_capture_source": "",
    "last_token_page_instance_id": "",
    "diagnostic_last_seen": "",
    "page_loaded": False,
    "fetch_hook_active": False,
    "fetch_repair_count": 0,
    "last_fetch_repair_at": "",
    "last_api_request_at": "",
    "last_authorization_at": "",
    "last_token_emit_at": "",
    "last_diagnostic_event": "",
    "page_instance_id": "",
    "relay_last_seen": "",
    "previous_worker_error": "",
    "last_recovered_at": "",
}

MONTHS = {
    1: "jan",
    2: "feb",
    3: "mar",
    4: "apr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "aug",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dec",
}

LS_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:authorization|cookie|set-cookie|openai[_-]?api[_-]?key|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|auth[_-]?token|suno[_-]?token|"
    r"password|passwd|secret|credential)",
    re.I,
)

LS_SENSITIVE_TEXT_PATTERNS = [
    re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s,;]+(?:\s+[^\s,;]+)?)"),
    re.compile(r"(?i)(cookie\s*[:=]\s*)([^\r\n]+)"),
    re.compile(r"(?i)(set-cookie\s*[:=]\s*)([^\r\n]+)"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(OPENAI_API_KEY\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|suno[_-]?token|password|secret)\s*[:=]\s*)[^\s,;]+"),
]

SECTION_VIEW_DEFAULTS = {
    "suno": "/",
    "downloader": "/downloader",
}


RUNTIME_STATE = {
    "active_http_server": None,
    "shutdown_reason": "",
}
