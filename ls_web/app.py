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

_LS_SERVER_MUTEX_HANDLE = None

def cleanup_waveform_memory_cache():
    WAVEFORM_MEMORY_CACHE.clear()
    return 0

def wait_for_previous_ls_process():
    pid_text = get_command_line_value("--ls-wait-for-pid")
    if not pid_text:
        return

    try:
        previous_pid = int(pid_text)
    except (TypeError, ValueError):
        return

    if previous_pid <= 0 or previous_pid == os.getpid():
        return

    if os.name == "nt":
        import ctypes

        process_synchronize = 0x00100000
        infinite = 0xFFFFFFFF
        handle = ctypes.windll.kernel32.OpenProcess(
            process_synchronize,
            False,
            previous_pid,
        )
        if not handle:
            return
        try:
            ctypes.windll.kernel32.WaitForSingleObject(handle, infinite)
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
        return

    while True:
        try:
            os.kill(previous_pid, 0)
        except OSError:
            return
        time.sleep(0.1)

def acquire_ls_server_single_instance():
    """Allow only one interactive LocalSunoDb server process on Windows."""
    global _LS_SERVER_MUTEX_HANDLE

    if os.name != "nt":
        return True
    if _LS_SERVER_MUTEX_HANDLE:
        return True

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    ctypes.set_last_error(0)
    handle = create_mutex(None, False, "Local\\Mariozo.LocalSunoDb.Server")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())

    ERROR_ALREADY_EXISTS = 183
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        close_handle(handle)
        return False

    _LS_SERVER_MUTEX_HANDLE = handle
    return True

def _write_ls_runtime_state():
    """Persist the one live LS backend identity for diagnostics and recovery."""
    if LS_UPDATE_PROBE_MODE:
        return
    payload = {
        "version": APP_VERSION,
        "pid": os.getpid(),
        "entrypoint": str(Path(APP_ENTRYPOINT_PATH).resolve()),
        "host": HOST,
        "port": int(PORT),
        "launch_mode": "restarted" if "--ls-restarted" in sys.argv else "manual",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    LS_RUNTIME_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = LS_RUNTIME_STATE_PATH.with_suffix(LS_RUNTIME_STATE_PATH.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, LS_RUNTIME_STATE_PATH)


def _clear_ls_runtime_state():
    """Remove only this process' runtime identity; never erase another live LS."""
    try:
        if not LS_RUNTIME_STATE_PATH.is_file():
            return
        raw = json.loads(LS_RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
        if int(raw.get("pid") or 0) != os.getpid():
            return
        LS_RUNTIME_STATE_PATH.unlink()
    except Exception:
        pass


def _launch_restarted_ls(entrypoint):
    """Launch a restarted LS without creating a second visible console window."""
    from ls_upgrade.bootstrapper import background_python_executable, hidden_process_kwargs

    return subprocess.Popen(
        [background_python_executable(), str(Path(entrypoint).resolve()), "--ls-restarted"],
        cwd=str(Path(entrypoint).resolve().parent),
        **hidden_process_kwargs(),
    )


def _schedule_post_upgrade_root_hygiene():
    """Finalize the flat-root migration only after bootstrapper completion.

    During READY/verification the old layout is deliberately preserved so a
    rollback remains bootable.  Once the transaction is completed and its
    staging/backup/candidate payload has been cleaned, the remaining legacy
    root copies can be removed or quarantined safely.
    """
    transaction_text = get_command_line_value("--ls-update-transaction")
    if not transaction_text:
        return
    transaction_dir = Path(transaction_text).resolve()

    def worker():
        deadline = time.monotonic() + 120.0
        while time.monotonic() < deadline:
            try:
                metadata_path = transaction_dir / "transaction.json"
                payload = json.loads(metadata_path.read_text(encoding="utf-8"))
                state = str(payload.get("state") or "").casefold()
                if state in {"failed", "rolled_back"}:
                    return
                payload_dirs_exist = any(
                    (transaction_dir / name).exists()
                    for name in ("staging", "backup", "candidate")
                )
                if state == "completed" and not payload_dirs_exist:
                    time.sleep(0.8)
                    report = organize_ls_root(
                        host_root=HOST_ROOT,
                        app_dir=APP_DIR,
                        data_dir=DATA_DIR,
                        logs_dir=LOGS_DIR,
                        reports_dir=REPORTS_DIR,
                        backup_dir=BACKUP_DIR,
                        temp_dir=TEMP_DIR,
                        tools_dir=TOOLS_DIR,
                        probe_mode=False,
                    )
                    if report.get("warnings"):
                        print("LocalSunoDb root hygiene warning: " + "; ".join(report.get("warnings") or []))
                    return
            except Exception:
                pass
            time.sleep(0.5)

    threading.Thread(
        target=worker,
        name="ls-post-upgrade-root-hygiene",
        daemon=True,
    ).start()


def keep_restarted_ls_console_out_of_foreground():
    """Keep automatic Upgrade restarts controllable without covering Chrome."""
    if os.name != "nt" or "--ls-restarted" not in sys.argv:
        return
    try:
        import ctypes
        console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if console_hwnd:
            # SW_SHOWMINNOACTIVE: keep the Ctrl+C console available on the
            # taskbar, but do not leave it as the active foreground window.
            ctypes.windll.user32.ShowWindow(console_hwnd, 7)
    except Exception:
        pass



def _load_runtime_modules():
    import importlib
    module_names = [
        "ls_core.runtime",
        "ls_core.service",
        "ls_core.probe",
        "ls_data.database_context",
        "ls_data.repository",
        "ls_suno.service",
        "ls_audio.service",
        "ls_audio.controller",
        "ls_media.service",
        "ls_media.controller",
        "ls_library.service",
        "ls_library.playlists",
        "ls_library.render",
        "ls_library.controller",
        "ls_player.render",
        "ls_stems.service",
        "ls_stems.render",
        "ls_stems.controller",
        "ls_downloader.service",
        "ls_downloader.render",
        "ls_downloader.controller",
        "ls_tools.service",
        "ls_tools.render",
        "ls_tools.controller",
        "ls_web.render",
        "ls_web.settings_controller",
        "ls_web.upgrade_controller",
        "ls_web.elza_controller",
        "ls_web.support_controller",
        "ls_web.response_controller",
        "ls_web.workflow_controller",
        "ls_web.pages",
        "ls_web.elza_adapter",
        "ls_web.upgrade_adapter",
        "ls_web.handler",
    ]
    modules = [importlib.import_module(name) for name in module_names]
    modules.append(sys.modules[__name__])
    return modules


def _load_external_adapters(probe_mode=False):
    if probe_mode:
        return {
            "render_ls_elza_assets": lambda *_args, **_kwargs: "",
            "render_ls_elza_button": lambda *_args, **_kwargs: "",
            "configure_ls_elza_app_source": lambda *_args, **_kwargs: None,
            "ls_elza_error_payload": None,
            "handle_ls_elza_action": None,
            "ls_elza_append_chat_exchange": None,
            "LS_ELZA_SERVICE_IMPORT_ERROR": "",
        }

    external = {}
    try:
        from LS_Elza.ui import render_ls_elza_assets, render_ls_elza_button
        external.update({
            "render_ls_elza_assets": render_ls_elza_assets,
            "render_ls_elza_button": render_ls_elza_button,
        })
    except Exception as exc:
        external.update({
            "render_ls_elza_assets": lambda *_args, **_kwargs: "",
            "render_ls_elza_button": lambda *_args, **_kwargs: "",
            "LS_ELZA_SERVICE_IMPORT_ERROR": str(exc),
        })

    try:
        from LS_Elza.service import configure_ls_elza_app_source
        from LS_Elza.service import error_payload as ls_elza_error_payload
        from LS_Elza.service import handle_ls_elza_action
        try:
            from LS_Elza.service import append_chat_exchange as ls_elza_append_chat_exchange
        except Exception:
            ls_elza_append_chat_exchange = None
        configure_ls_elza_app_source(Path(APP_ENTRYPOINT_PATH).resolve())
        external.update({
            "configure_ls_elza_app_source": configure_ls_elza_app_source,
            "ls_elza_error_payload": ls_elza_error_payload,
            "handle_ls_elza_action": handle_ls_elza_action,
            "ls_elza_append_chat_exchange": ls_elza_append_chat_exchange,
            "LS_ELZA_SERVICE_IMPORT_ERROR": "",
        })
    except Exception as exc:
        external.update({
            "configure_ls_elza_app_source": lambda *_args, **_kwargs: None,
            "ls_elza_error_payload": None,
            "handle_ls_elza_action": None,
            "ls_elza_append_chat_exchange": None,
            "LS_ELZA_SERVICE_IMPORT_ERROR": str(exc),
        })
    return external


def compose_runtime(probe_mode=False):
    """Import feature modules, then wire their declared public runtime symbols."""
    from ls_core.wiring import wire_runtime
    modules = _load_runtime_modules()
    external = _load_external_adapters(probe_mode=probe_mode)
    registry = wire_runtime(modules, external)
    return modules, registry


def main():
    keep_restarted_ls_console_out_of_foreground()
    wait_for_previous_ls_process()
    previous_app_path = ""
    if "--ls-restarted" in sys.argv:
        previous_app_path = get_command_line_value(LS_PREVIOUS_APP_PATH_FLAG)
    if not acquire_ls_server_single_instance():
        print("LocalSunoDb is already running; this second instance was not started.")
        return

    initialize_runtime_environment()
    ensure_ls_upgrade_log_files()

    upgrade_coordinator = initialize_ls_upgrade_coordinator()
    recovery_results = upgrade_coordinator.recover()
    restart_previous = next(
        (
            item.get("restart_path")
            for item in recovery_results
            if item.get("action") == "restart_previous" and item.get("restart_path")
        ),
        "",
    )
    if restart_previous:
        _launch_restarted_ls(restart_previous)
        return

    try:
        refresh_ls_version_registry()
    except Exception as exc:
        print(f"LS version registry warning: {exc}")

    try:
        ensure_local_suno_runtime_database()
    except Exception as exc:
        print(f"Could not prepare Local Suno database: {exc}")
        return

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    try:
        cleanup_waveform_memory_cache()
        EDIT_CACHE_DIR.mkdir(exist_ok=True)
        base_url = f"http://{HOST}:{PORT}"
        last_view_url = get_last_view_url()
        url = base_url + last_view_url
        server = LocalSunoDbHTTPServer((HOST, PORT), LocalSunoDbHandler)
        _write_ls_runtime_state()
        signal_ls_upgrade_ready()
        _schedule_post_upgrade_root_hygiene()
    except Exception as exc:
        _clear_ls_runtime_state()
        print(f"Could not start LocalSunoDb {APP_VERSION}: {exc}")
        return

    server.daemon_threads = True
    RUNTIME_STATE["active_http_server"] = server
    upgrade_coordinator.start_watcher()

    if previous_app_path:
        try:
            archive_previous_ls_version(previous_app_path)
        except Exception as exc:
            log_ls_exception(
                "comparison_history",
                "archive_previous_version",
                exc,
                context={
                    "previous_path": previous_app_path,
                    "history_dir": str(LS_COMPARISON_HISTORY_DIR),
                },
                include_traceback=True,
            )

    print(f"LocalSunoDb {APP_VERSION} is running.")
    print(f"Running file: {Path(APP_ENTRYPOINT_PATH).resolve()}")
    print(f"Process ID: {os.getpid()}")
    print("Press Ctrl+C to stop.")
    if "--ls-restarted" not in sys.argv and "--ls-update-transaction" not in sys.argv:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print("LocalSunoDb stopped.")
    finally:
        try:
            server.server_close()
        finally:
            RUNTIME_STATE["active_http_server"] = None
            try:
                close_upgrade_dialog = RUNTIME_STATE.get("shutdown_reason") != "upgrade"
                upgrade_coordinator.stop_watcher(close_dialog=close_upgrade_dialog)
            except Exception:
                pass
            try:
                stop_ls_comparison()
            except Exception:
                pass
            _clear_ls_runtime_state()

    if RUNTIME_STATE.get("shutdown_reason") == "user" and "--ls-restarted" not in sys.argv:
        print("LocalSunoDb stopped from the UI.")

    pending = get_pending_restart_path()
    if pending is not None:
        print("LocalSunoDb restart bootstrapper completed: " + Path(pending).name)


def entrypoint():
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    probe_mode = "--ls-update-probe" in sys.argv
    _modules, runtime_registry = compose_runtime(probe_mode=probe_mode)

    if probe_mode:
        probe_payload = runtime_registry["run_startup_probe"]()
        print(json.dumps(probe_payload, ensure_ascii=True))
        return 0 if probe_payload.get("ok") else 1
    main()
    return 0
