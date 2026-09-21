"""Transactional staging, commit, rollback, and recovery for LS Upgrade."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable

from .operator_contract import restore_operator_launch_contract
from .package import MANIFEST_NAME, UpgradePackage, parse_version, path_under, sha256_file, validate_zip

MetadataLogger = Callable[[str, dict[str, Any]], None]


class UpgradeTransaction:
    """One on-disk Upgrade transaction under .ls_update_transaction."""

    METADATA_NAME = "transaction.json"
    READY_NAME = "ready.json"

    def __init__(self, directory: Path):
        self.directory = Path(directory).resolve()
        self.metadata_path = self.directory / self.METADATA_NAME
        self.staging_dir = self.directory / "staging"
        self.backup_dir = self.directory / "backup"
        self.candidate_dir = self.directory / "candidate"
        self.ready_path = self.directory / self.READY_NAME

    @classmethod
    def create(
        cls,
        *,
        transaction_root: Path,
        base_dir: Path,
        package: UpgradePackage,
        running_entrypoint: str,
        running_version: str | None = None,
        install_mode: str = "standard",
        log_event: MetadataLogger | None = None,
    ) -> "UpgradeTransaction":
        transaction_root = Path(transaction_root).resolve()
        transaction_root.mkdir(parents=True, exist_ok=True)
        transaction_id = f"{int(time.time())}-{uuid.uuid4().hex[:12]}"
        transaction = cls(transaction_root / transaction_id)
        try:
            transaction.staging_dir.mkdir(parents=True, exist_ok=False)
            transaction.backup_dir.mkdir(parents=True, exist_ok=True)
            runtime_old_version = str(running_version or package.based_on).strip()
            parse_version(runtime_old_version)

            metadata: dict[str, Any] = {
                "schema_version": 2,
                "transaction_id": transaction_id,
                "state": "preparing",
                "created_at": time.time(),
                "updated_at": time.time(),
                "base_dir": str(Path(base_dir).resolve()),
                "source_path": str(package.source_path),
                "source_name": package.source_name,
                "source_sha256": package.source_sha256,
                "manifest_sha256": package.manifest_sha256,
                "package_id": package.package_id,
                "old_version": runtime_old_version,
                "semantic_based_on": package.based_on,
                "new_version": package.version,
                "install_mode": "emergency" if str(install_mode).casefold() == "emergency" else "standard",
                "updater_protocol": "bootstrapper_v2",
                "old_entrypoint": str(running_entrypoint),
                "new_entrypoint": package.entrypoint,
                "working_directory": package.working_directory,
                "prepared": False,
                "preflight_passed": False,
                "preflight": {},
                "commit_started": False,
                "commit_completed": False,
                "changed_files": [],
                "files": [
                    {
                        "path": item.path,
                        "action": item.action,
                        "resolved_action": "",
                        "size": item.size,
                        "sha256": item.sha256,
                        "existed_before": False,
                        "backup_path": "",
                        "old_sha256": "",
                    }
                    for item in package.files
                ],
                "error": "",
            }
            transaction.write_metadata(metadata)
            transaction._stage_and_backup(package, log_event=log_event)
            transaction.update_state("staged", extra={"prepared": True})
            if log_event:
                log_event("transaction_staged", transaction.read_metadata())
            return transaction
        except Exception:
            # Staging/backup never mutates the live runtime. A preparation failure
            # therefore has nothing to roll back and must not leave a recoverable
            # transaction whose default existed_before=False rows could later delete
            # a valid installation. Remove the partial transaction atomically.
            shutil.rmtree(transaction.directory, ignore_errors=True)
            raise

    @classmethod
    def load(cls, directory: Path) -> "UpgradeTransaction":
        transaction = cls(directory)
        if not transaction.metadata_path.is_file():
            raise ValueError(f"Upgrade transaction metadata was not found: {transaction.metadata_path}")
        transaction.read_metadata()
        return transaction

    def read_metadata(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid Upgrade transaction metadata: {self.metadata_path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Upgrade transaction metadata must be a JSON object")
        if int(payload.get("schema_version") or 0) != 2:
            raise ValueError("Unsupported Upgrade transaction schema")
        if str(payload.get("updater_protocol") or "") != "bootstrapper_v2":
            raise ValueError("Unsupported Upgrade transaction protocol")
        return payload

    def write_metadata(self, payload: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = dict(payload)
        payload["updated_at"] = time.time()
        temporary = self.metadata_path.with_suffix(".tmp")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(temporary, self.metadata_path)

    def update_state(self, state: str, *, error: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self.read_metadata()
        payload["state"] = str(state)
        if error:
            payload["error"] = str(error)
        if extra:
            payload.update(extra)
        self.write_metadata(payload)
        return payload

    def mark_ready(self, *, app_version: str, process_id: int, server_url: str = "") -> dict[str, Any]:
        """Atomically publish the restarted App readiness handshake."""
        metadata = self.read_metadata()
        expected_version = str(metadata.get("new_version") or "")
        if str(app_version or "") != expected_version:
            raise ValueError(
                f"Upgrade ready signal version mismatch: expected {expected_version}, got {app_version}"
            )
        payload = {
            "transaction_id": str(metadata.get("transaction_id") or ""),
            "app_version": str(app_version),
            "process_id": int(process_id),
            "server_url": str(server_url or ""),
            "ready_at": time.time(),
        }
        temporary = self.ready_path.with_suffix(".tmp")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        with temporary.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(temporary, self.ready_path)
        return payload

    def read_ready(self) -> dict[str, Any]:
        if not self.ready_path.is_file():
            return {}
        try:
            payload = json.loads(self.ready_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid Upgrade ready signal: {self.ready_path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Upgrade ready signal must be a JSON object")
        return payload

    def wait_for_ready(
        self,
        *,
        expected_version: str,
        expected_pid: int,
        timeout: float = 35.0,
    ) -> dict[str, Any]:
        """Wait for the new LS process to acknowledge this exact transaction."""
        deadline = time.monotonic() + max(3.0, float(timeout))
        last_error = "ready signal not written"
        while time.monotonic() < deadline:
            try:
                payload = self.read_ready()
                if not payload:
                    time.sleep(0.2)
                    continue
                if str(payload.get("transaction_id") or "") != self.directory.name:
                    last_error = "ready signal transaction id mismatch"
                elif str(payload.get("app_version") or "") != str(expected_version):
                    last_error = "ready signal version mismatch"
                elif int(payload.get("process_id") or 0) != int(expected_pid):
                    last_error = "ready signal process id mismatch"
                else:
                    return payload
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.2)
        raise TimeoutError(f"LocalSunoDb {expected_version} did not publish READY: {last_error}")


    @staticmethod
    def _candidate_source_entry_allowed(entry: Path) -> bool:
        """Return True for bounded runtime/source entries needed by --ls-update-probe.

        Candidate preflight must execute against the *complete prospective runtime*,
        not merely the Upgrade delta.  Copy Python/runtime packages and compact
        top-level source/config files while deliberately excluding mutable user data,
        logs, backups, transaction evidence, databases and caches.
        """
        name = entry.name
        folded = name.casefold()
        if folded.startswith((".ls_update_transaction", ".git", ".venv", "venv", "__pycache__")):
            return False
        if entry.is_dir():
            if folded == "localsunodb_app" or name == "LS_Elza" or folded.startswith("ls_"):
                return True
            return (entry / "__init__.py").is_file()
        if not entry.is_file():
            return False
        if folded == "localsunodb.py":
            return True
        if folded.startswith("ls_") and entry.suffix.casefold() in {".py", ".json", ".toml", ".yaml", ".yml", ".txt"}:
            return True
        return entry.suffix.casefold() == ".py"

    def build_candidate_tree(self, log_event: MetadataLogger | None = None) -> Path:
        """Build a full shadow runtime = live Accepted base + staged Upgrade delta.

        No live file is mutated.  This is the authoritative preflight tree used by
        --ls-update-probe before the old LS process is asked to stop.
        """
        metadata = self.read_metadata()
        if not metadata.get("prepared"):
            raise RuntimeError("Upgrade transaction is not fully prepared")
        base_dir = Path(metadata["base_dir"]).resolve()
        if self.candidate_dir.exists():
            shutil.rmtree(self.candidate_dir, ignore_errors=True)
        self.candidate_dir.mkdir(parents=True, exist_ok=False)

        copied_files = 0
        for source in base_dir.iterdir():
            if not self._candidate_source_entry_allowed(source):
                continue
            destination = self.candidate_dir / source.name
            if source.is_dir():
                shutil.copytree(
                    source,
                    destination,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
                )
                copied_files += sum(1 for item in destination.rglob("*") if item.is_file())
            else:
                shutil.copy2(source, destination)
                copied_files += 1

        applied = []
        for record in metadata.get("files") or []:
            relative_name = str(record.get("path") or "")
            if not relative_name:
                raise ValueError("Upgrade candidate contains an empty path")
            requested_action = str(record.get("action") or "replace").casefold()
            candidate_target = path_under(self.candidate_dir, relative_name)
            if requested_action == "delete":
                if candidate_target.exists():
                    if not candidate_target.is_file():
                        raise ValueError(f"Upgrade candidate delete target is not a file: {relative_name}")
                    candidate_target.unlink()
                applied.append(relative_name)
                continue

            staged_path = path_under(self.staging_dir, relative_name)
            if not staged_path.is_file():
                raise ValueError(f"Staged Upgrade file is missing for candidate preflight: {relative_name}")
            if sha256_file(staged_path) != str(record.get("sha256") or ""):
                raise ValueError(f"Staged Upgrade file hash changed before candidate preflight: {relative_name}")
            candidate_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_path, candidate_target)
            if sha256_file(candidate_target) != str(record.get("sha256") or ""):
                raise ValueError(f"Candidate Upgrade file hash mismatch: {relative_name}")
            applied.append(relative_name)

        new_entrypoint = path_under(self.candidate_dir, str(metadata.get("new_entrypoint") or ""))
        if not new_entrypoint.is_file():
            raise ValueError(f"Candidate Upgrade entrypoint is missing: {metadata.get('new_entrypoint')}")

        metadata = self.update_state(
            "staged",
            extra={
                "candidate_shadow_ready": True,
                "candidate_shadow_file_count": sum(1 for item in self.candidate_dir.rglob("*") if item.is_file()),
                "candidate_shadow_base_files": copied_files,
                "candidate_shadow_applied_files": len(applied),
            },
        )
        if log_event:
            log_event("candidate_shadow_built", {
                "transaction_id": metadata.get("transaction_id"),
                "base_files": metadata.get("candidate_shadow_base_files"),
                "applied_files": metadata.get("candidate_shadow_applied_files"),
                "candidate_files": metadata.get("candidate_shadow_file_count"),
            })
        return new_entrypoint

    def _stage_and_backup(self, package: UpgradePackage, log_event: MetadataLogger | None = None) -> None:
        metadata = self.read_metadata()
        base_dir = Path(metadata["base_dir"]).resolve()

        with zipfile.ZipFile(package.source_path, "r") as archive:
            manifest_bytes = archive.read(MANIFEST_NAME)
            (self.staging_dir / MANIFEST_NAME).write_bytes(manifest_bytes)
            staged_records: list[dict[str, Any]] = []
            reconciled: list[dict[str, str]] = []
            for record in metadata["files"]:
                relative_name = record["path"]
                requested_action = str(record.get("action") or "replace").casefold()
                target = path_under(base_dir, relative_name)
                if target.exists() and not target.is_file():
                    raise ValueError(f"Upgrade target is not a file: {relative_name}")
                existed = target.is_file()
                record["existed_before"] = existed

                # Full-snapshot Upgrade packages describe the desired managed-runtime
                # state.  'new' versus 'replace' is therefore advisory: local history
                # retention or a previous repair may legitimately change existence.
                # Resolve against the actual live tree and journal the decision so
                # rollback remains exact instead of rejecting a safe package.
                if requested_action == "delete":
                    resolved_action = "delete" if existed else "noop_delete"
                else:
                    resolved_action = "replace" if existed else "new"
                record["resolved_action"] = resolved_action
                if requested_action != resolved_action and not (requested_action == "delete" and resolved_action == "noop_delete"):
                    reconciled.append({
                        "path": relative_name,
                        "requested": requested_action,
                        "resolved": resolved_action,
                    })

                if existed:
                    backup_path = path_under(self.backup_dir, relative_name)
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup_path)
                    record["backup_path"] = str(backup_path.relative_to(self.directory).as_posix())
                    record["old_sha256"] = sha256_file(target)

                if requested_action != "delete":
                    staged_path = path_under(self.staging_dir, relative_name)
                    staged_path.parent.mkdir(parents=True, exist_ok=True)
                    data = archive.read(relative_name)
                    staged_path.write_bytes(data)
                    actual_sha = sha256_file(staged_path)
                    if actual_sha != record["sha256"] or staged_path.stat().st_size != int(record["size"]):
                        raise ValueError(f"Staged Upgrade file failed revalidation: {relative_name}")
                staged_records.append(record)

        metadata["files"] = staged_records
        metadata["action_reconciliations"] = reconciled
        metadata["prepared"] = True
        self.write_metadata(metadata)
        if log_event:
            log_event("package_staged", {
                "transaction_id": metadata["transaction_id"],
                "file_count": len(staged_records),
                "action_reconciliations": reconciled,
            })

    def commit(self, log_event: MetadataLogger | None = None) -> dict[str, Any]:
        metadata = self.read_metadata()
        if not metadata.get("prepared"):
            raise RuntimeError("Upgrade transaction is not fully prepared")
        metadata = self.update_state(
            "committing",
            extra={"commit_started": True, "commit_completed": False, "changed_files": []},
        )
        base_dir = Path(metadata["base_dir"]).resolve()
        changed: list[str] = []
        unchanged: list[str] = []
        try:
            for record in metadata["files"]:
                relative_name = record["path"]
                action = str(record.get("resolved_action") or record.get("action") or "replace")
                target = path_under(base_dir, relative_name)

                if action == "noop_delete":
                    unchanged.append(relative_name)
                    continue
                if action == "delete":
                    if target.exists():
                        if not target.is_file():
                            raise ValueError(f"Upgrade delete target is not a file: {relative_name}")
                        target.unlink()
                        changed.append(relative_name)
                        metadata["changed_files"] = list(changed)
                        self.write_metadata(metadata)
                    else:
                        unchanged.append(relative_name)
                    continue

                staged_path = path_under(self.staging_dir, relative_name)
                if not staged_path.is_file():
                    raise ValueError(f"Staged Upgrade file is missing: {relative_name}")
                if sha256_file(staged_path) != record["sha256"]:
                    raise ValueError(f"Staged Upgrade file hash changed: {relative_name}")

                if target.is_file() and sha256_file(target) == record["sha256"]:
                    unchanged.append(relative_name)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + f".ls-update-{os.getpid()}.tmp")
                shutil.copy2(staged_path, temporary)
                os.replace(temporary, target)
                if sha256_file(target) != record["sha256"]:
                    raise ValueError(f"Installed Upgrade file hash mismatch: {relative_name}")
                changed.append(relative_name)
                # Persist after every live mutation. If power/process loss occurs,
                # recovery knows exactly which paths may need restoration.
                metadata["changed_files"] = list(changed)
                self.write_metadata(metadata)
        except Exception:
            self.rollback(log_event=log_event)
            raise

        metadata = self.update_state(
            "restarting",
            extra={
                "changed_files": changed,
                "unchanged_files": unchanged,
                "commit_completed": True,
            },
        )
        if log_event:
            log_event("files_committed", {
                "transaction_id": metadata["transaction_id"],
                "changed_files": changed,
                "unchanged_files": unchanged,
            })
        return metadata

    def _prepared_records_are_durable(self, metadata: dict[str, Any]) -> bool:
        return bool(metadata.get("prepared"))

    def rollback(self, log_event: MetadataLogger | None = None) -> dict[str, Any]:
        metadata = self.read_metadata()
        state_before = str(metadata.get("state") or "")
        changed_names = {str(value) for value in (metadata.get("changed_files") or []) if str(value)}
        prepared = self._prepared_records_are_durable(metadata)
        # Current bootstrapper_v2 transactions carry explicit durable commit flags.
        # Lifecycle state names are never treated as evidence that live bytes changed.
        commit_evidence = (
            bool(metadata.get("commit_started"))
            or bool(metadata.get("commit_completed"))
            or bool(changed_names)
        )

        if not prepared:
            # Critical invariant: an incomplete preparation has never intentionally
            # mutated live runtime bytes. Never interpret default existed_before=False
            # rows as permission to delete current files.
            metadata = self.update_state(
                "failed",
                error=str(metadata.get("error") or "Upgrade preparation was incomplete; live tree was not changed"),
                extra={"rollback_skipped": "preparation_not_durable"},
            )
            self.cleanup_payload()
            if log_event:
                log_event("rollback_skipped_no_live_changes", {
                    "transaction_id": metadata.get("transaction_id"),
                    "state_before": state_before,
                })
            return metadata

        if not commit_evidence:
            metadata = self.update_state(
                "failed",
                error=str(metadata.get("error") or "Upgrade stopped before live commit"),
                extra={"rollback_skipped": "commit_not_started"},
            )
            self.cleanup_payload()
            if log_event:
                log_event("rollback_skipped_no_live_changes", {
                    "transaction_id": metadata.get("transaction_id"),
                    "state_before": state_before,
                })
            return metadata

        metadata = self.update_state("rolling_back")
        base_dir = Path(metadata["base_dir"]).resolve()
        errors: list[str] = []

        # The root launch contract is outside the managed App package, but it is
        # still part of this Upgrade transaction. If publication started and the
        # transaction did not complete, restore the captured root bytes before
        # restarting the previous runtime. This also closes the crash/power-loss
        # window between individual atomic root writes.
        operator_snapshot = metadata.get("operator_contract_snapshot")
        operator_started = bool(metadata.get("operator_contract_commit_started"))
        operator_restored = bool(metadata.get("operator_contract_restored"))
        if isinstance(operator_snapshot, dict) and operator_started and not operator_restored:
            try:
                restore_operator_launch_contract(base_dir, self.directory, operator_snapshot)
                metadata = self.update_state(
                    "rolling_back",
                    extra={
                        "operator_contract_applied": False,
                        "operator_contract_restored": True,
                    },
                )
                if log_event:
                    log_event("operator_launch_contract_rollback_completed", {
                        "transaction_id": metadata.get("transaction_id"),
                    })
            except Exception as exc:
                errors.append(f"operator_launch_contract: {exc}")

        records = list(metadata.get("files") or [])
        # Close the tiny crash/power-loss window between an atomic live mutation and
        # persisting changed_files.  For a fully prepared transaction with commit
        # evidence, infer only mutations that are cryptographically demonstrable from
        # the current target state. This keeps recovery conservative while allowing a
        # just-written-but-not-yet-journaled path to be restored safely.
        effective_changed_names = set(changed_names)
        if commit_evidence:
            for record in records:
                relative_name = str(record.get("path") or "")
                if not relative_name or relative_name in effective_changed_names:
                    continue
                try:
                    target = path_under(base_dir, relative_name)
                    existed_before = bool(record.get("existed_before"))
                    resolved_action = str(record.get("resolved_action") or record.get("action") or "replace")
                    expected_new = str(record.get("sha256") or "")
                    expected_old = str(record.get("old_sha256") or "")
                    if resolved_action == "delete":
                        if existed_before and not target.exists():
                            effective_changed_names.add(relative_name)
                        continue
                    if not target.is_file() or not expected_new:
                        continue
                    current_sha = sha256_file(target)
                    if current_sha != expected_new:
                        continue
                    if not existed_before or not expected_old or expected_old != expected_new:
                        effective_changed_names.add(relative_name)
                except Exception:
                    # Inference is best-effort. Ambiguous paths remain untouched and
                    # normal rollback validation below handles journaled mutations.
                    continue

        for record in reversed(records):
            relative_name = str(record.get("path") or "")
            if not relative_name:
                continue
            # Restore only durably journaled or cryptographically inferred mutations.
            if relative_name not in effective_changed_names:
                continue
            try:
                target = path_under(base_dir, relative_name)
                existed_before = bool(record.get("existed_before"))
                if existed_before:
                    backup_relative = str(record.get("backup_path") or "")
                    if not backup_relative:
                        raise ValueError("Backup metadata is missing")
                    backup_path = path_under(self.directory, backup_relative)
                    if not backup_path.is_file():
                        raise ValueError("Backup file is missing")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temporary = target.with_name(target.name + f".ls-rollback-{os.getpid()}.tmp")
                    shutil.copy2(backup_path, temporary)
                    os.replace(temporary, target)
                    expected_old = str(record.get("old_sha256") or "")
                    if expected_old and sha256_file(target) != expected_old:
                        raise ValueError("Restored file hash mismatch")
                elif target.exists():
                    # Never delete an unrelated file created outside the transaction.
                    # For a new path, remove it only if it matches the package bytes.
                    expected_new = str(record.get("sha256") or "")
                    if target.is_file() and expected_new and sha256_file(target) == expected_new:
                        target.unlink()
                    elif effective_changed_names:
                        raise ValueError("New Upgrade target no longer matches installed content")
            except Exception as exc:  # keep restoring the remaining files
                errors.append(f"{relative_name}: {exc}")

        state = "failed" if errors else "rolled_back"
        metadata = self.update_state(state, error="; ".join(errors))
        if log_event:
            log_event("rollback_failed" if errors else "rollback_completed", {
                "transaction_id": metadata.get("transaction_id"),
                "errors": errors,
                "changed_files": sorted(effective_changed_names),
            })
        if errors:
            raise RuntimeError("Upgrade rollback was incomplete: " + "; ".join(errors))
        self.cleanup_payload()
        return metadata

    def mark_verifying(self, child_pid: int) -> dict[str, Any]:
        return self.update_state("verifying", extra={"new_process_id": int(child_pid)})

    def mark_completed(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.update_state("completed", extra={"verification": payload or {}})

    def cleanup_payload(self) -> None:
        """Remove staging and backup bytes while preserving the authoritative receipt."""
        for folder in (self.staging_dir, self.backup_dir, self.candidate_dir):
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)


def find_transactions(transaction_root: Path) -> list[UpgradeTransaction]:
    root = Path(transaction_root)
    if not root.is_dir():
        return []
    result: list[UpgradeTransaction] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.is_dir() and (child / UpgradeTransaction.METADATA_NAME).is_file():
            try:
                result.append(UpgradeTransaction.load(child))
            except Exception:
                continue
    return result


def recover_transactions(
    *,
    transaction_root: Path,
    running_version: str,
    log_event: MetadataLogger | None = None,
) -> list[dict[str, Any]]:
    """Recover interrupted transactions conservatively.

    Preparation/staging states never mutate the live runtime and therefore must
    never trigger destructive rollback. Only transactions with durable commit
    evidence may restore live files.
    """
    results: list[dict[str, Any]] = []
    for transaction in find_transactions(transaction_root):
        metadata = transaction.read_metadata()
        state = str(metadata.get("state") or "")
        new_version = str(metadata.get("new_version") or "")
        old_version = str(metadata.get("old_version") or "")
        if state in {"completed", "rolled_back", "failed"}:
            continue

        try:
            running_is_newer = bool(new_version) and parse_version(running_version) > parse_version(new_version)
        except Exception:
            running_is_newer = False
        if running_is_newer:
            transaction.update_state(
                "failed",
                error=f"Superseded by already running {running_version}",
            )
            transaction.cleanup_payload()
            results.append({
                "transaction_id": metadata.get("transaction_id"),
                "action": "superseded",
                "state": "failed",
                "running_version": running_version,
                "transaction_version": new_version,
            })
            continue

        prepared = transaction._prepared_records_are_durable(metadata)
        changed_files = [str(value) for value in (metadata.get("changed_files") or []) if str(value)]
        commit_evidence = (
            bool(metadata.get("commit_started"))
            or bool(metadata.get("commit_completed"))
            or bool(changed_files)
        )

        if not prepared or not commit_evidence:
            # Any hardened transaction without durable commit evidence is safe to
            # discard regardless of its lifecycle label. This covers crashes after
            # the coordinator announced restarting but before the bootstrapper began
            # live commit, without interpreting state text as permission to restore.
            # This is the critical guard
            # against old partial transaction.json files deleting a healthy runtime.
            cleaned = transaction.rollback(log_event=log_event)
            results.append({
                "transaction_id": metadata.get("transaction_id"),
                "action": "discard_uncommitted",
                "state": cleaned.get("state"),
            })
            continue

        if state in {"restarting", "verifying"} and running_version == new_version:
            transaction.update_state("verifying")
            results.append({
                "transaction_id": metadata.get("transaction_id"),
                "action": "continue_verification",
                "state": "verifying",
            })
            continue

        # If the old version is running (or the target did not become authoritative),
        # a committed transaction is rolled back using its durable backup/journal.
        try:
            rolled_back = transaction.rollback(log_event=log_event)
            restart_needed = bool(old_version) and running_version != old_version
            results.append({
                "transaction_id": metadata.get("transaction_id"),
                "action": "restart_previous" if restart_needed else "rollback_confirmed",
                "restart_path": str(Path(metadata["base_dir"]) / metadata["old_entrypoint"]) if restart_needed else "",
                "state": rolled_back.get("state"),
            })
        except Exception as exc:
            results.append({
                "transaction_id": metadata.get("transaction_id"),
                "action": "recovery_failed",
                "error": str(exc),
            })
    return results
