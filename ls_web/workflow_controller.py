from ls_core.runtime import *


class WorkflowControllerMixin:
    def confirm_local_family(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(
                raw_body,
                keep_blank_values=True,
            )
            track_id = params.get("track_id", [""])[0]
            action = params.get("action", [""])[0]
            family_title = params.get("family_title", [""])[0]
            result = confirm_track_local_family(
                track_id,
                action,
                family_title,
            )
            if result.get("ok"):
                preview = build_selected_wav_download_preview(
                    [track_id],
                    local_family_title="",
                )
                if not preview.get("ok") or not preview.get("rows"):
                    result = {
                        "ok": False,
                        "error": preview.get("error") or "Could not rebuild WAV preview.",
                    }
                else:
                    result["row"] = preview["rows"][0]
            self.send_json_response(
                result,
                status=200 if result.get("ok") else 400,
            )
        except Exception as e:
            self.send_json_response(
                {"ok": False, "error": str(e)},
                status=500,
            )

