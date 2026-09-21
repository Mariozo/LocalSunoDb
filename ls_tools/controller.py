from ls_core.runtime import *
from ls_tools.launcher import (
    create_localsunodb_launcher_shortcut,
    open_localsunodb_pwa_install_page,
    record_localsunodb_app_session,
    start_localsunodb_backend_restart_helper,
)


class ToolsControllerMixin:
    def handle_lifecycle_post_request(self, path, parsed):
        if path == "/ls-tools/create-launcher-shortcut":
            self.create_ls_launcher_shortcut()
            return
        if path == "/ls-tools/open-pwa-install":
            self.open_ls_pwa_install()
            return
        if path == "/ls-lifecycle/app-session":
            self.record_ls_app_session()
            return
        if path == "/ls-lifecycle/restart-backend":
            self.restart_ls_backend_runtime()
            return
        if path != "/ls-lifecycle/shutdown":
            return False
        self.shutdown_ls_runtime()
        return


    def record_ls_app_session(self):
        origin = str(self.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = {
            f"http://{HOST}:{PORT}",
            f"http://localhost:{PORT}",
        }
        if origin not in allowed_origins:
            self.send_json_response({"ok": False, "error": "LS app session accepts only this local LocalSunoDb."}, status=403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > 512:
            self.send_json_response({"ok": False, "error": "Invalid LS app session request."}, status=400)
            return
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
        session_id = str(params.get("session_id", [""])[0] or "").strip()
        event = str(params.get("event", [""])[0] or "").strip()
        if not session_id or len(session_id) > 128:
            self.send_json_response({"ok": False, "error": "Invalid LS app session id."}, status=400)
            return
        try:
            payload = record_localsunodb_app_session(session_id, event)
        except ValueError as exc:
            self.send_json_response({"ok": False, "error": str(exc)}, status=400)
            return
        self.send_json_response(payload, cache_control="no-store, no-cache, must-revalidate, max-age=0")

    def open_ls_pwa_install(self):
        origin = str(self.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = {
            f"http://{HOST}:{PORT}",
            f"http://localhost:{PORT}",
        }
        if origin not in allowed_origins:
            self.send_json_response(
                {"ok": False, "error": "LS instalēšanas lapu drīkst atvērt tikai no šī lokālā LocalSunoDb."},
                status=403,
            )
            return
        try:
            payload = open_localsunodb_pwa_install_page()
            self.send_json_response(payload)
        except Exception as exc:
            log_ls_exception(
                "tools",
                "open_pwa_install",
                exc,
                include_traceback=True,
            )
            self.send_json_response(
                {"ok": False, "error": f"LocalSunoDb instalēšanas lapu neizdevās atvērt: {exc}"},
                status=500,
            )

    def create_ls_launcher_shortcut(self):
        origin = str(self.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = {
            f"http://{HOST}:{PORT}",
            f"http://localhost:{PORT}",
        }
        if origin not in allowed_origins:
            self.send_json_response(
                {"ok": False, "error": "LocalSunoDb saīsni drīkst izveidot tikai no šī lokālā LS."},
                status=403,
            )
            return
        try:
            payload = create_localsunodb_launcher_shortcut()
            status = 200 if payload.get("ok") else 409
            self.send_json_response(payload, status=status)
        except Exception as exc:
            log_ls_exception(
                "tools",
                "create_launcher_shortcut",
                exc,
                include_traceback=True,
            )
            self.send_json_response(
                {"ok": False, "error": str(exc)},
                status=500,
            )

    def restart_ls_backend_runtime(self):
        """Restart the backend from the current files without restarting Windows."""
        origin = str(self.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = {
            f"http://{HOST}:{PORT}",
            f"http://localhost:{PORT}",
        }
        if origin not in allowed_origins:
            self.send_json_response(
                {"ok": False, "error": "LS backend restart accepts only this local LocalSunoDb."},
                status=403,
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length < 0 or length > 256:
            self.send_json_response(
                {"ok": False, "error": "Invalid LS backend restart request."},
                status=400,
            )
            return
        if length:
            self.rfile.read(length)

        current_pid = os.getpid()
        self.send_json_response({
            "ok": True,
            "restarting": True,
            "process_id": current_pid,
        })

        def restart_later():
            # Give the HTTP response time to reach the PWA before the helper
            # terminates this backend process.
            time.sleep(0.35)
            try:
                start_localsunodb_backend_restart_helper()
            except Exception as exc:
                try:
                    log_ls_exception(
                        "backend_restart",
                        "spawn_helper",
                        exc,
                        {"process_id": current_pid},
                        include_traceback=True,
                    )
                except Exception:
                    pass

        threading.Thread(
            target=restart_later,
            name="ls-backend-restart-request",
            daemon=True,
        ).start()

    def shutdown_ls_runtime(self):
        """Gracefully stop the one local LS backend from the LS UI."""
        origin = str(self.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = {
            f"http://{HOST}:{PORT}",
            f"http://localhost:{PORT}",
        }
        if origin not in allowed_origins:
            self.send_json_response({"ok": False, "error": "LS shutdown accepts only this local LocalSunoDb."}, status=403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length < 0 or length > 256:
            self.send_json_response({"ok": False, "error": "Invalid LS shutdown request."}, status=400)
            return
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
        if str(params.get("confirm", [""])[0]) != "1":
            self.send_json_response({"ok": False, "error": "LS shutdown confirmation is required."}, status=400)
            return
        server = RUNTIME_STATE.get("active_http_server")
        if server is None:
            self.send_json_response({"ok": False, "error": "LocalSunoDb server is not active."}, status=409)
            return
        RUNTIME_STATE["shutdown_reason"] = "user"
        self.send_json_response({"ok": True, "stopping": True, "process_id": os.getpid()})

        def shutdown_later():
            time.sleep(0.15)
            try:
                server.shutdown()
            except Exception:
                pass

        threading.Thread(target=shutdown_later, name="ls-user-shutdown", daemon=True).start()

    def ls_comparison_versions(self):
        try:
            self.send_json_response(get_ls_comparison_payload())
        except Exception as exc:
            log_ls_exception(
                "comparison",
                "list_versions",
                exc,
                include_traceback=True,
            )
            self.send_json_response(
                {"ok": False, "error": "Salīdzināšanas versijas neizdevās ielādēt. Diagnostika saglabāta LS žurnālā."},
                status=400,
            )

    def launch_ls_comparison(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > 4096:
                raise ValueError("LS salīdzināšanas pieprasījums ir pārāk liels")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            version = str(params.get("version", [""])[0] or "").strip()
            running = launch_ls_comparison(version)
            payload = get_ls_comparison_payload()
            payload["running"] = running
            self.send_json_response(payload)
        except Exception as exc:
            log_ls_exception(
                "comparison",
                "launch_version",
                exc,
                include_traceback=True,
            )
            self.send_json_response(
                {"ok": False, "error": "Salīdzinājumu neizdevās palaist. Diagnostika saglabāta LS žurnālā."},
                status=400,
            )

    def stop_ls_comparison(self):
        try:
            stop_ls_comparison()
            self.send_json_response(get_ls_comparison_payload())
        except Exception as exc:
            log_ls_exception(
                "comparison",
                "stop_version",
                exc,
                include_traceback=True,
            )
            self.send_json_response(
                {"ok": False, "error": "Salīdzinājumu neizdevās apturēt. Diagnostika saglabāta LS žurnālā."},
                status=400,
            )

    def refresh_db_and_redirect(self, params):
        query = params.get("q", [""])[0]
        style_query = params.get("style_q", [""])[0]
        workspace = params.get("workspace", [])
        workspace_mode = params.get("workspace_mode", ["or"])[0]
        category_filter = params.get("category_filter", [])
        category_mode = params.get("category_mode", ["or"])[0]
        local_family_filter = params.get("local_family_filter", [])
        kind_filter = params.get("kind_filter", [""])[0]
        local_audio_filter = params.get("local_audio_filter", [""])[0]

        ok, output = run_refresh_db()

        if not ok:
            self.send_refresh_error(output)
            return

        redirect_params = {
            "q": query,
            "style_q": style_query,
            "workspace": workspace,
            "workspace_mode": workspace_mode,
            "category_filter": category_filter,
            "category_mode": category_mode,
            "local_family_filter": local_family_filter,
            "kind_filter": kind_filter,
            "local_audio_filter": local_audio_filter,
            "sort_by": params.get("sort_by", [""])[0],
            "sort_dir": params.get("sort_dir", ["asc"])[0],
            "search_name": params.get("search_name", ["1"])[0],
            "search_lyrics": params.get("search_lyrics", ["0"])[0],
            "search_prompt": params.get("search_prompt", ["0"])[0],
            "db_refresh": "ok",
        }

        query_string = urllib.parse.urlencode(redirect_params, doseq=True)
        self.send_redirect("/?" + query_string)

    def send_refresh_error(self, output):
        content = f"""
        <!doctype html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>LocalSunoDb refresh error</title>
            <style>
                body {{
                    font-family: Segoe UI, Arial, sans-serif;
                    margin: 24px;
                }}

                pre {{
                    background: #f4f4f4;
                    border: 1px solid #ccc;
                    padding: 14px;
                    white-space: pre-wrap;
                }}

                a {{
                    display: inline-block;
                    margin-top: 12px;
                    color: #1a73e8;
                }}
            </style>
        </head>
        <body>
            <h2>Refresh DB failed</h2>
            <p>Check this output:</p>
            <pre>{esc(output)}</pre>
            <p><a href="/">Back to LocalSunoDb</a></p>
        </body>
        </html>
        """.encode("utf-8")

        self.send_html(content)

    def edit_suno_audio(self, audio_url, track_id, title):
        # v3.59 safety: Edit must not create edit_cache MP3 automatically.
        # It opens only the real linked local WAV/MP3. Temporary MP3 creation remains
        # available only through the explicit row-menu command.
        track_id = urllib.parse.unquote(track_id or "")

        if not track_id:
            self.send_text_response(400, "Missing Track ID")
            return

        try:
            local_path = get_best_local_audio_path_for_track(track_id)
            if not local_path:
                self.send_text_response(
                    404,
                    "Šim ierakstam LS nav atrasts piesaistīts īsts lokāls WAV/MP3 fails. Edit neveido pagaidu edit_cache MP3 automātiski."
                )
                return

            if not os.path.exists(local_path):
                self.send_text_response(404, f"Linked local file not found: {local_path}")
                return

            open_file_in_audio_editor(local_path)
            send_no_content(self)
        except Exception as e:
            content = f"Could not open linked local audio in editor: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def cache_suno_audio_path(self, audio_url, track_id, title):
        audio_url = urllib.parse.unquote(audio_url or "")
        track_id = urllib.parse.unquote(track_id or "")
        title = urllib.parse.unquote(title or "")

        if not audio_url:
            self.send_text_response(400, "Missing Suno audio URL")
            return

        try:
            local_path = download_suno_audio_for_edit(track_id, audio_url, title)
            self.send_text_response(200, str(local_path))
        except Exception as e:
            self.send_text_response(500, f"Could not cache Suno audio: {e}")


