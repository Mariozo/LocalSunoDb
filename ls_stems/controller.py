from ls_core.runtime import *


class StemsControllerMixin:
    def choose_stem_folder(self, track_id):
        selected = choose_folder_dialog(get_stem_root_folder(), "Select Stem folder")
        if not selected:
            self.send_text_response(200, "Cancelled")
            return
        ok, message = add_stem_folder_to_track(track_id, selected)
        self.send_text_response(200 if ok else 400, message)

    def send_stems_json(self, track_id):
        stems = []
        for item in get_stems_for_track(track_id):
            path = item.get("path") or ""
            stems.append({
                "label": item.get("stem_label") or "Stem",
                "filename": item.get("filename") or Path(path).name,
                "path": path,
                "url": "/local-audio?path=" + urllib.parse.quote(path),
                "waveform_url": "/local-waveform?path=" + urllib.parse.quote(path),
            })
        self.send_json_response({"stems": stems})

    def open_stems_audacity(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = urllib.parse.parse_qs(raw_body)
        paths = params.get("path", [])
        ok, message = open_files_in_audio_editor(paths)
        self.send_text_response(200 if ok else 400, message)
