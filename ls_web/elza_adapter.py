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

def ls_elza_fold_text(value):
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )

def ls_elza_resolve_workspace(value):
    requested = re.sub(r"\s+", " ", str(value or "").strip())
    if not requested:
        return ""
    for row in get_workspaces():
        candidate = str(row["workspace"] or "").strip()
        if candidate.casefold() == requested.casefold():
            return candidate
    return ""

def ls_elza_resolve_local_family(value):
    requested = re.sub(r"\s+", " ", str(value or "").strip())
    if not requested:
        return ""
    for item in get_confirmed_local_family_filter_options():
        candidate = str(item.get("title") or "").strip()
        if candidate.casefold() == requested.casefold():
            return candidate
    return ""

def parse_ls_elza_selection_intent(message):
    """Translate a narrow, deterministic natural-language command to LS filters."""
    source = re.sub(r"\s+", " ", str(message or "").strip())
    plain = ls_elza_fold_text(source)
    if not plain:
        return None

    has_command_verb = bool(re.search(
        r"\b(paradi|atlasi|atrodi|atver|uzskaiti|ieliec|dabut|show|find|list|open)\b",
        plain,
    ))
    legacy_liked_query = bool(
        "liked" in plain
        and (
            re.search(r"\bbez\s+lokal\w*\s+audio\b", plain)
            or re.search(r"\blokal\w*\s+audio.{0,24}\bnav\b", plain)
            or re.search(r"\bno\s+local\s+audio\b", plain)
        )
    )
    if not has_command_verb and not legacy_liked_query:
        return None

    filters = {}
    labels = []

    exact_stem_match = re.search(
        r"\b(?:ar|with|has)\s+(\d{1,3})\s+(?:stems?|stemiem)\b",
        plain,
    )
    exact_stem_count = int(exact_stem_match.group(1)) if exact_stem_match else None
    liked = bool(re.search(r"\bliked\b", plain))
    has_stems = bool(re.search(
        r"\b(?:ar|with|has)\s+(?:(?:\d{1,3})\s+)?(?:stems?|stemiem)\b|\bhas\s+stems?\b",
        plain,
    ))
    without_stems = bool(re.search(
        r"\b(?:bez|without|no)\s+(?:stems?|stemiem)\b",
        plain,
    ))
    if without_stems:
        return {
            "error": "LS pašlaik nav droša filtra “bez Stems”. Atlase netika mainīta.",
        }
    if liked and has_stems:
        return {
            "error": (
                "Liked un Has Stems pašlaik ir vienas LS filtru dimensijas izvēles. "
                "Tās nevar droši apvienot vienā atlasē."
            ),
        }
    if liked:
        filters["kind_filter"] = "__liked__"
        labels.append("Liked")
    elif has_stems:
        filters["kind_filter"] = "__has_stems__"
        labels.append("Has Stems")

    without_local_audio = bool(
        re.search(r"\bbez\s+lokal\w*\s+audio\b", plain)
        or re.search(r"\blokal\w*\s+audio.{0,24}\bnav\b", plain)
        or re.search(r"\bwithout\s+local\s+audio\b", plain)
        or re.search(r"\bno\s+local\s+audio\b", plain)
    )
    with_local_audio = bool(
        not without_local_audio
        and (
            re.search(r"\bar\s+lokal\w*\s+audio\b", plain)
            or re.search(r"\blokal\w*\s+audio.{0,24}\bir\b", plain)
            or re.search(r"\bwith\s+local\s+audio\b", plain)
        )
    )
    if without_local_audio:
        filters["local_audio_filter"] = "without"
        labels.append("No local audio")
    elif with_local_audio:
        filters["local_audio_filter"] = "with"
        labels.append("With local audio")

    local_audio_extensions = []
    if re.search(r"\bwav\b", plain):
        filters["local_audio_filter"] = "with"
        local_audio_extensions.append("wav")
        labels = [label for label in labels if label != "With local audio"]
        labels.append("Local WAV")

    exclude_ui_types = []
    exclude_upload = bool(
        re.search(
            r"\b(?:bez|iznem\w*|exclude\w*|without)\s+(?:upload|uplod|uploads?)\b",
            plain,
        )
        or re.search(r"(?:^|\s)-\s*(?:upload|uplod|uploads?)\b", plain)
    )
    if exclude_upload:
        exclude_ui_types.append("Upload")
        labels.append("Bez Type: Upload")

    if re.search(r"\binstrumental\w*\b", plain):
        filters["category_filter"] = "Instrumental"
        labels.append("Instrumental")
    elif (
        re.search(r"\b(?:tikai|only)\s+song\b", plain)
        or re.search(r"\bsong\s+kategor\w*\b", plain)
        or re.search(r"\bkategor\w*\s+song\b", plain)
    ):
        filters["category_filter"] = "Song"
        labels.append("Song")

    flag_numbers = []
    for match in re.finditer(r"(?<!\d)([0-5])\s*\+\s*\*", plain):
        number = int(match.group(1))
        if number not in flag_numbers:
            flag_numbers.append(number)

    # Natural Latvian/English aliases: “1. un 4. karodziņš”, “flags 1 and 4”.
    # LS multiple Flag filters are AND, matching the existing Filter Library
    # semantics. Explicit OR is not silently converted to AND.
    has_named_flag_term = bool(re.search(
        r"\b(?:karodz\w*|flags?|zvaigzn\w*)\b", plain,
    ))
    exact_flag_set_requested = bool(re.search(
        r"\b(?:tikai|tika|tiesi|vienigi|only|exactly)\s+"
        r"(?:(?:flags?|karodz\w*|zvaigzn\w*)\s+)?"
        r"[1-5](?:\s*[.)])?(?:\s*(?:un|and|,)\s*[1-5](?:\s*[.)])?)*",
        plain,
    ))
    if (has_named_flag_term or exact_flag_set_requested) and not flag_numbers:
        natural_flags = []
        for match in re.finditer(r"(?<!\d)([0-5])(?:\s*[.)])?(?!\d)", plain):
            number = int(match.group(1))
            if number not in natural_flags:
                natural_flags.append(number)
        if (
            not has_named_flag_term
            and exact_flag_set_requested
            and len([number for number in natural_flags if number > 0]) < 2
        ):
            natural_flags = []
        if len(natural_flags) > 1 and re.search(r"\b(?:vai|or)\b", plain):
            return {
                "error": (
                    "LS vairāku Flags atlase izmanto AND. “Vai/OR” kombinācija "
                    "vienā drošajā atlasē pašlaik netiek piemērota."
                ),
            }
        flag_numbers.extend(natural_flags)

    exact_flags = [number for number in flag_numbers if number > 0]
    if exact_flags:
        masks = [1 << (number - 1) for number in exact_flags]
        filters["flag_filter"] = ",".join(str(mask) for mask in masks)
        labels.extend([f"{number}+*" for number in exact_flags])
    elif 0 in flag_numbers:
        filters["search_marks"] = True
        labels.append("Any Flag")

    tags = normalize_tag_filter(
        [match.group(0) for match in re.finditer(r"(?<!\w)#[\w-]+", source)]
    )
    if tags:
        filters["tag_filter"] = ",".join(tags)
        labels.extend(tags)

    workspace_match = re.search(
        r"(?:workspace|darbviet\w*)\s*(?::|=)?\s*[\"“']([^\"”']+)[\"”']",
        source,
        flags=re.IGNORECASE,
    )
    if workspace_match:
        requested = workspace_match.group(1)
        workspace = ls_elza_resolve_workspace(requested)
        if not workspace:
            return {"error": f"Workspace “{requested}” LS datubāzē nav atrasts."}
        filters["workspace"] = workspace
        labels.append(f"Workspace: {workspace}")

    family_match = re.search(
        r"local\s+family(?:\s+title)?\s*(?::|=)?\s*[\"“']([^\"”']+)[\"”']",
        source,
        flags=re.IGNORECASE,
    )
    if family_match:
        requested = family_match.group(1)
        family = ls_elza_resolve_local_family(requested)
        if not family:
            return {"error": f"Apstiprināta Local family “{requested}” nav atrasta."}
        filters["local_family_filter"] = family
        labels.append(f"Local family: {family}")

    title_match = re.search(
        r"nosaukum\w*\s*(?::|=)?\s*[\"“']([^\"”']+)[\"”']",
        source,
        flags=re.IGNORECASE,
    )
    if title_match:
        title_query = re.sub(r"\s+", " ", title_match.group(1).strip())
        if title_query:
            filters["query"] = title_query
            filters["search_name"] = True
            labels.append(f"Name: {title_query}")

    if not filters:
        return None
    result = {
        "filters": filters,
        "labels": labels,
        "summary": " + ".join(labels),
        "save_name": " + ".join(labels)[:80] or "LS Elza selection",
        "local_audio_extensions": local_audio_extensions,
        "exclude_ui_types": exclude_ui_types,
    }
    if exact_flag_set_requested and exact_flags:
        exact_flag_mask = 0
        for mask in masks:
            exact_flag_mask |= mask
        result["exact_flag_mask"] = exact_flag_mask
        result["summary"] = "Tieši Flags " + " + ".join(
            str(number) for number in exact_flags
        )
        result["save_name"] = result["summary"]
    if exact_stem_count is not None:
        result["exact_stem_count"] = exact_stem_count
        result["summary"] = f"Tieši {exact_stem_count} Stems"
        result["save_name"] = result["summary"]
    return result

def ls_elza_selection_view_url(filters):
    pairs = []
    param_map = {
        "query": "q",
        "workspace": "workspace",
        "kind_filter": "kind_filter",
        "category_filter": "category_filter",
        "local_family_filter": "local_family_filter",
        "local_audio_filter": "local_audio_filter",
        "flag_filter": "flag_filter",
        "tag_filter": "tag_filter",
    }
    for filter_key, param_key in param_map.items():
        value = filters.get(filter_key)
        if value not in (None, ""):
            pairs.append((param_key, str(value)))
    if filters.get("search_marks"):
        pairs.append(("search_marks", "1"))
    if filters.get("query"):
        pairs.append(("search_name", "1"))
    pairs.extend([
        ("rows", "300"),
        ("sort_by", "title"),
        ("sort_dir", "asc"),
    ])
    return "/?" + urllib.parse.urlencode(pairs)

def find_ls_elza_track_by_stem_count(stem_count):
    """Return the first active visible track with exactly the requested stems."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            t.id,
            t.title,
            COALESCE(t.workspaceName, t.workspace, '') AS workspace,
            IFNULL(tu.stem_count, 0) AS stem_count
        FROM tracks t
        LEFT JOIN track_ui tu ON tu.track_id = t.id
        WHERE IFNULL(t.library_status, 'active') = 'active'
          AND (tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)
          AND IFNULL(t.kind, '') != 'Stem'
          AND IFNULL(tu.stem_count, 0) = ?
        ORDER BY lower(COALESCE(t.title, '')), lower(COALESCE(t.id, ''))
        LIMIT 1
    """, (int(stem_count),))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "track_id": str(row["id"] or ""),
        "title": re.sub(r"\s+", " ", str(row["title"] or "").strip()),
        "workspace": re.sub(r"\s+", " ", str(row["workspace"] or "").strip()),
        "stem_count": int(row["stem_count"] or 0),
    }

def get_ls_elza_exact_stem_result(stem_count):
    track = find_ls_elza_track_by_stem_count(stem_count)
    if not track:
        return {
            "matched_count": 0,
            "returned_count": 0,
            "tracks": [],
            "summary": f"Tieši {stem_count} Stems",
            "single_track": True,
        }
    track_id = track["track_id"]
    return {
        "matched_count": 1,
        "returned_count": 1,
        "tracks": [track],
        "view_url": "/?" + urllib.parse.urlencode({
            "track_ids": track_id,
            "rows": "300",
        }),
        "summary": f"Tieši {stem_count} Stems",
        "single_track": True,
        "exact_stem_count": stem_count,
    }

def get_ls_elza_selection_result(intent, limit=20):
    try:
        preview_limit = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        preview_limit = 20

    filters = dict(intent.get("filters") or {})
    exact_flag_mask = intent.get("exact_flag_mask")
    local_audio_extensions = {
        str(item or "").strip().lower().lstrip(".")
        for item in (intent.get("local_audio_extensions") or [])
        if str(item or "").strip()
    }
    excluded_ui_types = {
        str(item or "").strip().casefold()
        for item in (intent.get("exclude_ui_types") or [])
        if str(item or "").strip()
    }
    needs_exact_track_view = (
        exact_flag_mask is not None
        or bool(local_audio_extensions)
        or bool(excluded_ui_types)
    )

    def row_text(row, key):
        try:
            return str(row[key] or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""

    if needs_exact_track_view:
        try:
            required_marks = (
                int(exact_flag_mask)
                if exact_flag_mask is not None
                else None
            )
        except (TypeError, ValueError):
            required_marks = -1
        candidate_rows = search_tracks(
            **filters,
            limit_value="all",
            sort_by="title",
            sort_dir="asc",
        )
        exact_rows = []
        for row in candidate_rows:
            if required_marks is not None:
                try:
                    row_marks = int(row["user_marks"] or 0)
                except (TypeError, ValueError, KeyError, IndexError):
                    row_marks = 0
                if row_marks != required_marks:
                    continue

            ui_type = row_text(row, "ui_type") or row_text(row, "kind")
            if ui_type.casefold() in excluded_ui_types:
                continue

            if local_audio_extensions:
                row_extensions = set()
                if row_text(row, "local_wav"):
                    row_extensions.add("wav")
                if row_text(row, "local_mp3"):
                    row_extensions.add("mp3")
                best_path = row_text(row, "ui_best_local_audio_path")
                if best_path:
                    suffix = Path(best_path).suffix.lower().lstrip(".")
                    if suffix:
                        row_extensions.add(suffix)
                if not local_audio_extensions.intersection(row_extensions):
                    continue

            exact_rows.append(row)

        rows = exact_rows[:preview_limit]
        total = len(exact_rows)
        exact_track_ids = [
            row_text(row, "id")
            for row in exact_rows
            if row_text(row, "id")
        ]
        view_url = "/?" + urllib.parse.urlencode({
            "track_ids": ",".join(exact_track_ids),
            "rows": "all",
            "sort_by": "title",
            "sort_dir": "asc",
        })
        save_view_supported = False
    else:
        total = count_tracks(**filters)
        rows = search_tracks(
            **filters,
            limit_value=str(preview_limit),
            sort_by="title",
            sort_dir="asc",
        )
        view_url = ls_elza_selection_view_url(filters)
        save_view_supported = True

    tracks = []
    for row in rows:
        tracks.append({
            "track_id": row_text(row, "id"),
            "title": re.sub(r"\s+", " ", row_text(row, "title")),
            "workspace": re.sub(r"\s+", " ", row_text(row, "workspace")),
        })
    return {
        "matched_count": int(total or 0),
        "returned_count": len(tracks),
        "tracks": tracks,
        "view_url": view_url,
        "summary": str(intent.get("summary") or "LS selection"),
        "save_name": str(intent.get("save_name") or "LS Elza selection"),
        "save_view_supported": save_view_supported,
    }

def build_ls_elza_selection_answer(result):
    total = int(result.get("matched_count") or 0)
    tracks = result.get("tracks") if isinstance(result.get("tracks"), list) else []
    summary = str(result.get("summary") or "LS selection")
    if result.get("single_track"):
        stem_count = int(result.get("exact_stem_count") or 0)
        if not tracks:
            return f"LS neatrada nevienu dziesmu ar tieši {stem_count} stemiem."
        item = tracks[0]
        title = str(item.get("title") or "Untitled")
        workspace = str(item.get("workspace") or "Workspace nav norādīts")
        return (
            f"Atradu dziesmu ar tieši {stem_count} stemiem: "
            f"**{title}** — {workspace}.\n\n"
            "Nospied **Atvērt dziesmu LS**. DB netiek mainīta."
        )
    lines = [f"Saprastā atlase: **{summary}**.", "", f"Atrasti **{total} ieraksti**."]
    if tracks:
        lines.extend(["", f"Pirmie {len(tracks)} pēc nosaukuma:"])
        for item in tracks:
            title = str(item.get("title") or "Untitled")
            workspace = str(item.get("workspace") or "Workspace nav norādīts")
            lines.append(f"- {title} — {workspace}")
        if total > len(tracks):
            lines.extend(["", f"Čatā parādīti {len(tracks)} no {total} ierakstiem."])
    if total <= 0:
        lines.extend([
            "",
            "Darbību pogas netiek rādītas, jo atlase ir tukša. "
            "Pamēģini noņemt vienu no nosacījumiem.",
        ])
    return "\n".join(lines)

def get_ls_elza_local_readonly_response(payload):
    """Handle deterministic LS selections locally and preserve chat history."""
    if not isinstance(payload, dict):
        return None
    selected_mode = str(payload.get("selected_mode") or "").strip().upper()
    action = str(payload.get("action") or "send").strip().lower()
    if action not in {"send", "local_readonly"} or payload.get("images"):
        return None
    if selected_mode and action != "local_readonly":
        # Explicit UI modes must reach ls_elza_service unchanged for normal
        # send requests.  A frontend-classified local_readonly selection is
        # already a deterministic DB action and must not fall through to the
        # model service merely because a persistent mode button is active.
        return None

    user_text = str(payload.get("message") or "").strip()
    query_id = str(payload.get("query_id") or "").strip().lower()
    intent = parse_ls_elza_selection_intent(user_text)
    if intent is None and action == "local_readonly" and query_id == "liked_without_local_audio":
        intent = {
            "filters": {
                "kind_filter": "__liked__",
                "local_audio_filter": "without",
            },
            "summary": "Liked + No local audio",
            "save_name": "Liked + No local audio",
        }
    if intent is None:
        return None

    try:
        query_result = None
        if intent.get("error"):
            answer = str(intent.get("error"))
        else:
            if intent.get("exact_stem_count") is not None:
                query_result = get_ls_elza_exact_stem_result(
                    int(intent["exact_stem_count"])
                )
            else:
                query_result = get_ls_elza_selection_result(intent, limit=20)
            answer = build_ls_elza_selection_answer(query_result)
        chat_id = str(payload.get("chat_id") or "").strip()
        source = {
            "id": "db",
            "label": "DB read-only",
            "kind": "consulted",
            "detail": (
                "LS lokāli interpretēja atlases komandu un nolasīja atbilstošos "
                "aktīvos ierakstus. DB un faili netika mainīti."
            ),
        }
        chat_payload = None
        if ls_elza_append_chat_exchange is not None:
            try:
                chat_payload = ls_elza_append_chat_exchange(
                    chat_id, user_text, answer, [source],
                )
            except TypeError:
                chat_payload = ls_elza_append_chat_exchange(
                    chat_id, user_text, answer,
                )
        if not isinstance(chat_payload, dict):
            chat_payload = {
                "chat_id": chat_id,
                "local_exchange_only": True,
                "local_user_text": user_text,
            }
        response_update = {
            "ok": True,
            "answer": answer,
            "model": "local-readonly",
            "image_count": 0,
            "sources": [{
                "id": "db",
                "label": "DB read-only",
                "kind": "consulted",
            }],
        }
        if (
            query_result is not None
            and int(query_result.get("matched_count") or 0) > 0
        ):
            if query_result.get("single_track"):
                response_update.update({
                    "ls_view_url": query_result.get("view_url"),
                    "ls_view_label": "Atvērt dziesmu LS",
                })
            else:
                response_update.update({
                    "ls_view_url": query_result.get("view_url"),
                    "ls_view_label": "Atvērt atlasi LS",
                })
                if query_result.get("save_view_supported", True):
                    response_update.update({
                        "ls_save_view_url": query_result.get("view_url"),
                        "ls_save_view_name": query_result.get("save_name"),
                        "ls_save_view_label": "Saglabāt kā View",
                    })
        chat_payload.update(response_update)
        return chat_payload
    except Exception:
        return {
            "ok": False,
            "error": "LS neizdevās izveidot drošo atlases priekšskatījumu.",
            "error_code": "local_readonly_query_failed",
        }

