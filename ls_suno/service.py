import base64
import difflib
import importlib.util
import socket
import threading
import html
import json
import os
import shutil
import mimetypes
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import warnings
import webbrowser
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from ls_core.runtime import *
from ls_core.assets import asset_text
from ls_data.repository import get_track_download_info

SUNO_METADATA_JOB_THREAD = None
SUNO_TOKEN_INVALID_IN_PROCESS = False

SUNO_PLAYBACK_URL_CACHE = {}
SUNO_PLAYBACK_URL_CACHE_TTL_SECONDS = 60.0
SUNO_PLAYBACK_URL_CACHE_LOCK = threading.RLock()


def set_suno_api_token(token, source="manual"):
    global SUNO_TOKEN_INVALID_IN_PROCESS
    token = str(token or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    save_settings({
        "suno_api_token": token,
        "suno_api_token_updated_at": now_iso_local() if token else "",
        "suno_api_token_source": str(source or "manual") if token else "",
        "suno_api_token_invalid_at": "",
    })
    SUNO_TOKEN_INVALID_IN_PROCESS = False
    return True, "Token saved" if token else "Token cleared"

def mark_suno_api_token_invalid():
    global SUNO_TOKEN_INVALID_IN_PROCESS
    settings = get_settings()
    if str(settings.get("suno_api_token") or "").strip():
        save_settings({"suno_api_token_invalid_at": now_iso_local()})
        SUNO_TOKEN_INVALID_IN_PROCESS = True

def mark_suno_api_token_valid():
    global SUNO_TOKEN_INVALID_IN_PROCESS
    settings_reader = globals().get("get_settings")
    settings_writer = globals().get("save_settings")
    if callable(settings_reader) and callable(settings_writer):
        settings = settings_reader()
        if str(settings.get("suno_api_token_invalid_at") or "").strip():
            settings_writer({"suno_api_token_invalid_at": ""})
    SUNO_TOKEN_INVALID_IN_PROCESS = False

def get_suno_api_token():
    token = str(get_settings().get("suno_api_token") or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token

def set_token_bridge_state(**updates):
    with TOKEN_BRIDGE_LOCK:
        TOKEN_BRIDGE_STATE.update(updates)
        return dict(TOKEN_BRIDGE_STATE)

def _token_bridge_age_seconds(value):
    parsed = parse_local_iso(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now() - parsed).total_seconds())

def _token_bridge_bool(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

def _token_bridge_int(value, minimum=0, maximum=1_000_000):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))

def _token_bridge_diagnosis(
    settings,
    bridge_state,
    bridge_active,
    diagnostic_active,
    token_saved,
):
    token_invalid = bool(str(settings.get("suno_api_token_invalid_at") or ""))
    page_loaded = _token_bridge_bool(bridge_state.get("page_loaded"))
    fetch_hook_active = _token_bridge_bool(bridge_state.get("fetch_hook_active"))
    api_request_seen = bool(str(bridge_state.get("last_api_request_at") or ""))
    authorization_seen = bool(str(bridge_state.get("last_authorization_at") or ""))
    page_instance_id = str(bridge_state.get("page_instance_id") or "")
    token_page_instance_id = str(
        bridge_state.get("last_token_page_instance_id") or ""
    )
    relay_seen = bool(str(bridge_state.get("last_token_at") or ""))
    if page_instance_id:
        relay_seen = relay_seen and token_page_instance_id == page_instance_id

    if token_saved and token_invalid and SUNO_TOKEN_INVALID_IN_PROCESS:
        return {
            "code": "session_expired",
            "level": "error",
            "summary": "Suno rejected the saved authorization in this LS session.",
            "action": "Reload or open Suno, then trigger one authenticated request.",
        }
    if token_saved and token_invalid and bridge_active:
        return {
            "code": "session_unverified",
            "level": "warn",
            "summary": "The saved Suno authorization needs one live re-check after LS restart.",
            "action": "Continue with the next Suno action; LS will trust the live response.",
        }
    if not bridge_active:
        return {
            "code": "extension_offline",
            "level": "error",
            "summary": "The Token Bridge service worker is not connected to LS.",
            "action": "Reload the extension in chrome://extensions/.",
        }
    if not diagnostic_active:
        return {
            "code": "page_not_reporting",
            "level": "warn",
            "summary": "The extension is connected, but no current Suno page diagnostics arrived.",
            "action": "Open or reload a Suno tab and wait a few seconds.",
        }
    if not page_loaded:
        return {
            "code": "page_bridge_missing",
            "level": "error",
            "summary": "The Suno page bridge did not finish loading.",
            "action": "Reload the Suno tab. If it persists, reload the extension.",
        }
    if not fetch_hook_active:
        return {
            "code": "fetch_hook_inactive",
            "level": "warn",
            "summary": "Suno replaced the fetch hook; automatic repair is pending.",
            "action": "Wait up to two seconds. The bridge should repair itself.",
        }
    if not api_request_seen:
        return {
            "code": "waiting_for_api_request",
            "level": "warn",
            "summary": "The page bridge is ready, but no Suno API request was observed yet.",
            "action": "Play a song or open Suno Library to trigger an API request.",
        }
    if not authorization_seen:
        return {
            "code": "authorization_missing",
            "level": "error",
            "summary": "A Suno API request was seen without an Authorization header.",
            "action": "Check that Suno is logged in. A Suno authentication change may require an update.",
        }
    if not relay_seen:
        return {
            "code": "relay_pending",
            "level": "warn",
            "summary": "Authorization was found, but LS has not received the token yet.",
            "action": "Wait a few seconds. If unchanged, reload the extension.",
        }
    return {
        "code": "healthy",
        "level": "ok",
        "summary": "All Token Bridge checks passed.",
        "action": "No action is needed.",
    }

def get_suno_token_status():
    settings = get_settings()
    token_saved = bool(str(settings.get("suno_api_token") or "").strip())
    with TOKEN_BRIDGE_LOCK:
        bridge_state = dict(TOKEN_BRIDGE_STATE)

    last_seen = str(bridge_state.get("last_seen") or "")
    bridge_age = _token_bridge_age_seconds(last_seen)
    bridge_active = bridge_age is not None and bridge_age <= 180
    diagnostic_last_seen = str(bridge_state.get("diagnostic_last_seen") or "")
    diagnostic_age = _token_bridge_age_seconds(diagnostic_last_seen)
    diagnostic_active = diagnostic_age is not None and diagnostic_age <= 75
    diagnosis = _token_bridge_diagnosis(
        settings,
        bridge_state,
        bridge_active,
        diagnostic_active,
        token_saved,
    )

    return {
        "ok": True,
        "token_saved": token_saved,
        "token_updated_at": str(settings.get("suno_api_token_updated_at") or ""),
        "token_source": str(settings.get("suno_api_token_source") or ""),
        "token_invalid_at": str(settings.get("suno_api_token_invalid_at") or ""),
        "token_invalid_current_process": bool(SUNO_TOKEN_INVALID_IN_PROCESS),
        "bridge_last_seen": last_seen,
        "bridge_active": bridge_active,
        "bridge_last_token_at": str(bridge_state.get("last_token_at") or ""),
        "bridge_last_error": str(bridge_state.get("last_error") or ""),
        "bridge_extension_version": str(bridge_state.get("extension_version") or ""),
        "bridge_capture_source": str(bridge_state.get("last_capture_source") or ""),
        "last_token_page_instance_id": str(
            bridge_state.get("last_token_page_instance_id") or ""
        ),
        "bridge_folder": str(TOKEN_BRIDGE_DIR),
        "diagnostic_last_seen": diagnostic_last_seen,
        "diagnostic_active": diagnostic_active,
        "page_loaded": _token_bridge_bool(bridge_state.get("page_loaded")),
        "fetch_hook_active": _token_bridge_bool(bridge_state.get("fetch_hook_active")),
        "fetch_repair_count": _token_bridge_int(bridge_state.get("fetch_repair_count")),
        "last_fetch_repair_at": str(bridge_state.get("last_fetch_repair_at") or ""),
        "last_api_request_at": str(bridge_state.get("last_api_request_at") or ""),
        "last_authorization_at": str(bridge_state.get("last_authorization_at") or ""),
        "last_token_emit_at": str(bridge_state.get("last_token_emit_at") or ""),
        "last_diagnostic_event": str(bridge_state.get("last_diagnostic_event") or ""),
        "page_instance_id": str(bridge_state.get("page_instance_id") or ""),
        "relay_last_seen": str(bridge_state.get("relay_last_seen") or ""),
        "previous_worker_error": str(bridge_state.get("previous_worker_error") or ""),
        "last_recovered_at": str(bridge_state.get("last_recovered_at") or ""),
        "diagnosis_code": diagnosis["code"],
        "diagnosis_level": diagnosis["level"],
        "diagnosis_summary": diagnosis["summary"],
        "diagnosis_action": diagnosis["action"],
    }

def update_token_bridge_diagnostic(diagnostic, extension_version=""):
    if not isinstance(diagnostic, dict):
        raise ValueError("Bridge diagnostic payload must be an object")

    clean = {
        "page_loaded": _token_bridge_bool(diagnostic.get("page_loaded")),
        "fetch_hook_active": _token_bridge_bool(
            diagnostic.get("fetch_hook_active")
        ),
        "fetch_repair_count": _token_bridge_int(
            diagnostic.get("fetch_repair_count")
        ),
    }
    for key in (
        "last_fetch_repair_at",
        "last_api_request_at",
        "last_authorization_at",
        "last_token_emit_at",
        "last_diagnostic_event",
        "page_instance_id",
    ):
        clean[key] = str(diagnostic.get(key) or "")[:240]

    now_value = now_iso_local()
    clean.update({
        "diagnostic_last_seen": now_value,
        "relay_last_seen": now_value,
        "last_seen": now_value,
        "last_error": "",
    })
    if extension_version:
        clean["extension_version"] = str(extension_version)[:40]
    return set_token_bridge_state(**clean)

def _token_bridge_manifest_text():
    return json.dumps({
        "manifest_version": 3,
        "name": "LS Suno Token Bridge",
        "version": "2.4.2",
        "description": (
            "Captures Suno API authorization from Suno page fetch/XHR calls and "
            "relays it only to the local LocalSunoDb on 127.0.0.1:8765."
        ),
        "minimum_chrome_version": "120",
        "permissions": [
            "alarms",
            "tabs",
            "storage",
        ],
        "host_permissions": [
            "https://suno.com/*",
            "http://127.0.0.1:8765/*",
        ],
        "background": {
            "service_worker": "service_worker.js",
        },
        "content_scripts": [
            {
                "matches": ["https://suno.com/*"],
                "js": ["page_capture.js"],
                "run_at": "document_start",
                "world": "MAIN",
            },
            {
                "matches": ["https://suno.com/*"],
                "js": ["content_bridge.js"],
                "run_at": "document_start",
                "world": "ISOLATED",
            },
            {
                "matches": ["http://127.0.0.1:8765/*"],
                "js": ["local_probe.js"],
                "run_at": "document_start",
                "world": "ISOLATED",
            },
        ],
    }, ensure_ascii=False, indent=2)

def _token_bridge_worker_text():
    return asset_text("ls_suno/static/token_bridge_worker.js")


def _token_bridge_page_capture_text():
    return asset_text("ls_suno/static/token_bridge_page_capture.js")


def _token_bridge_local_probe_text():
    return asset_text("ls_suno/static/token_bridge_local_probe.js")


def _token_bridge_content_bridge_text():
    return r'''(() => {
  "use strict";

  const BRIDGE_SOURCE = "ls-suno-token-bridge-v2";

  function runtimeIsAvailable() {
    try {
      return Boolean(chrome && chrome.runtime && chrome.runtime.id);
    } catch (error) {
      return false;
    }
  }

  async function safeSendMessage(message) {
    if (!runtimeIsAvailable()) return false;
    try {
      await chrome.runtime.sendMessage(message);
      return true;
    } catch (error) {
      return false;
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== window.location.origin) return;
    const data = event.data;
    if (!data || data.source !== BRIDGE_SOURCE) return;

    if (data.type === "LS_SUNO_DIAGNOSTIC") {
      safeSendMessage({
        type: "LS_SUNO_DIAGNOSTIC",
        diagnostic: data.diagnostic && typeof data.diagnostic === "object" ? data.diagnostic : {},
      });
      return;
    }

    if (data.type !== "LS_SUNO_TOKEN") return;
    const token = String(data.token || "").trim();
    if (!token) return;

    safeSendMessage({
      type: "LS_SUNO_TOKEN_CAPTURED",
      token,
      capture_source: String(data.captureSource || "page"),
      page_instance_id: String(data.pageInstanceId || ""),
    });
  });

  window.postMessage({ source: BRIDGE_SOURCE, type: "LS_SUNO_DIAGNOSTIC_REQUEST" }, window.location.origin);
  safeSendMessage({ type: "LS_SUNO_BRIDGE_PAGE_READY" });
})();
'''

def ensure_suno_token_bridge_files():
    TOKEN_BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "manifest.json": _token_bridge_manifest_text() + "\n",
        "service_worker.js": _token_bridge_worker_text(),
        "page_capture.js": _token_bridge_page_capture_text(),
        "content_bridge.js": _token_bridge_content_bridge_text(),
        "local_probe.js": _token_bridge_local_probe_text(),
        "README.txt": _token_bridge_readme_text(),
    }
    for filename, content in files.items():
        path_obj = TOKEN_BRIDGE_DIR / filename
        if not path_obj.exists() or path_obj.read_text(
            encoding="utf-8",
            errors="replace",
        ) != content:
            path_obj.write_text(content, encoding="utf-8")
    return TOKEN_BRIDGE_DIR

def open_token_bridge_setup():
    folder = ensure_suno_token_bridge_files()
    extensions_url = "chrome://extensions/"
    folder_opened = False
    errors = []

    try:
        os.startfile(str(folder))
        folder_opened = True
    except Exception as exc:
        errors.append(f"Could not open the Token Bridge folder: {exc}")
        log_ls_exception(
            "token_bridge",
            "open_setup_folder",
            exc,
            context={"folder": str(folder)},
            include_traceback=False,
        )

    return {
        "ok": folder_opened,
        "folder": str(folder),
        "folder_opened": folder_opened,
        "browser_opened": False,
        "extensions_url": extensions_url,
        "requires_manual_navigation": True,
        "error": " ".join(errors),
    }

def start_suno_token_renewal():
    ensure_suno_token_bridge_files()
    browser = find_chrome_executable()

    settings = get_settings()
    requested_at = now_iso_local()
    previous_updated_at = str(
        settings.get("suno_api_token_updated_at") or ""
    )
    save_settings({
        "suno_token_renew_requested_at": requested_at,
    })

    opened_urls = ["https://suno.com/create"]
    launched = []
    for url in opened_urls:
        try:
            if browser:
                subprocess.Popen([browser, url])
            else:
                webbrowser.open(url)
            launched.append(url)
        except Exception:
            pass
    return {
        "ok": True,
        "requested_at": requested_at,
        "previous_token_updated_at": previous_updated_at,
        "bridge_folder": str(TOKEN_BRIDGE_DIR),
        "opened_urls": launched,
        "error": "" if launched else "Suno was not opened automatically; use the browser window opened by the button, or open https://suno.com/create manually.",
    }

def get_or_create_suno_device_id():
    settings = get_settings()
    device_id = str(settings.get("suno_device_id") or "").strip()
    if device_id:
        return device_id

    import uuid
    device_id = str(uuid.uuid4())
    save_settings({"suno_device_id": device_id})
    return device_id

def ls_generate_browser_token():
    import base64
    payload = json.dumps({"timestamp": int(time.time() * 1000)}, separators=(",", ":")).encode("utf-8")
    token = base64.b64encode(payload).decode("ascii")
    return json.dumps({"token": token})


def _normalize_suno_credit_value(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(" ", "").replace(",", "")
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 100_000_000:
        return None
    return int(number)

def _extract_suno_credits_remaining(payload):
    preferred_keys = (
        "total_credits_left",
        "credits_left",
        "credits_remaining",
        "remaining_credits",
        "credit_balance",
        "available_credits",
    )

    def walk(value):
        if isinstance(value, dict):
            normalized = {
                re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_"): item
                for key, item in value.items()
            }
            for key in preferred_keys:
                if key in normalized:
                    result = _normalize_suno_credit_value(normalized[key])
                    if result is not None:
                        return result
            for key in ("data", "billing", "credits", "subscription", "account"):
                if key in normalized:
                    result = walk(normalized[key])
                    if result is not None:
                        return result
            for item in value.values():
                if isinstance(item, (dict, list)):
                    result = walk(item)
                    if result is not None:
                        return result
        elif isinstance(value, list):
            for item in value:
                result = walk(item)
                if result is not None:
                    return result
        return None

    return walk(payload)

def get_cached_suno_credits_display():
    value = _normalize_suno_credit_value(
        get_settings().get("suno_credits_remaining")
    )
    return str(value) if value is not None else "—"

def get_suno_credits_status(force=False):
    """Read Suno billing credits with the saved token; never mutates Suno."""
    settings = get_settings()
    cached = _normalize_suno_credit_value(
        settings.get("suno_credits_remaining")
    )
    updated_at = str(settings.get("suno_credits_updated_at") or "")
    age = _token_bridge_age_seconds(updated_at)
    if (
        not force
        and cached is not None
        and age is not None
        and age < SUNO_CREDITS_CACHE_SECONDS
    ):
        return {
            "ok": True,
            "credits_remaining": cached,
            "updated_at": updated_at,
            "cached": True,
            "stale": False,
        }

    if not SUNO_CREDITS_LOCK.acquire(blocking=False):
        return {
            "ok": cached is not None,
            "credits_remaining": cached,
            "updated_at": updated_at,
            "cached": True,
            "stale": True,
            "message": "Credits refresh is already running.",
        }
    try:
        settings = get_settings()
        cached = _normalize_suno_credit_value(
            settings.get("suno_credits_remaining")
        )
        updated_at = str(settings.get("suno_credits_updated_at") or "")
        age = _token_bridge_age_seconds(updated_at)
        if (
            not force
            and cached is not None
            and age is not None
            and age < SUNO_CREDITS_CACHE_SECONDS
        ):
            return {
                "ok": True,
                "credits_remaining": cached,
                "updated_at": updated_at,
                "cached": True,
                "stale": False,
            }

        request = urllib.request.Request(
            SUNO_CREDITS_API_URL,
            headers=suno_api_headers(),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(
                    response.read().decode("utf-8", errors="replace")
                )
            mark_suno_api_token_valid()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code == 401:
                mark_suno_api_token_invalid()
                raise SunoAuthenticationError(
                    "Suno API token is expired. Open Suno.com to renew it."
                ) from exc
            if exc.code == 429:
                raise SunoRateLimitError(
                    "Suno API rate limit reached. Credits were not refreshed."
                ) from exc
            raise RuntimeError(
                f"Suno credits API HTTP {exc.code}: {detail}"
            ) from exc

        credits = _extract_suno_credits_remaining(payload)
        if credits is None:
            raise RuntimeError(
                "Suno billing response did not contain Credits Remaining."
            )
        updated_at = now_iso_local()
        save_settings({
            "suno_credits_remaining": credits,
            "suno_credits_updated_at": updated_at,
        })
        return {
            "ok": True,
            "credits_remaining": credits,
            "updated_at": updated_at,
            "cached": False,
            "stale": False,
        }
    except Exception as exc:
        if cached is not None:
            return {
                "ok": True,
                "credits_remaining": cached,
                "updated_at": updated_at,
                "cached": True,
                "stale": True,
                "message": str(exc),
            }
        return {
            "ok": False,
            "credits_remaining": None,
            "updated_at": "",
            "cached": False,
            "stale": True,
            "error": str(exc),
        }
    finally:
        SUNO_CREDITS_LOCK.release()

def fetch_suno_track_by_id(track_id):
    """Fetch one track from Suno API using the same API family as Suno Tracks Exporter.

    Read-only. It does not write to LS DB.
    """
    track_id = str(track_id or "").strip()
    if not track_id:
        raise ValueError("Missing Track ID")

    headers = suno_api_headers()

    # Current Suno rich single-clip endpoint. Unlike the legacy feed-by-id
    # response, this shape carries top-level media_urls (MP3 + M4A).
    url = "https://studio-api-prod.suno.com/api/clip/" + urllib.parse.quote(track_id)
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        mark_suno_api_token_valid()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        if e.code == 401:
            mark_suno_api_token_invalid()
            raise SunoAuthenticationError("Suno API HTTP 401: token is expired or invalid. Use Renew Suno login in LS.") from e
        if e.code == 429:
            raise SunoRateLimitError("Suno API HTTP 429: Too many requests. LS stopped this batch safely. Wait 5-10 minutes, then continue with a smaller Limit.") from e
        raise RuntimeError(f"Suno API HTTP {e.code}: {detail}") from e

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and str(item.get("id") or "").lower() == track_id.lower():
                return item

    if isinstance(data, dict):
        for key in ["clip", "track", "data"]:
            item = data.get(key)
            if isinstance(item, dict) and str(item.get("id") or item.get("clip_id") or "").lower() == track_id.lower():
                return item
        clips = data.get("clips")
        if isinstance(clips, list):
            for item in clips:
                if isinstance(item, dict) and str(item.get("id") or item.get("clip_id") or "").lower() == track_id.lower():
                    return item
        if str(data.get("id") or data.get("clip_id") or "").lower() == track_id.lower():
            return data

    raise SunoTrackNotFoundError(f"Suno API returned no data for Track ID {track_id}")


def _validate_suno_playback_media_url(value):
    url = str(value or "").strip()
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme.casefold() != "https" or not host:
        raise ValueError("Unsupported Suno playback media URL")
    if not (
        host == "suno.ai"
        or host.endswith(".suno.ai")
        or host == "suno.com"
        or host.endswith(".suno.com")
        or host == "cloudfront.net"
        or host.endswith(".cloudfront.net")
    ):
        raise ValueError("Unsupported Suno playback media host")
    return url


def _suno_playback_media_candidates(track):
    if not isinstance(track, dict):
        return []

    explicit = []
    media_urls = track.get("media_urls")
    if isinstance(media_urls, list):
        for item in media_urls:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            content_type = str(item.get("content_type") or "").strip().casefold()
            if not url:
                continue
            if content_type == "mp3" or url.casefold().split("?", 1)[0].endswith(".mp3"):
                explicit.append({"url": url, "content_type": "mp3", "extension": ".mp3", "priority": 0})
            elif content_type in {"m4a", "m4a-opus", "audio/mp4"} or url.casefold().split("?", 1)[0].endswith(".m4a"):
                explicit.append({"url": url, "content_type": content_type or "m4a", "extension": ".m4a", "priority": 1})
    elif isinstance(media_urls, dict):
        for key, raw in media_urls.items():
            if isinstance(raw, dict):
                url = str(raw.get("url") or "").strip()
                content_type = str(raw.get("content_type") or key or "").strip().casefold()
            else:
                url = str(raw or "").strip()
                content_type = str(key or "").strip().casefold()
            if not url:
                continue
            if "mp3" in content_type or url.casefold().split("?", 1)[0].endswith(".mp3"):
                explicit.append({"url": url, "content_type": "mp3", "extension": ".mp3", "priority": 0})
            elif "m4a" in content_type or url.casefold().split("?", 1)[0].endswith(".m4a"):
                explicit.append({"url": url, "content_type": content_type or "m4a", "extension": ".m4a", "priority": 1})

    result = []
    seen = set()
    for item in sorted(explicit, key=lambda x: x["priority"]):
        try:
            url = _validate_suno_playback_media_url(item["url"])
        except ValueError:
            continue
        if url in seen:
            continue
        seen.add(url)
        clean = dict(item)
        clean.pop("priority", None)
        clean["url"] = url
        result.append(clean)

    legacy = str(track.get("audio_url") or "").strip()
    if legacy and legacy not in seen:
        try:
            legacy = _validate_suno_playback_media_url(legacy)
        except ValueError:
            legacy = ""
        if legacy:
            extension = ".m4a" if legacy.casefold().split("?", 1)[0].endswith(".m4a") else ".mp3"
            result.append({
                "url": legacy,
                "content_type": "m4a" if extension == ".m4a" else "mp3",
                "extension": extension,
            })
    return result


def select_suno_playback_media(track):
    candidates = _suno_playback_media_candidates(track)
    if not candidates:
        raise SunoTrackNotFoundError("Suno API returned no usable playback media URL")
    return dict(candidates[0])


def resolve_suno_playback_url(track_id):
    """Resolve a fresh trusted Suno media URL for the same-origin MEDIA proxy.

    Fresh authenticated metadata is the authority for the current media URL.
    The URL is validated against trusted Suno/CDN hosts and consumed by the
    local playback proxy; a short in-memory URL cache prevents simultaneous
    media + waveform requests from repeating the metadata lookup.
    """
    track_id = str(track_id or "").strip()
    if not track_id:
        raise ValueError("Missing Track ID")

    key = track_id.casefold()
    with SUNO_PLAYBACK_URL_CACHE_LOCK:
        cached = SUNO_PLAYBACK_URL_CACHE.get(key)
        if isinstance(cached, tuple) and len(cached) == 2:
            cached_at, cached_url = cached
            if (
                str(cached_url or "").strip()
                and time.monotonic() - float(cached_at) <= SUNO_PLAYBACK_URL_CACHE_TTL_SECONDS
            ):
                return str(cached_url).strip()

        track = fetch_suno_track_by_id(track_id)
        media = select_suno_playback_media(track)
        playback_url = str(media.get("url") or "").strip()
        if not playback_url:
            raise SunoTrackNotFoundError("Suno API returned no usable playback media URL")
        SUNO_PLAYBACK_URL_CACHE[key] = (time.monotonic(), playback_url)
        return playback_url


def is_suno_stem_track(track):
    if not isinstance(track, dict):
        return False

    def text(value):
        return str(value or "").strip().lower()

    if track.get("is_stem") is True:
        return True

    type_text = text(track.get("type"))
    if "stem" in type_text:
        return True

    md = track.get("metadata") if isinstance(track.get("metadata"), dict) else {}
    for key in ["is_stem", "stem", "stem_type", "stem_label"]:
        value = md.get(key)
        if value is True:
            return True
        if text(value):
            return True

    title = str(track.get("title") or "").strip()
    # Suno split/stem titles often appear only as title suffix, without is_stem/type flags.
    if re.search(r"\((Drums|Backing Vocals|Vocals|Woodwinds|Brass|FX|Synth|Strings|Percussion|Bass|Guitar|Piano|Keys|Keyboard|Keyboards|Other|Without Bass|Without Drums|Without Vocals)\)\s*$", title, re.I):
        return True
    if re.search(r"\bWithout\s+(Bass|Drums|Vocals|Guitar|Piano|Keyboard|Keyboards)\b", title, re.I):
        return True

    return False

def fetch_suno_workspaces_page(page=1):
    headers = suno_api_headers()
    url = f"https://studio-api-prod.suno.com/api/project/me?page={int(page or 1)}&sort=created_at&show_trashed=false"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        mark_suno_api_token_valid()
        return data
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        if e.code == 401:
            mark_suno_api_token_invalid()
            raise SunoAuthenticationError("Suno API HTTP 401: token is expired or invalid. Use Renew Suno login in LS.") from e
        if e.code == 429:
            raise SunoRateLimitError("Suno API HTTP 429: Too many requests. Wait 5-10 minutes and try Refresh Tracklist again.") from e
        raise RuntimeError(f"Suno API HTTP {e.code}: {detail}") from e

def list_recent_suno_workspaces(limit=8):
    data = fetch_suno_workspaces_page(page=1)
    projects = data.get("projects") or []
    if not isinstance(projects, list):
        projects = []

    result = []
    seen = set()
    for project in projects:
        if not isinstance(project, dict):
            continue
        wid = str(project.get("id") or project.get("project_id") or project.get("workspace_id") or "").strip()
        if not wid or wid in seen:
            continue
        seen.add(wid)
        result.append({
            "id": wid,
            "name": str(project.get("name") or project.get("title") or project.get("display_name") or "(workspace)").strip(),
            "created_at": str(project.get("created_at") or project.get("updated_at") or "").strip(),
        })
        if len(result) >= int(limit or 8):
            break
    return result

def fetch_suno_feed_page(cursor=None, limit=100, workspace_id="default"):
    """Read one Suno Library/Workspace page from feed/v3.

    Read-only. Does not write LS DB.
    """
    limit = max(1, min(int(limit or 100), 100))
    headers = suno_api_headers()
    filters = {
        "disliked": "False",
        "trashed": "False",
    }
    # v4.58: Suno Library is not the same as a Workspace.
    # For Library/global mode we must NOT pass workspace filter.
    if str(workspace_id or "").lower() not in ("library", "__library__", "global", "all", "__all__"):
        filters["workspace"] = {
            "presence": "True",
            "workspaceId": workspace_id or "default",
        }

    body = {
        "cursor": cursor,
        "limit": limit,
        "filters": filters,
    }
    request = urllib.request.Request(
        "https://studio-api-prod.suno.com/api/feed/v3",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        mark_suno_api_token_valid()
        return data
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        if e.code == 401:
            mark_suno_api_token_invalid()
            raise SunoAuthenticationError("Suno API HTTP 401: token is expired or invalid. Use Renew Suno login in LS.") from e
        if e.code == 429:
            raise SunoRateLimitError("Suno API HTTP 429: Too many requests. Wait 5-10 minutes and try Refresh Tracklist again.") from e
        raise RuntimeError(f"Suno API HTTP {e.code}: {detail}") from e


def ignore_suno_tracklist_selected(track_ids):
    selected = []
    seen = set()
    for value in track_ids or []:
        tid = str(value or "").strip()
        if tid and tid.lower() not in seen:
            selected.append(tid)
            seen.add(tid.lower())

    if not selected:
        return {"ok": False, "error": "No Suno tracks selected to ignore"}

    all_ignored = add_ignored_suno_tracklist_ids(selected)
    return {
        "ok": True,
        "ignored_added": len(selected),
        "ignored_total": len(all_ignored),
        "ignored_ids": selected,
    }

def restore_suno_tracklist_ignored(track_ids):
    selected = []
    seen = set()
    for value in track_ids or []:
        tid = str(value or "").strip()
        if tid and tid.lower() not in seen:
            selected.append(tid)
            seen.add(tid.lower())

    if not selected:
        return {"ok": False, "error": "No ignored Suno tracks selected to restore"}

    remaining, restored_count = remove_ignored_suno_tracklist_ids(selected)
    return {
        "ok": True,
        "restored": restored_count,
        "ignored_total": len(remaining),
        "restored_ids": selected,
    }

def import_suno_tracklist_selected(track_ids, limit=100, workspace_id="latest"):
    selected = []
    seen = set()
    for value in track_ids or []:
        tid = str(value or "").strip()
        if tid and tid.lower() not in seen:
            selected.append(tid)
            seen.add(tid.lower())

    if not selected:
        return {"ok": False, "error": "No new Suno tracks selected"}

    # Re-read current recent tracklist from Suno API and import only selected IDs.
    preview = build_suno_tracklist_preview(limit=max(int(limit or 100), len(selected)), workspace_id=workspace_id or "latest")
    wanted = {tid.lower() for tid in selected}
    tracks_to_import = []
    for raw in preview.get("raw_regular_tracks", []):
        tid = str(raw.get("id") or raw.get("clip_id") or "").strip().lower()
        if tid in wanted:
            tracks_to_import.append(raw)

    if not tracks_to_import:
        return {"ok": False, "error": "Selected IDs were not found in the current Suno tracklist preview. Refresh Tracklist and try again."}

    prepared_tracks = [
        {
            "raw": raw,
            "meta": extract_suno_metadata_for_ls(raw),
            "is_stem": is_suno_stem_track(raw),
        }
        for raw in tracks_to_import
    ]
    return insert_suno_tracks_metadata_only(prepared_tracks)



LS_PROVEN_STRUCTURED_FIELDS = (
    "metadata_is_remix",
    "metadata_has_vocal",
    "metadata_make_instrumental",
    "metadata_has_stem",
    "model_name",
)

LS_CONFIRMED_PROMPT_REPAIR_IDS = {
    "b3deeaae-5247-40ab-85ca-27fdd3919a6c",
}

LS_INTENT_AUDIT_ENGINE_VERSION = "2026-07-19.2"

LS_INTENT_AUDIT_TABLE = "ls_category_intent_audit"

LS_INTENT_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

LS_INTENT_BRACKET_LINE_RE = re.compile(r"^\s*[\[(].*[\])]\s*$")

LS_INTENT_INSTRUMENTAL_ONLY_RE = re.compile(
    r"^\s*(?:[\[(]\s*)?instrumental(?:\s*[\])])?\s*$",
    re.IGNORECASE,
)

LS_INTENT_STRUCTURE_MARKER_RE = re.compile(
    r"[\[(]\s*(?:verse|chorus|bridge|intro|outro|pre[- ]?chorus|refrain|pants|piedziedājums)\b",
    re.IGNORECASE,
)

LS_CATEGORY_ASSIGNMENT_SCORE = 90

def refresh_suno_metadata_for_track_ids(track_ids, overwrite=False, delay_seconds=1.25, progress_callback=None):
    ids = []
    seen = set()
    for value in track_ids or []:
        tid = str(value or "").strip()
        if not tid:
            continue
        key = tid.lower()
        if key not in seen:
            ids.append(tid)
            seen.add(key)

    if not ids:
        return {
            "ok": False,
            "error": "No Track IDs selected",
        }

    backup_path = backup_db_before_metadata_import()

    rows = []
    updated_tracks = 0
    total_fields = 0
    total_conflicts = 0
    errors = 0
    rate_limited = False
    authentication_stopped = False
    repeated_errors_stopped = False
    stopped_after = 0
    skipped_excluded = 0
    consecutive_errors = 0

    def emit_progress(processed):
        if not callable(progress_callback):
            return
        try:
            last_row = rows[-1] if rows else {}
            progress_callback({
                "processed": int(processed),
                "total": len(ids),
                "updated_tracks": updated_tracks,
                "total_fields": total_fields,
                "total_conflicts": total_conflicts,
                "errors": errors,
                "current_track_id": last_row.get("track_id") or "",
                "current_title": last_row.get("title") or "",
                "current_status": last_row.get("status") or "",
                "current_source": last_row.get("source") or "",
            })
        except Exception:
            # Progress persistence must never interrupt the metadata transaction.
            pass

    for index, track_id in enumerate(ids, start=1):
        used_api = False
        try:
            current = get_track_row_for_meta(track_id)
            if not current:
                raise RuntimeError("Track ID not found in LS DB")
            if is_ls_stem_metadata_row(current):
                skipped_excluded += 1
                rows.append({
                    "track_id": track_id,
                    "short_id": track_id[:8],
                    "title": current.get("title") or "",
                    "status": "SKIPPED_STEM",
                    "source": "LS DB",
                    "error": "Known Stem metadata row; automatic song backfill is disabled.",
                    "fields": [],
                    "conflicts": [],
                })
                emit_progress(index)
                continue
            if is_ls_edit_section_row(current):
                skipped_excluded += 1
                rows.append({
                    "track_id": track_id,
                    "short_id": track_id[:8],
                    "title": current.get("title") or "",
                    "status": "SKIPPED_EDIT_SECTION",
                    "source": "LS DB",
                    "error": "Known Edit/Section row; automatic song backfill is disabled.",
                    "fields": [],
                    "conflicts": [],
                })
                emit_progress(index)
                continue

            source = "Suno API"
            raw_json_text = str(current.get("raw_json") or "").strip()
            if raw_json_text:
                try:
                    track_data = json.loads(raw_json_text)
                    if not isinstance(track_data, dict):
                        raise ValueError("raw_json is not an object")
                    source = "Stored Suno data"
                except Exception:
                    used_api = True
                    track_data = fetch_suno_track_by_id(track_id)
            else:
                used_api = True
                track_data = fetch_suno_track_by_id(track_id)

            api_meta = extract_suno_metadata_for_ls(track_data)
            apply_result = apply_suno_metadata_to_db(track_id, api_meta, overwrite=overwrite)
            consecutive_errors = 0
            updated_fields = apply_result.get("updated_fields") or []
            conflicts = apply_result.get("conflicts") or []
            if updated_fields:
                updated_tracks += 1
                total_fields += len(updated_fields)
            total_conflicts += len(conflicts)
            if updated_fields and conflicts:
                status = "UPDATED_WITH_CONFLICTS"
            elif updated_fields:
                status = "UPDATED"
            elif conflicts:
                status = "CONFLICTS_NOT_CHANGED"
            else:
                status = "NO_CHANGES"
            rows.append({
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": api_meta.get("title") or current.get("title") or "",
                "status": status,
                "source": source,
                "fields": updated_fields,
                "conflicts": conflicts,
                "error": ("Conflicts left unchanged: " + ", ".join(conflicts)) if conflicts else "",
            })
        except SunoAuthenticationError as e:
            errors += 1
            authentication_stopped = True
            stopped_after = index
            rows.append({
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": "",
                "status": "AUTHENTICATION_STOP",
                "source": "Suno API",
                "error": str(e),
                "fields": [],
                "conflicts": [],
            })
            for remaining_id in ids[index:]:
                rows.append({
                    "track_id": remaining_id,
                    "short_id": remaining_id[:8],
                    "title": "",
                    "status": "SKIPPED_AFTER_401",
                    "source": "Suno API",
                    "error": "Skipped because authorization expired. Renew Suno login, then continue.",
                    "fields": [],
                    "conflicts": [],
                })
            emit_progress(index)
            break
        except SunoRateLimitError as e:
            errors += 1
            rate_limited = True
            stopped_after = index
            rows.append({
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": "",
                "status": "RATE_LIMIT",
                "source": "Suno API",
                "error": str(e),
                "fields": [],
                "conflicts": [],
            })
            for remaining_id in ids[index:]:
                rows.append({
                    "track_id": remaining_id,
                    "short_id": remaining_id[:8],
                    "title": "",
                    "status": "SKIPPED_AFTER_RATE_LIMIT",
                    "source": "Suno API",
                    "error": "Skipped because Suno API returned 429. Run again later.",
                    "fields": [],
                    "conflicts": [],
                })
            emit_progress(index)
            break
        except SunoTrackNotFoundError as e:
            errors += 1
            consecutive_errors = 0
            rows.append({
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": "",
                "status": "NOT_FOUND_IN_SUNO",
                "source": "Suno API",
                "error": str(e),
                "fields": [],
                "conflicts": [],
            })
        except Exception as e:
            errors += 1
            consecutive_errors += 1
            rows.append({
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": "",
                "status": "ERROR",
                "source": "Suno API" if used_api else "Stored Suno data",
                "error": str(e),
                "fields": [],
                "conflicts": [],
            })
            if consecutive_errors >= 3:
                repeated_errors_stopped = True
                stopped_after = index
                for remaining_id in ids[index:]:
                    rows.append({
                        "track_id": remaining_id,
                        "short_id": remaining_id[:8],
                        "title": "",
                        "status": "SKIPPED_AFTER_REPEATED_ERRORS",
                        "source": "Suno API",
                        "error": "Skipped after three consecutive unexpected errors. Check the report, then continue.",
                        "fields": [],
                        "conflicts": [],
                    })
                emit_progress(index)
                break

        emit_progress(index)
        if used_api and index < len(ids) and delay_seconds:
            time.sleep(float(delay_seconds))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = REPORTS_DIR
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"suno_meta_refresh_{stamp}.md"
    csv_path = reports_dir / f"suno_meta_refresh_{stamp}.csv"

    try:
        import csv
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["track_id", "short_id", "title", "status", "source", "fields", "conflicts", "error"])
            writer.writeheader()
            for row in rows:
                writer.writerow({
                    "track_id": row.get("track_id", ""),
                    "short_id": row.get("short_id", ""),
                    "title": row.get("title", ""),
                    "status": row.get("status", ""),
                    "source": row.get("source", ""),
                    "fields": ",".join(row.get("fields") or []),
                    "conflicts": ",".join(row.get("conflicts") or []),
                    "error": row.get("error", ""),
                })
    except Exception:
        csv_path = ""

    lines = []
    lines.append("# Suno API Metadata Refresh")
    lines.append("")
    lines.append(f"- Backup: `{backup_path}`")
    lines.append(f"- Mode: **{'overwrite existing fields' if overwrite else 'fill empty fields only'}**")
    lines.append(f"- Selected Track IDs: **{len(ids)}**")
    lines.append(f"- Updated tracks: **{updated_tracks}**")
    lines.append(f"- Total field updates: **{total_fields}**")
    lines.append(f"- Conflicts left unchanged: **{total_conflicts}**")
    lines.append(f"- Stem/Edit rows skipped: **{skipped_excluded}**")
    lines.append(f"- Errors: **{errors}**")
    lines.append(f"- Delay between API calls: **{delay_seconds}s**")
    if rate_limited:
        lines.append(f"- Rate limited: **YES** — stopped after request **{stopped_after}**. Wait 5-10 minutes and continue with a smaller Limit.")
    if authentication_stopped:
        lines.append(f"- Authentication expired: **YES** — stopped safely after request **{stopped_after}**. Renew Suno login, then continue.")
    if repeated_errors_stopped:
        lines.append(f"- Repeated errors: **YES** — stopped safely after request **{stopped_after}**. Check the report before continuing.")
    if csv_path:
        lines.append(f"- CSV: `{csv_path}`")
    lines.append("")
    lines.append("## Rows")
    for row in rows:
        if row.get("status") in ("UPDATED", "UPDATED_WITH_CONFLICTS"):
            suffix = ""
            if row.get("conflicts"):
                suffix = f"; conflicts unchanged: `{', '.join(row.get('conflicts') or [])}`"
            lines.append(f"- `{row.get('short_id')}` — {row.get('title') or row.get('track_id')} — `{', '.join(row.get('fields') or [])}`{suffix}")
        elif row.get("status") == "ERROR":
            lines.append(f"- `{row.get('short_id')}` — ERROR — {row.get('error')}")
        elif row.get("conflicts"):
            lines.append(f"- `{row.get('short_id')}` — conflicts unchanged — `{', '.join(row.get('conflicts') or [])}`")
        else:
            lines.append(f"- `{row.get('short_id')}` — {row.get('status') or 'no changes'}")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "ok": True,
        "backup": str(backup_path),
        "report": str(report_path),
        "csv": str(csv_path) if csv_path else "",
        "selected": len(ids),
        "updated_tracks": updated_tracks,
        "total_fields": total_fields,
        "total_conflicts": total_conflicts,
        "skipped_excluded": skipped_excluded,
        "errors": errors,
        "rate_limited": rate_limited,
        "authentication_stopped": authentication_stopped,
        "repeated_errors_stopped": repeated_errors_stopped,
        "stopped_after": stopped_after,
        "delay_seconds": delay_seconds,
        "rows": rows,
    }

def get_suno_metadata_job_status():
    global SUNO_METADATA_JOB_THREAD
    with SUNO_METADATA_JOB_LOCK:
        state = read_suno_metadata_job_state()
        thread_alive = bool(SUNO_METADATA_JOB_THREAD and SUNO_METADATA_JOB_THREAD.is_alive())
        if state.get("running") and not thread_alive:
            state.update({
                "status": "interrupted",
                "running": False,
                "finished_at": now_iso_local(),
                "message": "The previous LS process stopped. Start automatic backfill again to continue from the remaining DB rows.",
            })
            state = write_suno_metadata_job_state(state)
        return state

def _run_full_suno_metadata_backfill_job(track_ids):
    global SUNO_METADATA_JOB_THREAD
    last_persisted_at = [0.0]

    def progress_callback(progress):
        now = time.time()
        processed = int(progress.get("processed") or 0)
        total = int(progress.get("total") or len(track_ids))
        if processed < total and now - last_persisted_at[0] < 0.45:
            return
        last_persisted_at[0] = now
        state = read_suno_metadata_job_state()
        state.update(progress)
        state.update({
            "status": "running",
            "running": True,
            "message": "Automatic metadata backfill is running.",
        })
        write_suno_metadata_job_state(state)

    try:
        result = refresh_suno_metadata_for_track_ids(
            track_ids,
            overwrite=False,
            delay_seconds=1.25,
            progress_callback=progress_callback,
        )
        state = read_suno_metadata_job_state()
        processed = int(result.get("stopped_after") or len(track_ids))
        if result.get("authentication_stopped"):
            status = "stopped_401"
            message = "Suno session expired. Renew Suno login, then start again; LS will continue from the remaining rows."
        elif result.get("rate_limited"):
            status = "stopped_429"
            message = "Suno rate limit reached. Wait 5-10 minutes, then start again; LS will continue from the remaining rows."
        elif result.get("repeated_errors_stopped"):
            status = "stopped_errors"
            message = "LS stopped after three consecutive unexpected errors. Check the report, then start again to continue."
        elif result.get("errors"):
            status = "completed_with_errors"
            message = "Automatic metadata backfill completed with individual row errors."
            processed = len(track_ids)
        else:
            status = "completed"
            message = "Automatic metadata backfill completed."
            processed = len(track_ids)
        state.update({
            "status": status,
            "running": False,
            "message": message,
            "finished_at": now_iso_local(),
            "processed": processed,
            "total": len(track_ids),
            "updated_tracks": result.get("updated_tracks") or 0,
            "total_fields": result.get("total_fields") or 0,
            "total_conflicts": result.get("total_conflicts") or 0,
            "errors": result.get("errors") or 0,
            "backup": result.get("backup") or "",
            "report": result.get("report") or "",
            "csv": result.get("csv") or "",
        })
        write_suno_metadata_job_state(state)
    except Exception as exc:
        state = read_suno_metadata_job_state()
        state.update({
            "status": "failed",
            "running": False,
            "message": str(exc),
            "finished_at": now_iso_local(),
            "errors": int(state.get("errors") or 0) + 1,
        })
        write_suno_metadata_job_state(state)
    finally:
        with SUNO_METADATA_JOB_LOCK:
            SUNO_METADATA_JOB_THREAD = None

def start_full_suno_metadata_backfill():
    global SUNO_METADATA_JOB_THREAD
    with SUNO_METADATA_JOB_LOCK:
        if SUNO_METADATA_JOB_THREAD and SUNO_METADATA_JOB_THREAD.is_alive():
            state = read_suno_metadata_job_state()
            state["already_running"] = True
            return state

        preview = build_suno_update_preview(limit=1000000)
        track_ids = [str(row.get("id") or "").strip() for row in preview.get("rows") or []]
        track_ids = [track_id for track_id in track_ids if track_id]
        if not track_ids:
            state = default_suno_metadata_job_state()
            state.update({
                "status": "completed",
                "running": False,
                "message": "No actionable missing metadata rows remain.",
                "started_at": now_iso_local(),
                "finished_at": now_iso_local(),
            })
            return write_suno_metadata_job_state(state)

        state = default_suno_metadata_job_state()
        state.update({
            "status": "running",
            "running": True,
            "message": "Automatic metadata backfill is starting.",
            "started_at": now_iso_local(),
            "total": len(track_ids),
            "remaining": len(track_ids),
            "conflict_rows": preview.get("conflict_rows") or 0,
            "excluded_stems": preview.get("excluded_stems") or 0,
            "excluded_edits": preview.get("excluded_edits") or 0,
        })
        write_suno_metadata_job_state(state)
        SUNO_METADATA_JOB_THREAD = threading.Thread(
            target=_run_full_suno_metadata_backfill_job,
            args=(track_ids,),
            name="suno-metadata-backfill",
            daemon=True,
        )
        SUNO_METADATA_JOB_THREAD.start()
        return state


def find_chrome_executable():
    chrome_candidates = []
    edge_candidates = []

    for env_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        root = os.environ.get(env_name)
        if not root:
            continue
        root_path = Path(root)
        chrome_candidates.append(
            root_path / "Google" / "Chrome" / "Application" / "chrome.exe"
        )
        edge_candidates.append(
            root_path / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        )

    located_chrome = shutil.which("chrome.exe")
    if located_chrome:
        chrome_candidates.append(Path(located_chrome))

    located_edge = shutil.which("msedge.exe")
    if located_edge:
        edge_candidates.append(Path(located_edge))

    seen = set()
    for candidate in chrome_candidates + edge_candidates:
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.is_file():
            return str(candidate)

    return ""

class SunoAuthenticationError(RuntimeError):
    pass

class SunoRateLimitError(RuntimeError):
    pass

class SunoTrackNotFoundError(RuntimeError):
    pass


def _token_bridge_readme_text():
    return """LS SUNO TOKEN BRIDGE v2.4.2

Purpose
-------
The extension runs only on https://suno.com/ and observes Suno page fetch/XHR calls
to https://studio-api-prod.suno.com/. When one of those calls carries the current
Authorization: Bearer token, the extension relays that token only to the local
LocalSunoDb endpoint:
http://127.0.0.1:8765/bridge-set-suno-api-token

Architecture
------------
page_capture.js  - MAIN world; reads Authorization before fetch/XHR is sent.
content_bridge.js - isolated content script; relays the captured token to the extension.
service_worker.js - sends the token only to local LocalSunoDb and keeps the bridge ping alive.

Self-diagnostics
----------------
The page bridge checks every two seconds that its fetch hook is still active. If Suno
replaces window.fetch, the bridge attaches itself again without replacing or bypassing
the current Suno request chain. A small diagnostic snapshot is sent only after a state
change and every 30 seconds. It contains no token and does not access the LS database.

Install / update
----------------
1. Start LocalSunoDb.
2. In LS Rīki → Suno savienojums click Bridge setup. This refreshes the files in:
   E:\\LocalSunoDb\\LS_Suno_TokenBridge
3. Open chrome://extensions/
4. On LS Suno Token Bridge click Reload.
   For a first install: enable Developer mode, click Load unpacked, and select the folder above.
5. Open Suno tabs are refreshed automatically once after the extension reloads.

After installation
------------------
Use Renew Suno login in LS or simply reload/open Suno Library. The next authenticated
Suno API request updates the token in LS automatically. F12 and manual token copying
are not needed.

Security
--------
The extension contains no remote code. It runs only on suno.com and can send data only
to the local LS address declared in host_permissions. The token is never logged by the
extension and is not sent to any third-party destination.
"""

def suno_api_headers():
    token = get_suno_api_token()
    if not token:
        raise ValueError("Missing Suno API token. Paste token in Downloader tab first.")

    return {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.8",
        "Authorization": f"Bearer {token}",
        "Browser-Token": ls_generate_browser_token(),
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Device-Id": get_or_create_suno_device_id(),
        "Origin": "https://suno.com",
        "Pragma": "no-cache",
        "Referer": "https://suno.com/",
        "User-Agent": "Mozilla/5.0",
    }


def _request_suno_wav_conversion(track_id):
    track_id = str(track_id or "").strip()
    if not track_id:
        raise ValueError("Missing Track ID")

    url = (
        "https://studio-api-prod.suno.com/api/gen/"
        + urllib.parse.quote(track_id)
        + "/convert_wav/"
    )
    request = urllib.request.Request(
        url,
        data=b"",
        headers=suno_api_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            status = int(response.getcode() or 0)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        if exc.code == 401:
            mark_suno_api_token_invalid()
            raise SunoAuthenticationError(
                "Suno convert_wav HTTP 401: token is expired or invalid."
            ) from exc
        if exc.code == 429:
            raise SunoRateLimitError(
                "Suno convert_wav HTTP 429: Too many requests. Wait and try again later."
            ) from exc
        raise RuntimeError(
            f"Suno convert_wav HTTP {exc.code}: {detail or exc.reason}"
        ) from exc

    if status not in (200, 202, 204):
        raise RuntimeError(f"Suno convert_wav returned unexpected HTTP {status}")
    mark_suno_api_token_valid()


def _wait_for_suno_wav_file_url(track_id, max_wait_seconds=120, poll_interval=2.5):
    track_id = str(track_id or "").strip()
    if not track_id:
        raise ValueError("Missing Track ID")

    url = (
        "https://studio-api-prod.suno.com/api/gen/"
        + urllib.parse.quote(track_id)
        + "/wav_file/"
    )
    deadline = time.monotonic() + float(max_wait_seconds)
    attempt = 0
    last_detail = "WAV conversion is still pending"

    while True:
        attempt += 1
        request = urllib.request.Request(
            url,
            headers=suno_api_headers(),
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                status = int(response.getcode() or 0)
                raw = response.read().decode("utf-8", errors="replace").strip()

            mark_suno_api_token_valid()
            if status == 200:
                try:
                    data = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    data = {}
                    last_detail = "wav_file returned non-JSON response"

                wav_url = (
                    str(data.get("wav_file_url") or "").strip()
                    if isinstance(data, dict)
                    else ""
                )
                if wav_url.startswith(("http://", "https://")):
                    return wav_url
                last_detail = "wav_file_url is not ready yet"
            else:
                last_detail = f"wav_file returned HTTP {status}"

        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code == 401:
                mark_suno_api_token_invalid()
                raise SunoAuthenticationError(
                    "Suno wav_file HTTP 401: token is expired or invalid."
                ) from exc
            if exc.code == 429:
                raise SunoRateLimitError(
                    "Suno wav_file HTTP 429: Too many requests. Wait and try again later."
                ) from exc
            if exc.code in (404, 409, 425, 502, 503, 504):
                last_detail = f"wav_file HTTP {exc.code}: conversion is not ready yet"
            else:
                raise RuntimeError(
                    f"Suno wav_file HTTP {exc.code}: {detail or exc.reason}"
                ) from exc

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Timed out waiting for Suno WAV after {attempt} checks. "
                f"Last status: {last_detail}"
            )
        time.sleep(float(poll_interval))


def prepare_suno_wav(track_id):
    """Prepare one Suno track for WAV download and return its final WAV URL."""
    _request_suno_wav_conversion(track_id)
    return _wait_for_suno_wav_file_url(track_id)


def build_suno_tracklist_preview(limit=100, workspace_id="latest"):
    """Compare recent Suno regular tracks with LS DB.

    Preview only; no DB writes.
    v4.53 skips stems and scans the newest workspaces instead of only "default".
    """
    target_regular = max(1, min(int(limit or 100), 100))

    workspaces_scanned = []
    raw_fetched = 0
    skipped_stems = 0
    skipped_ignored = 0
    ignored_ids = {tid.lower() for tid in get_ignored_suno_tracklist_ids()}
    clips = []
    seen_clip_ids = set()

    workspace_mode = str(workspace_id or "library").lower()
    if workspace_mode in ("library", "__library__", "global", "all", "__all__"):
        workspaces = [{"id": "__library__", "name": "Suno Library", "created_at": ""}]
    elif workspace_id in ("latest", "__latest__", "auto", ""):
        workspaces = list_recent_suno_workspaces(limit=6)
        if not workspaces:
            workspaces = [{"id": "default", "name": "default", "created_at": ""}]
    else:
        workspaces = [{"id": workspace_id, "name": workspace_id, "created_at": ""}]

    for ws_index, ws in enumerate(workspaces, start=1):
        if len(clips) >= target_regular:
            break
        wid = ws.get("id") or "default"
        api_workspace_id = "library" if wid == "__library__" else wid
        try:
            data = fetch_suno_feed_page(cursor=None, limit=100 if wid == "__library__" else 50, workspace_id=api_workspace_id)
        except SunoRateLimitError:
            raise
        except Exception as e:
            workspaces_scanned.append({
                "id": wid,
                "name": ws.get("name") or wid,
                "created_at": ws.get("created_at") or "",
                "error": str(e),
                "raw_fetched": 0,
                "regular": 0,
                "stems": 0,
            })
            continue

        page_clips = data.get("clips") or []
        if not isinstance(page_clips, list):
            page_clips = []

        ws_regular = 0
        ws_stems = 0
        raw_fetched += len(page_clips)

        for track in page_clips:
            if not isinstance(track, dict):
                continue

            if is_suno_stem_track(track):
                skipped_stems += 1
                ws_stems += 1
                continue

            tid = str(track.get("id") or track.get("clip_id") or "").strip()
            tid_key = tid.lower()
            if not tid or tid_key in seen_clip_ids:
                continue
            if tid_key in ignored_ids:
                skipped_ignored += 1
                continue
            seen_clip_ids.add(tid_key)

            # Attach workspace name from project API if feed item does not contain it.
            track.setdefault("workspaceId", wid)
            if ws.get("name"):
                track.setdefault("workspaceName", ws.get("name"))
            clips.append(track)
            ws_regular += 1

            if len(clips) >= target_regular:
                break

        workspaces_scanned.append({
            "id": wid,
            "name": ws.get("name") or wid,
            "created_at": ws.get("created_at") or "",
            "error": "",
            "raw_fetched": len(page_clips),
            "regular": ws_regular,
            "stems": ws_stems,
        })

        if ws_index < len(workspaces) and len(clips) < target_regular:
            time.sleep(0.7)

    ls_ids, ls_map = get_track_identity_snapshot()

    new_items = []
    existing_items = []
    changed_items = []
    for track in clips:
        meta = extract_suno_metadata_for_ls(track)
        tid = (meta.get("id") or "").strip()
        if not tid:
            continue
        item = {
            "id": tid,
            "short_id": tid[:8],
            "title": meta.get("title") or "(untitled)",
            "workspace": meta.get("workspaceName") or "",
            "workspace_id": meta.get("workspaceId") or "",
            "created_at": meta.get("created_at") or "",
            "model_name": meta.get("model_name") or "",
            "audio_url": meta.get("audio_url") or "",
            "has_audio_url": bool(meta.get("audio_url")),
            "has_lyrics": bool(meta.get("lyrics")),
            "has_prompt": bool(meta.get("prompt")),
            "has_style": bool(meta.get("metadata_tags")),
        }
        key = tid.lower()
        if key in ls_ids:
            ls_item = ls_map.get(key) or {}
            ls_title = ls_item.get("title") or ""
            ls_workspace = ls_item.get("workspace") or ""
            item["ls_title"] = ls_title
            item["ls_workspace"] = ls_workspace
            existing_items.append(item)
            if (ls_title or "").strip() and (item["title"] or "").strip() and ls_title.strip() != item["title"].strip():
                changed_items.append(item)
        else:
            new_items.append(item)

    return {
        "ok": True,
        "workspace_id": workspace_id or "latest",
        "requested_limit": target_regular,
        "fetched": raw_fetched,
        "regular_fetched": len(clips),
        "skipped_stems": skipped_stems,
        "skipped_ignored": skipped_ignored,
        "ignored_total": len(ignored_ids),
        "new_count": len(new_items),
        "existing_count": len(existing_items),
        "changed_count": len(changed_items),
        "has_more": False,
        "next_cursor": "",
        "workspaces_scanned": workspaces_scanned,
        "raw_regular_tracks": clips,
        "new_items": new_items,
        "changed_items": changed_items[:100],
        "existing_items": existing_items[:50],
    }


def update_selected_suno_titles_from_library(track_ids, limit=100, workspace_id="latest"):
    selected = []
    seen = set()
    for value in track_ids or []:
        tid = str(value or "").strip()
        if tid and tid.lower() not in seen:
            selected.append(tid)
            seen.add(tid.lower())
    if not selected:
        return {"ok": False, "error": "No changed title rows selected"}
    preview = build_suno_tracklist_preview(
        limit=max(int(limit or 100), len(selected)),
        workspace_id=workspace_id or "latest",
    )
    return apply_suno_title_updates(selected, preview.get("changed_items", []))


