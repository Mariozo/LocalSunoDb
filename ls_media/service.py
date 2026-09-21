from ls_audio.service import ensure_browser_safe_local_audio
from ls_data.repository import get_best_local_audio_path_for_track
from ls_suno.service import resolve_suno_playback_url


class MediaPlaybackNotFoundError(LookupError):
    """The requested playback source cannot resolve to a usable target."""


def normalize_playback_source(value):
    source = str(value or "").strip().casefold()
    if source not in {"local", "suno"}:
        raise ValueError("Unsupported playback source")
    return source


def resolve_browser_playback_target(track_id, source):
    """Resolve one Player source to a browser-consumable path or HTTPS URL."""
    track_id = str(track_id or "").strip()
    if not track_id:
        raise ValueError("Missing Track ID")

    source = normalize_playback_source(source)
    if source == "local":
        local_path = str(get_best_local_audio_path_for_track(track_id) or "").strip()
        if not local_path:
            raise MediaPlaybackNotFoundError("Local audio file not found")
        try:
            playback_path = str(ensure_browser_safe_local_audio(local_path) or "").strip()
        except FileNotFoundError as exc:
            raise MediaPlaybackNotFoundError("Local audio file not found") from exc
        if not playback_path:
            raise MediaPlaybackNotFoundError("Local audio file not found")
        return playback_path

    target = str(resolve_suno_playback_url(track_id) or "").strip()
    if not target:
        raise MediaPlaybackNotFoundError("Suno playback media is unavailable")
    return target
