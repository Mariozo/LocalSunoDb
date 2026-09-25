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
from ls_web.assets import read_static_asset
from ls_library.controller import LibraryControllerMixin
from ls_downloader.controller import DownloaderControllerMixin
from ls_audio.controller import AudioControllerMixin
from ls_media.controller import MediaControllerMixin
from ls_stems.controller import StemsControllerMixin
from ls_tools.controller import ToolsControllerMixin
from ls_web.settings_controller import SettingsControllerMixin
from ls_web.upgrade_controller import UpgradeControllerMixin
from ls_web.elza_controller import ElzaControllerMixin
from ls_web.support_controller import SupportControllerMixin
from ls_web.response_controller import ResponseControllerMixin
from ls_web.workflow_controller import WorkflowControllerMixin

class LocalSunoDbHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if exc is None:
            return
        connection_error = isinstance(
            exc,
            (ConnectionAbortedError, BrokenPipeError, ConnectionResetError),
        )
        log_ls_exception(
            "http_server",
            "handle_request",
            exc,
            {"client_address": list(client_address or [])},
            include_traceback=not connection_error,
        )
        if connection_error:
            return
        super().handle_error(request, client_address)

class LocalSunoDbHandler(LibraryControllerMixin, DownloaderControllerMixin, MediaControllerMixin, AudioControllerMixin, StemsControllerMixin, ToolsControllerMixin, SettingsControllerMixin, UpgradeControllerMixin, ElzaControllerMixin, SupportControllerMixin, ResponseControllerMixin, WorkflowControllerMixin, BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def handle_pwa_get_request(self, path, params):
        """Serve the installable LocalSunoDb Web App shell resources."""
        if path == "/manifest.webmanifest":
            payload = (APP_DIR / "ls_web" / "static" / "manifest.webmanifest").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            self._write_response_body(payload, "pwa_manifest")
            return

        if path == "/ls-pwa-sw.js":
            payload = (APP_DIR / "ls_web" / "static" / "ls_pwa_sw.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("Service-Worker-Allowed", "/")
            self.end_headers()
            self._write_response_body(payload, "pwa_service_worker")
            return

        if path in {"/ls-pwa-start", "/sf-pwa-start"}:
            self.send_redirect("/")
            return

        if path == "/ls-pwa-install":
            template = (APP_DIR / "ls_web" / "templates" / "pwa_install.html").read_text(encoding="utf-8")
            self.send_html(template.replace("@@LS_VERSION@@", APP_VERSION))
            return

        return False

    def handle_page_get_request(self, path, params):
        """Render top-level LocalSunoDb pages and lazy Library row chunks."""
        if path == "/playlists":
            playlist_id = params.get("id", [""])[0]
            add_track_id = params.get("add_track", [""])[0]
            save_last_view_url(self.path)
            self.send_html(render_playlists_page(playlist_id, add_track_id))
            return

        if path == "/library-rows":
            query = params.get("q", [""])[0]
            style_query = params.get("style_q", [""])[0]
            workspace = params.get("workspace", [])
            workspace_mode = params.get("workspace_mode", ["or"])[0]
            category_filter = params.get("category_filter", [])
            category_mode = params.get("category_mode", ["or"])[0]
            local_family_filter = params.get("local_family_filter", [])
            kind_filter = params.get("kind_filter", [""])[0]
            local_audio_filter = params.get("local_audio_filter", [""])[0]
            if params.get("last_imported", [""])[0] == "1":
                kind_filter = "__last_imported__"
            payload = render_library_rows_chunk(
                query=query,
                style_query=style_query,
                workspace=workspace,
                workspace_mode=workspace_mode,
                category_filter=category_filter,
                category_mode=category_mode,
                local_family_filter=local_family_filter,
                kind_filter=kind_filter,
                local_audio_filter=local_audio_filter,
                search_name=params.get("search_name", ["1"])[0],
                search_lyrics=params.get("search_lyrics", ["0"])[0],
                search_prompt=params.get("search_prompt", ["0"])[0],
                search_marks=params.get("search_marks", ["0"])[0],
                search_tags=params.get("search_tags", ["0"])[0],
                flag_filter=params.get("flag_filter", [""])[0],
                tag_filter=params.get("tag_filter", [""])[0],
                track_ids_filter=params.get("track_ids", [""])[0],
                sort_by=params.get("sort_by", [""])[0],
                sort_dir=params.get("sort_dir", ["asc"])[0],
                cursor=params.get("cursor", [""])[0],
                index_start=params.get("index_start", ["0"])[0],
                batch_size=params.get("batch", ["40"])[0],
            )
            self.send_json_response(
                payload,
                cache_control="no-store, no-cache, must-revalidate, max-age=0",
            )
            return

        if path == "/library-count":
            query = params.get("q", [""])[0]
            style_query = params.get("style_q", [""])[0]
            workspace = params.get("workspace", [])
            workspace_mode = params.get("workspace_mode", ["or"])[0]
            category_filter = params.get("category_filter", [])
            category_mode = params.get("category_mode", ["or"])[0]
            local_family_filter = params.get("local_family_filter", [])
            kind_filter = params.get("kind_filter", [""])[0]
            local_audio_filter = params.get("local_audio_filter", [""])[0]
            if params.get("last_imported", [""])[0] == "1":
                kind_filter = "__last_imported__"
            payload = render_library_result_count(
                query=query,
                style_query=style_query,
                workspace=workspace,
                workspace_mode=workspace_mode,
                category_filter=category_filter,
                category_mode=category_mode,
                local_family_filter=local_family_filter,
                kind_filter=kind_filter,
                local_audio_filter=local_audio_filter,
                search_name=params.get("search_name", ["1"])[0],
                search_lyrics=params.get("search_lyrics", ["0"])[0],
                search_prompt=params.get("search_prompt", ["0"])[0],
                search_marks=params.get("search_marks", ["0"])[0],
                search_tags=params.get("search_tags", ["0"])[0],
                flag_filter=params.get("flag_filter", [""])[0],
                tag_filter=params.get("tag_filter", [""])[0],
                track_ids_filter=params.get("track_ids", [""])[0],
            )
            self.send_json_response(
                payload,
                cache_control="no-store, no-cache, must-revalidate, max-age=0",
            )
            return

        if path == "/":
            # v4.66: remember the exact current Database view, including filters/search/row count.
            save_last_view_url(self.path)
            query = params.get("q", [""])[0]
            style_query = params.get("style_q", [""])[0]
            workspace = params.get("workspace", [])
            workspace_mode = params.get("workspace_mode", ["or"])[0]
            category_filter = params.get("category_filter", [])
            category_mode = params.get("category_mode", ["or"])[0]
            local_family_filter = params.get("local_family_filter", [])
            kind_filter = params.get("kind_filter", [""])[0]
            local_audio_filter = params.get("local_audio_filter", [""])[0]
            if params.get("last_imported", [""])[0] == "1":
                kind_filter = "__last_imported__"
            limit_value = "all"
            db_refresh = params.get("db_refresh", [""])[0]
            search_name = params.get("search_name", ["1"])[0]
            search_lyrics = params.get("search_lyrics", ["0"])[0]
            search_prompt = params.get("search_prompt", ["0"])[0]
            search_marks = params.get("search_marks", ["0"])[0]
            search_tags = params.get("search_tags", ["0"])[0]
            flag_filter = params.get("flag_filter", [""])[0]
            tag_filter = params.get("tag_filter", [""])[0]
            track_ids_filter = params.get("track_ids", [""])[0]
            sort_by = params.get("sort_by", [""])[0]
            sort_dir = params.get("sort_dir", ["asc"])[0]

            self.send_html(render_page(
                query=query,
                style_query=style_query,
                workspace=workspace,
                workspace_mode=workspace_mode,
                category_filter=category_filter,
                category_mode=category_mode,
                local_family_filter=local_family_filter,
                kind_filter=kind_filter,
                local_audio_filter=local_audio_filter,
                limit_value=limit_value,
                db_refresh=db_refresh,
                search_name=search_name,
                search_lyrics=search_lyrics,
                search_prompt=search_prompt,
                search_marks=search_marks,
                search_tags=search_tags,
                flag_filter=flag_filter,
                tag_filter=tag_filter,
                track_ids_filter=track_ids_filter,
                sort_by=sort_by,
                sort_dir=sort_dir,
            ))
            return

        if path == "/downloader":
            # Embedded Imports keeps the already-rendered Library page alive underneath.
            # Do not replace the remembered top-level view merely because the overlay
            # iframe requested its own Imports document.
            embedded_imports = str(params.get("ls_embedded", [""])[0]).strip() == "1"
            if not embedded_imports:
                save_last_view_url("/downloader")
            self.send_html(render_downloader_page())
            return

        return False

    def handle_status_get_request(self, path, params):
        """Serve read-only application and Downloader status endpoints."""
        if path == "/playlists-json":
            self.send_json_response(
                playlists_json_payload(),
                cache_control="no-store, no-cache, must-revalidate, max-age=0",
            )
            return

        if path == "/ls-upgrade/status":
            transaction_id = params.get("transaction_id", [""])[0]
            self.send_json_response(
                get_ls_upgrade_coordinator().status(transaction_id=transaction_id),
                cache_control="no-store, no-cache, must-revalidate, max-age=0",
            )
            return

        if path == "/app-version":
            registry = read_ls_version_registry()
            self.send_json_response({
                "ok": True,
                "app_version": APP_VERSION,
                "running_version": APP_VERSION,
                "app_file": Path(APP_ENTRYPOINT_PATH).name,
                "app_path": str(Path(APP_ENTRYPOINT_PATH).resolve()),
                "process_id": os.getpid(),
                "server_ready": True,
                "database_ready": DB_PATH.is_file(),
                "last_view_url": get_last_view_url(),
                "latest_available": format_ls_minor_version(registry.get("highest_issued")),
                "highest_issued": registry.get("highest_issued"),
                "current_running": registry.get("current_running"),
                "latest_stable": registry.get("latest_stable"),
                "latest_stable_version": format_ls_minor_version(registry.get("latest_stable")),
                "rollback_mode": False,
            }, cache_control="no-store, no-cache, must-revalidate, max-age=0")
            return

        if path == "/downloader-state":
            self.send_json_response(get_downloader_state())
            return

        if path == "/suno-token-status":
            self.send_json_response(get_suno_token_status())
            return

        if path == "/suno-credits-status":
            force = str(params.get("refresh", ["0"])[0]).strip() in {
                "1", "true", "yes"
            }
            payload = get_suno_credits_status(force=force)
            self.send_json_response(
                payload,
                status=200 if payload.get("ok") else 503,
            )
            return

        if path == "/audio-output-state":
            force = str(params.get("refresh", ["0"])[0]).strip() in {
                "1", "true", "yes"
            }
            payload = get_ls_audio_output_state(force=force)
            self.send_json_response(
                payload,
                status=200 if payload.get("ok") else 503,
                cache_control="no-store, no-cache, must-revalidate, max-age=0",
            )
            return

        if path == "/suno-metadata-backfill-status":
            self.send_json_response(get_suno_metadata_job_status())
            return

        if path == "/suno-ignored-tracklist":
            self.send_json_response(get_ignored_suno_tracklist_summary())
            return

        return False


    def handle_media_get_request(self, path, params):
        """Serve local-file, Suno-audio, image, and waveform endpoints."""
        if path == "/open-local":
            local_path = params.get("path", [""])[0]
            self.open_local_file(local_path)
            return

        if path == "/show-local":
            local_path = params.get("path", [""])[0]
            self.show_local_file(local_path)
            return

        if path == "/edit-local":
            local_path = params.get("path", [""])[0]
            self.edit_local_file(local_path)
            return

        if path == "/local-audio-path":
            track_id = params.get("track_id", [""])[0]
            self.send_local_audio_path(track_id)
            return

        if path == "/cache-suno-audio-path":
            audio_url = params.get("audio_url", [""])[0]
            track_id = params.get("track_id", [""])[0]
            title = params.get("title", [""])[0]
            self.cache_suno_audio_path(audio_url, track_id, title)
            return

        if path == "/edit-suno":
            audio_url = params.get("audio_url", [""])[0]
            track_id = params.get("track_id", [""])[0]
            title = params.get("title", [""])[0]
            self.edit_suno_audio(audio_url, track_id, title)
            return

        if path == "/local-audio":
            track_id = params.get("track_id", [""])[0]
            if track_id:
                self.send_local_audio_for_track(track_id)
                return
            local_path = params.get("path", [""])[0]
            self.send_local_audio(local_path)
            return

        if path == "/playback-media":
            track_id = params.get("track_id", [""])[0]
            source = params.get("source", [""])[0]
            self.send_playback_media(track_id, source)
            return

        if path == "/playback-waveform":
            track_id = params.get("track_id", [""])[0]
            source = params.get("source", [""])[0]
            self.send_playback_waveform(track_id, source)
            return

        if path == "/suno-image":
            track_id = params.get("track_id", [""])[0]
            self.send_suno_image_redirect(track_id)
            return

        if path == "/waveform":
            track_id = params.get("track_id", [""])[0]
            audio_url = params.get("audio_url", [""])[0]
            self.send_waveform(track_id, audio_url)
            return

        if path == "/local-waveform":
            local_path = params.get("path", [""])[0]
            self.send_local_waveform(local_path)
            return

        return False



    def handle_support_get_request(self, path, params):
        """Serve settings, stems, help, profile, tags, and track-text endpoints."""
        if path == "/settings-json":
            self.send_settings_json()
            return

        if path == "/fresh-install-state":
            self.send_fresh_install_state()
            return

        if path == "/choose-audio-library-root":
            self.choose_audio_library_root()
            return

        if path == "/choose-stem-root":
            self.choose_stem_root()
            return

        if path == "/choose-stem-folder":
            track_id = params.get("track_id", [""])[0]
            self.choose_stem_folder(track_id)
            return

        if path == "/stems-json":
            track_id = params.get("track_id", [""])[0]
            self.send_stems_json(track_id)
            return

        if path == "/help":
            self.send_help_page()
            return

        if path == "/help-text":
            self.send_help_text()
            return

        if path == "/profile-image":
            self.send_profile_image()
            return

        if path == "/user-tags-json":
            self.send_json_response(get_user_tag_manager_state())
            return

        if path == "/track-text-json":
            track_id = params.get("track_id", [""])[0]
            ok, payload = get_track_text_payload(track_id)
            self.send_json_response(payload, status=200 if ok else 404)
            return

        if path == "/track-lyrics-json":
            track_id = params.get("track_id", [""])[0]
            ok, payload = get_track_lyrics_payload(track_id)
            self.send_json_response(payload, status=200 if ok else 404)
            return

        return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        static_asset = read_static_asset(self.path)
        if static_asset is not None:
            payload, mime = static_asset
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(payload)
            return

        route_handlers = (
            self.handle_pwa_get_request,
            self.handle_page_get_request,
            self.handle_status_get_request,
            self.handle_suno_workflow_get_request,
            self.handle_media_get_request,
            self.handle_support_get_request,
        )
        for route_handler in route_handlers:
            if route_handler(path, params) is not False:
                return

        self.send_error(404, "Not found")






    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        route_handlers = (
            self.handle_lifecycle_post_request,
            self.handle_update_assistant_post_request,
            self.handle_library_post_request,
            self.handle_settings_bridge_post_request,
            self.handle_suno_workflow_post_request,
            self.handle_audio_post_request,
        )
        for route_handler in route_handlers:
            if route_handler(path, parsed) is not False:
                return

        self.send_error(404, "Not found")













































































































    def log_message(self, format, *args):
        return

