import base64
import difflib
import hashlib
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
import tempfile
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
from ls_data.repository import get_track_local_family_titles

def get_downloader_state():
    """Return the last saved Downloader UI state.

    This cache is independent of the Python version, so a new LocalSunoDb file can
    reopen the previous Downloader result without contacting Suno again.
    """
    try:
        if not DOWNLOADER_STATE_PATH.exists():
            return {"ok": True, "state": {}}
        data = json.loads(DOWNLOADER_STATE_PATH.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, dict):
            data = {}
        return {"ok": True, "state": data}
    except Exception as e:
        return {"ok": False, "error": str(e), "state": {}}

def save_downloader_state(state):
    """Persist Downloader HTML and UI choices without touching the LS database."""
    if not isinstance(state, dict):
        state = {}

    allowed = {
        "html",
        "status_text",
        "status_mode",
        "scroll_y",
        "checked_controls",
        "select_values",
        "saved_at",
        "view_kind",
    }
    clean = {key: state.get(key) for key in allowed if key in state}
    saved_at = str(clean.get("saved_at") or "").strip()
    if not saved_at:
        saved_at = now_iso_local()
    clean["saved_at"] = saved_at[:80]
    clean["saved_by_version"] = APP_VERSION

    html_text = str(clean.get("html") or "")
    if len(html_text) > 5_000_000:
        raise ValueError("Saglabātais Importa skats ir pārāk liels")
    clean["html"] = html_text

    DOWNLOADER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DOWNLOADER_STATE_PATH.with_suffix(DOWNLOADER_STATE_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(DOWNLOADER_STATE_PATH)
    return {"ok": True, "saved_at": clean["saved_at"], "path": str(DOWNLOADER_STATE_PATH)}

def clear_downloader_state():
    try:
        if DOWNLOADER_STATE_PATH.exists():
            DOWNLOADER_STATE_PATH.unlink()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}







def build_meta_preview(track_id):
    track_data = fetch_suno_track_by_id(track_id)
    api_meta = extract_suno_metadata_for_ls(track_data)
    db_row = get_track_row_for_meta(track_id)
    columns = get_table_columns()

    mapping = [
        ("audio_url", ["audio_url"]),
        ("created_at", ["created_at"]),
        ("lyrics", ["lyrics"]),
        ("prompt", ["prompt", "metadata_prompt"]),
        ("metadata_tags", ["metadata_tags", "tags", "style"]),
        ("image_url", ["image_url", "raw_image_url", "cover_art_url"]),
        ("workspaceName", ["workspaceName", "workspace_name", "workspace"]),
        ("workspaceId", ["workspaceId", "workspace_id"]),
        ("reaction_type", ["reaction_type"]),
        ("model_name", ["model_name", "model", "major_model_version"]),
        ("bpm", ["bpm", "metadata_avg_bpm"]),
        ("key", ["key", "musical_key"]),
        ("raw_json", ["raw_json", "raw_api_json", "full_data_json", "full_metadata_json"]),
    ]

    fields = []
    for api_key, db_candidates in mapping:
        db_col = ls_column_exists(columns, db_candidates)
        api_value = str(api_meta.get(api_key) or "").strip()
        db_value = str(db_row.get(db_col) or "").strip() if db_col and db_row else ""
        can_fill = bool(api_value and db_col and not db_value)
        fields.append({
            "api_key": api_key,
            "db_column": db_col,
            "api_present": bool(api_value),
            "db_empty": not bool(db_value),
            "can_fill": can_fill,
            "api_preview": shorten_text(api_value.replace("\\n", " / "), 180),
            "db_preview": shorten_text(db_value.replace("\\n", " / "), 120),
        })

    return {
        "ok": True,
        "track_id": track_id,
        "title": api_meta.get("title") or (db_row.get("title") if db_row else ""),
        "found_in_db": bool(db_row),
        "api_meta": {k: (shorten_text(str(v).replace("\\n", " / "), 260) if k != "raw_json" else f"{len(str(v))} chars") for k, v in api_meta.items() if v},
        "fields": fields,
        "fillable_count": sum(1 for item in fields if item["can_fill"]),
    }



def safe_windows_path_part(value, fallback="Untitled", max_length=110):
    """Return a Windows-safe folder/file stem while keeping the title human-readable."""
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        text = fallback
    if text.upper() in WINDOWS_RESERVED_NAMES:
        text = "_" + text
    text = text[:max_length].rstrip(" .")
    return text or fallback

def next_variant_folder(song_folder):
    song_folder = Path(song_folder)
    used = []
    if song_folder.exists():
        for child in song_folder.iterdir():
            if not child.is_dir():
                continue
            name = child.name.strip()
            if name.isdigit():
                value = int(name)
                if value > 0:
                    used.append(value)

    highest_existing = max(used) if used else 0
    highest_remembered = get_remembered_variant_number(song_folder)
    next_number = max(highest_existing, highest_remembered) + 1
    return next_number, song_folder / str(next_number)

def backup_db_before_wav_download():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{DB_PATH.stem}_BEFORE_WAV_DOWNLOAD_{stamp}{DB_PATH.suffix}"
    shutil.copy2(DB_PATH, target)
    return target

def _collect_http_urls_with_wav_hint(value, result, key_hint=""):
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_http_urls_with_wav_hint(item, result, str(key or ""))
        return
    if isinstance(value, list):
        for item in value:
            _collect_http_urls_with_wav_hint(item, result, key_hint)
        return
    if not isinstance(value, str):
        return

    url = value.strip()
    if not url.startswith(("http://", "https://")):
        return

    low_url = url.lower().split("?", 1)[0]
    low_key = key_hint.lower()
    if low_url.endswith(".wav") or "wav" in low_key:
        if url not in result:
            result.append(url)

def _is_wav_file(path_obj):
    try:
        with open(path_obj, "rb") as handle:
            header = handle.read(12)
        return len(header) >= 12 and header[:4] in (b"RIFF", b"RF64", b"RIFX") and header[8:12] == b"WAVE"
    except Exception:
        return False

def download_url_to_wav(url, target_path, timeout=180):
    target_path = Path(target_path)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    if temp_path.exists():
        temp_path.unlink()

    request_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "audio/wav,audio/*;q=0.9,*/*;q=0.5",
        "Referer": "https://suno.com/",
    }
    request = urllib.request.Request(url, headers=request_headers, method="GET")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with open(temp_path, "wb") as handle:
                while True:
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    handle.write(chunk)

        if not temp_path.exists() or temp_path.stat().st_size == 0:
            raise RuntimeError("Lejupielādētais fails ir tukšs")
        if not _is_wav_file(temp_path):
            raise RuntimeError("Servera atbilde nav WAV fails")

        temp_path.replace(target_path)
        return target_path
    except Exception:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception as cleanup_exc:
            log_ls_exception(
                "downloader",
                "remove_partial_wav",
                cleanup_exc,
                context={"temp_path": str(temp_path)},
                include_traceback=False,
            )
        raise

def _unique_track_ids(track_ids):
    ids = []
    seen = set()
    for value in track_ids or []:
        tid = str(value or "").strip()
        key = tid.lower()
        if tid and key not in seen:
            ids.append(tid)
            seen.add(key)
    return ids

def build_selected_wav_download_preview(track_ids, local_family_title=""):
    """Build a read-only WAV target preview with manual Local family confirmation.

    The persistent Track ID -> Local family map is authoritative. The saved
    Local Database family title is only a proposal for tracks that have not yet
    been assigned.
    """
    ids = _unique_track_ids(track_ids)
    if not ids:
        return {"ok": False, "error": "Nav izvēlēta neviena dziesma"}

    if len(ids) != 1:
        return {
            "ok": False,
            "error": (
                "Lokālās saimes apstiprināšanai pašlaik jāizvēlas tieši 1 dziesma. "
                f"Izvēlētas: {len(ids)}"
            ),
        }

    proposal_title = clean_local_family_title(local_family_title)
    root = Path(get_audio_library_root_folder())
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": f"Audio bibliotēkas saknes mape nav atrasta: {root}"}

    rows = []
    for track_id in ids:
        info = get_track_download_info(track_id)
        if not info:
            return {"ok": False, "error": f"Track ID nav atrasts LS DB: {track_id}"}

        title = str(info.get("title") or "").strip() or "Untitled"
        category = normalize_download_category(info)
        existing_local_wav = str(info.get("local_wav") or "").strip()

        mapping = get_track_local_family(track_id)
        mapped_family_title = clean_local_family_title(
            mapping.get("family_title")
        )
        family_confirmed = bool(mapped_family_title)
        proposed_family_title = (
            mapped_family_title
            or proposal_title
            or title
        )

        safe_family_title = safe_windows_path_part(proposed_family_title)
        safe_filename_title = safe_windows_path_part(title)

        song_folder = root / category / safe_family_title
        variant_number, variant_folder = next_variant_folder(song_folder)
        target_path = variant_folder / f"{safe_filename_title}.wav"
        stems_folder = variant_folder / "Stems"

        family_options = get_local_family_options(proposed_family_title)
        similar_families = [
            item
            for item in family_options
            if item.get("is_similar")
        ][:12]

        rows.append({
            "track_id": track_id,
            "short_id": track_id[:8],
            "title": title,
            "category": category,
            "local_family_title": proposed_family_title,
            "proposed_family_title": proposed_family_title,
            "mapped_family_title": mapped_family_title,
            "family_confirmed": family_confirmed,
            "family_source": "track_map" if family_confirmed else "proposal",
            "family_map_updated_at": str(mapping.get("updated_at") or ""),
            "family_options": family_options,
            "similar_families": similar_families,
            "safe_family_title": safe_family_title,
            "filename_title": safe_filename_title,
            "variant": str(variant_number),
            "variant_folder": str(variant_folder),
            "target_path": str(target_path),
            "stems_folder": str(stems_folder),
            "already_linked": bool(existing_local_wav and Path(existing_local_wav).exists()),
            "existing_local_wav": existing_local_wav,
        })

    return {
        "ok": True,
        "root": str(root),
        "local_family_title": proposal_title,
        "selected": len(ids),
        "rows": rows,
    }

def download_selected_wavs_to_library(track_ids, local_family_title=""):
    """Download exactly one WAV using the confirmed Track ID -> Local Family map."""
    ids = _unique_track_ids(track_ids)
    if not ids:
        return {"ok": False, "error": "Nav izvēlēta neviena dziesma"}

    if len(ids) != 1:
        return {
            "ok": False,
            "error": (
                "WAV importam ar lokālo saimi pašlaik jāizvēlas tieši 1 dziesma. "
                f"Izvēlētas: {len(ids)}"
            ),
        }

    track_id = ids[0]
    root = Path(get_audio_library_root_folder())
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": f"Audio bibliotēkas saknes mape nav atrasta: {root}"}

    info = get_track_download_info(track_id)
    if not info:
        return {"ok": False, "error": f"Track ID nav atrasts LS DB: {track_id}"}

    title = str(info.get("title") or "").strip() or "Untitled"
    category = normalize_download_category(info)
    existing_local_wav = str(info.get("local_wav") or "").strip()

    local_family_titles = get_track_local_family_titles()
    family_title = clean_local_family_title(
        local_family_titles.get(str(track_id or "").strip().lower(), "")
    )
    if not family_title:
        return {
            "ok": False,
            "error": (
                "Šim Track ID lokālā saime nav manuāli apstiprināta. "
                "Atver WAV priekšskatījumu un izvēlies esošu saimi vai izveido jaunu."
            ),
        }

    if existing_local_wav and Path(existing_local_wav).exists():
        return {
            "ok": True,
            "root": str(root),
            "local_family_title": family_title,
            "backup": "",
            "report": "",
            "selected": 1,
            "downloaded": 0,
            "skipped": 1,
            "errors": 0,
            "auth_expired": False,
            "rows": [{
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": title,
                "local_family_title": family_title,
                "category": category,
                "variant": "",
                "status": "ALREADY_LINKED",
                "path": existing_local_wav,
                "error": "",
            }],
        }

    prepared_url = ""
    prepare_error = None
    try:
        prepared_url = prepare_suno_wav(track_id)
    except SunoAuthenticationError as exc:
        return {
            "ok": False,
            "error": "Suno autorizācija nav derīga. Atjauno Suno savienojumu un mēģini vēlreiz.",
            "auth_expired": True,
            "rows": [{
                "track_id": track_id,
                "short_id": track_id[:8],
                "title": title,
                "local_family_title": family_title,
                "category": category,
                "variant": "",
                "status": "AUTH_REQUIRED",
                "path": "",
                "error": str(exc),
            }],
        }
    except Exception as exc:
        prepare_error = exc

    backup_path = ""
    if prepare_error is None:
        backup_path = str(backup_db_before_wav_download())

    safe_family_title = safe_windows_path_part(family_title)
    safe_filename_title = safe_windows_path_part(title)
    song_folder = root / category / safe_family_title
    variant_number, variant_folder = next_variant_folder(song_folder)
    target_path = variant_folder / f"{safe_filename_title}.wav"
    stems_folder = variant_folder / "Stems"

    rows = []
    downloaded = 0
    errors = 0
    auth_expired = False

    try:
        if prepare_error is not None:
            raise prepare_error

        variant_folder.mkdir(parents=True, exist_ok=False)
        stems_folder.mkdir(exist_ok=True)
        download_url_to_wav(prepared_url, target_path)

        ok, message = add_local_audio_to_track(track_id, str(target_path))
        if not ok:
            raise RuntimeError("WAV lejupielādēts, bet piesaiste LS DB neizdevās: " + str(message))

        remember_variant_number(song_folder, variant_number)
        downloaded = 1
        rows.append({
            "track_id": track_id,
            "short_id": track_id[:8],
            "title": title,
            "local_family_title": family_title,
            "category": category,
            "variant": str(variant_number),
            "status": "DOWNLOADED",
            "path": str(target_path),
            "source_url": prepared_url,
            "error": "",
        })
    except Exception as exc:
        errors = 1
        auth_expired = (
            isinstance(exc, SunoAuthenticationError)
            or "HTTP 401" in str(exc)
            or "token is expired" in str(exc).lower()
        )
        try:
            part_path = target_path.with_suffix(target_path.suffix + ".part")
            if part_path.exists():
                part_path.unlink()
            if variant_folder.exists() and stems_folder.exists() and not any(stems_folder.iterdir()):
                stems_folder.rmdir()
            if variant_folder.exists() and not any(variant_folder.iterdir()):
                variant_folder.rmdir()
        except Exception as cleanup_exc:
            log_ls_exception(
                "downloader",
                "cleanup_failed_wav_download",
                cleanup_exc,
                context={
                    "track_id": track_id,
                    "variant_folder": str(variant_folder),
                    "partial_path": str(target_path.with_suffix(target_path.suffix + ".part")),
                },
                include_traceback=False,
            )

        rows.append({
            "track_id": track_id,
            "short_id": track_id[:8],
            "title": title,
            "local_family_title": family_title,
            "category": category,
            "variant": str(variant_number),
            "status": "ERROR",
            "path": str(target_path),
            "error": str(exc),
        })

    reports_dir = REPORTS_DIR
    reports_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"wav_download_{stamp}.md"

    lines = [
        "# LocalSunoDb WAV Download",
        "",
        f"- Audio library root: `{root}`",
        f"- Confirmed Local family: `{family_title}`",
        f"- Family map: `{LOCAL_FAMILY_MAP_PATH}`",
        f"- DB backup: `{backup_path}`" if backup_path else "- DB backup: `not needed`",
        "- Selected: **1**",
        f"- Downloaded: **{downloaded}**",
        "- Already linked: **0**",
        f"- Errors: **{errors}**",
        "",
        "| ID | Category | Family | Variant | Title | Status | Path | Error |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row.get('short_id','')}` | {row.get('category','')} | "
            f"{row.get('local_family_title','').replace('|','/')} | "
            f"{row.get('variant','')} | {row.get('title','').replace('|','/')} | "
            f"{row.get('status','')} | `{row.get('path','')}` | "
            f"{row.get('error','').replace('|','/')} |"
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "ok": True,
        "root": str(root),
        "local_family_title": family_title,
        "backup": backup_path,
        "report": str(report_path),
        "selected": 1,
        "downloaded": downloaded,
        "skipped": 0,
        "errors": errors,
        "auth_expired": auth_expired,
        "rows": rows,
    }
