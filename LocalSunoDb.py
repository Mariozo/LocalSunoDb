# LocalSunoDb - Local Web Interface
# Canonical LocalSunoDb runtime entrypoint.
# Based on: v1.03
# Upgrade probe contract: --ls-update-probe / LS_UPDATE_PROBE_OK

APP_VERSION = "v1.16"
APP_BASED_ON = "v1.15"

from datetime import datetime
from pathlib import Path
import sys
import threading
import traceback

ROOT_DIR = Path(__file__).resolve().parent
ERROR_LOG_PATH = ROOT_DIR / "error.log"


def _write_error_log(kind, exc_type, exc_value, exc_tb):
    try:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        with ERROR_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {kind}\n{details}\n")
    except Exception:
        pass


def _main_exception_hook(exc_type, exc_value, exc_tb):
    _write_error_log("MAIN", exc_type, exc_value, exc_tb)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _thread_exception_hook(args):
    _write_error_log(
        "THREAD " + str(getattr(args.thread, "name", "")),
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
    )


sys.excepthook = _main_exception_hook
if hasattr(threading, "excepthook"):
    threading.excepthook = _thread_exception_hook



def _ensure_backend_supervisor_process():
    """Best-effort: every normal backend start leaves one persistent supervisor behind."""
    if "--ls-update-probe" in sys.argv or "--ls-comparison-runner" in sys.argv:
        return
    try:
        from ls_tools.launcher import (
            install_localsunodb_backend_run_entry,
            start_localsunodb_backend_supervisor,
        )
        install_localsunodb_backend_run_entry()
        start_localsunodb_backend_supervisor()
    except Exception:
        pass


_ensure_backend_supervisor_process()

try:
    from ls_web.app import entrypoint
except Exception:
    exc_type, exc_value, exc_tb = sys.exc_info()
    _write_error_log("IMPORT", exc_type, exc_value, exc_tb)
    raise


if __name__ == "__main__":
    try:
        entrypoint()
    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        _write_error_log("STARTUP", exc_type, exc_value, exc_tb)
        raise
