from ls_core.runtime import *


class SettingsControllerMixin:
    def handle_settings_bridge_post_request(self, path, parsed):
        """Handle Settings, Token Bridge, and Downloader-state POST endpoints."""
        if path == "/set-audio-library-root":
            self.set_audio_library_root()
            return

        if path == "/set-stem-root":
            self.set_stem_root()
            return

        if path == "/set-ls-update-check-interval":
            self.set_ls_update_check_interval()
            return

        if path == "/set-autoplay-list":
            self.set_autoplay_list()
            return

        if path == "/set-audio-output-devices":
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body)
            payload = set_ls_audio_output_devices(
                params.get("audio_output_speakers_id", [""])[0],
                params.get("audio_output_headphones_id", [""])[0],
            )
            self.send_json_response(
                payload,
                status=200 if payload.get("ok") else 400,
            )
            return

        if path == "/toggle-audio-output":
            payload = toggle_ls_audio_output()
            self.send_json_response(
                payload,
                status=200 if payload.get("ok") else 500,
            )
            return

        if path == "/set-suno-api-token":
            self.set_suno_api_token()
            return

        if path == "/start-suno-token-renewal":
            self.start_suno_token_renewal()
            return

        if path == "/open-token-bridge-setup":
            self.open_token_bridge_setup()
            return

        if path == "/bridge-ping":
            self.bridge_ping()
            return

        if path == "/bridge-diagnostic":
            self.bridge_diagnostic()
            return

        if path == "/save-downloader-state":
            self.save_downloader_state()
            return

        if path == "/clear-downloader-state":
            self.clear_downloader_state()
            return

        if path == "/bridge-set-suno-api-token":
            self.bridge_set_suno_api_token()
            return

        return False

    def send_settings_json(self):
        self.send_json_response(get_settings())

    def choose_audio_library_root(self):
        selected = choose_folder_dialog(get_audio_library_root_folder(), "Select Audio Library root folder")
        if not selected:
            self.send_text_response(200, "")
            return
        ok, message = set_audio_library_root_folder(selected)
        self.send_text_response(200 if ok else 400, message)

    def choose_stem_root(self):
        selected = choose_folder_dialog(get_stem_root_folder(), "Select Stem root folder")
        if not selected:
            self.send_text_response(200, "")
            return
        ok, message = set_stem_root_folder(selected)
        self.send_text_response(200 if ok else 400, message)

    def set_audio_library_root(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        folder = params.get("audio_library_root_folder", [""])[0]
        ok, message = set_audio_library_root_folder(folder)
        self.send_text_response(200 if ok else 400, message)

    def set_stem_root(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        folder = params.get("stem_root_folder", [""])[0]
        ok, message = set_stem_root_folder(folder)
        self.send_text_response(200 if ok else 400, message)

    def set_ls_update_check_interval(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        value = params.get("ls_update_check_interval_seconds", ["10"])[0]
        ok, message = set_ls_update_check_interval_setting(value)
        self.send_text_response(200 if ok else 400, message)

    def set_autoplay_list(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        value = params.get("autoplay_list", ["0"])[0]
        ok, message = set_autoplay_list_setting(value)
        self.send_text_response(200 if ok else 400, message)
