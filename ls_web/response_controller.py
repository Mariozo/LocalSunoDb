from ls_core.runtime import *


class ResponseControllerMixin:
    def _write_response_body(self, content, response_kind):
        try:
            self.wfile.write(content)
            return True
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError) as exc:
            log_ls_exception(
                "http_response",
                response_kind,
                exc,
                {"method": self.command, "path": urllib.parse.urlparse(self.path).path},
                include_traceback=False,
            )
            return False

    def send_text_response(self, status_code, text):
        content = str(text or "").encode("utf-8")
        try:
            self.send_response(status_code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self._write_response_body(content, "send_text")
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError) as exc:
            log_ls_exception("http_response", "send_text", exc, {"method": self.command, "path": urllib.parse.urlparse(self.path).path}, include_traceback=False)

    def send_json_response(self, data, status=200, cache_control=""):
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            if cache_control:
                self.send_header("Cache-Control", str(cache_control))
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            self._write_response_body(content, "send_json")
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError) as exc:
            log_ls_exception("http_response", "send_json", exc, {"method": self.command, "path": urllib.parse.urlparse(self.path).path}, include_traceback=False)

    def send_html(self, content):
        body = content if isinstance(content, bytes) else str(content).encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self._write_response_body(body, "send_html")
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError) as exc:
            log_ls_exception(
                "http_response",
                "send_html",
                exc,
                {"method": self.command, "path": urllib.parse.urlparse(self.path).path},
                include_traceback=False,
            )
            return

    def send_redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def send_png_bytes(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
