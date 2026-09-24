# LocalSunoDb - Local Web Interface
# Canonical LocalSunoDb runtime entrypoint.
# Based on: v2.16
# Upgrade probe contract: --ls-update-probe / LS_UPDATE_PROBE_OK

APP_VERSION = "v2.17"
APP_BASED_ON = "v2.16"

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



def _disable_legacy_backend_autostart():
    """Retire the PWA-era persistent backend before normal SF-style startup."""
    if "--ls-update-probe" in sys.argv or "--ls-comparison-runner" in sys.argv:
        return
    try:
        from ls_tools.launcher import uninstall_localsunodb_backend_autostart
        uninstall_localsunodb_backend_autostart(stop_supervisors=True)
    except Exception:
        pass


_disable_legacy_backend_autostart()

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
