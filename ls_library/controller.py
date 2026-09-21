from ls_core.runtime import *


_SAVED_VIEW_REUSABLE_PARAMS = {
    "q",
    "style_q",
    "workspace",
    "workspace_mode",
    "category_filter",
    "category_mode",
    "local_family_filter",
    "kind_filter",
    "local_audio_filter",
    "search_name",
    "search_lyrics",
    "search_prompt",
    "search_marks",
    "search_tags",
    "flag_filter",
    "tag_filter",
    "sort_by",
    "sort_dir",
}


def _saved_view_reusable_query(value):
    """Drop transient URL state before Saved views validates the query."""
    text = str(value or "").strip()
    if "://" in text:
        text = urllib.parse.urlparse(text).query
    text = text.lstrip("?")
    pairs = [
        (key, raw_value)
        for key, raw_value in urllib.parse.parse_qsl(
            text,
            keep_blank_values=False,
        )
        if key in _SAVED_VIEW_REUSABLE_PARAMS
    ]
    return urllib.parse.urlencode(pairs, doseq=True)


class LibraryControllerMixin:
    def scan_local_inventory_now(self):
        try:
            result = scan_local_inventory()
            self.send_json_response(result)
        except Exception as e:
            self.send_json_response({"ok": False, "error": str(e)}, status=500)

    def save_local_family_title_setting(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            value = params.get("local_family_title", [""])[0]
            ok, clean_value = set_local_family_title(value)
            self.send_json_response({
                "ok": ok,
                "local_family_title": clean_value,
            }, status=200 if ok else 400)
        except Exception as e:
            self.send_json_response({"ok": False, "error": str(e)}, status=500)


    def add_local_audio(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        local_path = params.get("path", [""])[0]

        ok, message = add_local_audio_to_track(track_id, local_path)

        if ok:
            content = message.encode("utf-8")
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def delete_local_variant(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        local_path = params.get("path", [""])[0]

        ok, message = delete_local_variant_from_track(track_id, local_path)

        content = str(message or "").encode("utf-8")
        self.send_response(200 if ok else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def delete_local_audio(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        local_path = params.get("path", [""])[0]

        ok, message = delete_local_audio_from_track(track_id, local_path)

        if ok:
            content = message.encode("utf-8")
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def handle_library_post_request(self, path, parsed):
        """Handle saved views, track metadata, tags, and local-audio POST endpoints."""
        if path == "/playlist-create":
            self.create_playlist()
            return

        if path == "/playlist-rename":
            self.rename_playlist()
            return

        if path == "/playlist-delete":
            self.delete_playlist()
            return

        if path == "/playlist-add-track":
            self.add_playlist_track()
            return

        if path == "/playlist-add-tracks":
            self.add_playlist_tracks()
            return

        if path == "/playlist-remove-track":
            self.remove_playlist_track()
            return

        if path == "/playlist-reorder":
            self.reorder_playlist_tracks()
            return

        if path == "/save-current-view":
            self.save_current_view()
            return

        if path == "/rename-saved-view":
            self.rename_saved_view()
            return

        if path == "/delete-saved-view":
            self.delete_saved_view()
            return

        if path == "/scan-local-inventory":
            self.scan_local_inventory_now()
            return

        if path == "/set-local-family-title":
            self.save_local_family_title_setting()
            return

        if path == "/confirm-local-family":
            self.confirm_local_family()
            return

        if path == "/local-family-quick-catalog":
            self.local_family_quick_catalog()
            return

        if path == "/save-title":
            self.save_title()
            return

        if path == "/save-lyrics":
            self.save_lyrics()
            return

        if path == "/save-style":
            self.save_style()
            return

        if path == "/toggle-like":
            self.toggle_like()
            return

        if path == "/toggle-main-category":
            self.toggle_main_category()
            return

        if path == "/save-user-review":
            self.save_user_review()
            return

        if path == "/add-user-tag":
            self.add_user_tag()
            return

        if path == "/pin-user-tag":
            self.pin_user_tag()
            return

        if path == "/delete-user-tag":
            self.delete_user_tag()
            return

        if path == "/add-local-audio":
            self.add_local_audio()
            return

        if path == "/delete-local-variant":
            self.delete_local_variant()
            return

        if path == "/delete-local-audio":
            self.delete_local_audio()
            return

        if path == "/hide-track":
            self.hide_track()
            return

        return False

    def read_playlist_form(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > 131072:
            raise ValueError("Playlist request is too large.")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        return urllib.parse.parse_qs(raw_body, keep_blank_values=True)

    def create_playlist(self):
        try:
            params = self.read_playlist_form()
            item = create_local_playlist(params.get("name", [""])[0])
            self.send_json_response({"ok": True, "playlist": item})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def rename_playlist(self):
        try:
            params = self.read_playlist_form()
            item = rename_local_playlist(
                params.get("playlist_id", [""])[0],
                params.get("name", [""])[0],
            )
            self.send_json_response({"ok": True, "playlist": item})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def delete_playlist(self):
        try:
            params = self.read_playlist_form()
            deleted_id = delete_local_playlist(
                params.get("playlist_id", [""])[0]
            )
            self.send_json_response({"ok": True, "deleted_id": deleted_id})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def add_playlist_track(self):
        try:
            params = self.read_playlist_form()
            item = add_track_to_local_playlist(
                params.get("playlist_id", [""])[0],
                params.get("track_id", [""])[0],
            )
            self.send_json_response({"ok": True, "playlist": item})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def add_playlist_tracks(self):
        try:
            params = self.read_playlist_form()
            track_ids = [
                value.strip()
                for value in params.get("track_ids", [""])[0].split(",")
                if value.strip()
            ]
            item = add_tracks_to_local_playlist(
                params.get("playlist_id", [""])[0],
                track_ids,
            )
            self.send_json_response({"ok": True, "playlist": item})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def remove_playlist_track(self):
        try:
            params = self.read_playlist_form()
            item = remove_track_from_local_playlist(
                params.get("playlist_id", [""])[0],
                params.get("track_id", [""])[0],
            )
            self.send_json_response({"ok": True, "playlist": item})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def reorder_playlist_tracks(self):
        try:
            params = self.read_playlist_form()
            track_ids = [
                value.strip()
                for value in params.get("track_ids", [""])[0].split(",")
                if value.strip()
            ]
            item = reorder_local_playlist(
                params.get("playlist_id", [""])[0],
                track_ids,
            )
            self.send_json_response({"ok": True, "playlist": item})
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def read_saved_view_form(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > 32768:
            raise ValueError("Saved views request is too large.")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        return urllib.parse.parse_qs(raw_body, keep_blank_values=True)

    def save_current_view(self):
        try:
            params = self.read_saved_view_form()
            item = create_saved_view(
                params.get("name", [""])[0],
                _saved_view_reusable_query(params.get("query", [""])[0]),
            )
            self.send_json_response({
                "ok": True,
                "view": item,
                "views": get_saved_views(),
            })
        except ValueError as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=400)
        except Exception as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=500)

    def rename_saved_view(self):
        try:
            params = self.read_saved_view_form()
            item = rename_saved_view(
                params.get("view_id", [""])[0],
                params.get("name", [""])[0],
            )
            self.send_json_response({
                "ok": True,
                "view": item,
                "views": get_saved_views(),
            })
        except ValueError as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=400)
        except Exception as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=500)

    def delete_saved_view(self):
        try:
            params = self.read_saved_view_form()
            view_id = delete_saved_view(
                params.get("view_id", [""])[0]
            )
            self.send_json_response({
                "ok": True,
                "deleted_id": view_id,
                "views": get_saved_views(),
            })
        except ValueError as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=400)
        except Exception as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=500)

    # LS_LOCAL_FAMILY_TAB_QUICK_V1
    def local_family_quick_catalog(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > 16384:
                raise ValueError("Local Family request is too large.")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            track_id = params.get("track_id", [""])[0]
            result = get_quick_local_family_catalog(track_id)
            self.send_json_response(result, status=200)
        except ValueError as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            self.send_json_response({"ok": False, "error": str(error)}, status=500)

    def save_user_review(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        # keep_blank_values=True is required when the user removes the last tag.
        # Without it, form data such as ``tags=`` disappears from parse_qs(),
        # so the update is mistaken for a request with nothing to save.
        params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)

        track_id = params.get("track_id", [""])[0]
        rating = params.get("rating", [None])[0]
        tags = params.get("tags", [None])[0]
        marks = params.get("marks", [None])[0]

        ok, message = update_track_user_review(track_id, rating=rating, tags=tags, marks=marks)
        self.send_text_response(200 if ok else 400, message)

    def add_user_tag(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        tag = params.get("tag", [""])[0]
        ok, data = add_available_user_tag(tag)
        payload = {"ok": ok}
        payload.update(data)
        self.send_json_response(payload, status=200 if ok else 400)

    def pin_user_tag(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        tag = params.get("tag", [""])[0]
        pinned = normalize_search_scope_flag(params.get("pinned", ["1"])[0], True)
        ok, data = set_user_tag_pinned(tag, pinned=pinned)
        payload = {"ok": ok}
        payload.update(data)
        self.send_json_response(payload, status=200 if ok else 400)

    def delete_user_tag(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        tag = params.get("tag", [""])[0]
        try:
            ok, data = delete_available_user_tag(tag)
            payload = {"ok": ok}
            payload.update(data)
            self.send_json_response(payload, status=200 if ok else 400)
        except Exception as exc:
            self.send_json_response({"ok": False, "error": str(exc)}, status=500)

    def toggle_main_category(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        track_id = params.get("track_id", [""])[0]
        category = params.get("category", [""])[0]
        ok, message = update_track_main_category(track_id, category)
        self.send_text_response(200 if ok else 400, message)

    def toggle_like(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        liked_text = params.get("liked", ["false"])[0]
        liked = str(liked_text or "").strip().lower() == "true"

        ok, message = update_track_like(track_id, liked)

        if ok:
            content = message.encode("utf-8")
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def hide_track(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        reason = params.get("reason", ["manual_hide_from_finder"])[0]

        ok, message = update_track_hidden(track_id, hidden=True, reason=reason)

        if ok:
            content = b"Hidden"
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def save_lyrics(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)

        track_id = params.get("track_id", [""])[0]
        lyrics_text = params.get("lyrics", [""])[0]

        ok, message = update_track_lyrics(track_id, lyrics_text)

        if ok:
            content = b"Lyrics saved"
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def save_title(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        title_text = params.get("title", [""])[0]

        ok, message = update_track_title(track_id, title_text)

        if ok:
            content = b"Title saved"
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def save_style(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)

        track_id = params.get("track_id", [""])[0]
        style_text = params.get("style", [""])[0]

        ok, message = update_track_style(track_id, style_text)

        if ok:
            content = b"Saved"
            self.send_response(200)
        else:
            content = message.encode("utf-8")
            self.send_response(400)

        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
