from ls_core.runtime import *
from ls_core.assets import render_template_tokens, asset_url
from ls_upgrade.changelog import read_changelog_markdown


class SupportControllerMixin:
    def send_help_text(self):
        content = get_help_text().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def send_help_page(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if str(params.get("changelog", [""])[0]).strip().casefold() in {"1", "true", "yes"}:
            self.send_changelog_page()
            return

        help_text, help_format, help_source = get_help_source()
        if help_format == "markdown":
            help_body, help_toc = render_help_markdown(help_text)
        else:
            help_body = '<pre class="help-plain">' + esc(help_text) + "</pre>"
            help_toc = ""
        source_name = Path(help_source).name if help_source and help_source != "built-in Help" else help_source
        plain_toc = help_toc or '<span style="color:#667085;font-size:13px;">Plain-text Help</span>'
        page = render_template_tokens(
            "ls_web/templates/help.html",
            [esc(APP_VERSION), plain_toc, help_body, esc(source_name), asset_url("ls_web/static/help.css")],
        )
        self.send_html(page.encode("utf-8"))

    def send_changelog_page(self):
        changelog_text = read_changelog_markdown(BASE_DIR)
        changelog_body, changelog_toc = render_help_markdown(changelog_text)
        plain_toc = changelog_toc or '<span style="color:#667085;font-size:13px;">Izmaiņu žurnāls</span>'
        page = render_template_tokens(
            "ls_web/templates/changelog.html",
            [esc(APP_VERSION), plain_toc, changelog_body, asset_url("ls_web/static/help.css")],
        )
        self.send_html(page.encode("utf-8"))


    def send_profile_image(self):
        path = find_profile_image_path()
        if not path:
            self.send_error(404, "Profile image not found")
            return
        try:
            data = path.read_bytes()
            mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            content = f"Could not read profile image: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def send_suno_image_redirect(self, track_id):
        track_id = urllib.parse.unquote(track_id or "")

        if not track_id:
            self.send_error(400, "Missing Track ID")
            return

        try:
            image_url = extract_suno_page_image_url(track_id)

            if not image_url:
                self.send_error(404, "Suno image not found")
                return

            self.send_response(302)
            self.send_header("Location", image_url)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
        except Exception as e:
            content = f"Could not resolve Suno image: {e}".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
