import urllib.error

from ls_core.runtime import *
from ls_media.service import (
    MediaPlaybackNotFoundError,
    normalize_playback_source,
    resolve_browser_playback_target,
)
from ls_suno.service import SunoAuthenticationError, SunoTrackNotFoundError


class MediaControllerMixin:
    def _resolve_playback_target_or_error(self, track_id, source, action):
        try:
            normalized_source = normalize_playback_source(source)
            target = resolve_browser_playback_target(track_id, normalized_source)
            return normalized_source, target
        except ValueError as exc:
            self.send_error(400, str(exc))
        except (MediaPlaybackNotFoundError, SunoTrackNotFoundError) as exc:
            self.send_error(404, str(exc))
        except SunoAuthenticationError as exc:
            self.send_error(502, str(exc))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            try:
                log_ls_exception(
                    "media_playback",
                    action,
                    exc,
                    {"track_id": str(track_id or ""), "source": str(source or "")},
                    include_traceback=False,
                )
            except Exception:
                pass
            self.send_error(502, "Playback media unavailable")
        return "", ""

    def _send_remote_playback_audio(self, target):
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "audio/*,*/*;q=0.8",
        }
        range_header = str(self.headers.get("Range", "") or "").strip()
        if range_header:
            headers["Range"] = range_header
        request = urllib.request.Request(str(target), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = int(getattr(response, "status", 200) or 200)
                self.send_response(status)
                for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                    value = str(response.headers.get(name) or "").strip()
                    if value:
                        self.send_header(name, value)
                if not str(response.headers.get("Accept-Ranges") or "").strip():
                    self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                while True:
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                        return
        except urllib.error.HTTPError as exc:
            code = int(getattr(exc, "code", 502) or 502)
            self.send_error(code if 400 <= code < 500 else 502, "Playback media unavailable")
        except (urllib.error.URLError, TimeoutError, OSError):
            self.send_error(502, "Playback media unavailable")

    def send_playback_media(self, track_id, source):
        normalized_source, target = self._resolve_playback_target_or_error(
            track_id, source, "resolve_media"
        )
        if not target:
            return
        if normalized_source == "suno":
            self._send_remote_playback_audio(target)
            return
        self.send_local_audio(target)

    def send_playback_waveform(self, track_id, source):
        normalized_source, target = self._resolve_playback_target_or_error(
            track_id, source, "resolve_waveform"
        )
        if not target:
            return
        if normalized_source == "suno":
            self.send_waveform(track_id, target)
            return
        self.send_local_waveform(target)
