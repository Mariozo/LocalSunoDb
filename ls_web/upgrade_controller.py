from ls_core.runtime import *


class UpgradeControllerMixin:
    def ls_update_candidate(self, silent=False):
        payload = get_ls_upgrade_coordinator().discover(
            manual=not bool(silent),
            force=not bool(silent),
        )
        self.send_json_response(payload, status=200 if payload.get("ok") else 400)

    def install_ls_update(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > 16384:
                raise ValueError("LS Upgrade pieprasījums ir pārāk liels")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            request = {key: values[0] if values else "" for key, values in params.items()}
            payload = get_ls_upgrade_coordinator().install(request)
            self.send_json_response(payload, status=200 if payload.get("ok") else 400)
        except Exception as exc:
            log_ls_exception("upgrade", "install_http_adapter", exc, include_traceback=True)
            self.send_json_response({"ok": False, "error": str(exc)}, status=400)

    def open_ls_native_update_dialog(self):
        try:
            payload = get_ls_upgrade_coordinator().open_dialog(manual=True)
            self.send_json_response(payload, status=200 if payload.get("ok") else 400)
        except Exception as exc:
            log_ls_exception("upgrade", "open_native_dialog_http_adapter", exc, include_traceback=True)
            self.send_json_response({"ok": False, "error": str(exc)}, status=400)

    def show_ls_upgrade_native_message_http(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length < 0 or length > 8192:
                raise ValueError("LS Upgrade paziņojums ir pārāk liels")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            message = params.get("message", [""])[0]
            title = params.get("title", ["LocalSunoDb Upgrade"])[0]
            error_value = params.get("error", ["1"])[0].strip().casefold()
            shown = show_ls_upgrade_native_message(
                message,
                title=title,
                error=error_value not in {"0", "false", "no"},
            )
            self.send_json_response({"ok": True, "shown": bool(shown)})
        except Exception as exc:
            log_ls_exception("upgrade", "native_message_http_adapter", exc, include_traceback=True)
            self.send_json_response({"ok": False, "error": str(exc)}, status=400)

    def reject_ls_upgrade_candidate(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            signature = params.get("signature", [""])[0]
            payload = get_ls_upgrade_coordinator().reject(signature)
            self.send_json_response(payload)
        except Exception as exc:
            self.send_json_response({"ok": False, "error": str(exc)}, status=400)
