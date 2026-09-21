from ls_core.runtime import *
from ls_data.repository import get_best_local_audio_path_for_track
from ls_audio.service import ensure_browser_safe_local_audio


class AudioControllerMixin:
    def handle_audio_post_request(self, path, parsed):
        """Handle audio/Stems launch POST endpoints."""
        if path == "/open-stems-audacity":
            self.open_stems_audacity()
            return

        return False

    def send_local_waveform(self, local_path):
        local_path = urllib.parse.unquote(local_path or "")

        if not local_path:
            self.send_error(400, "Missing local path")
            return

        if not os.path.exists(local_path):
            self.send_error(404, "Local audio file not found")
            return

        # v2 key keeps the stronger waveform rendering separate from older cached keys.
        key = "local_v2_" + hashlib.sha1(local_path.encode("utf-8", errors="ignore")).hexdigest()
        png_data, error = generate_waveform_bytes(key, local_path)

        if error:
            content = f"Local waveform error: {error}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_png_bytes(png_data)

    def send_waveform(self, track_id, audio_url):
        png_data, error = generate_waveform_bytes(track_id, audio_url)

        if error:
            content = f"Waveform error: {error}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_png_bytes(png_data)

    def show_local_file(self, local_path):
        local_path = urllib.parse.unquote(local_path)

        if not local_path:
            self.send_error(400, "Missing local path")
            return

        if not os.path.exists(local_path):
            self.send_error(404, "Local file not found")
            return

        try:
            reveal_file_in_explorer(local_path)
            send_no_content(self)
        except Exception as e:
            content = f"Could not open folder: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def edit_local_file(self, local_path):
        local_path = urllib.parse.unquote(local_path)

        if not local_path:
            self.send_error(400, "Missing local path")
            return

        if not os.path.exists(local_path):
            self.send_error(404, "Local file not found")
            return

        try:
            open_file_in_audio_editor(local_path)
            send_no_content(self)
        except Exception as e:
            content = f"Could not open audio editor: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def send_local_audio_path(self, track_id):
        track_id = urllib.parse.unquote(track_id or "")
        local_path = get_best_local_audio_path_for_track(track_id)
        if not local_path:
            self.send_text_response(404, "Šim ierakstam LS nav piesaistīts īsts lokāls WAV/MP3 fails.")
            return
        self.send_text_response(200, local_path)



    def send_local_audio_for_track(self, track_id):
        track_id = urllib.parse.unquote(track_id or "").strip()
        if not track_id:
            self.send_error(400, "Missing Track ID")
            return
        local_path = get_best_local_audio_path_for_track(track_id)
        if not local_path:
            self.send_error(404, "Local audio file not found")
            return
        try:
            playback_path = ensure_browser_safe_local_audio(local_path)
        except FileNotFoundError:
            self.send_error(404, "Local audio file not found")
            return
        except (RuntimeError, OSError):
            self.send_error(500, "Local audio preparation failed")
            return
        self.send_local_audio(playback_path)


    def send_local_audio(self, local_path):
        local_path = urllib.parse.unquote(local_path)

        if not local_path:
            self.send_error(400, "Missing local path")
            return

        if not os.path.exists(local_path):
            self.send_error(404, "Local audio file not found")
            return

        file_size = os.path.getsize(local_path)
        mime_type = mimetypes.guess_type(local_path)[0] or "audio/wav"
        range_header = self.headers.get("Range", "")

        start = 0
        end = file_size - 1
        status_code = 200

        if range_header.startswith("bytes="):
            try:
                range_value = range_header.split("=", 1)[1]
                start_text, end_text = range_value.split("-", 1)

                if start_text:
                    start = int(start_text)

                if end_text:
                    end = int(end_text)

                end = min(end, file_size - 1)
                status_code = 206
            except Exception:
                start = 0
                end = file_size - 1
                status_code = 200

        if start > end or start >= file_size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        length = end - start + 1

        self.send_response(status_code)
        self.send_header("Content-Type", mime_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))

        if status_code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")

        self.end_headers()

        try:
            with open(local_path, "rb") as f:
                f.seek(start)
                remaining = length
                chunk_size = 1024 * 128

                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))

                    if not chunk:
                        break

                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                        # Browser stopped this audio request; this is normal when
                        # switching tracks, searching, closing a player, or starting
                        # several stem players. Do not print a traceback or block LS.
                        return

                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def open_local_file(self, local_path):
        local_path = urllib.parse.unquote(local_path)

        if not local_path:
            self.send_error(400, "Missing local path")
            return

        if not os.path.exists(local_path):
            self.send_error(404, "Local file not found")
            return

        try:
            open_file_with_default_app(local_path)
            send_no_content(self)
        except Exception as e:
            content = f"Could not open local file: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
