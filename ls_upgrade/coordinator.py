"""Single authoritative LocalSunoDb Upgrade coordinator."""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .bootstrapper import background_python_executable, encode_payload, hidden_process_kwargs, run_source_probe
from .package import NoUpdateCandidate, UpgradePackage, is_direct_successor, iter_download_candidates, parse_version, validate_zip
from .transaction import UpgradeTransaction, find_transactions, recover_transactions

LogEvent = Callable[[str, dict[str, Any]], None]
LogError = Callable[[str, Exception, dict[str, Any]], None]
IntervalProvider = Callable[[], float]
ShutdownCallback = Callable[[Path], None]

VALID_STATES = {
    "idle",
    "discovered",
    "offered",
    "preparing",
    "installing",
    "staged",
    "committing",
    "restarting",
    "verifying",
    "completed",
    "rolling_back",
    "failed",
}


@dataclass(frozen=True)
class UpgradeConfig:
    base_dir: Path
    downloads_dir: Path
    transaction_root: Path
    running_version: str
    entrypoint: Path
    host: str
    port: int
    version_registry_path: Path
    audit_log_path: Path
    error_log_path: Path
    interval_provider: IntervalProvider
    shutdown_callback: ShutdownCallback
    log_event: LogEvent
    log_error: LogError
    comparison_history_dir: Path | None = None
    comparison_history_limit: int = 15


class UpgradeCoordinator:
    """Own candidate discovery, the one dialog, installation, and recovery."""

    def __init__(self, config: UpgradeConfig):
        self.config = config
        self._lock = threading.RLock()
        self._install_lock = threading.Lock()
        self._state = "idle"
        self._candidate: UpgradePackage | None = None
        self._candidate_cache: dict[str, dict[str, Any]] = {}
        self._directory_signature: tuple[tuple[str, int, int], ...] = ()
        self._rejected_signatures: set[str] = set()
        self._dialog_process: subprocess.Popen[Any] | None = None
        self._dialog_signature = ""
        self._watcher_thread: threading.Thread | None = None
        self._watcher_stop = threading.Event()
        self._current_transaction_dir: Path | None = None
        self._last_error = ""

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _set_state(self, state: str, *, error: str = "") -> None:
        if state not in VALID_STATES:
            raise ValueError(f"Invalid Upgrade state: {state}")
        with self._lock:
            self._state = state
            if error:
                self._last_error = str(error)
        self.config.log_event("coordinator_state", {"state": state, "error": error})

    def _metadata_signature(self) -> tuple[tuple[str, int, int], ...]:
        rows: list[tuple[str, int, int]] = []
        for path in iter_download_candidates(self.config.downloads_dir):
            try:
                stat = path.stat()
            except OSError:
                continue
            rows.append((path.name, int(stat.st_size), int(stat.st_mtime_ns)))
        return tuple(rows)

    def _installed_recovery_bases(self) -> tuple[str, ...]:
        """Return the semantic base proven by the exact installed running receipt.

        This does not authorize recovery by itself. The candidate manifest must also
        explicitly name the running version in recovery_from, and package validation
        only permits a direct-successor recovery.
        """
        path = Path(self.config.version_registry_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ()
        rows = payload.get("installed_packages") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return ()
        for item in reversed(rows):
            if not isinstance(item, dict):
                continue
            if str(item.get("version") or "").strip() != self.config.running_version:
                continue
            based_on = str(item.get("based_on") or "").strip()
            identity = str(item.get("source_sha256") or item.get("package_id") or "").strip()
            if not based_on or not identity:
                return ()
            try:
                parse_version(based_on)
            except ValueError:
                return ()
            return (based_on,)
        return ()

    def _refresh_candidates(self, *, force: bool = False) -> None:
        signature = self._metadata_signature()
        with self._lock:
            if not force and signature == self._directory_signature:
                return
            self._directory_signature = signature

        names_present = {name for name, _size, _mtime in signature}
        for cached_name in tuple(self._candidate_cache):
            if cached_name not in names_present:
                self._candidate_cache.pop(cached_name, None)

        recovery_bases = self._installed_recovery_bases()
        for name, size, mtime_ns in signature:
            path = self.config.downloads_dir / name
            cache = self._candidate_cache.get(name)
            if cache and cache.get("size") == size and cache.get("mtime_ns") == mtime_ns:
                continue
            try:
                package = validate_zip(
                    path,
                    running_version=self.config.running_version,
                    require_newer=True,
                    require_direct_successor=False,
                    allowed_recovery_bases=recovery_bases,
                )
                install_mode = (
                    "standard"
                    if is_direct_successor(package.version, self.config.running_version)
                    else "emergency"
                )
                self._candidate_cache[name] = {
                    "size": size,
                    "mtime_ns": mtime_ns,
                    "package": package,
                    "install_mode": install_mode,
                    "error": "",
                }
            except Exception as exc:
                self._candidate_cache[name] = {
                    "size": size,
                    "mtime_ns": mtime_ns,
                    "package": None,
                    "error": str(exc),
                }

    def _candidate_failure_path(self) -> Path:
        return self.config.transaction_root / "failed_candidates.json"

    def _load_recorded_failed_signatures(self) -> set[str]:
        path = self._candidate_failure_path()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        rows = payload.get("failures") if isinstance(payload, dict) else []
        return {
            str(item.get("signature") or "")
            for item in (rows if isinstance(rows, list) else [])
            if isinstance(item, dict) and str(item.get("signature") or "")
        }

    def _record_failed_signature(self, signature: str, error: str) -> None:
        signature = str(signature or "").strip()
        if not signature:
            return
        path = self._candidate_failure_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}
        rows = payload.get("failures")
        if not isinstance(rows, list):
            rows = []
        rows = [item for item in rows if not isinstance(item, dict) or item.get("signature") != signature]
        rows.append({"signature": signature, "error": str(error or ""), "failed_at": time.time()})
        payload["failures"] = rows[-64:]
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    def _failed_transaction_signatures(self) -> set[str]:
        signatures: set[str] = set(self._load_recorded_failed_signatures())
        for transaction in find_transactions(self.config.transaction_root):
            try:
                metadata = transaction.read_metadata()
            except Exception:
                continue
            if str(metadata.get("state") or "") not in {"rolled_back", "failed"}:
                continue
            version = str(metadata.get("new_version") or "")
            source_name = str(metadata.get("source_name") or "")
            source_sha = str(metadata.get("source_sha256") or "")
            manifest_sha = str(metadata.get("manifest_sha256") or "")
            if version and source_name and source_sha and manifest_sha:
                signatures.add("|".join((version, source_name, source_sha, manifest_sha)))
        return signatures

    def discover(self, *, manual: bool = False, force: bool = False) -> dict[str, Any]:
        try:
            self._refresh_candidates(force=force)
            failed_signatures = set() if manual else self._failed_transaction_signatures()
            valid_rows = [
                item
                for item in self._candidate_cache.values()
                if isinstance(item.get("package"), UpgradePackage)
                and (manual or item["package"].signature not in failed_signatures)
            ]
            if not valid_rows:
                with self._lock:
                    self._candidate = None
                    if self._state in {"idle", "discovered", "offered"}:
                        self._state = "idle"
                invalid_rows = [
                    (name, str(item.get("error") or ""))
                    for name, item in self._candidate_cache.items()
                    if item.get("package") is None and str(item.get("error") or "")
                ]
                invalid_rows.sort(key=lambda row: row[0].casefold(), reverse=True)
                message = "Downloads mapē nav jaunākas derīgas LS Upgrade pakotnes."
                if manual and invalid_rows:
                    invalid_name, invalid_error = invalid_rows[0]
                    message = f"Atrasta nederīga Upgrade pakotne {invalid_name}: {invalid_error}"
                return {
                    "ok": True,
                    "available": False,
                    "state": self.state,
                    "message": message,
                    "invalid_candidates": [
                        {"source_name": name, "error": error}
                        for name, error in invalid_rows[:5]
                    ],
                }
            # Always surface the newest valid package based directly on the running
            # LS. If that skips version numbers, the dialog requires the explicit
            # Emergency button; an older direct-successor ZIP must not hide the newer
            # intended repair package.
            selected = max(valid_rows, key=lambda item: parse_version(item["package"].version))
            package = selected["package"]
            install_mode = str(selected.get("install_mode") or "standard")
            with self._lock:
                self._candidate = package
                if self._state in {"idle", "discovered", "offered"}:
                    self._state = "discovered"
            payload = package.to_payload()
            payload["install_mode"] = install_mode
            payload["emergency_install"] = install_mode == "emergency"
            payload["state"] = self.state
            payload["rejected_in_session"] = package.signature in self._rejected_signatures
            payload["previous_attempt_failed"] = package.signature in self._failed_transaction_signatures()
            payload["manual"] = bool(manual)
            return payload
        except Exception as exc:
            self.config.log_error("candidate_discovery", exc, {})
            self._set_state("failed", error=str(exc))
            return {"ok": False, "available": False, "state": self.state, "error": str(exc)}

    def _dialog_is_alive(self) -> bool:
        process = self._dialog_process
        if process is None:
            return False
        if process.poll() is None:
            return True
        self._dialog_process = None
        self._dialog_signature = ""
        return False

    def _handoff_dialog_process(self) -> int:
        """Relinquish the active Upgrade dialog before the old LS process exits.

        The native dialog is intentionally a detached process. Once installation
        has been handed to the external bootstrapper, the dialog must survive the
        old backend shutdown so it can observe the new backend's terminal
        transaction state and finish step 3 for the user.
        """
        with self._lock:
            process = self._dialog_process
            if process is None or process.poll() is not None:
                self._dialog_process = None
                self._dialog_signature = ""
                return 0
            pid = int(process.pid or 0)
            self._dialog_process = None
            self._dialog_signature = ""
            return pid

    def open_dialog(self, *, manual: bool = False) -> dict[str, Any]:
        payload = self.discover(manual=manual, force=manual)
        if not payload.get("available"):
            if not manual or not payload.get("ok"):
                return payload
            info_message = str(payload.get("message") or "").strip()
            with self._lock:
                if self._dialog_is_alive():
                    payload["offered"] = True
                    payload["native_dialog_active"] = True
                    return payload
                dialog_payload = {
                    "base_url": f"http://{self.config.host}:{int(self.config.port)}",
                    "running_version": self.config.running_version,
                    "info_message": info_message,
                }
                command = [
                    background_python_executable(),
                    "-m",
                    "ls_upgrade.native_dialog",
                    "--payload",
                    encode_payload(dialog_payload),
                ]
                process = subprocess.Popen(
                    command,
                    cwd=str(self.config.entrypoint.parent),
                    **hidden_process_kwargs(),
                )
                self._dialog_process = process
                self._dialog_signature = ""
            self.config.log_event("dialog_opened", {"signature": "", "manual": True, "informational": True, "pid": process.pid})
            payload["offered"] = True
            payload["native_dialog_active"] = True
            payload["dialog_process_id"] = process.pid
            return payload
        package = self._candidate
        if package is None:
            return {"ok": False, "available": False, "error": "Upgrade kandidāts nav pieejams"}
        with self._lock:
            if not manual and package.signature in self._rejected_signatures:
                payload["offered"] = False
                payload["rejected_in_session"] = True
                return payload
            if self._dialog_is_alive():
                payload["ok"] = True
                payload["offered"] = True
                payload["native_dialog_active"] = True
                return payload

            # Keep the native-dialog process command line deliberately small.
            # A full package payload may contain hundreds of manifest file rows;
            # encoding that JSON into --payload exceeds the Windows CreateProcess
            # command-line limit (WinError 206).  The dialog only needs immutable
            # candidate identity fields and the coordinator revalidates the ZIP
            # again before installation.
            package_payload = package.to_payload()
            dialog_candidate = {
                "source_name": package_payload.get("source_name", ""),
                "zip_name": package_payload.get("zip_name", ""),
                "source_sha256": package_payload.get("source_sha256", ""),
                "manifest_sha256": package_payload.get("manifest_sha256", ""),
                "version": package_payload.get("version", ""),
                "new_version": package_payload.get("new_version", ""),
                "based_on": package_payload.get("based_on", ""),
                "package_id": package_payload.get("package_id", ""),
                "signature": package_payload.get("signature", ""),
                "file_count": package_payload.get("file_count", 0),
                "upgrade_points": package_payload.get("upgrade_points", []),
                "install_mode": payload.get("install_mode", "standard"),
                "emergency_install": bool(payload.get("emergency_install")),
            }
            dialog_payload = {
                "base_url": f"http://{self.config.host}:{int(self.config.port)}",
                "running_version": self.config.running_version,
                "candidate": dialog_candidate,
            }
            command = [
                background_python_executable(),
                "-m",
                "ls_upgrade.native_dialog",
                "--payload",
                encode_payload(dialog_payload),
            ]
            process = subprocess.Popen(
                command,
                cwd=str(self.config.entrypoint.parent),
                **hidden_process_kwargs(),
            )
            self._dialog_process = process
            self._dialog_signature = package.signature
            self._state = "offered"
        self.config.log_event("dialog_opened", {
            "signature": package.signature,
            "manual": manual,
            "pid": process.pid,
            "install_mode": payload.get("install_mode", "standard"),
        })
        payload["offered"] = True
        payload["native_dialog_active"] = True
        payload["dialog_process_id"] = process.pid
        return payload

    def reject(self, signature: str) -> dict[str, Any]:
        signature = str(signature or "").strip()
        with self._lock:
            if signature:
                self._rejected_signatures.add(signature)
            if self._candidate and self._candidate.signature == signature:
                self._state = "discovered"
            self._dialog_process = None
            self._dialog_signature = ""
        self.config.log_event("candidate_rejected_for_session", {"signature": signature})
        return {"ok": True, "rejected": True, "signature": signature, "state": self.state}

    def install(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self._install_lock.acquire(blocking=False):
            return {"ok": False, "error": "LS Upgrade instalēšana jau notiek", "state": self.state}
        transaction: UpgradeTransaction | None = None
        try:
            self._set_state("installing")
            source_name = Path(str(request.get("source_name") or request.get("zip_name") or "")).name
            source_sha = str(request.get("source_sha256") or "").strip().casefold()
            manifest_sha = str(request.get("manifest_sha256") or "").strip().casefold()
            signature = str(request.get("signature") or "").strip()
            requested_mode = str(request.get("install_mode") or "standard").strip().casefold()
            if requested_mode not in {"standard", "emergency"}:
                raise ValueError("Nederīgs LS Upgrade instalācijas režīms")
            if not source_name:
                raise ValueError("Upgrade pakotnes nosaukums nav norādīts")
            source_path = (self.config.downloads_dir / source_name).resolve()
            if source_path.parent != self.config.downloads_dir.resolve():
                raise ValueError("Upgrade pakotne nav Downloads mapē")
            package = validate_zip(
                source_path,
                running_version=self.config.running_version,
                require_newer=True,
                require_direct_successor=False,
                allowed_recovery_bases=self._installed_recovery_bases(),
            )
            package_is_emergency = not is_direct_successor(
                package.version,
                self.config.running_version,
            )
            if package_is_emergency and requested_mode != "emergency":
                raise ValueError("Izlaista LS versija jāinstalē kā ārkārtas labojums")
            if not package_is_emergency and requested_mode != "standard":
                raise ValueError("Secīga LS versija jāinstalē standarta režīmā")
            install_mode = "emergency" if package_is_emergency else "standard"
            self.config.log_event("install_requested", {
                "install_mode": install_mode,
                "from_version": self.config.running_version,
                "to_version": package.version,
                "source_name": package.source_name,
            })
            if source_sha and package.source_sha256 != source_sha:
                raise ValueError("Upgrade ZIP pēc piedāvāšanas ir mainījies")
            if manifest_sha and package.manifest_sha256 != manifest_sha:
                raise ValueError("Upgrade manifests pēc piedāvāšanas ir mainījies")
            if signature and package.signature != signature:
                raise ValueError("Upgrade kandidāta identitāte ir mainījusies")

            transaction = UpgradeTransaction.create(
                transaction_root=self.config.transaction_root,
                base_dir=self.config.base_dir,
                package=package,
                running_entrypoint=self.config.entrypoint.resolve().relative_to(self.config.base_dir.resolve()).as_posix(),
                running_version=self.config.running_version,
                install_mode=install_mode,
                log_event=self.config.log_event,
            )
            self._current_transaction_dir = transaction.directory

            # Complete all expensive/source-level validation while the currently
            # running LS is still healthy. The Upgrade ZIP may be a delta, therefore
            # probe a complete shadow runtime: live Accepted base + staged delta.
            # Only after this full candidate passes do we launch the external
            # bootstrapper and request shutdown. A bad candidate therefore cannot
            # create downtime or a rollback cycle.
            candidate_entrypoint = transaction.build_candidate_tree(log_event=self.config.log_event)
            staged_probe = run_source_probe(candidate_entrypoint, package.version)
            transaction.update_state(
                "staged",
                extra={
                    "preflight_passed": True,
                    "preflight": {
                        "marker": staged_probe.get("marker", ""),
                        "app_version": staged_probe.get("app_version", ""),
                        "imports": (staged_probe.get("imports") or {}).get("count", 0),
                    },
                },
            )
            self.config.log_event("candidate_shadow_probe_passed", {
                "transaction_id": transaction.directory.name,
                "version": package.version,
                "imports": (staged_probe.get("imports") or {}).get("count", 0),
            })
            self._set_state("staged")
            bootstrapper_payload = {
                "transaction_dir": str(transaction.directory),
                "old_pid": os.getpid(),
                "host": self.config.host,
                "port": int(self.config.port),
                "version_registry_path": str(self.config.version_registry_path),
                "audit_log_path": str(self.config.audit_log_path),
                "error_log_path": str(self.config.error_log_path),
                "comparison_history_dir": str(self.config.comparison_history_dir) if self.config.comparison_history_dir else "",
                "comparison_history_limit": int(self.config.comparison_history_limit),
            }
            command = [
                background_python_executable(),
                "-m",
                "ls_upgrade.bootstrapper",
                "--payload",
                encode_payload(bootstrapper_payload),
            ]
            bootstrapper = subprocess.Popen(
                command,
                cwd=str(self.config.entrypoint.parent),
                **hidden_process_kwargs(),
            )
            self._set_state("restarting")
            result = package.to_payload()
            result.update({
                "ok": True,
                "state": "restarting",
                "transaction_id": transaction.read_metadata().get("transaction_id"),
                "bootstrapper_process_id": bootstrapper.pid,
                "handoff_process_id": bootstrapper.pid,
                "restart_scheduled": True,
                "install_mode": install_mode,
                "emergency_install": install_mode == "emergency",
            })
            self.config.log_event("bootstrapper_process_started", {"pid": bootstrapper.pid, "transaction_dir": str(transaction.directory)})
            dialog_handoff_pid = self._handoff_dialog_process()
            if dialog_handoff_pid:
                result["dialog_handoff_process_id"] = dialog_handoff_pid
                self.config.log_event(
                    "dialog_handed_off_to_bootstrapper",
                    {
                        "pid": dialog_handoff_pid,
                        "transaction_id": result.get("transaction_id", ""),
                        "expected_version": package.version,
                    },
                )
            self.config.shutdown_callback(self.config.entrypoint)
            return result
        except Exception as exc:
            if signature:
                with self._lock:
                    self._rejected_signatures.add(signature)
                try:
                    self._record_failed_signature(signature, str(exc))
                except Exception as failure_record_exc:
                    self.config.log_error("candidate_failure_receipt", failure_record_exc, {"signature": signature})
            if transaction is not None:
                try:
                    transaction.rollback(log_event=self.config.log_event)
                except Exception as rollback_exc:
                    self.config.log_error("prepare_rollback", rollback_exc, {"transaction": str(transaction.directory)})
            self.config.log_error("install", exc, {})
            self._set_state("failed", error=str(exc))
            return {"ok": False, "error": str(exc), "state": self.state}
        finally:
            self._install_lock.release()

    def recover(self) -> list[dict[str, Any]]:
        results = recover_transactions(
            transaction_root=self.config.transaction_root,
            running_version=self.config.running_version,
            log_event=self.config.log_event,
        )
        for item in results:
            if item.get("action") == "continue_verification":
                self._current_transaction_dir = self.config.transaction_root / str(item.get("transaction_id"))
                self._set_state("verifying")
            elif item.get("action") == "recovery_failed":
                self._set_state("failed", error=str(item.get("error") or ""))
        return results

    def status(self, transaction_id: str = "") -> dict[str, Any]:
        transaction_payload: dict[str, Any] = {}
        transactions = find_transactions(self.config.transaction_root)
        requested_transaction_id = str(transaction_id or "").strip()
        if transactions:
            if requested_transaction_id:
                for transaction in transactions:
                    if transaction.directory.name != requested_transaction_id:
                        continue
                    try:
                        transaction_payload = transaction.read_metadata()
                    except Exception:
                        transaction_payload = {}
                    break
            else:
                rows: list[tuple[float, str, dict[str, Any]]] = []
                for transaction in transactions:
                    try:
                        payload = transaction.read_metadata()
                        rows.append((float(payload.get("updated_at") or 0.0), transaction.directory.name, payload))
                    except Exception:
                        continue
                if rows:
                    _updated_at, _name, transaction_payload = max(rows, key=lambda row: (row[0], row[1]))
        state = str(transaction_payload.get("state") or self.state)

        if state in VALID_STATES:
            with self._lock:
                self._state = state

        response_state = self.state

        return {
            "ok": True,
            "state": response_state,
            "running_version": self.config.running_version,
            "expected_version": str(transaction_payload.get("new_version") or ""),
            "old_version": str(transaction_payload.get("old_version") or ""),
            "transaction_id": str(transaction_payload.get("transaction_id") or ""),
            "error": str(transaction_payload.get("error") or self._last_error or ""),
            "candidate": self._candidate.to_payload() if self._candidate else None,
        }

    def start_watcher(self) -> bool:
        with self._lock:
            if self._watcher_thread and self._watcher_thread.is_alive():
                return False
            self._watcher_stop.clear()
            self._watcher_thread = threading.Thread(
                target=self._watcher_loop,
                name="ls-upgrade-watcher",
                daemon=True,
            )
            self._watcher_thread.start()
            return True

    def stop_watcher(self, *, close_dialog: bool = False) -> None:
        self._watcher_stop.set()
        thread = self._watcher_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if not close_dialog:
            return
        with self._lock:
            process = self._dialog_process
            self._dialog_process = None
            self._dialog_signature = ""
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=3.0)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _watcher_loop(self) -> None:
        while not self._watcher_stop.is_set():
            try:
                interval = float(self.config.interval_provider() or 0)
            except Exception:
                interval = 10.0
            if interval <= 0:
                self._watcher_stop.wait(1.0)
                continue
            try:
                payload = self.discover(manual=False, force=False)
                if payload.get("available"):
                    self.open_dialog(manual=False)
            except Exception as exc:
                self.config.log_error("watcher", exc, {})
            self._watcher_stop.wait(max(1.0, min(interval, 3600.0)))
