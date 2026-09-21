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

from ls_upgrade import UpgradeConfig, UpgradeCoordinator, UpgradeTransaction

PENDING_RESTART_PATH = None

LS_UPGRADE_COORDINATOR = None

def show_ls_upgrade_native_message(message, *, title="LocalSunoDb Upgrade", error=True):
    """Show bounded Upgrade feedback through the native Windows message path."""
    text = str(message or "").strip()[:2000]
    if not text:
        return False
    if os.name != "nt":
        return False
    try:
        import ctypes
        flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, text, str(title or "LocalSunoDb Upgrade")[:120], flags)
        return True
    except Exception:
        return False

def log_ls_upgrade_stage(stage, context=None):
    """Append one informational event to the dedicated Upgrade audit journal."""
    try:
        record = sanitize_ls_error_data({
            "timestamp": now_iso_local(),
            "area": "upgrade",
            "event": str(stage or ""),
            "context": context or {},
        })
        encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with LS_UPGRADE_AUDIT_LOG_LOCK:
            LS_UPGRADE_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            current_size = LS_UPGRADE_AUDIT_LOG_PATH.stat().st_size if LS_UPGRADE_AUDIT_LOG_PATH.exists() else 0
            if current_size + len(encoded) > LS_UPGRADE_LOG_MAX_BYTES and LS_UPGRADE_AUDIT_LOG_PATH.exists():
                try:
                    if LS_UPGRADE_AUDIT_LOG_PREVIOUS_PATH.exists():
                        LS_UPGRADE_AUDIT_LOG_PREVIOUS_PATH.unlink()
                    os.replace(LS_UPGRADE_AUDIT_LOG_PATH, LS_UPGRADE_AUDIT_LOG_PREVIOUS_PATH)
                except Exception:
                    pass
            with LS_UPGRADE_AUDIT_LOG_PATH.open("ab") as handle:
                handle.write(encoded)
                handle.flush()
    except Exception:
        return False
    return True

def ls_upgrade_log_error(operation, exc, context=None):
    log_ls_exception(
        "upgrade",
        str(operation or "upgrade"),
        exc,
        context=context or {},
        include_traceback=True,
    )

def ls_upgrade_check_interval_seconds():
    try:
        return float(get_settings().get("ls_update_check_interval_seconds", 10) or 0)
    except Exception:
        return 10.0

def begin_ls_server_shutdown(_target_path=None):
    """Stop the current LS process deterministically after flushing the request."""
    global PENDING_RESTART_PATH
    PENDING_RESTART_PATH = Path(_target_path or APP_ENTRYPOINT_PATH).resolve()
    RUNTIME_STATE["shutdown_reason"] = "upgrade"
    server = RUNTIME_STATE.get("active_http_server")

    def force_exit_watchdog():
        # Handoff waits for this exact PID. If normal shutdown gets stuck in an
        # unrelated cleanup path, do not leave Upgrade blocked forever.
        time.sleep(10.0)
        os._exit(0)

    threading.Thread(
        target=force_exit_watchdog,
        name="ls-upgrade-force-exit-watchdog",
        daemon=True,
    ).start()

    if server is None:
        return

    def shutdown_later():
        time.sleep(0.35)
        try:
            server.shutdown()
        except Exception:
            pass

    threading.Thread(target=shutdown_later, name="ls-upgrade-server-shutdown", daemon=True).start()

def initialize_ls_upgrade_coordinator():
    """Create the one authoritative in-process Upgrade coordinator."""
    global LS_UPGRADE_COORDINATOR
    if LS_UPGRADE_COORDINATOR is not None:
        return LS_UPGRADE_COORDINATOR
    config = UpgradeConfig(
        base_dir=BASE_DIR,
        downloads_dir=LS_UPDATE_DOWNLOADS_DIR,
        transaction_root=LS_UPDATE_TRANSACTION_ROOT,
        running_version=APP_VERSION,
        entrypoint=Path(APP_ENTRYPOINT_PATH).resolve(),
        host=HOST,
        port=PORT,
        version_registry_path=LS_VERSION_REGISTRY_PATH,
        audit_log_path=LS_UPGRADE_AUDIT_LOG_PATH,
        error_log_path=LS_UPGRADE_ERROR_LOG_PATH,
        interval_provider=ls_upgrade_check_interval_seconds,
        shutdown_callback=begin_ls_server_shutdown,
        log_event=lambda event, payload: log_ls_upgrade_stage(event, payload),
        log_error=ls_upgrade_log_error,
        comparison_history_dir=LS_COMPARISON_HISTORY_DIR,
        comparison_history_limit=LS_COMPARISON_HISTORY_LIMIT,
    )
    LS_UPGRADE_COORDINATOR = UpgradeCoordinator(config)
    return LS_UPGRADE_COORDINATOR

def get_ls_upgrade_coordinator():
    coordinator = LS_UPGRADE_COORDINATOR
    if coordinator is None:
        coordinator = initialize_ls_upgrade_coordinator()
    return coordinator


def signal_ls_upgrade_ready():
    """Publish READY for the external Upgrade bootstrapper after HTTP bind succeeds."""
    transaction_dir = get_command_line_value("--ls-update-transaction")
    if not transaction_dir:
        return {}
    transaction = UpgradeTransaction.load(Path(transaction_dir))
    metadata = transaction.read_metadata()
    if Path(metadata.get("base_dir") or "").resolve() != BASE_DIR.resolve():
        raise ValueError("Upgrade transaction belongs to a different LocalSunoDb directory")
    ready = transaction.mark_ready(
        app_version=APP_VERSION,
        process_id=os.getpid(),
        server_url=f"http://{HOST}:{int(PORT)}",
    )
    log_ls_upgrade_stage(
        "app_ready_signal",
        {
            "transaction_id": ready.get("transaction_id"),
            "version": APP_VERSION,
            "process_id": os.getpid(),
        },
    )
    return ready


def get_pending_restart_path():
    return PENDING_RESTART_PATH
