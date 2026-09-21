from ls_core.runtime import *
from ls_downloader.token_bridge_liveness import ensure_token_bridge_liveness_files


class DownloaderControllerMixin:
    def handle_suno_workflow_get_request(self, path, params):
        """Serve Suno preview, audit, and refresh workflow endpoints."""
        if path == "/suno-meta-preview":
            track_id = params.get("track_id", [""])[0]
            self.send_suno_meta_preview(track_id)
            return

        if path == "/suno-update-preview":
            self.send_suno_update_preview()
            return

        if path == "/suno-structured-repair-preview":
            try:
                self.send_json_response(build_ls_structured_repair_preview())
            except Exception as exc:
                self.send_json_response(
                    {"ok": False, "error": str(exc)},
                    status=500,
                )
            return

        if path == "/ls-intent-audit-preview":
            try:
                self.send_json_response(build_ls_intent_audit_preview())
            except Exception as exc:
                self.send_json_response(
                    {"ok": False, "error": str(exc)},
                    status=500,
                )
            return

        if path == "/ls-category-assignment-preview":
            try:
                self.send_json_response(build_ls_category_assignment_preview())
            except Exception as exc:
                self.send_json_response(
                    {"ok": False, "error": str(exc)},
                    status=500,
                )
            return

        if path == "/suno-tracklist-preview":
            limit_value = params.get("limit", ["100"])[0]
            workspace_id = params.get("workspace_id", ["latest"])[0]
            self.send_suno_tracklist_preview(limit_value, workspace_id)
            return

        if path == "/refresh-db":
            self.refresh_db_and_redirect(params)
            return

        return False

    def handle_suno_workflow_post_request(self, path, parsed):
        """Handle Downloader/Suno workflow POST endpoints."""
        if path == "/preview-selected-wav-download":
            self.preview_selected_wav_download()
            return

        if path == "/download-selected-wav":
            self.download_selected_wav()
            return

        if path == "/suno-refresh-selected-metadata":
            self.suno_refresh_selected_metadata()
            return

        if path == "/suno-start-full-metadata-backfill":
            self.suno_start_full_metadata_backfill()
            return

        if path == "/suno-apply-structured-repair":
            try:
                self.send_json_response(apply_ls_structured_repair())
            except Exception as exc:
                self.send_json_response(
                    {"ok": False, "error": str(exc)},
                    status=500,
                )
            return

        if path == "/ls-intent-audit-apply":
            params = urllib.parse.parse_qs(parsed.query)
            expected_signature = params.get("signature", [""])[0]
            try:
                self.send_json_response(
                    apply_ls_intent_audit(expected_signature)
                )
            except Exception as exc:
                self.send_json_response(
                    {"ok": False, "error": str(exc)},
                    status=500,
                )
            return

        if path == "/ls-category-assignment-apply":
            params = urllib.parse.parse_qs(parsed.query)
            expected_signature = params.get("signature", [""])[0]
            try:
                self.send_json_response(
                    apply_ls_category_assignment(expected_signature)
                )
            except Exception as exc:
                self.send_json_response(
                    {"ok": False, "error": str(exc)},
                    status=500,
                )
            return

        if path == "/suno-import-selected-tracklist":
            self.suno_import_selected_tracklist()
            return

        if path == "/suno-ignore-selected-tracklist":
            self.suno_ignore_selected_tracklist()
            return

        if path == "/suno-restore-ignored-tracklist":
            self.suno_restore_ignored_tracklist()
            return

        if path == "/suno-update-selected-titles":
            self.suno_update_selected_titles()
            return

        return False

    def bridge_ping(self):
        try:
            length = int(
                self.headers.get("Content-Length", "0") or "0"
            )
            raw_body = self.rfile.read(length).decode(
                "utf-8",
                errors="replace",
            )
            params = urllib.parse.parse_qs(raw_body)
            version = params.get("extension_version", [""])[0]
            previous_worker_error = params.get(
                "previous_worker_error",
                [""],
            )[0]
            updates = {
                "last_seen": now_iso_local(),
                "last_error": "",
                "extension_version": str(version or "")[:40],
            }
            if previous_worker_error:
                updates.update({
                    "previous_worker_error": str(previous_worker_error)[:240],
                    "last_recovered_at": now_iso_local(),
                })
            state = set_token_bridge_state(
                **updates,
            )
            self.send_json_response({
                "ok": True,
                "extension_version": version,
                "last_seen": state.get("last_seen") or "",
            })
        except Exception as exc:
            set_token_bridge_state(last_error=str(exc))
            self.send_json_response(
                {"ok": False, "error": str(exc)},
                status=400,
            )

    def bridge_diagnostic(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > 65536:
                raise ValueError("Token Bridge diagnostikas dati ir pārāk lieli")
            raw_body = self.rfile.read(length).decode(
                "utf-8",
                errors="replace",
            )
            params = urllib.parse.parse_qs(
                raw_body,
                keep_blank_values=True,
            )
            diagnostic_text = params.get("diagnostic_json", ["{}"])[0]
            extension_version = params.get("extension_version", [""])[0]
            diagnostic = json.loads(diagnostic_text or "{}")
            state = update_token_bridge_diagnostic(
                diagnostic,
                extension_version=extension_version,
            )
            self.send_json_response({
                "ok": True,
                "diagnostic_last_seen": state.get("diagnostic_last_seen") or "",
                "fetch_hook_active": bool(state.get("fetch_hook_active")),
                "fetch_repair_count": int(state.get("fetch_repair_count") or 0),
            })
        except Exception as exc:
            set_token_bridge_state(last_error=str(exc)[:240])
            self.send_json_response(
                {"ok": False, "error": str(exc)},
                status=400,
            )

    def save_downloader_state(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body)
            state_json = params.get("state_json", ["{}"])[0]
            state = json.loads(state_json or "{}")
            result = save_downloader_state(state)
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def clear_downloader_state(self):
        result = clear_downloader_state()
        self.send_json_response(result)

    def bridge_set_suno_api_token(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        token = params.get("suno_api_token", [""])[0]
        extension_version = params.get("extension_version", [""])[0]
        capture_source = params.get("capture_source", [""])[0]
        page_instance_id = params.get("page_instance_id", [""])[0]
        ok, message = set_suno_api_token(token, source="Chrome Token Bridge")
        received_at = now_iso_local()
        state = set_token_bridge_state(
            last_seen=received_at,
            last_token_at=received_at,
            relay_last_seen=received_at,
            last_error="",
            extension_version=str(extension_version or ""),
            last_capture_source=str(capture_source or ""),
            last_token_page_instance_id=str(page_instance_id or "")[:240],
        )
        content = json.dumps({
            "ok": ok,
            "message": message,
            "last_seen": state.get("last_seen") or "",
            "extension_version": state.get("extension_version") or "",
            "capture_source": state.get("last_capture_source") or "",
        }, ensure_ascii=False).encode("utf-8")
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def suno_refresh_selected_metadata(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body)
            ids_text = params.get("track_ids", [""])[0]
            overwrite = normalize_search_scope_flag(params.get("overwrite", ["0"])[0], False)
            track_ids = [x.strip() for x in re.split(r"[\s,;]+", ids_text) if x.strip()]
            result = refresh_suno_metadata_for_track_ids(track_ids, overwrite=overwrite)
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def suno_start_full_metadata_backfill(self):
        try:
            result = start_full_suno_metadata_backfill()
            self.send_json_response(result)
        except Exception as e:
            self.send_json_response({"ok": False, "error": str(e)}, status=400)

    def send_suno_meta_preview(self, track_id):
        try:
            result = build_meta_preview(track_id)
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def send_suno_update_preview(self):
        try:
            result = build_suno_update_preview()
            self.send_json_response(result)
        except Exception as e:
            try:
                result = build_suno_update_preview_fallback(error=str(e))
                self.send_json_response(result)
            except Exception as fallback_error:
                import traceback as _traceback
                content = json.dumps({
                    "ok": False,
                    "error": str(e),
                    "fallback_error": str(fallback_error),
                    "traceback": _traceback.format_exc()[-4000:],
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

    def send_suno_tracklist_preview(self, limit_value="100", workspace_id="default"):
        try:
            try:
                limit = int(limit_value or "100")
            except ValueError:
                limit = 100
            result = build_suno_tracklist_preview(limit=limit, workspace_id=workspace_id or "default")
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def preview_selected_wav_download(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body)
            track_ids_text = params.get("track_ids", [""])[0]
            track_ids = [
                line.strip()
                for line in track_ids_text.replace(",", "\n").splitlines()
                if line.strip()
            ]
            result = build_selected_wav_download_preview(
                track_ids,
                local_family_title=get_local_family_title(),
            )
            self.send_json_response(result, status=200 if result.get("ok") else 400)
        except Exception as e:
            self.send_json_response({"ok": False, "error": str(e)}, status=400)

    def download_selected_wav(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body)
            track_ids_text = params.get("track_ids", [""])[0]
            track_ids = [
                line.strip()
                for line in track_ids_text.replace(",", "\n").splitlines()
                if line.strip()
            ]
            local_family_title = params.get(
                "local_family_title",
                [get_local_family_title()],
            )[0]
            result = download_selected_wavs_to_library(
                track_ids,
                local_family_title=local_family_title,
            )
            if not result.get("ok"):
                content = json.dumps(result, ensure_ascii=False).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def suno_ignore_selected_tracklist(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        track_ids_text = params.get("track_ids", [""])[0]
        track_ids = [line.strip() for line in track_ids_text.replace(",", "\n").splitlines() if line.strip()]

        try:
            result = ignore_suno_tracklist_selected(track_ids)
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def suno_restore_ignored_tracklist(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        track_ids_text = params.get("track_ids", [""])[0]
        track_ids = [
            line.strip()
            for line in track_ids_text.replace(",", "\n").splitlines()
            if line.strip()
        ]

        try:
            result = restore_suno_tracklist_ignored(track_ids)
            self.send_json_response(result)
        except Exception as e:
            self.send_json_response({"ok": False, "error": str(e)}, status=400)

    def suno_update_selected_titles(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        track_ids_text = params.get("track_ids", [""])[0]
        limit_value = params.get("limit", ["100"])[0]
        workspace_id = params.get("workspace_id", ["latest"])[0]
        track_ids = [line.strip() for line in track_ids_text.replace(",", "\n").splitlines() if line.strip()]

        try:
            result = update_selected_suno_titles_from_library(track_ids, limit=limit_value, workspace_id=workspace_id or "latest")
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def suno_import_selected_tracklist(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        track_ids_text = params.get("track_ids", [""])[0]
        limit_value = params.get("limit", ["100"])[0]
        workspace_id = params.get("workspace_id", ["latest"])[0]
        track_ids = [line.strip() for line in track_ids_text.replace(",", "\n").splitlines() if line.strip()]

        try:
            result = import_suno_tracklist_selected(track_ids, limit=limit_value, workspace_id=workspace_id or "latest")
            self.send_json_response(result)
        except Exception as e:
            content = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def set_suno_api_token(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        token = params.get("suno_api_token", [""])[0]
        ok, message = set_suno_api_token(token, source="manual")
        self.send_text_response(200 if ok else 400, message)

    def start_suno_token_renewal(self):
        try:
            result = start_suno_token_renewal()
            liveness = ensure_token_bridge_liveness_files()
            result["token_bridge_liveness"] = liveness
            self.send_json_response(
                result,
                status=200 if result.get("ok") else 400,
            )
        except Exception as exc:
            self.send_json_response(
                {"ok": False, "error": str(exc)},
                status=500,
            )

    def open_token_bridge_setup(self):
        try:
            result = open_token_bridge_setup()
            liveness = ensure_token_bridge_liveness_files()
            result["token_bridge_liveness"] = liveness
            self.send_json_response(
                result,
                status=200 if result.get("ok") else 400,
            )
        except Exception as exc:
            self.send_json_response(
                {"ok": False, "error": str(exc)},
                status=500,
            )
