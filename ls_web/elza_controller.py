from ls_core.runtime import *
from ls_web.elza_locf import build_locf_selection_answer, get_locf_selection_result
from ls_web.elza_selection_bridge import (
    finalize_semantic_selection,
    prepare_local_locf_service_result,
    prepare_selection_transport,
)


class ElzaControllerMixin:
    def handle_update_assistant_post_request(self, path, parsed):
        """Handle Upgrade and LS Elza POST endpoints."""
        if path == "/ls-update-candidate":
            self.ls_update_candidate()
            return

        if path == "/ls-update-candidate-poll":
            self.ls_update_candidate(silent=True)
            return

        if path == "/install-ls-update":
            self.install_ls_update()
            return

        if path == "/open-ls-native-update-dialog":
            self.open_ls_native_update_dialog()
            return

        if path == "/ls-upgrade/native-message":
            self.show_ls_upgrade_native_message_http()
            return

        if path == "/ls-upgrade/reject":
            self.reject_ls_upgrade_candidate()
            return

        if path == "/ls-comparison-versions":
            self.ls_comparison_versions()
            return

        if path == "/launch-ls-comparison":
            self.launch_ls_comparison()
            return

        if path == "/stop-ls-comparison":
            self.stop_ls_comparison()
            return

        if path == "/ls-assistant-chat":
            self.ls_assistant_chat()
            return

        if path == "/set-ls-elza-opacity":
            self.set_ls_elza_opacity()
            return

        return False

    def ls_assistant_chat(self):
        origin = str(self.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = {
            f"http://{HOST}:{PORT}",
            f"http://localhost:{PORT}",
        }
        if origin and origin not in allowed_origins:
            self.send_json_response({
                "ok": False,
                "error": "LS Elza accepts requests only from this local LocalSunoDb.",
                "error_code": "origin_not_allowed",
            }, status=403)
            return

        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0

        # Text requests remain small; Base64 image input may use up to ~16 MB.
        if length <= 0 or length > 20 * 1024 * 1024:
            self.send_json_response({
                "ok": False,
                "error": "Invalid LS Elza request size.",
                "error_code": "invalid_request_size",
            }, status=400)
            return

        try:
            raw_body = self.rfile.read(length).decode("utf-8", errors="strict")
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json_response({
                "ok": False,
                "error": "LS Elza requires a valid JSON request.",
                "error_code": "invalid_json",
            }, status=400)
            return

        payload, _use_legacy_local = prepare_selection_transport(payload)
        local_readonly_result = get_ls_elza_local_readonly_response(payload)
        if local_readonly_result is not None:
            self.send_json_response(
                local_readonly_result,
                status=200 if local_readonly_result.get("ok") else 500,
            )
            return

        local_locf_result = prepare_local_locf_service_result(payload)
        if local_locf_result is not None:
            result = finalize_semantic_selection(
                payload,
                local_locf_result,
                resolve_workspace=lambda value: value,
                resolve_local_family=lambda value: value,
                normalize_tags=lambda values: list(values or []),
                get_selection_result=lambda *_args, **_kwargs: {},
                get_exact_stem_result=lambda *_args, **_kwargs: {},
                build_answer=build_locf_selection_answer,
                append_chat_exchange=ls_elza_append_chat_exchange,
                get_locf_selection_result=get_locf_selection_result,
            )
            self.send_json_response(result)
            return

        if handle_ls_elza_action is None:
            self.send_json_response({
                "ok": False,
                "error": "LS Elza service could not be loaded.",
                "error_code": "service_unavailable",
            }, status=503)
            return

        try:
            result = handle_ls_elza_action(payload)
            if isinstance(result, dict) and isinstance(result.get("selection_request"), dict):
                result = finalize_semantic_selection(
                    payload,
                    result,
                    resolve_workspace=ls_elza_resolve_workspace,
                    resolve_local_family=ls_elza_resolve_local_family,
                    normalize_tags=normalize_tag_filter,
                    get_selection_result=get_ls_elza_selection_result,
                    get_exact_stem_result=get_ls_elza_exact_stem_result,
                    build_answer=build_ls_elza_selection_answer,
                    append_chat_exchange=ls_elza_append_chat_exchange,
                    get_locf_selection_result=get_locf_selection_result,
                )
            self.send_json_response(result)
        except Exception as error:
            if ls_elza_error_payload is not None:
                data, status = ls_elza_error_payload(error)
            else:
                data = {
                    "ok": False,
                    "error": "Unexpected LS Elza server error.",
                    "error_code": "unexpected_error",
                }
                status = 500
            self.send_json_response(data, status=status)

    def set_ls_elza_opacity(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
            params = urllib.parse.parse_qs(raw_body, keep_blank_values=True)
            value = params.get("opacity", ["50"])[0]
            ok, message, opacity = set_ls_elza_background_opacity(value)
            self.send_json_response({
                "ok": ok,
                "message": message,
                "opacity": opacity,
            }, status=200 if ok else 400)
        except Exception as error:
            self.send_json_response({
                "ok": False,
                "error": str(error),
            }, status=500)
