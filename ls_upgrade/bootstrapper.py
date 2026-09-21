"""Out-of-process transactional Upgrade bootstrapper.

The bootstrapper is the authoritative installer process. It survives the old
LocalSunoDb process, commits the staged transaction, launches the new App with
a transaction handshake, verifies readiness, and rolls back on failure.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import signal
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .changelog import (
    append_verified_upgrade_changelog,
    capture_changelog_snapshot,
    restore_changelog_snapshot,
)
from .operator_contract import (
    capture_operator_launch_contract,
    publish_operator_launch_contract,
    restore_operator_launch_contract,
)
from .package import MANIFEST_NAME, PROBE_MARKER
from .transaction import UpgradeTransaction


def encode_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_payload(value: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(str(value).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid LS Upgrade bootstrapper payload") from exc
    if not isinstance(payload, dict):
        raise ValueError("Invalid LS Upgrade bootstrapper payload")
    return payload


def console_python_executable() -> str:
    executable = Path(sys.executable).resolve()
    if os.name == "nt" and executable.name.casefold() == "pythonw.exe":
        candidate = executable.with_name("python.exe")
        if candidate.is_file():
            return str(candidate)
    return str(executable)


def background_python_executable() -> str:
    executable = Path(sys.executable).resolve()
    if os.name == "nt" and executable.name.casefold() == "python.exe":
        candidate = executable.with_name("pythonw.exe")
        if candidate.is_file():
            return str(candidate)
    return str(executable)


def hidden_process_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {"start_new_session": True}
    creationflags = 0
    creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    return {
        "creationflags": creationflags,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }


def main_app_process_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {"start_new_session": True}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    # SW_SHOWMINNOACTIVE keeps the console available for manual Ctrl+C, but
    # prevents automatic Upgrade restarts from taking focus from the browser.
    startupinfo.wShowWindow = 7
    return {
        "creationflags": getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        "startupinfo": startupinfo,
    }


def append_jsonl(path: str | Path | None, event: str, payload: dict[str, Any]) -> None:
    if not path:
        return
    log_path = Path(path)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "area": "upgrade",
            "event": event,
            "payload": payload,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return int(code.value) == 259
        os.kill(pid, 0)
        proc_stat = Path(f"/proc/{pid}/stat")
        if proc_stat.exists():
            try:
                fields = proc_stat.read_text(encoding="utf-8", errors="replace").split()
                if len(fields) > 2 and fields[2] == "Z":
                    return False
            except Exception:
                pass
        return True
    except Exception:
        return False


def wait_for_process_exit(pid: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + max(1.0, float(timeout))
    while process_is_alive(pid):
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Old LocalSunoDb process {pid} did not stop")
        time.sleep(0.1)


def force_terminate_process(pid: int) -> None:
    """Terminate only the known old LS PID after graceful shutdown timed out."""
    if pid <= 0 or not process_is_alive(pid):
        return
    if os.name == "nt":
        import ctypes

        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if not handle:
            raise RuntimeError(f"Could not open old LocalSunoDb process {pid} for termination")
        try:
            if not ctypes.windll.kernel32.TerminateProcess(handle, 0):
                raise RuntimeError(f"Could not terminate old LocalSunoDb process {pid}")
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        os.kill(pid, signal.SIGTERM)


def ensure_old_process_stopped(pid: int, graceful_timeout: float = 8.0, forced_timeout: float = 5.0) -> bool:
    """Return True only when a forced termination was required."""
    try:
        wait_for_process_exit(pid, timeout=graceful_timeout)
        return False
    except TimeoutError:
        force_terminate_process(pid)
        wait_for_process_exit(pid, timeout=forced_timeout)
        return True


def terminate_child(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=4)
        return
    except Exception:
        pass
    try:
        process.kill()
    except Exception:
        pass


def _latviskot_starta_parbaudes_detalas(details: str) -> str:
    text = str(details or "").strip()
    replacements = (
        ("architecture guard: Static asset size drift:", "arhitektūras pārbaude: statiskā faila izmērs neatbilst:"),
        ("architecture guard: Static asset hash drift:", "arhitektūras pārbaude: statiskā faila kontrolsumma neatbilst:"),
        ("architecture guard: Frozen feature DOM bridge changed without architecture migration:", "arhitektūras pārbaude: mainīts fiksētais DOM savienojums bez arhitektūras bāzes atjaunošanas:"),
        ("architecture guard: Frozen unscoped feature CSS changed without scope migration:", "arhitektūras pārbaude: mainīts fiksētais CSS bez tvēruma migrācijas:"),
        ("architecture guard:", "arhitektūras pārbaude:"),
        ("Static asset size drift:", "statiskā faila izmērs neatbilst:"),
        ("Static asset hash drift:", "statiskā faila kontrolsumma neatbilst:"),
        ("Frozen feature DOM bridge changed without architecture migration:", "mainīts fiksētais DOM savienojums bez arhitektūras bāzes atjaunošanas:"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return text


def run_source_probe(entrypoint: Path, expected_version: str, timeout: float = 30.0) -> dict[str, Any]:
    completed = subprocess.run(
        [console_python_executable(), str(entrypoint), "--ls-update-probe"],
        cwd=str(entrypoint.parent),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    payload: dict[str, Any] = {}
    for line in reversed(lines):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if completed.returncode != 0:
        details = (completed.stderr or "").strip()
        if payload.get("failures"):
            details = "; ".join(str(item) for item in payload.get("failures") or [])
        elif not details and completed.stdout:
            details = completed.stdout.strip()[-2000:]
        details = _latviskot_starta_parbaudes_detalas(details)
        raise RuntimeError(f"LocalSunoDb starta pārbaude neizdevās (kods {completed.returncode}): {details}")
    if not payload.get("ok") or payload.get("marker") != PROBE_MARKER:
        raise RuntimeError("LocalSunoDb starta pārbaude neatgrieza gaidīto apstiprinājuma marķieri")
    if str(payload.get("app_version") or "") != expected_version:
        raise RuntimeError("LocalSunoDb starta pārbaude atgrieza negaidītu LS versiju")
    return payload


def get_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("LocalSunoDb returned invalid JSON")
    return payload


def wait_for_http_version(host: str, port: int, expected_version: str, timeout: float = 35.0) -> dict[str, Any]:
    deadline = time.monotonic() + max(3.0, float(timeout))
    nonce = 0
    last_error = ""
    while time.monotonic() < deadline:
        nonce += 1
        url = f"http://{host}:{int(port)}/app-version?ls_upgrade_probe={nonce}"
        try:
            payload = get_json(url, timeout=1.5)
            if (
                payload.get("ok")
                and payload.get("server_ready")
                and str(payload.get("app_version") or payload.get("running_version") or "") == expected_version
            ):
                return payload
            last_error = f"Unexpected /app-version payload: {payload}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.35)
    raise TimeoutError(f"LocalSunoDb {expected_version} did not become ready: {last_error}")



def _snapshot_runtime_entry_allowed(entry: Path) -> bool:
    name = entry.name
    folded = name.casefold()
    if folded.startswith((".git", ".venv", "venv", "__pycache__", "data", "logs", "reports", "backup", "temp", "tools", "exports", ".ls_update_transaction")):
        return False
    if entry.is_dir():
        return name == "LS_Elza" or name == "LS_Suno_TokenBridge" or folded.startswith("ls_")
    if not entry.is_file():
        return False
    if folded == "localsunodb.py":
        return True
    if folded.startswith("ls_") and entry.suffix.casefold() in {".py", ".json", ".toml", ".yaml", ".yml", ".txt"}:
        return True
    return entry.suffix.casefold() == ".py"


def capture_previous_app_snapshot(
    base_dir: Path,
    previous_entrypoint: Path,
    previous_version: str,
    transaction_dir: Path,
) -> Path:
    """Capture the flat managed runtime for optional version comparison."""
    base = Path(base_dir).resolve()
    entrypoint = Path(previous_entrypoint).resolve()
    if entrypoint.parent != base or not entrypoint.is_file():
        raise ValueError("Previous LocalSunoDb entrypoint is outside the flat Upgrade base")

    snapshot = Path(transaction_dir).resolve() / "comparison_previous_app"
    if snapshot.exists():
        shutil.rmtree(snapshot, ignore_errors=True)
    snapshot.mkdir(parents=True, exist_ok=False)
    target_app = snapshot / "app"
    target_app.mkdir(parents=True, exist_ok=False)
    for source in base.iterdir():
        if not _snapshot_runtime_entry_allowed(source):
            continue
        destination = target_app / source.name
        if source.is_dir():
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.pyo"))
        else:
            shutil.copy2(source, destination)

    metadata = {
        "schema_version": 2,
        "layout": "flat-root",
        "version": str(previous_version),
        "entrypoint": entrypoint.name,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (snapshot / "comparison_snapshot.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return snapshot


def _comparison_snapshot_version_key(path: Path) -> tuple[int, int]:
    name = str(Path(path).name or "").strip()
    if not name.startswith("v") or "." not in name:
        return (-1, -1)
    try:
        major, minor = name[1:].split(".", 1)
        return int(major), int(minor)
    except Exception:
        return (-1, -1)


def publish_previous_app_snapshot(
    captured_snapshot: Path,
    history_dir: str | Path | None,
    history_limit: int,
) -> dict[str, Any]:
    """Publish a verified flat-runtime snapshot into short-term CompareHistory."""
    if not history_dir:
        return {"published": False, "reason": "history_disabled"}
    source = Path(captured_snapshot).resolve()
    metadata_path = source / "comparison_snapshot.json"
    app_dir = source / "app"
    if not metadata_path.is_file() or not app_dir.is_dir():
        raise ValueError("Captured comparison snapshot is incomplete")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    if not isinstance(metadata, dict):
        raise ValueError("Captured comparison snapshot metadata is invalid")
    version = str(metadata.get("version") or "").strip()
    entrypoint = str(metadata.get("entrypoint") or "").strip()
    if not version or not entrypoint or not (app_dir / entrypoint).is_file():
        raise ValueError("Captured comparison snapshot identity is incomplete")

    root = Path(history_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = root / version
    temporary = root / f".{version}.publishing-{os.getpid()}-{time.time_ns()}"
    if temporary.exists():
        shutil.rmtree(temporary, ignore_errors=True)
    shutil.copytree(source, temporary)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    os.replace(temporary, target)

    snapshots = []
    for child in root.iterdir():
        if not child.is_dir() or not (child / "comparison_snapshot.json").is_file():
            continue
        key = _comparison_snapshot_version_key(child)
        if key >= (0, 0):
            snapshots.append((key, child.stat().st_mtime_ns, child))
    snapshots.sort(reverse=True)
    for _version_key, _mtime, obsolete in snapshots[max(1, int(history_limit or 15)):]:
        shutil.rmtree(obsolete, ignore_errors=True)
    return {
        "published": True,
        "version": version,
        "source": str(source),
        "target": str(target),
    }


def record_installed_receipt(registry_path: str | Path | None, metadata: dict[str, Any]) -> None:
    if not registry_path:
        return
    path = Path(registry_path)
    raw: dict[str, Any] = {}
    try:
        if path.is_file():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                raw = loaded
    except Exception:
        raw = {}
    receipts = raw.get("installed_packages")
    if not isinstance(receipts, list):
        receipts = []
    receipt = {
        "version": metadata.get("new_version", ""),
        "based_on": metadata.get("semantic_based_on") or metadata.get("old_version", ""),
        "installed_from": metadata.get("old_version", ""),
        "package_id": metadata.get("package_id", ""),
        "source_sha256": metadata.get("source_sha256", ""),
        "manifest_sha256": metadata.get("manifest_sha256", ""),
        "source_name": metadata.get("source_name", ""),
        "install_mode": metadata.get("install_mode", "standard"),
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    identity = receipt["source_sha256"] or receipt["package_id"]
    filtered = [
        item for item in receipts
        if not isinstance(item, dict)
        or (item.get("source_sha256") or item.get("package_id")) != identity
    ]
    filtered.append(receipt)
    raw["installed_packages"] = filtered[-64:]
    try:
        minor = int(str(receipt["version"]).split(".", 1)[1])
        raw["highest_issued"] = max(int(raw.get("highest_issued") or 0), minor)
        raw["current_running"] = minor
    except Exception:
        pass
    raw["updated_at"] = receipt["installed_at"]
    raw["updated_by"] = receipt["version"]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".upgrade.tmp")
    temporary.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def launch_app(
    entrypoint: Path,
    *,
    restarted: bool = True,
    transaction_dir: Path | None = None,
) -> subprocess.Popen[Any]:
    # Automatic Upgrade/recovery restarts must not create a second visible
    # console.  Manual launches remain attached to the user's PowerShell; a
    # restarted backend is controlled by the LS UI and runtime PID registry.
    executable = background_python_executable() if restarted else console_python_executable()
    command = [executable, str(entrypoint)]
    if restarted:
        command.append("--ls-restarted")
    if transaction_dir is not None:
        command.extend(["--ls-update-transaction", str(Path(transaction_dir).resolve())])
    process_kwargs = hidden_process_kwargs() if restarted else main_app_process_kwargs()
    return subprocess.Popen(command, cwd=str(entrypoint.parent), **process_kwargs)


def run_bootstrapper(payload: dict[str, Any]) -> int:
    transaction = UpgradeTransaction.load(Path(payload["transaction_dir"]))
    metadata = transaction.read_metadata()
    base_dir = Path(metadata["base_dir"]).resolve()
    new_entrypoint = (base_dir / metadata["new_entrypoint"]).resolve()
    old_entrypoint = (base_dir / metadata["old_entrypoint"]).resolve()
    expected_version = str(metadata["new_version"])
    old_version = str(metadata["old_version"])
    old_pid = int(payload.get("old_pid") or 0)
    host = str(payload.get("host") or "127.0.0.1")
    port = int(payload.get("port") or 8765)
    audit_path = payload.get("audit_log_path")
    error_path = payload.get("error_log_path")
    new_process: subprocess.Popen[Any] | None = None
    old_process_stopped = False
    changelog_snapshot: dict[str, Any] | None = None
    operator_contract_snapshot: dict[str, Any] | None = None
    previous_app_snapshot: Path | None = None

    append_jsonl(audit_path, "bootstrapper_started", {"transaction_id": metadata.get("transaction_id"), "old_pid": old_pid})
    try:
        if not metadata.get("preflight_passed"):
            raise RuntimeError("Upgrade preflight was not completed by the coordinator")

        forced_old_stop = ensure_old_process_stopped(old_pid)
        old_process_stopped = True
        append_jsonl(
            audit_path,
            "old_process_stopped",
            {"old_pid": old_pid, "forced": bool(forced_old_stop)},
        )
        try:
            previous_app_snapshot = capture_previous_app_snapshot(
                base_dir,
                old_entrypoint,
                old_version,
                transaction.directory,
            )
            append_jsonl(audit_path, "previous_app_snapshot_captured", {
                "version": old_version,
                "path": str(previous_app_snapshot),
            })
        except Exception as snapshot_exc:
            previous_app_snapshot = None
            append_jsonl(error_path, "previous_app_snapshot_capture_failed", {"error": str(snapshot_exc)})
        transaction.commit(log_event=lambda event, data: append_jsonl(audit_path, event, data))
        new_process = launch_app(new_entrypoint, transaction_dir=transaction.directory)
        transaction.mark_verifying(new_process.pid)
        append_jsonl(audit_path, "new_process_started", {"pid": new_process.pid, "version": expected_version})
        ready = transaction.wait_for_ready(
            expected_version=expected_version,
            expected_pid=new_process.pid,
            timeout=35.0,
        )
        append_jsonl(audit_path, "new_process_ready_signal", ready)
        live = wait_for_http_version(host, port, expected_version)
        verification = dict(live)
        verification["ready_signal"] = ready
        verification["confirmed_by"] = "bootstrapper"

        # READY + live HTTP prove that the new managed runtime is healthy. Only
        # now may Upgrade switch the operator-facing cold-start contract. Capture
        # byte-exact prior root files first so any later failure or recovery can
        # restore the previously bootable launcher state.
        root_entrypoint_name = Path(str(metadata.get("new_entrypoint") or "")).name
        operator_contract_snapshot = capture_operator_launch_contract(
            base_dir,
            transaction.directory,
            root_entrypoint_name,
        )
        transaction.update_state(
            "verifying",
            extra={
                "operator_contract_snapshot": operator_contract_snapshot,
                "operator_contract_commit_started": True,
                "operator_contract_applied": False,
                "operator_contract_restored": False,
            },
        )
        operator_contract = publish_operator_launch_contract(
            base_dir,
            internal_entrypoint_name=root_entrypoint_name,
            version=expected_version,
            based_on=str(metadata.get("semantic_based_on") or old_version),
            package_id=str(metadata.get("package_id") or ""),
            package_sha256=str(metadata.get("source_sha256") or ""),
            source_name=str(metadata.get("source_name") or ""),
        )
        transaction.update_state(
            "verifying",
            extra={"operator_contract_applied": True},
        )
        append_jsonl(audit_path, "operator_launch_contract_published", operator_contract)

        manifest_path = transaction.staging_dir / MANIFEST_NAME
        installed_manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(installed_manifest, dict) or str(installed_manifest.get("version") or "") != expected_version:
            raise ValueError("Installed Upgrade changelog manifest version mismatch")
        changelog_snapshot = capture_changelog_snapshot(base_dir, transaction.directory)
        changelog_changed = append_verified_upgrade_changelog(base_dir, installed_manifest)
        append_jsonl(audit_path, "changelog_updated", {
            "version": expected_version,
            "changed": bool(changelog_changed),
            "path": str(base_dir / "LS_CHANGELOG.md"),
        })

        if previous_app_snapshot is not None:
            try:
                publish_result = publish_previous_app_snapshot(
                    previous_app_snapshot,
                    payload.get("comparison_history_dir"),
                    int(payload.get("comparison_history_limit") or 15),
                )
                append_jsonl(audit_path, "previous_app_snapshot_published", publish_result)
            except Exception as publish_exc:
                append_jsonl(error_path, "previous_app_snapshot_publish_failed", {"error": str(publish_exc)})

        completed = transaction.mark_completed(verification)
        changelog_snapshot = None
        try:
            record_installed_receipt(payload.get("version_registry_path"), completed)
        except Exception as receipt_exc:
            append_jsonl(error_path, "installed_receipt_failed", {"error": str(receipt_exc)})
        transaction.cleanup_payload()
        append_jsonl(audit_path, "upgrade_completed", {
            "version": expected_version,
            "pid": new_process.pid,
            "install_mode": metadata.get("install_mode", "standard"),
            "from_version": old_version,
        })
        return 0
    except Exception as exc:
        append_jsonl(error_path, "bootstrapper_failed", {"error": str(exc), "expected_version": expected_version})
        terminate_child(new_process)
        operator_contract_restore_error: Exception | None = None
        if operator_contract_snapshot is not None:
            try:
                restore_operator_launch_contract(
                    base_dir,
                    transaction.directory,
                    operator_contract_snapshot,
                )
                current = transaction.read_metadata()
                transaction.update_state(
                    str(current.get("state") or "failed"),
                    extra={
                        "operator_contract_applied": False,
                        "operator_contract_restored": True,
                    },
                )
                append_jsonl(audit_path, "operator_launch_contract_rollback_completed", {"version": expected_version})
            except Exception as restore_operator_exc:
                operator_contract_restore_error = restore_operator_exc
                append_jsonl(error_path, "operator_launch_contract_rollback_failed", {"error": str(restore_operator_exc)})
        changelog_restore_error: Exception | None = None
        if changelog_snapshot is not None:
            try:
                restore_changelog_snapshot(base_dir, changelog_snapshot)
                append_jsonl(audit_path, "changelog_rollback_completed", {"version": expected_version})
            except Exception as restore_changelog_exc:
                changelog_restore_error = restore_changelog_exc
                append_jsonl(error_path, "changelog_rollback_failed", {"error": str(restore_changelog_exc)})
        try:
            current = transaction.read_metadata()
            transaction.update_state(
                str(current.get("state") or "failed"),
                error=str(exc),
                extra={"failure_stage": "bootstrapper"},
            )
        except Exception:
            pass
        try:
            transaction.rollback(log_event=lambda event, data: append_jsonl(audit_path, event, data))
        except Exception as rollback_exc:
            append_jsonl(error_path, "rollback_failed", {"error": str(rollback_exc)})
            return 8

        # If failure happened before the old process was stopped, do not create a
        # duplicate LS instance.  If the coordinator's graceful-shutdown request
        # has already completed in parallel, process_is_alive() detects that and
        # we restore the previous entrypoint exactly once.
        should_restart_previous = old_process_stopped or not process_is_alive(old_pid)
        if should_restart_previous:
            try:
                previous = launch_app(old_entrypoint)
                wait_for_http_version(host, port, old_version)
                append_jsonl(audit_path, "previous_version_restored", {"version": old_version, "pid": previous.pid})
            except Exception as restore_exc:
                append_jsonl(error_path, "previous_version_restart_failed", {"error": str(restore_exc)})
                return 9
        else:
            append_jsonl(audit_path, "previous_version_still_running", {"version": old_version, "pid": old_pid})
        return 8 if (changelog_restore_error is not None or operator_contract_restore_error is not None) else 7


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args(argv)
    return run_bootstrapper(decode_payload(args.payload))


if __name__ == "__main__":
    raise SystemExit(main())
