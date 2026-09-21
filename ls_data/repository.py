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
import sqlite3
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


def _canonical_db_active(conn=None):
    own = conn is None
    if own:
        if not Path(DB_PATH).is_file():
            return False
        conn = sqlite3.connect(DB_PATH)
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM main.sqlite_master WHERE type='table'"
            ).fetchall()
        }
        return {"tracks", "track_user", "track_variants", "media_files"}.issubset(names)
    finally:
        if own:
            conn.close()


def _legacy_path_filename(value):
    text = str(value or "").replace("/", "\\")
    return text.rsplit("\\", 1)[-1] if text else ""


def _legacy_path_folder(value):
    text = str(value or "").replace("/", "\\")
    return text.rsplit("\\", 1)[0] if "\\" in text else ""


def _configure_canonical_compat(conn):
    """Expose the old read contract over the canonical Local Suno schema.

    Views are TEMP-only: the clean DB file itself is not polluted with legacy
    cache tables or duplicate compatibility columns.
    """
    if not _canonical_db_active(conn):
        return False

    conn.create_function("ls_path_filename", 1, _legacy_path_filename)
    conn.create_function("ls_path_folder", 1, _legacy_path_folder)
    conn.executescript(
        """
        DROP VIEW IF EXISTS temp.tracks_compat;
        DROP VIEW IF EXISTS temp.track_ui;
        DROP VIEW IF EXISTS temp.local_audio_files;

        CREATE TEMP VIEW tracks_compat AS
        SELECT
            t.id,
            t.title,
            t.created_at,
            t.workspace_name AS workspaceName,
            t.workspace_name AS workspace,
            t.workspace_id AS workspaceId,
            t.workspace_id AS workspace_id,
            t.project_id,
            t.audio_url,
            '' AS status,
            t.image_url,
            t.image_large_url,
            t.image_url AS raw_image_url,
            t.image_large_url AS raw_image_large_url,
            t.model_name,
            t.major_model_version,
            t.major_model_version AS model_version,
            t.source_type AS metadata_type,
            t.source_type AS type,
            t.source_type AS raw_type,
            t.source_task AS metadata_task,
            t.source_task AS raw_task,
            t.style_tags AS metadata_tags,
            t.style_tags AS style,
            t.style_tags AS raw_tags,
            t.negative_tags AS metadata_negative_tags,
            t.prompt AS metadata_prompt,
            t.prompt AS prompt,
            t.duration_seconds AS metadata_duration,
            CASE
                WHEN t.duration_seconds IS NULL THEN ''
                ELSE printf('%d:%02d',
                    CAST(t.duration_seconds / 60 AS INTEGER),
                    CAST(t.duration_seconds AS INTEGER) % 60)
            END AS duration,
            t.has_stem AS metadata_has_stem,
            CAST(t.has_stem AS TEXT) AS raw_has_stem,
            t.has_vocal AS metadata_has_vocal,
            CAST(t.has_vocal AS TEXT) AS raw_has_vocal,
            t.make_instrumental AS metadata_make_instrumental,
            CAST(t.make_instrumental AS TEXT) AS raw_make_instrumental,
            t.is_remix AS metadata_is_remix,
            CAST(t.is_remix AS TEXT) AS raw_is_remix,
            t.studio_project_id AS metadata_studio_project_id,
            t.studio_project_version_id AS metadata_studio_project_version_id,
            t.edited_clip_id AS metadata_edited_clip_id,
            t.cover_clip_id AS metadata_cover_clip_id,
            t.avg_bpm AS metadata_avg_bpm,
            t.min_bpm AS metadata_min_bpm,
            t.max_bpm AS metadata_max_bpm,
            t.avg_bpm AS bpm,
            '' AS key,
            t.is_liked,
            CASE WHEN t.is_liked = 1 THEN 'True' ELSE 'False' END AS raw_is_liked,
            t.explicit,
            t.display_tags,
            t.display_tags AS raw_display_tags,
            t.kind,
            CASE WHEN lower(COALESCE(t.kind,'')) = 'stem' THEN 1 ELSE 0 END AS is_stem,
            t.caption,
            t.lyrics,
            t.library_status,
            t.finder_hidden,
            t.finder_hidden_reason,
            t.updated_at,
            '' AS reaction_type,
            '' AS notes,
            (
                SELECT mf.path
                FROM main.media_files mf
                JOIN main.track_variants tv ON tv.id = mf.variant_id
                WHERE tv.track_id = t.id
                  AND mf.role = 'main'
                  AND lower(COALESCE(mf.format,'')) = 'wav'
                ORDER BY COALESCE(tv.variant_no, 2147483647), mf.id
                LIMIT 1
            ) AS local_wav,
            (
                SELECT mf.path
                FROM main.media_files mf
                JOIN main.track_variants tv ON tv.id = mf.variant_id
                WHERE tv.track_id = t.id
                  AND mf.role = 'main'
                  AND lower(COALESCE(mf.format,'')) = 'mp3'
                ORDER BY COALESCE(tv.variant_no, 2147483647), mf.id
                LIMIT 1
            ) AS local_mp3,
            COALESCE(sp.raw_json, '') AS raw_json
        FROM main.tracks t
        LEFT JOIN main.suno_source_payload sp ON sp.track_id = t.id;

        CREATE TEMP VIEW track_ui AS
        SELECT
            t.id AS track_id,
            '' AS play_status,
            0 AS play_sort,
            CASE lower(COALESCE(t.source_task, ''))
                WHEN 'cover' THEN 'Cover'
                WHEN 'extend' THEN 'Extend'
                WHEN 'mashup' THEN 'Mashup'
                WHEN 'upload' THEN 'Upload'
                WHEN 'replace_section' THEN 'Replace Section'
                ELSE COALESCE(NULLIF(t.source_task, ''), NULLIF(t.kind, ''), '')
            END AS ui_type,
            0 AS ui_type_sort,
            COALESCE(t.display_tags, t.style_tags, '') AS ui_tags,
            COALESCE(t.duration_seconds, 0) AS duration_seconds,
            CASE
                WHEN t.duration_seconds IS NULL THEN ''
                ELSE printf('%d:%02d',
                    CAST(t.duration_seconds / 60 AS INTEGER),
                    CAST(t.duration_seconds AS INTEGER) % 60)
            END AS duration_text,
            CASE
                WHEN t.avg_bpm IS NULL THEN ''
                ELSE CAST(CAST(ROUND(t.avg_bpm) AS INTEGER) AS TEXT)
            END AS bpm_text,
            COALESCE(NULLIF(t.major_model_version,''), t.model_name, '') AS model_badge,
            CASE WHEN EXISTS (
                SELECT 1
                FROM main.track_variants tv
                JOIN main.media_files mf ON mf.variant_id = tv.id
                WHERE tv.track_id = t.id AND mf.role = 'main'
            ) THEN 1 ELSE 0 END AS has_local_audio,
            COALESCE((
                SELECT mf.path
                FROM main.track_variants tv
                JOIN main.media_files mf ON mf.variant_id = tv.id
                WHERE tv.track_id = t.id AND mf.role = 'main'
                ORDER BY COALESCE(tv.variant_no, 2147483647), mf.id
                LIMIT 1
            ), '') AS best_local_audio_path,
            (
                SELECT COUNT(*)
                FROM main.track_variants tv
                JOIN main.media_files mf ON mf.variant_id = tv.id
                WHERE tv.track_id = t.id AND mf.role = 'stem'
            ) AS stem_count,
            COALESCE(
                NULLIF(tu.manual_category, ''),
                CASE WHEN t.kind IN ('Song','Instrumental') THEN t.kind ELSE '' END
            ) AS main_category,
            '' AS proposed_main_category,
            '' AS main_category_confidence,
            '' AS main_category_confidence_label,
            '' AS main_category_review_reason,
            CASE WHEN COALESCE(tu.manual_category,'') != '' THEN 'manual_toggle' ELSE '' END
                AS main_category_review_group,
            CASE WHEN COALESCE(tu.manual_category,'') != '' THEN 'manual category toggle in LS' ELSE '' END
                AS main_category_rule,
            0 AS main_category_score,
            '' AS review_group,
            COALESCE(tu.rating, 0) AS user_rating,
            COALESCE(tu.tags, '') AS user_tags,
            COALESCE(tu.marks, 0) AS user_marks,
            CASE WHEN COALESCE(t.finder_hidden,0) = 1 THEN 0 ELSE 1 END AS visible_in_finder
        FROM main.tracks t
        LEFT JOIN main.track_user tu ON tu.track_id = t.id;

        CREATE TEMP VIEW local_audio_files AS
        SELECT
            mf.id,
            tv.track_id,
            mf.path,
            ls_path_filename(mf.path) AS filename,
            ls_path_folder(mf.path) AS folder,
            mf.format AS extension,
            mf.size_bytes,
            mf.modified_at AS modified_time,
            CASE WHEN mf.role = 'stem' THEN 1 ELSE 0 END AS is_stem,
            mf.stem_label,
            mf.chronology_at AS created_at,
            mf.modified_at AS updated_at,
            '' AS linked_by,
            mf.suno_clip_id,
            mf.suno_project_token,
            mf.suno_created_at,
            mf.embedded_suno_metadata AS suno_metadata_raw
        FROM main.media_files mf
        LEFT JOIN main.track_variants tv ON tv.id = mf.variant_id;
        """
    )
    return True


def _canonical_variant_folder(path_value, role):
    path = Path(str(path_value or ""))
    folder = path.parent
    if role == "stem" and folder.name.casefold() == "stems":
        folder = folder.parent
    return str(folder)


def _canonical_variant_no(path_value, role):
    folder = Path(_canonical_variant_folder(path_value, role))
    try:
        value = int(folder.name)
    except Exception:
        return None
    return value if value > 0 else None


def _canonical_get_or_create_variant(cur, track_id, path_value, role):
    folder = _canonical_variant_folder(path_value, role)
    cur.execute(
        """
        SELECT id
        FROM main.track_variants
        WHERE lower(track_id)=lower(?) AND lower(folder_path)=lower(?)
        ORDER BY id
        LIMIT 1
        """,
        (track_id, folder),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    if role == "stem":
        cur.execute(
            """
            SELECT id
            FROM main.track_variants
            WHERE lower(track_id)=lower(?)
            ORDER BY CASE WHEN variant_kind='main' THEN 0 ELSE 1 END, id
            """,
            (track_id,),
        )
        rows = cur.fetchall()
        if len(rows) == 1:
            return int(rows[0][0])

    cur.execute(
        """
        INSERT INTO main.track_variants(track_id, variant_no, folder_path, variant_kind)
        VALUES (?, ?, ?, ?)
        """,
        (
            track_id,
            _canonical_variant_no(path_value, role),
            folder,
            "stems_only" if role == "stem" else "main",
        ),
    )
    return int(cur.lastrowid)


def _canonical_delete_orphan_variants(cur, track_id):
    cur.execute(
        """
        DELETE FROM main.track_variants
        WHERE lower(track_id)=lower(?)
          AND NOT EXISTS (
              SELECT 1 FROM main.media_files mf
              WHERE mf.variant_id = main.track_variants.id
          )
        """,
        (track_id,),
    )


from ls_data.local_suno_migration import migrate as migrate_local_suno_database
from ls_data.local_suno_runtime import configure_legacy_runtime_views


# DATA-private copies of stable v5.394 domain constants used by repository
# functions.  DATA must not depend upward on SUNO/LOCAL/STEMS modules; keeping
# these names private prevents runtime export collisions while preserving the
# exact legacy behavior of the SQL-owning repository functions.
_DATA_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
_DATA_STEM_LABEL_ORDER = [
    "Vocals", "Backing Vocals", "Bass", "Drums", "Percussion", "Keyboard",
    "Piano", "Guitar", "Synth", "Strings", "Woodwinds", "FX", "Other"
]
_DATA_LOCAL_INVENTORY_KNOWN_ROOTS = [
    r"E:\Audio-Lib-NEW",
    r"E:\Audio Lib",
]
_DATA_LS_PROVEN_STRUCTURED_FIELDS = (
    "metadata_is_remix",
    "metadata_has_vocal",
    "metadata_make_instrumental",
    "metadata_has_stem",
    "model_name",
)
_DATA_LS_CONFIRMED_PROMPT_REPAIR_IDS = {
    "b3deeaae-5247-40ab-85ca-27fdd3919a6c",
}
_DATA_LS_INTENT_AUDIT_ENGINE_VERSION = "2026-07-19.2"
_DATA_LS_INTENT_AUDIT_TABLE = "ls_category_intent_audit"
_DATA_LS_INTENT_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
_DATA_LS_INTENT_BRACKET_LINE_RE = re.compile(r"^\s*[\[(].*[\])]\s*$")
_DATA_LS_INTENT_INSTRUMENTAL_ONLY_RE = re.compile(
    r"^\s*(?:[\[(]\s*)?instrumental(?:\s*[\])])?\s*$",
    re.IGNORECASE,
)
_DATA_LS_INTENT_STRUCTURE_MARKER_RE = re.compile(
    r"[\[(]\s*(?:verse|chorus|bridge|intro|outro|pre[- ]?chorus|refrain|pants|piedziedājums)\b",
    re.IGNORECASE,
)
_DATA_LS_CATEGORY_ASSIGNMENT_SCORE = 90

STEM_SUFFIX_PATTERN = re.compile(
    r"\s*\((Vocals|Vocal|Instrumental|Bass|Drums|Guitar|Keyboard|Percussion|Synth|Strings|Woodwinds|FX|Other|Backing Vocals|Lead Vocals)\)\s*$",
    re.I,
)

def ls_stem_base_title(value):
    text = str(value or "").strip()
    text = STEM_SUFFIX_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text

_LOCAL_SUNO_DB_INIT_LOCK = threading.Lock()

def ensure_local_suno_runtime_database():
    if DB_PATH.is_file():
        return
    with _LOCAL_SUNO_DB_INIT_LOCK:
        if DB_PATH.is_file():
            return
        if not LEGACY_DB_PATH.is_file():
            raise FileNotFoundError(
                f"Canonical Local Suno DB is missing and legacy DB was not found: {LEGACY_DB_PATH}"
            )
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        migrate_local_suno_database(
            LEGACY_DB_PATH,
            DB_PATH,
            REPORTS_DIR / "local_suno_migration_report.json",
        )

def get_connection():
    ensure_local_suno_runtime_database()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("ls_stem_base_title", 1, ls_stem_base_title)
    conn.create_function("ls_sort_text", 1, lv_sort_key)
    conn.create_function("ls_duration_seconds", 1, duration_sort_value)
    configure_legacy_runtime_views(conn)
    return conn

def get_table_columns():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(tracks_compat);")
    rows = cur.fetchall()
    conn.close()

    return {row["name"] for row in rows}

def get_track_ui_columns():
    if not table_exists("track_ui"):
        return set()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(track_ui);")
    rows = cur.fetchall()
    conn.close()
    return {row["name"] for row in rows}

def table_exists(table_name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT name FROM sqlite_master WHERE type IN ('table', 'view')
            UNION ALL
            SELECT name FROM sqlite_temp_master WHERE type IN ('table', 'view')
        )
        WHERE name = ?;
    """, (table_name,))
    exists = cur.fetchone()[0] > 0
    conn.close()
    return exists

def get_named_table_columns(table_name):
    """Return columns only for the small set of LS tables used by read-only filters."""
    table_name = str(table_name or "").strip()
    if table_name not in {"tracks", "track_ui", "local_audio_files"}:
        return set()
    if not table_exists(table_name):
        return set()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name});")
    rows = cur.fetchall()
    conn.close()
    return {row["name"] for row in rows}

def get_has_local_audio_condition_sql():
    """Build the same conservative local-audio test for LS views and Elza."""
    track_alias = "t"
    ui_alias = "tu"
    track_columns = get_table_columns()
    ui_columns = get_track_ui_columns()
    local_columns = get_named_table_columns("local_audio_files")
    parts = []

    if "has_local_audio" in ui_columns:
        parts.append(f"IFNULL({ui_alias}.has_local_audio, 0) = 1")
    if "best_local_audio_path" in ui_columns:
        parts.append(f"TRIM(COALESCE({ui_alias}.best_local_audio_path, '')) != ''")
    if "local_wav" in track_columns:
        parts.append(f"TRIM(COALESCE({track_alias}.local_wav, '')) != ''")
    if "local_mp3" in track_columns:
        parts.append(f"TRIM(COALESCE({track_alias}.local_mp3, '')) != ''")
    if {"track_id", "is_stem"}.issubset(local_columns):
        parts.append(
            "EXISTS ("
            "SELECT 1 FROM local_audio_files ls_laf "
            f"WHERE lower(ls_laf.track_id) = lower({track_alias}.id) "
            "AND IFNULL(ls_laf.is_stem, 0) = 0"
            ")"
        )

    return "(" + " OR ".join(parts) + ")" if parts else "0"

def get_unlinked_stems_condition_sql():
    return """
        kind = 'Stem'
        AND ls_stem_base_title(title) NOT IN (
            SELECT DISTINCT ls_stem_base_title(t2.title)
            FROM tracks_compat t2
            WHERE IFNULL(t2.library_status, 'active') = 'active'
              AND EXISTS (
                  SELECT 1
                  FROM local_audio_files laf2
                  WHERE laf2.is_stem = 1
                    AND lower(laf2.track_id) = lower(t2.id)
              )
        )
    """

def get_main_category_filter_sql(ui_columns=None):
    """Return the independent Song/Instrumental category expression.

    ``ui_type`` describes the Suno operation shown by LS (Cover, Mashup,
    Extend, ...).  It must not replace the user-facing Song/Instrumental
    category.  Older databases without ``track_ui.main_category`` retain a
    conservative fallback to the legacy main kinds.
    """
    if ui_columns is None:
        ui_columns = get_track_ui_columns()
    if "main_category" in ui_columns:
        return "TRIM(COALESCE(tu.main_category, ''))"
    return "CASE WHEN t.kind IN ('Song', 'Instrumental') THEN t.kind ELSE '' END"

def get_confirmed_local_family_filter_options():
    """Return mapped Local families that can filter exact Track IDs.

    Folder-only family names are deliberately excluded because they have no
    authoritative Track ID association in the persistent Local family map.
    """
    by_key = {}
    data = _load_local_family_map()
    for track_id, payload in (data.get("tracks") or {}).items():
        if not isinstance(payload, dict):
            continue
        family_title = clean_local_family_title(payload.get("family_title"))
        clean_track_id = str(track_id or "").strip()
        if not family_title or not clean_track_id:
            continue
        key = family_title.casefold()
        item = by_key.setdefault(key, {
            "title": family_title,
            "track_ids": [],
            "categories": [],
        })
        if clean_track_id.lower() not in {
            value.lower() for value in item["track_ids"]
        }:
            item["track_ids"].append(clean_track_id)
        category = str(payload.get("category") or "").strip()
        if category and category not in item["categories"]:
            item["categories"].append(category)

    result = list(by_key.values())
    for item in result:
        item["count"] = len(item["track_ids"])
        item["categories"] = sorted(item["categories"], key=lv_sort_key)
    result.sort(key=lambda item: lv_sort_key(item["title"]))
    return result


# LS_LOCAL_FAMILY_TAB_QUICK_V1
# Quick initial Local Family catalog: physical D:\Local-Suno-Library folder names
# plus every already-confirmed Track ID -> Local Family mapping.
def get_quick_local_family_catalog(track_id=""):
    root = Path(r"D:\Local-Suno-Library")
    by_key = {}

    try:
        if root.exists() and root.is_dir():
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                title = clean_local_family_title(child.name)
                if title:
                    by_key.setdefault(title.casefold(), title)
    except OSError:
        pass

    assigned_family = ""
    wanted_track_id = str(track_id or "").strip().casefold()
    data = _load_local_family_map()
    for stored_track_id, payload in (data.get("tracks") or {}).items():
        if not isinstance(payload, dict):
            continue
        title = clean_local_family_title(payload.get("family_title"))
        if not title:
            continue
        by_key.setdefault(title.casefold(), title)
        if wanted_track_id and str(stored_track_id or "").strip().casefold() == wanted_track_id:
            assigned_family = title

    families = sorted(by_key.values(), key=lv_sort_key)
    return {
        "ok": True,
        "root": str(root),
        "root_exists": root.exists() and root.is_dir(),
        "families": families,
        "assigned_family": assigned_family,
    }

def get_track_ids_for_local_family_filter(value):
    selected = {
        item.casefold() for item in normalize_multi_filter_values(value)
    }
    if not selected:
        return []
    result = []
    seen = set()
    for item in get_confirmed_local_family_filter_options():
        if str(item.get("title") or "").casefold() not in selected:
            continue
        for track_id in item.get("track_ids") or []:
            key = str(track_id or "").lower()
            if key and key not in seen:
                result.append(str(track_id))
                seen.add(key)
    return result

def get_local_family_group_match_track_ids(
    workspace_values=None,
    category_values=None,
):
    """Return mapped Track IDs whose family covers every selected value.

    Matching is group-level: separate rows may satisfy separate Workspace or
    Category values, but all rows must belong to the same confirmed Local
    family. The returned IDs include every mapped row in each qualifying
    family; normal row-level filters decide which members remain visible.
    """
    selected_workspaces = normalize_multi_filter_values(workspace_values)
    selected_categories = normalize_multi_filter_values(category_values)
    if not selected_workspaces and not selected_categories:
        return []

    family_options = get_confirmed_local_family_filter_options()
    track_to_family = {}
    family_track_ids = {}
    for item in family_options:
        title = str(item.get("title") or "").strip()
        family_key = title.casefold()
        if not family_key:
            continue
        ids = []
        for track_id in item.get("track_ids") or []:
            clean_id = str(track_id or "").strip()
            if not clean_id:
                continue
            ids.append(clean_id)
            track_to_family[clean_id.lower()] = family_key
        family_track_ids[family_key] = ids

    all_track_ids = list(track_to_family.keys())
    if not all_track_ids:
        return []

    track_columns = get_table_columns()
    ui_columns = get_track_ui_columns()
    category_sql = get_main_category_filter_sql(ui_columns)
    review_group_sql = (
        "COALESCE(tu.main_category_review_group, '')"
        if "main_category_review_group" in ui_columns
        else "''"
    )
    visibility_parts = [
        "IFNULL(t.library_status, 'active') = 'active'",
        "IFNULL(t.kind, '') != 'Stem'",
    ]
    if "visible_in_finder" in ui_columns:
        visibility_parts.append(
            "(tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)"
        )
    if "finder_hidden" in track_columns:
        visibility_parts.append("IFNULL(t.finder_hidden, 0) != 1")
    visibility_sql = " AND ".join(visibility_parts)

    family_workspaces = {key: set() for key in family_track_ids}
    family_categories = {key: set() for key in family_track_ids}
    conn = get_connection()
    try:
        cur = conn.cursor()
        for start in range(0, len(all_track_ids), 800):
            chunk = all_track_ids[start:start + 800]
            placeholders = ",".join(["?"] * len(chunk))
            cur.execute(f"""
                SELECT
                    lower(t.id) AS track_id,
                    COALESCE(t.workspaceName, t.workspace, '') AS workspace,
                    {category_sql} AS main_category,
                    {review_group_sql} AS review_group
                FROM tracks_compat t
                LEFT JOIN track_ui tu ON tu.track_id = t.id
                WHERE lower(t.id) IN ({placeholders})
                  AND {visibility_sql};
            """, chunk)
            for row in cur.fetchall():
                track_id = str(row["track_id"] or "").lower()
                family_key = track_to_family.get(track_id)
                if not family_key:
                    continue
                workspace = str(row["workspace"] or "").strip()
                if workspace:
                    family_workspaces[family_key].add(workspace.casefold())

                category = str(row["main_category"] or "").strip()
                if category in ("Song", "Instrumental", "SongOrInstrumental"):
                    family_categories[family_key].add(category.casefold())
                else:
                    family_categories[family_key].add("__unclassified__")
                if (
                    category == "Instrumental" and
                    str(row["review_group"] or "") != "manual_toggle"
                ):
                    family_categories[family_key].add(
                        "__instrumental_review__"
                    )
    finally:
        conn.close()

    wanted_workspaces = {value.casefold() for value in selected_workspaces}
    wanted_categories = {value.casefold() for value in selected_categories}
    result = []
    seen = set()
    for family_key, ids in family_track_ids.items():
        if not wanted_workspaces.issubset(family_workspaces.get(family_key, set())):
            continue
        if not wanted_categories.issubset(family_categories.get(family_key, set())):
            continue
        for track_id in ids:
            key = track_id.lower()
            if key not in seen:
                result.append(track_id)
                seen.add(key)
    return result

def get_workspaces():
    conn = get_connection()
    cur = conn.cursor()

    columns = get_table_columns()

    where_parts = [
        "workspace IS NOT NULL",
        "workspace != ''",
    ]

    if "library_status" in columns:
        where_parts.append("IFNULL(library_status, 'active') = 'active'")

    # Keep the Workspace dropdown count consistent with the table:
    # rows hidden by Finder-only duplicate cleanup are not counted here either.
    if "finder_hidden" in columns:
        where_parts.append("IFNULL(finder_hidden, 0) != 1")

    where_sql = " AND ".join(where_parts)

    cur.execute(f"""
        SELECT workspace, COUNT(*) AS count
        FROM tracks_compat
        WHERE {where_sql}
        GROUP BY workspace
        ORDER BY workspace COLLATE NOCASE;
    """)

    rows = cur.fetchall()
    conn.close()

    # SQLite NOCASE is not Latvian-aware. This keeps Ā/Č/Ē... in natural A-Z order.
    return sorted(rows, key=lambda row: lv_sort_key(row["workspace"]))

def safe_count(cur, sql):
    try:
        cur.execute(sql)
        return cur.fetchone()[0]
    except Exception:
        return 0

def get_last_sync():
    if not table_exists("sync_log"):
        return {
            "sync_time": "",
            "inserted_new_tracks": 0,
            "marked_missing": 0,
        }

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            sync_time,
            inserted_new_tracks,
            marked_missing
        FROM sync_log
        ORDER BY id DESC
        LIMIT 1;
    """)

    row = cur.fetchone()
    conn.close()

    if not row:
        return {
            "sync_time": "",
            "inserted_new_tracks": 0,
            "marked_missing": 0,
        }

    return {
        "sync_time": row["sync_time"] or "",
        "inserted_new_tracks": row["inserted_new_tracks"] or 0,
        "marked_missing": row["marked_missing"] or 0,
    }

def get_ui_type_counts():
    """Return dynamic v4 UI type counts for the Kind/Type dropdown.

    Uses track_ui.ui_type, not old tracks.kind. This keeps the dropdown in sync
    after normalize_v4_ui_types*.py rebuilds the UI cache.
    """
    conn = get_connection()
    cur = conn.cursor()

    base_from = """
        FROM tracks_compat t
        LEFT JOIN track_ui tu ON tu.track_id = t.id
    """
    main_where = """
        WHERE IFNULL(t.library_status, 'active') = 'active'
          AND (tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)
          AND IFNULL(t.kind, '') != 'Stem'
          AND TRIM(COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '')) != ''
    """

    cur.execute(f"""
        SELECT
            COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') AS ui_type,
            COUNT(*) AS count,
            MIN(COALESCE(tu.ui_type_sort, 999)) AS sort_value
        {base_from}
        {main_where}
        GROUP BY COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '')
        ORDER BY sort_value ASC, ui_type COLLATE NOCASE ASC;
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = get_connection()
    cur = conn.cursor()

    total_tracks = safe_count(cur, "SELECT COUNT(*) FROM tracks_compat;")

    base_from = """
        FROM tracks_compat t
        LEFT JOIN track_ui tu ON tu.track_id = t.id
    """
    active_where = """
        WHERE IFNULL(t.library_status, 'active') = 'active'
          AND (tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)
    """
    main_where = active_where + " AND IFNULL(t.kind, '') != 'Stem'"

    total_active = safe_count(cur, f"SELECT COUNT(*) {base_from} {active_where};")
    total_main_active = safe_count(cur, f"SELECT COUNT(*) {base_from} {main_where};")

    total_missing = safe_count(cur, """
        SELECT COUNT(*)
        FROM tracks_compat
        WHERE library_status = 'missing_from_latest_csv';
    """)

    missing_stems = safe_count(cur, """
        SELECT COUNT(*)
        FROM tracks_compat
        WHERE library_status = 'missing_from_latest_csv'
          AND kind = 'Stem';
    """)

    total_workspaces = safe_count(cur, """
        SELECT COUNT(DISTINCT COALESCE(workspaceName, workspace, ''))
        FROM tracks_compat
        WHERE COALESCE(workspaceName, workspace, '') != ''
          AND IFNULL(library_status, 'active') = 'active';
    """)

    total_stems = safe_count(cur, """
        SELECT COUNT(*)
        FROM tracks_compat
        WHERE IFNULL(library_status, 'active') = 'active'
          AND kind = 'Stem';
    """)

    total_uploads = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') = 'Upload';
    """)

    total_instrumental = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') = 'Instrumental';
    """)

    total_song = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') = 'Song';
    """)

    ui_columns = get_track_ui_columns()
    main_category_sql = get_main_category_filter_sql(ui_columns)
    total_category_song = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND {main_category_sql} = 'Song';
    """)
    total_category_instrumental = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND {main_category_sql} = 'Instrumental';
    """)
    total_category_uncertain = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND {main_category_sql} = 'SongOrInstrumental';
    """)
    total_category_unclassified = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND {main_category_sql} NOT IN
              ('Song', 'Instrumental', 'SongOrInstrumental');
    """)
    if "main_category_review_group" in ui_columns:
        total_instrumental_review = safe_count(cur, f"""
            SELECT COUNT(*) {base_from} {main_where}
              AND {main_category_sql} = 'Instrumental'
              AND COALESCE(tu.main_category_review_group, '') != 'manual_toggle';
        """)
    else:
        total_instrumental_review = total_category_instrumental

    total_cover = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') = 'Cover';
    """)

    total_with_style = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND TRIM(COALESCE(t.metadata_tags, t.style, t.display_tags, '')) != '';
    """)

    total_liked = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND (IFNULL(t.is_liked, 0) = 1 OR lower(COALESCE(t.raw_is_liked, '')) = 'true');
    """)

    total_not_liked = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND NOT (IFNULL(t.is_liked, 0) = 1 OR lower(COALESCE(t.raw_is_liked, '')) = 'true');
    """)

    track_columns = get_table_columns()
    ui_columns = get_track_ui_columns()
    if "finder_hidden" in track_columns:
        hidden_duplicates = safe_count(cur, """
            SELECT COUNT(*)
            FROM tracks_compat
            WHERE IFNULL(library_status, 'active') = 'active'
              AND IFNULL(finder_hidden, 0) = 1;
        """)
    else:
        hidden_duplicates = 0

    total_has_stems = safe_count(cur, f"""
        SELECT COUNT(*) {base_from} {main_where}
          AND IFNULL(tu.stem_count, 0) > 0;
    """)

    if table_exists("local_audio_files"):
        total_local_stem_files = safe_count(cur, """
            SELECT COUNT(*)
            FROM local_audio_files
            WHERE IFNULL(is_stem, 0) = 1
              AND TRIM(COALESCE(track_id, '')) != '';
        """)
    else:
        total_local_stem_files = 0

    ui_columns = get_track_ui_columns()
    if "review_group" in ui_columns:
        total_conflict_s_to_i = safe_count(cur, f"""
            SELECT COUNT(*) {base_from} {main_where}
              AND tu.review_group = 'mismatch_db_Song_proposed_Instrumental';
        """)
        total_conflict_i_to_s = safe_count(cur, f"""
            SELECT COUNT(*) {base_from} {main_where}
              AND tu.review_group = 'mismatch_db_Instrumental_proposed_Song';
        """)
    else:
        total_conflict_s_to_i = 0
        total_conflict_i_to_s = 0

    if table_exists("ls_category_intent_audit"):
        total_intent_s_to_i = safe_count(cur, """
            SELECT COUNT(*)
              FROM ls_category_intent_audit
             WHERE current_category = 'Song'
               AND intent_label = 'Instrumental'
               AND recommended_action = 'review_category_conflict';
        """)
        total_intent_i_to_s = safe_count(cur, """
            SELECT COUNT(*)
              FROM ls_category_intent_audit
             WHERE current_category = 'Instrumental'
               AND intent_label = 'Song'
               AND recommended_action = 'review_category_conflict';
        """)
    else:
        total_intent_s_to_i = 0
        total_intent_i_to_s = 0

    if table_exists("local_audio_files"):
        total_unlinked_stems = safe_count(cur, """
            SELECT COUNT(*)
            FROM tracks_compat
            WHERE IFNULL(library_status, 'active') = 'active'
              AND kind = 'Stem'
              AND ls_stem_base_title(title) NOT IN (
                  SELECT DISTINCT ls_stem_base_title(t2.title)
                  FROM tracks_compat t2
                  WHERE IFNULL(t2.library_status, 'active') = 'active'
                    AND EXISTS (
                        SELECT 1
                        FROM local_audio_files laf2
                        WHERE laf2.is_stem = 1
                          AND lower(laf2.track_id) = lower(t2.id)
                    )
              );
        """)
    else:
        total_unlinked_stems = total_stems

    conn.close()

    last_sync = get_last_sync()

    return {
        "total_tracks": total_tracks,
        "total_active": total_active,
        "total_main_active": total_main_active,
        "total_missing": total_missing,
        "missing_stems": missing_stems,
        "total_workspaces": total_workspaces,
        "total_stems": total_stems,
        "total_uploads": total_uploads,
        "total_instrumental": total_instrumental,
        "total_song": total_song,
        "total_category_song": total_category_song,
        "total_category_instrumental": total_category_instrumental,
        "total_category_uncertain": total_category_uncertain,
        "total_category_unclassified": total_category_unclassified,
        "total_instrumental_review": total_instrumental_review,
        "total_cover": total_cover,
        "total_with_style": total_with_style,
        "total_liked": total_liked,
        "total_not_liked": total_not_liked,
        "hidden_duplicates": hidden_duplicates,
        "total_has_stems": total_has_stems,
        "total_local_stem_files": total_local_stem_files,
        "total_conflict_s_to_i": total_conflict_s_to_i,
        "total_conflict_i_to_s": total_conflict_i_to_s,
        "total_intent_s_to_i": total_intent_s_to_i,
        "total_intent_i_to_s": total_intent_i_to_s,
        "total_unlinked_stems": total_unlinked_stems,
        "last_sync_time": last_sync["sync_time"],
        "new_since_last_sync": last_sync["inserted_new_tracks"],
        "marked_missing_last_sync": last_sync["marked_missing"],
    }

def update_track_style(track_id, style_text):
    track_id = (track_id or "").strip()
    style_text = (style_text or "").strip()
    if not track_id:
        return False, "Missing Track ID"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE main.tracks
               SET style_tags = ?,
                   prompt = ?,
                   updated_at = COALESCE(updated_at, datetime('now'))
             WHERE id = ?;
        """, (style_text, style_text, track_id))
        conn.commit()
        if cur.rowcount == 0:
            return False, "Track ID not found"
        return True, "Saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_track_lyrics_payload(track_id):
    """Return exact current Lyrics for one Track ID.

    The main list intentionally contains only a short preview. Full Lyrics are
    read only after the user opens the editor, which keeps large result lists
    responsive and avoids duplicating long text inside HTML attributes.
    """
    track_id = str(track_id or "").strip()
    if not track_id:
        return False, {
            "ok": False,
            "error": "Missing Track ID",
        }

    columns = get_table_columns()
    if "lyrics" not in columns:
        return False, {
            "ok": False,
            "error": "DB column missing: lyrics",
        }

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                id,
                COALESCE(title, '') AS title,
                COALESCE(lyrics, '') AS lyrics
            FROM tracks_compat
            WHERE lower(id) = lower(?)
            LIMIT 1;
            """,
            (track_id,),
        )
        row = cur.fetchone()

        if not row:
            return False, {
                "ok": False,
                "error": "Track ID not found",
            }

        return True, {
            "ok": True,
            "track_id": str(row["id"] or track_id),
            "title": str(row["title"] or ""),
            "lyrics": str(row["lyrics"] or ""),
        }
    except Exception as exc:
        return False, {
            "ok": False,
            "error": str(exc),
        }
    finally:
        conn.close()

def get_track_text_payload(track_id):
    """Return exact Lyrics, Prompt and Style text for one Track ID.

    The payload keeps the visible field source explicit. Prompt and Style use
    the same priority order as the main list. Only Lyrics is editable here;
    Prompt and Style are read-only so this viewer never moves or overwrites DB
    fields implicitly.
    """
    track_id = str(track_id or "").strip()
    if not track_id:
        return False, {
            "ok": False,
            "error": "Missing Track ID",
        }

    columns = get_table_columns()
    requested_columns = [
        "id",
        "title",
        "lyrics",
        "metadata_prompt",
        "prompt",
        "metadata_tags",
        "style",
        "display_tags",
    ]

    select_parts = []
    for column_name in requested_columns:
        if column_name in columns:
            select_parts.append(f'"{column_name}"')
        else:
            select_parts.append(f"'' AS \"{column_name}\"")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT {", ".join(select_parts)}
            FROM tracks_compat
            WHERE lower(id) = lower(?)
            LIMIT 1;
            """,
            (track_id,),
        )
        row = cur.fetchone()
        if not row:
            return False, {
                "ok": False,
                "error": "Track ID not found",
            }

        row_data = dict(row)

        lyrics_text = str(row_data.get("lyrics") or "")

        prompt_text = ""
        prompt_source = ""
        for column_name in ("metadata_prompt", "prompt"):
            candidate = str(row_data.get(column_name) or "")
            if candidate.strip():
                prompt_text = candidate
                prompt_source = column_name
                break

        style_text = ""
        style_source = ""
        for column_name in ("metadata_tags", "style", "display_tags"):
            candidate = str(row_data.get(column_name) or "")
            if candidate.strip():
                style_text = candidate
                style_source = column_name
                break

        def normalized_text_for_duplicate_check(value):
            return (
                str(value or "")
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .strip()
            )

        prompt_duplicate_of_lyrics = bool(
            normalized_text_for_duplicate_check(lyrics_text)
            and normalized_text_for_duplicate_check(prompt_text)
            == normalized_text_for_duplicate_check(lyrics_text)
        )

        fields = {
            "lyrics": {
                "label": "Lyrics",
                "text": lyrics_text,
                "source_column": "lyrics",
                "editable": True,
                "has_text": bool(lyrics_text.strip()),
                "duplicate_of": "",
            },
            "prompt": {
                "label": "Prompt",
                "text": prompt_text,
                "source_column": prompt_source,
                "editable": False,
                "has_text": bool(prompt_text.strip()),
                "duplicate_of": (
                    "lyrics" if prompt_duplicate_of_lyrics else ""
                ),
            },
            "style": {
                "label": "Style",
                "text": style_text,
                "source_column": style_source,
                "editable": False,
                "has_text": bool(style_text.strip()),
                "duplicate_of": "",
            },
        }

        return True, {
            "ok": True,
            "track_id": str(row_data.get("id") or track_id),
            "title": str(row_data.get("title") or ""),
            "fields": fields,
        }
    except Exception as exc:
        return False, {
            "ok": False,
            "error": str(exc),
        }
    finally:
        conn.close()

def update_track_lyrics(track_id, lyrics_text):
    """Save the exact Lyrics text for one Track ID."""
    track_id = (track_id or "").strip()
    lyrics_text = str(lyrics_text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not track_id:
        return False, "Missing Track ID"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE main.tracks
               SET lyrics = ?,
                   updated_at = COALESCE(updated_at, datetime('now'))
             WHERE lower(id) = lower(?);
        """, (lyrics_text, track_id))
        conn.commit()
        if cur.rowcount == 0:
            return False, "Track ID not found"
        return True, "Lyrics saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_track_title(track_id, title_text):
    track_id = (track_id or "").strip()
    title_text = (title_text or "").strip()
    if not track_id:
        return False, "Missing Track ID"
    if not title_text:
        return False, "Title cannot be empty"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE main.tracks
               SET title = ?,
                   updated_at = COALESCE(updated_at, datetime('now'))
             WHERE id = ?;
        """, (title_text, track_id))
        conn.commit()
        if cur.rowcount == 0:
            return False, "Track ID not found"
        return True, "Title saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def ensure_track_column(cur, column_name, column_type="TEXT"):
    cur.execute("PRAGMA table_info(tracks);")
    columns = {row[1] for row in cur.fetchall()}

    if column_name not in columns:
        cur.execute(f"ALTER TABLE tracks ADD COLUMN {column_name} {column_type};")

def update_track_hidden(track_id, hidden=True, reason="manual_hide_from_finder"):
    track_id = (track_id or "").strip()
    if not track_id:
        return False, "Missing Track ID"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE main.tracks
               SET finder_hidden = ?,
                   finder_hidden_reason = ?,
                   updated_at = COALESCE(updated_at, datetime('now'))
             WHERE id = ?;
        """, (1 if hidden else 0, reason, track_id))
        conn.commit()
        if cur.rowcount == 0:
            return False, "Track ID not found"
        return True, "Hidden" if hidden else "Unhidden"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def ensure_local_audio_files_table(cur):
    """Compatibility no-op for the canonical Track -> Variant -> Media schema."""
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='media_files' LIMIT 1;"
    ).fetchone()
    if row:
        return
    cur.execute("""
        CREATE TABLE IF NOT EXISTS local_audio_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id TEXT,
            path TEXT,
            filename TEXT,
            folder TEXT,
            extension TEXT,
            size_bytes INTEGER,
            modified_time TEXT,
            is_stem INTEGER DEFAULT 0,
            stem_label TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """)

def normalize_bool_liked(value):
    return str(value or "").strip().lower() == "true"

def ensure_default_tags_file():
    if TAGS_FILE_PATH.exists():
        return

    default_tags = [
        "#Piano",
        "#Choir",
        "#Fretsless",
        "#Rhodes",
        "#Hammond",
        "#BariSax",
        "#SopranoSax",
        "#Guitar",
        "#Bass",
        "#Drums",
        "#Percussion",
        "#Vocal",
        "#Instrumental",
        "#Intro",
        "#Outro",
        "#Solo",
        "#Folk",
        "#Jazz",
        "#Bossa",
        "#Salsa",
    ]
    TAGS_FILE_PATH.write_text("\n".join(default_tags) + "\n", encoding="utf-8")

def _normalize_single_user_tag(value):
    """Normalize one catalog tag. Spaces become underscores so one input creates one tag."""
    text = str(value or "").strip()
    text = re.sub(r"^#+", "", text).strip()
    text = re.sub(r"[\s]+", "_", text)
    text = re.sub(r"[,;]+", "", text)
    text = text.strip("#_")
    return f"#{text}" if text else ""

def _parse_user_tags_value(value):
    """Parse the comma/semicolon/whitespace separated track_ui.user_tags value."""
    result = []
    seen = set()
    for part in re.split(r"[,;\s]+", str(value or "")):
        tag = _normalize_single_user_tag(part)
        key = tag.lower()
        if tag and key not in seen:
            result.append(tag)
            seen.add(key)
    return result

def _write_available_user_tags(tags):
    """Write the catalog atomically, unique and A-Z sorted."""
    normalized = []
    seen = set()
    for value in tags or []:
        tag = _normalize_single_user_tag(value)
        key = tag.lower()
        if tag and key not in seen:
            normalized.append(tag)
            seen.add(key)

    normalized.sort(key=lv_sort_key)
    TAGS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = TAGS_FILE_PATH.with_suffix(TAGS_FILE_PATH.suffix + ".tmp")
    temp_path.write_text("\n".join(normalized) + ("\n" if normalized else ""), encoding="utf-8")
    temp_path.replace(TAGS_FILE_PATH)
    return normalized

def get_available_user_tags():
    ensure_default_tags_file()
    try:
        raw = TAGS_FILE_PATH.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    result = []
    seen = set()
    for line in raw.splitlines():
        item = line.strip()
        if not item or item.startswith("//"):
            continue
        tag = _normalize_single_user_tag(item)
        key = tag.lower()
        if tag and key not in seen:
            result.append(tag)
            seen.add(key)

    return sorted(result, key=lv_sort_key)

def get_pinned_user_tags():
    available = get_available_user_tags()
    available_by_key = {tag.lower(): tag for tag in available}
    raw = get_settings().get("pinned_user_tags") or []
    if isinstance(raw, str):
        raw = re.split(r"[,;\s]+", raw)
    if not isinstance(raw, list):
        raw = []

    result = []
    seen = set()
    for value in raw:
        tag = _normalize_single_user_tag(value)
        key = tag.lower()
        canonical = available_by_key.get(key)
        if canonical and key not in seen:
            result.append(canonical)
            seen.add(key)
    return sorted(result, key=lv_sort_key)

def add_available_user_tag(value):
    tag = _normalize_single_user_tag(value)
    if not tag:
        return False, {"error": "Tag cannot be empty"}

    tags = get_available_user_tags()
    by_key = {item.lower(): item for item in tags}
    if tag.lower() in by_key:
        tag = by_key[tag.lower()]
    else:
        tags.append(tag)
        tags = _write_available_user_tags(tags)

    return True, {
        "tag": tag,
        "tags": tags,
        "pinned": get_pinned_user_tags(),
    }

def set_user_tag_pinned(value, pinned=True):
    tag = _normalize_single_user_tag(value)
    tags = get_available_user_tags()
    by_key = {item.lower(): item for item in tags}
    canonical = by_key.get(tag.lower())
    if not canonical:
        return False, {"error": "Tag is not in the tag catalog"}

    pinned_tags = get_pinned_user_tags()
    pinned_by_key = {item.lower(): item for item in pinned_tags}

    if pinned:
        pinned_by_key[canonical.lower()] = canonical
    else:
        pinned_by_key.pop(canonical.lower(), None)

    result = sorted(pinned_by_key.values(), key=lv_sort_key)
    save_settings({"pinned_user_tags": result})
    return True, {
        "tag": canonical,
        "pinned": result,
        "tags": tags,
    }

def backup_db_before_user_tag_delete():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{DB_PATH.stem}_BEFORE_USER_TAG_DELETE_{stamp}{DB_PATH.suffix}"
    shutil.copy2(DB_PATH, target)
    return target

def backup_tags_file_before_user_tag_delete():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{TAGS_FILE_PATH.stem}_BEFORE_USER_TAG_DELETE_{stamp}{TAGS_FILE_PATH.suffix}"
    if TAGS_FILE_PATH.exists():
        shutil.copy2(TAGS_FILE_PATH, target)
        return target
    return None

def delete_available_user_tag(value):
    """Delete one catalog tag and remove the exact same tag from track_user."""
    requested = _normalize_single_user_tag(value)
    tags = get_available_user_tags()
    by_key = {item.lower(): item for item in tags}
    canonical = by_key.get(requested.lower())
    if not canonical:
        return False, {"error": "Tag is not in the tag catalog"}

    db_backup = backup_db_before_user_tag_delete()
    tags_backup = backup_tags_file_before_user_tag_delete()

    removed_from_tracks = 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT track_id, tags
              FROM main.track_user
             WHERE TRIM(COALESCE(tags, '')) != '';
        """)
        rows = cur.fetchall()
        target_key = canonical.lower()
        for row in rows:
            old_tags = _parse_user_tags_value(row["tags"])
            new_tags = [tag for tag in old_tags if tag.lower() != target_key]
            if len(new_tags) != len(old_tags):
                cur.execute("""
                    UPDATE main.track_user
                       SET tags = ?, updated_at = ?
                     WHERE lower(track_id) = lower(?);
                """, (", ".join(new_tags), now_iso_local(), row["track_id"]))
                removed_from_tracks += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    remaining_tags = [item for item in tags if item.lower() != canonical.lower()]
    remaining_tags = _write_available_user_tags(remaining_tags)
    pinned = [item for item in get_pinned_user_tags() if item.lower() != canonical.lower()]
    save_settings({"pinned_user_tags": pinned})

    return True, {
        "tag": canonical,
        "tags": remaining_tags,
        "pinned": pinned,
        "removed_from_tracks": removed_from_tracks,
        "db_backup": str(db_backup),
        "tags_backup": str(tags_backup or ""),
    }

def get_user_tag_manager_state():
    return {
        "ok": True,
        "tags": get_available_user_tags(),
        "pinned": get_pinned_user_tags(),
    }

def normalize_user_tags_text(value):
    tags = []
    seen = set()
    for part in re.split(r"[,;\s]+", str(value or "")):
        tag = part.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        key = tag.lower()
        if key not in seen:
            tags.append(tag)
            seen.add(key)
    return ", ".join(tags)

def user_mark_labels(mask):
    try:
        value = int(mask or 0)
    except Exception:
        value = 0

    labels = []
    if value & 1:
        labels.append("Ritms")
    if value & 2:
        labels.append("Pavadījums")
    if value & 4:
        labels.append("Solo")
    if value & 8:
        labels.append("Interesants")
    if value & 16:
        labels.append("Uzmanību")
    return labels

def update_track_user_review(track_id, rating=None, tags=None, marks=None):
    track_id = (track_id or "").strip()
    if not track_id:
        return False, "Missing Track ID"

    updates = []
    params = []
    if rating is not None:
        try:
            rating_int = int(rating)
        except Exception:
            rating_int = 0
        updates.append("rating = ?")
        params.append(max(0, min(5, rating_int)))
    if tags is not None:
        updates.append("tags = ?")
        params.append(str(tags or "").strip())
    if marks is not None:
        try:
            marks_int = int(marks)
        except Exception:
            marks_int = 0
        updates.append("marks = ?")
        params.append(max(0, min(31, marks_int)))
    if not updates:
        return False, "Nothing to update"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT OR IGNORE INTO main.track_user(track_id) VALUES (?);",
            (track_id,),
        )
        updates.append("updated_at = ?")
        params.append(now_iso_local())
        params.append(track_id)
        cur.execute(
            f"UPDATE main.track_user SET {', '.join(updates)} "
            "WHERE lower(track_id) = lower(?);",
            params,
        )
        conn.commit()
        return True, "Saved"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_track_main_category(track_id, category):
    track_id = (track_id or "").strip()
    category = (category or "").strip()
    if not track_id:
        return False, "Missing Track ID"
    if category not in ["Song", "Instrumental"]:
        return False, "Invalid category"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT OR IGNORE INTO main.track_user(track_id) VALUES (?);",
            (track_id,),
        )
        cur.execute("""
            UPDATE main.track_user
               SET manual_category = ?,
                   updated_at = ?
             WHERE lower(track_id) = lower(?);
        """, (category, now_iso_local(), track_id))
        conn.commit()
        return True, category
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_track_like(track_id, liked):
    track_id = (track_id or "").strip()
    if not track_id:
        return False, "Missing Track ID"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE main.tracks
               SET is_liked = ?,
                   updated_at = COALESCE(updated_at, datetime('now'))
             WHERE id = ?;
        """, (1 if liked else 0, track_id))
        conn.commit()
        if cur.rowcount == 0:
            return False, "Track ID not found"
        return True, "Liked" if liked else "Unliked"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def add_local_audio_to_track(track_id, local_path):
    track_id = (track_id or "").strip()
    local_path = urllib.parse.unquote(str(local_path or "")).strip().strip('"')
    if not track_id:
        return False, "Missing Track ID"
    if not local_path:
        return False, "Missing local file path"

    path_obj = Path(local_path)
    if not path_obj.exists() or not path_obj.is_file():
        return False, "Local file not found"
    extension = path_obj.suffix.lower()
    if extension not in _DATA_AUDIO_EXTENSIONS:
        return False, "Unsupported audio extension"

    conn = get_connection()
    cur = conn.cursor()
    try:
        if cur.execute(
            "SELECT COUNT(*) FROM main.tracks WHERE id = ?;", (track_id,)
        ).fetchone()[0] == 0:
            return False, "Track ID not found"

        folder_path = str(path_obj.parent)
        variant_no = None
        try:
            parsed_no = int(path_obj.parent.name)
            if parsed_no > 0:
                variant_no = parsed_no
        except Exception:
            pass

        # Preserve one physical path only once. Relinking transfers that path.
        old_variant_ids = [
            row[0] for row in cur.execute(
                "SELECT variant_id FROM main.media_files WHERE path = ?;",
                (str(path_obj),),
            ).fetchall() if row[0] is not None
        ]
        cur.execute("DELETE FROM main.media_files WHERE path = ?;", (str(path_obj),))

        variant_row = cur.execute("""
            SELECT tv.id
              FROM main.track_variants tv
             WHERE tv.track_id = ?
               AND lower(tv.folder_path) = lower(?)
               AND NOT EXISTS (
                    SELECT 1 FROM main.media_files mf
                     WHERE mf.variant_id = tv.id AND mf.role = 'main'
               )
             ORDER BY tv.id
             LIMIT 1;
        """, (track_id, folder_path)).fetchone()

        if variant_row:
            variant_id = int(variant_row[0])
        else:
            cur.execute("""
                INSERT INTO main.track_variants(
                    track_id, variant_no, label, folder_path, variant_kind
                ) VALUES (?, ?, ?, ?, 'main');
            """, (track_id, variant_no, path_obj.parent.name, folder_path))
            variant_id = int(cur.lastrowid)

        stat = path_obj.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
        file_created_at = (
            datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds")
            if os.name == "nt" else None
        )
        chronology_at = file_created_at or modified_at
        chronology_source = "filesystem_created_at" if file_created_at else "modified_time"

        cur.execute("""
            INSERT INTO main.media_files(
                variant_id, path, role, format, stem_label, size_bytes,
                modified_at, file_created_at, file_created_at_source,
                chronology_at
            ) VALUES (?, ?, 'main', ?, '', ?, ?, ?, ?, ?);
        """, (
            variant_id,
            str(path_obj),
            extension.lstrip("."),
            int(stat.st_size or 0),
            modified_at,
            file_created_at,
            chronology_source,
            chronology_at,
        ))

        for old_variant_id in old_variant_ids:
            cur.execute("""
                DELETE FROM main.track_variants
                 WHERE id = ?
                   AND NOT EXISTS (
                       SELECT 1 FROM main.media_files WHERE variant_id = ?
                   );
            """, (old_variant_id, old_variant_id))

        conn.commit()
        return True, "Local audio added"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_local_audio_from_track(track_id, local_path):
    track_id = (track_id or "").strip()
    local_path = urllib.parse.unquote(str(local_path or "")).strip().strip('"')
    if not track_id:
        return False, "Missing Track ID"
    if not local_path:
        return False, "Missing local file path"

    path_obj = Path(local_path)
    conn = get_connection()
    cur = conn.cursor()
    try:
        row = cur.execute("""
            SELECT mf.id, mf.variant_id
              FROM main.media_files mf
              JOIN main.track_variants tv ON tv.id = mf.variant_id
             WHERE lower(tv.track_id) = lower(?)
               AND mf.path = ?
             LIMIT 1;
        """, (track_id, str(path_obj))).fetchone()
        if not row:
            return False, "This local file is not linked to this track in LS DB"

        media_id = int(row["id"])
        variant_id = row["variant_id"]
        moved_to = ""

        if path_obj.exists() and path_obj.is_file():
            backup_dir = BASE_DIR / "Backup" / "deleted_local_audio"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = backup_dir / f"{path_obj.stem}__deleted_{stamp}{path_obj.suffix}"
            counter = 1
            while target.exists():
                target = backup_dir / f"{path_obj.stem}__deleted_{stamp}_{counter}{path_obj.suffix}"
                counter += 1
            shutil.move(str(path_obj), str(target))
            moved_to = str(target)

        cur.execute("DELETE FROM main.media_files WHERE id = ?;", (media_id,))
        if variant_id is not None:
            cur.execute("""
                DELETE FROM main.track_variants
                 WHERE id = ?
                   AND NOT EXISTS (
                       SELECT 1 FROM main.media_files WHERE variant_id = ?
                   );
            """, (variant_id, variant_id))
        conn.commit()

        if moved_to:
            return True, f"Local audio moved to Backup: {moved_to}"
        return True, "Local audio link removed; file was already missing on disk"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def backup_db_before_local_variant_delete():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{DB_PATH.stem}_BEFORE_LOCAL_VARIANT_DELETE_{stamp}{DB_PATH.suffix}"
    shutil.copy2(DB_PATH, target)
    return target

def _normalized_absolute_path(path_value):
    return os.path.normcase(os.path.abspath(str(Path(path_value))))

def _path_is_inside(path_value, folder_value, allow_equal=True):
    """Return True when path_value is inside folder_value.

    Uses os.path.commonpath so Windows drive letters and case normalization are
    handled by the OS when LS runs on Windows.
    """
    try:
        path_key = _normalized_absolute_path(path_value)
        folder_key = _normalized_absolute_path(folder_value)
        common = os.path.commonpath([path_key, folder_key])
        if common != folder_key:
            return False
        if not allow_equal and path_key == folder_key:
            return False
        return True
    except Exception:
        return False

def _load_variant_counters():
    try:
        if not VARIANT_COUNTERS_PATH.exists():
            return {}
        data = json.loads(VARIANT_COUNTERS_PATH.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_variant_counters(data):
    clean = {}
    for key, value in (data or {}).items():
        try:
            number = int(value)
        except Exception:
            continue
        if number > 0:
            clean[str(key)] = number

    VARIANT_COUNTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = VARIANT_COUNTERS_PATH.with_suffix(VARIANT_COUNTERS_PATH.suffix + ".tmp")
    temp_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(VARIANT_COUNTERS_PATH)

def _variant_counter_key(song_folder):
    return _normalized_absolute_path(song_folder)

def remember_variant_number(song_folder, variant_number):
    """Remember the highest variant number ever used for this song folder."""
    try:
        number = int(variant_number)
    except Exception:
        return

    if number <= 0:
        return

    data = _load_variant_counters()
    key = _variant_counter_key(song_folder)
    previous = int(data.get(key) or 0)
    if number > previous:
        data[key] = number
        _save_variant_counters(data)

def get_remembered_variant_number(song_folder):
    data = _load_variant_counters()
    try:
        return int(data.get(_variant_counter_key(song_folder)) or 0)
    except Exception:
        return 0

def delete_local_variant_from_track(track_id, local_path):
    r"""Move one complete numbered LS variant folder to Backup and remove its canonical DB rows."""
    track_id = str(track_id or "").strip()
    local_path = urllib.parse.unquote(str(local_path or "")).strip().strip('"')
    if not track_id:
        return False, "Missing Track ID"
    if not local_path:
        return False, "Missing local file path"

    root = Path(get_audio_library_root_folder())
    path_obj = Path(local_path)
    if not root.exists() or not root.is_dir():
        return False, f"Audio library root folder not found: {root}"
    if not path_obj.exists() or not path_obj.is_file():
        return False, f"Linked local audio file not found: {path_obj}"

    variant_folder = path_obj.parent
    if not variant_folder.name.isdigit() or int(variant_folder.name) <= 0:
        return False, "Linked file is not inside an LS numbered variant folder (1, 2, 3...)."

    song_folder = variant_folder.parent
    category_folder = song_folder.parent
    if category_folder.name not in ("Song", "Instrumental"):
        return False, "Linked file is not inside the LS Song / Instrumental library structure."
    try:
        if _normalized_absolute_path(category_folder.parent) != _normalized_absolute_path(root):
            return False, "Linked variant is outside the configured Audio library root."
    except Exception:
        return False, "Could not validate the local variant path."

    conn = get_connection()
    moved_to = None
    backup_path = None
    report_path = None
    try:
        cur = conn.cursor()
        row = cur.execute("""
            SELECT tv.id AS variant_id, t.title
              FROM main.media_files mf
              JOIN main.track_variants tv ON tv.id = mf.variant_id
              JOIN main.tracks t ON t.id = tv.track_id
             WHERE lower(tv.track_id) = lower(?)
               AND mf.path = ?
             LIMIT 1;
        """, (track_id, str(path_obj))).fetchone()
        if not row:
            return False, "This numbered variant folder is not linked to this Track ID in LS DB."

        variant_id = int(row["variant_id"])
        title = str(row["title"] or "")
        media_rows = [
            dict(item) for item in cur.execute("""
                SELECT id, path, role
                  FROM main.media_files
                 WHERE variant_id = ?
                 ORDER BY id;
            """, (variant_id,)).fetchall()
        ]
        if not media_rows:
            return False, "Variant has no linked media rows"

        remember_variant_number(song_folder, int(variant_folder.name))
        backup_path = backup_db_before_local_variant_delete()

        relative_variant = Path(os.path.relpath(str(variant_folder), str(root)))
        delete_stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_root = BASE_DIR / "Backup" / "deleted_local_variants" / delete_stamp
        moved_to = backup_root / relative_variant
        moved_to.parent.mkdir(parents=True, exist_ok=True)
        if moved_to.exists():
            raise RuntimeError(f"Backup target already exists: {moved_to}")

        shutil.move(str(variant_folder), str(moved_to))
        try:
            cur.execute("DELETE FROM main.media_files WHERE variant_id = ?;", (variant_id,))
            cur.execute("DELETE FROM main.track_variants WHERE id = ?;", (variant_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            try:
                if moved_to.exists() and not variant_folder.exists():
                    variant_folder.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(moved_to), str(variant_folder))
            except Exception as rollback_exc:
                log_ls_exception(
                    "local_audio",
                    "restore_deleted_variant",
                    rollback_exc,
                    context={
                        "track_id": track_id,
                        "backup_path": str(moved_to or ""),
                        "restore_path": str(variant_folder),
                    },
                    include_traceback=False,
                )
            raise

        song_folder_removed = False
        if song_folder.exists():
            has_remaining_files = any(item.is_file() for item in song_folder.rglob("*"))
            if not has_remaining_files:
                shutil.rmtree(song_folder)
                song_folder_removed = True

        REPORTS_DIR.mkdir(exist_ok=True)
        report_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"local_variant_delete_{report_stamp}.md"
        removed_links = len(media_rows)
        removed_stem_links = sum(1 for item in media_rows if item.get("role") == "stem")
        report_path.write_text("\n".join([
            "# LocalSunoDb Local Variant Delete",
            "",
            f"- Track ID: `{track_id}`",
            f"- Title: `{title}`",
            f"- Original variant: `{variant_folder}`",
            f"- Variant backup: `{moved_to}`",
            f"- DB backup: `{backup_path}`",
            f"- Removed media_files rows: **{removed_links}**",
            f"- Removed stem links: **{removed_stem_links}**",
            f"- Song title folder removed: **{'yes' if song_folder_removed else 'no'}**",
            "",
            "Variant numbers are not renumbered or reused.",
        ]), encoding="utf-8")

        return True, "\n".join([
            "Local variant moved to Backup:",
            str(moved_to),
            "",
            f"DB backup: {backup_path}",
            f"Removed DB audio links: {removed_links}",
            f"Removed stem links: {removed_stem_links}",
            f"Song title folder removed: {'yes' if song_folder_removed else 'no'}",
            f"Report: {report_path}",
        ])
    except Exception as exc:
        return False, str(exc)
    finally:
        conn.close()

def normalize_saved_view_name(value):
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ValueError("Saved view name is required.")
    if len(text) > 80:
        raise ValueError("Saved view name may contain at most 80 characters.")
    return text

def normalize_saved_view_query(value):
    """Keep only reusable, read-only Suno Database view parameters."""
    text = str(value or "").strip()
    if len(text) > 16384:
        raise ValueError("Saved view filter is too large.")
    if "://" in text:
        text = urllib.parse.urlparse(text).query
    text = text.lstrip("?")

    grouped = {key: [] for key in SAVED_VIEW_PARAM_ORDER}
    for key, raw_value in urllib.parse.parse_qsl(
        text,
        keep_blank_values=False,
    )[:100]:
        if key not in grouped:
            continue
        clean_value = str(raw_value or "").strip()
        if not clean_value:
            continue
        if len(clean_value) > 1000:
            raise ValueError(f"Saved view value is too large: {key}")
        if key in SAVED_VIEW_MULTI_PARAMS:
            if clean_value.casefold() not in {
                item.casefold() for item in grouped[key]
            }:
                grouped[key].append(clean_value)
        else:
            grouped[key] = [clean_value]

    pairs = []
    for key in SAVED_VIEW_PARAM_ORDER:
        for clean_value in grouped[key]:
            pairs.append((key, clean_value))
    return urllib.parse.urlencode(pairs, doseq=True)

def get_saved_views():
    raw_views = get_settings().get("saved_views") or []
    if not isinstance(raw_views, list):
        return []

    result = []
    seen_ids = set()
    for item in raw_views:
        if not isinstance(item, dict):
            continue
        view_id = str(item.get("id") or "").strip()
        try:
            name = normalize_saved_view_name(item.get("name"))
            query = normalize_saved_view_query(item.get("query"))
        except ValueError:
            continue
        if not view_id or view_id in seen_ids:
            continue
        seen_ids.add(view_id)
        result.append({
            "id": view_id,
            "name": name,
            "query": query,
            "created_at": str(item.get("created_at") or ""),
            "updated_at": str(item.get("updated_at") or ""),
        })
    return result[:SAVED_VIEW_MAX_COUNT]

def create_saved_view(name, query):
    clean_name = normalize_saved_view_name(name)
    clean_query = normalize_saved_view_query(query)
    with SAVED_VIEWS_LOCK:
        views = get_saved_views()
        if any(item["name"].casefold() == clean_name.casefold() for item in views):
            raise ValueError("A saved view with this name already exists.")
        if len(views) >= SAVED_VIEW_MAX_COUNT:
            raise ValueError(f"LocalSunoDb supports up to {SAVED_VIEW_MAX_COUNT} saved views.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        view_id = "sv_" + hashlib.sha256(
            f"{time.time_ns()}|{clean_name}".encode("utf-8")
        ).hexdigest()[:16]
        item = {
            "id": view_id,
            "name": clean_name,
            "query": clean_query,
            "created_at": now,
            "updated_at": now,
        }
        views.append(item)
        save_settings({"saved_views": views})
        return item

def rename_saved_view(view_id, name):
    clean_id = str(view_id or "").strip()
    clean_name = normalize_saved_view_name(name)
    with SAVED_VIEWS_LOCK:
        views = get_saved_views()
        if any(
            item["id"] != clean_id and
            item["name"].casefold() == clean_name.casefold()
            for item in views
        ):
            raise ValueError("A saved view with this name already exists.")
        target = next((item for item in views if item["id"] == clean_id), None)
        if target is None:
            raise ValueError("Saved view was not found.")
        target["name"] = clean_name
        target["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save_settings({"saved_views": views})
        return target

def delete_saved_view(view_id):
    clean_id = str(view_id or "").strip()
    with SAVED_VIEWS_LOCK:
        views = get_saved_views()
        remaining = [item for item in views if item["id"] != clean_id]
        if len(remaining) == len(views):
            raise ValueError("Saved view was not found.")
        save_settings({"saved_views": remaining})
        return clean_id


def build_track_filter_query_parts(
    query="",
    style_query="",
    workspace="",
    kind_filter="",
    category_filter="",
    local_family_filter="",
    like_filter="",
    local_audio_filter="",
    search_name=True,
    search_lyrics=False,
    search_prompt=False,
    search_marks=False,
    search_tags=False,
    flag_filter="",
    tag_filter="",
    track_ids_filter="",
    family_group_track_ids=None,
):
    """Build the shared Library WHERE clause and parameters.

    ``search_tracks()`` and ``count_tracks()`` must apply exactly the same
    filters. Keeping their WHERE construction in one function prevents the
    visible result list and its reported count from drifting apart.
    """
    query = (query or "").strip()
    style_query = (style_query or "").strip()
    selected_workspaces = normalize_multi_filter_values(workspace)
    kind_filter = (kind_filter or "").strip()
    selected_categories = normalize_multi_filter_values(category_filter)
    selected_local_families = normalize_multi_filter_values(local_family_filter)
    local_audio_filter = (local_audio_filter or "").strip().lower()

    params = []
    where_parts = [
        "IFNULL(t.library_status, 'active') = 'active'",
        "(tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)",
    ]

    columns = get_table_columns()
    ui_columns = get_track_ui_columns()
    intent_audit_available = table_exists("ls_category_intent_audit")
    if "finder_hidden" in columns:
        where_parts.append("IFNULL(t.finder_hidden, 0) != 1")

    # Stem metadata rows are not normal songs in the main list.
    if kind_filter != "__unlinked_stems__":
        where_parts.append("IFNULL(t.kind, '') != 'Stem'")

    searchable_parts = build_searchable_parts(
        search_name=search_name,
        search_lyrics=search_lyrics,
        search_prompt=search_prompt,
    )

    query_tokens = split_search_tokens(query)
    if query_tokens:
        append_token_search(where_parts, params, searchable_parts, query_tokens)

    # ✶ and #tag are additional requirements, not alternative text fields.
    # Separate WHERE parts make them AND conditions.
    append_mark_tag_presence_filters(
        where_parts,
        search_marks=search_marks,
        search_tags=search_tags,
        ui_columns=ui_columns,
    )
    append_specific_user_review_filters(
        where_parts,
        params,
        flag_filter=flag_filter,
        tag_filter=tag_filter,
        ui_columns=ui_columns,
    )

    style_tokens = split_search_tokens(style_query)
    if style_tokens:
        style_searchable_parts = [
            "lower(COALESCE(t.metadata_tags, t.style, t.display_tags, ''))",
        ]
        append_token_search(where_parts, params, style_searchable_parts, style_tokens)

    if selected_workspaces:
        where_parts.append(
            "COALESCE(t.workspaceName, t.workspace, '') IN (" +
            ",".join(["?"] * len(selected_workspaces)) + ")"
        )
        params.extend(selected_workspaces)

    if selected_local_families:
        family_track_ids = get_track_ids_for_local_family_filter(
            selected_local_families
        )
        if family_track_ids:
            where_parts.append(
                "lower(t.id) IN (" +
                ",".join(["?"] * len(family_track_ids)) + ")"
            )
            params.extend([track_id.lower() for track_id in family_track_ids])
        else:
            where_parts.append("1 = 0")

    if family_group_track_ids is not None:
        group_track_ids = normalize_track_ids_filter(family_group_track_ids)
        if group_track_ids:
            where_parts.append(
                "lower(t.id) IN (" +
                ",".join(["?"] * len(group_track_ids)) + ")"
            )
            params.extend([track_id.lower() for track_id in group_track_ids])
        else:
            where_parts.append("1 = 0")

    selected_track_ids = normalize_track_ids_filter(track_ids_filter)
    if selected_track_ids:
        where_parts.append(
            "lower(t.id) IN (" + ",".join(["?"] * len(selected_track_ids)) + ")"
        )
        params.extend([track_id.lower() for track_id in selected_track_ids])

    if kind_filter == "__last_imported__":
        last_ids = get_last_imported_suno_ids()
        if last_ids:
            where_parts.append(
                "lower(t.id) IN (" + ",".join(["?"] * len(last_ids)) + ")"
            )
            params.extend([track_id.lower() for track_id in last_ids])
        else:
            where_parts.append("1 = 0")
    elif kind_filter == "__liked__":
        where_parts.append(
            "(IFNULL(t.is_liked, 0) = 1 OR "
            "lower(COALESCE(t.raw_is_liked, '')) = 'true')"
        )
    elif kind_filter == "__conflict_s_to_i__":
        if "review_group" in ui_columns:
            where_parts.append(
                "tu.review_group = 'mismatch_db_Song_proposed_Instrumental'"
            )
        else:
            where_parts.append("1 = 0")
    elif kind_filter == "__conflict_i_to_s__":
        if "review_group" in ui_columns:
            where_parts.append(
                "tu.review_group = 'mismatch_db_Instrumental_proposed_Song'"
            )
        else:
            where_parts.append("1 = 0")
    elif kind_filter == "__intent_s_to_i__":
        if intent_audit_available:
            where_parts.append("""
                EXISTS (
                    SELECT 1 FROM ls_category_intent_audit sia_filter
                     WHERE lower(sia_filter.track_id) = lower(t.id)
                       AND sia_filter.current_category = 'Song'
                       AND sia_filter.intent_label = 'Instrumental'
                       AND sia_filter.recommended_action = 'review_category_conflict'
                )
            """)
        else:
            where_parts.append("1 = 0")
    elif kind_filter == "__intent_i_to_s__":
        if intent_audit_available:
            where_parts.append("""
                EXISTS (
                    SELECT 1 FROM ls_category_intent_audit sia_filter
                     WHERE lower(sia_filter.track_id) = lower(t.id)
                       AND sia_filter.current_category = 'Instrumental'
                       AND sia_filter.intent_label = 'Song'
                       AND sia_filter.recommended_action = 'review_category_conflict'
                )
            """)
        else:
            where_parts.append("1 = 0")
    elif kind_filter == "__has_stems__":
        where_parts.append("IFNULL(tu.stem_count, 0) > 0")
    elif kind_filter == "__unlinked_stems__":
        if table_exists("local_audio_files") and "kind" in columns:
            where_parts.append(
                get_unlinked_stems_condition_sql().replace("tracks.", "t.")
            )
        else:
            where_parts.append("1 = 0")
    elif kind_filter:
        where_parts.append(
            "COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') = ?"
        )
        params.append(kind_filter)

    append_main_category_filter(
        where_parts,
        params,
        selected_categories,
        ui_columns=ui_columns,
    )

    if local_audio_filter in {"with", "without"}:
        has_local_audio_sql = get_has_local_audio_condition_sql()
        if local_audio_filter == "with":
            where_parts.append(has_local_audio_sql)
        else:
            where_parts.append(f"NOT ({has_local_audio_sql})")

    where_sql = "WHERE " + " AND ".join(where_parts) if where_parts else ""
    return where_sql, params, ui_columns, intent_audit_available



def _decode_track_page_cursor(value, sort_by="", sort_dir="asc"):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        padding = "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode((raw + padding).encode("ascii")).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict) or int(payload.get("v") or 0) != 1:
        return None
    if str(payload.get("sort_by") or "") != normalize_sort_by(sort_by):
        return None
    if str(payload.get("sort_dir") or "asc") != normalize_sort_dir(sort_dir):
        return None
    values = payload.get("values")
    return values if isinstance(values, dict) else None


def encode_track_page_cursor(row, sort_by="", sort_dir="asc"):
    if not row:
        return ""
    sort_by = normalize_sort_by(sort_by)
    sort_dir = normalize_sort_dir(sort_dir)
    keys = row.keys() if hasattr(row, "keys") else ()
    duration_value = row["sort_duration_seconds"] if "sort_duration_seconds" in keys else duration_sort_value(row["duration"] if "duration" in keys else "")
    try:
        duration_value = float(duration_value or 0)
    except (TypeError, ValueError):
        duration_value = 0.0
    payload = {
        "v": 1,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "values": {
            "workspace": lv_sort_key(row["workspace"] if "workspace" in keys else ""),
            "title": lv_sort_key(row["title"] if "title" in keys else ""),
            "created": str(row["created_at"] if "created_at" in keys else "" or ""),
            "duration": duration_value,
            "id": str(row["id"] if "id" in keys else "").lower(),
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _track_cursor_predicate(cursor_value, sort_by="", sort_dir="asc"):
    values = _decode_track_page_cursor(cursor_value, sort_by, sort_dir)
    if not values:
        return "", []

    workspace_expr = "ls_sort_text(COALESCE(t.workspaceName, t.workspace, ''))"
    title_expr = "ls_sort_text(COALESCE(t.title, ''))"
    created_expr = "COALESCE(t.created_at, '')"
    duration_expr = (
        "COALESCE(tu.duration_seconds, t.metadata_duration, "
        "ls_duration_seconds(t.duration), 0)"
    )
    id_expr = "lower(t.id)"

    try:
        duration_value = float(values.get("duration") or 0)
    except (TypeError, ValueError):
        duration_value = 0.0
    cursor = {
        "workspace": str(values.get("workspace") or ""),
        "title": str(values.get("title") or ""),
        "created": str(values.get("created") or ""),
        "duration": duration_value,
        "id": str(values.get("id") or "").lower(),
    }

    primary_op = "<" if normalize_sort_dir(sort_dir) == "desc" else ">"
    sort_by = normalize_sort_by(sort_by)

    if sort_by == "title":
        return (
            f"(({title_expr} {primary_op} ?) OR "
            f"({title_expr} = ? AND {created_expr} < ?) OR "
            f"({title_expr} = ? AND {created_expr} = ? AND {id_expr} > ?))",
            [cursor["title"], cursor["title"], cursor["created"], cursor["title"], cursor["created"], cursor["id"]],
        )

    if sort_by == "created":
        return (
            f"(({created_expr} {primary_op} ?) OR "
            f"({created_expr} = ? AND {title_expr} > ?) OR "
            f"({created_expr} = ? AND {title_expr} = ? AND {id_expr} > ?))",
            [cursor["created"], cursor["created"], cursor["title"], cursor["created"], cursor["title"], cursor["id"]],
        )

    if sort_by == "duration":
        return (
            f"(({duration_expr} {primary_op} ?) OR "
            f"({duration_expr} = ? AND {title_expr} > ?) OR "
            f"({duration_expr} = ? AND {title_expr} = ? AND {id_expr} > ?))",
            [cursor["duration"], cursor["duration"], cursor["title"], cursor["duration"], cursor["title"], cursor["id"]],
        )

    return (
        f"(({workspace_expr} > ?) OR "
        f"({workspace_expr} = ? AND {title_expr} > ?) OR "
        f"({workspace_expr} = ? AND {title_expr} = ? AND {created_expr} < ?) OR "
        f"({workspace_expr} = ? AND {title_expr} = ? AND {created_expr} = ? AND {id_expr} > ?))",
        [
            cursor["workspace"],
            cursor["workspace"], cursor["title"],
            cursor["workspace"], cursor["title"], cursor["created"],
            cursor["workspace"], cursor["title"], cursor["created"], cursor["id"],
        ],
    )


def search_tracks(query="", style_query="", workspace="", kind_filter="", category_filter="", local_family_filter="", like_filter="", local_audio_filter="", limit_value="300", search_name=True, search_lyrics=False, search_prompt=False, search_marks=False, search_tags=False, flag_filter="", tag_filter="", track_ids_filter="", family_group_track_ids=None, sort_by="", sort_dir="asc", offset_value=0, cursor_value=""):
    """Fast v4 list query.

    v4.01 reads the user-facing list values from track_ui where possible:
    play_status, ui_type, duration_text, bpm_text, model_badge, stem_count.
    tracks still keeps the Suno/source values.
    """
    conn = get_connection()
    cur = conn.cursor()

    limit = normalize_limit(limit_value)
    try:
        offset = max(0, int(offset_value or 0))
    except (TypeError, ValueError):
        offset = 0
    sort_by = normalize_sort_by(sort_by)
    sort_dir = normalize_sort_dir(sort_dir)
    order_sql = get_track_order_sql(sort_by, sort_dir)
    where_sql, params, ui_columns, intent_audit_available = (
        build_track_filter_query_parts(
            query=query,
            style_query=style_query,
            workspace=workspace,
            kind_filter=kind_filter,
            category_filter=category_filter,
            local_family_filter=local_family_filter,
            like_filter=like_filter,
            local_audio_filter=local_audio_filter,
            search_name=search_name,
            search_lyrics=search_lyrics,
            search_prompt=search_prompt,
            search_marks=search_marks,
            search_tags=search_tags,
            flag_filter=flag_filter,
            tag_filter=tag_filter,
            track_ids_filter=track_ids_filter,
            family_group_track_ids=family_group_track_ids,
        )
    )

    cursor_sql, cursor_params = _track_cursor_predicate(cursor_value, sort_by, sort_dir)
    if cursor_sql:
        where_sql = (where_sql + " AND " if where_sql else "WHERE ") + cursor_sql
        params.extend(cursor_params)

    limit_sql = ""
    if limit is not None:
        if cursor_sql:
            limit_sql = "LIMIT ?"
            params.append(limit)
        else:
            limit_sql = "LIMIT ? OFFSET ?"
            params.extend([limit, offset])

    def ui_col_expr(col, fallback="''"):
        if col in ui_columns:
            return f"COALESCE(tu.{col}, '')"
        return fallback

    main_category_sql = ui_col_expr("main_category", "COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '')")
    proposed_main_category_sql = ui_col_expr("proposed_main_category", "''")
    main_category_confidence_sql = ui_col_expr("main_category_confidence", "''")
    main_category_confidence_label_sql = ui_col_expr("main_category_confidence_label", "''")
    main_category_review_reason_sql = ui_col_expr("main_category_review_reason", "''")
    main_category_review_group_sql = ui_col_expr("main_category_review_group", "''")
    user_rating_sql = ui_col_expr("user_rating", "0")
    user_tags_sql = ui_col_expr("user_tags", "''")
    user_marks_sql = ui_col_expr("user_marks", "0")
    audit_join_sql = (
        "LEFT JOIN ls_category_intent_audit sia ON lower(sia.track_id) = lower(t.id)"
        if intent_audit_available else ""
    )
    audit_intent_label_sql = "COALESCE(sia.intent_label, '')" if intent_audit_available else "''"
    audit_intent_confidence_sql = "COALESCE(sia.intent_confidence, '')" if intent_audit_available else "''"
    audit_intent_score_sql = "COALESCE(sia.intent_score, 0)" if intent_audit_available else "0"
    audit_rule_code_sql = "COALESCE(sia.rule_code, '')" if intent_audit_available else "''"
    audit_recommended_action_sql = "COALESCE(sia.recommended_action, '')" if intent_audit_available else "''"
    audit_evidence_json_sql = "COALESCE(sia.evidence_json, '[]')" if intent_audit_available else "'[]'"

    full_select_sql = f"""
        SELECT
            t.id,
            t.title,
            COALESCE(t.workspaceName, t.workspace, '') AS workspace,
            COALESCE(t.workspaceId, t.workspace_id, '') AS workspace_id,
            t.audio_url,
            t.status,
            t.created_at,
            COALESCE(
                NULLIF(tu.duration_text, ''),
                NULLIF(t.duration, ''),
                CASE
                    WHEN t.metadata_duration IS NOT NULL THEN
                        printf('%d:%02d', CAST(t.metadata_duration / 60 AS INTEGER), CAST(t.metadata_duration AS INTEGER) % 60)
                    ELSE ''
                END
            ) AS duration,
            COALESCE(
                tu.duration_seconds,
                t.metadata_duration,
                ls_duration_seconds(t.duration),
                0
            ) AS sort_duration_seconds,
            COALESCE(t.metadata_type, t.type, '') AS type,
            t.is_stem,
            t.local_mp3,
            t.local_wav,
            t.notes,
            COALESCE(NULLIF(t.metadata_tags, ''), NULLIF(t.style, ''), NULLIF(t.display_tags, ''), '') AS style,
            t.caption,
            COALESCE(NULLIF(t.metadata_prompt, ''), NULLIF(t.prompt, ''), '') AS prompt,
            CASE
                WHEN TRIM(COALESCE(t.lyrics, '')) != ''
                THEN SUBSTR(t.lyrics, 1, 800)
                ELSE ''
            END AS lyrics,
            CASE
                WHEN TRIM(COALESCE(t.lyrics, '')) != '' THEN 1
                ELSE 0
            END AS has_lyrics,
            COALESCE(NULLIF(tu.ui_type, ''), NULLIF(t.kind, ''), '') AS kind,
            CASE WHEN IFNULL(t.is_liked, 0) = 1 OR lower(COALESCE(t.raw_is_liked, '')) = 'true' THEN 'True' ELSE 'False' END AS raw_is_liked,
            COALESCE(NULLIF(t.raw_image_url, ''), NULLIF(t.image_url, ''), '') AS raw_image_url,
            COALESCE(NULLIF(t.raw_image_large_url, ''), NULLIF(t.image_large_url, ''), NULLIF(t.image_url, ''), '') AS raw_image_large_url,
            COALESCE(
                NULLIF(REPLACE(REPLACE(tu.bpm_text, ' BPM', ''), ' bpm', ''), ''),
                NULLIF(t.bpm, ''),
                CASE WHEN t.metadata_avg_bpm IS NOT NULL THEN CAST(CAST(ROUND(t.metadata_avg_bpm) AS INTEGER) AS TEXT) ELSE '' END
            ) AS bpm,
            COALESCE(NULLIF(tu.model_badge, ''), NULLIF(t.major_model_version, ''), NULLIF(t.model_version, ''), '') AS model_version,
            COALESCE(NULLIF(t.major_model_version, ''), NULLIF(tu.model_badge, ''), '') AS major_model_version,
            t.model_name,
            tu.play_status AS ui_play_status,
            tu.play_sort AS ui_play_sort,
            tu.ui_type AS ui_type,
            tu.ui_type_sort AS ui_type_sort,
            tu.ui_tags AS ui_tags,
            tu.duration_seconds AS ui_duration_seconds,
            tu.duration_text AS ui_duration_text,
            tu.bpm_text AS ui_bpm_text,
            tu.model_badge AS ui_model_badge,
            tu.has_local_audio AS ui_has_local_audio,
            tu.best_local_audio_path AS ui_best_local_audio_path,
            tu.stem_count AS ui_stem_count,
            {main_category_sql} AS main_category,
            {proposed_main_category_sql} AS proposed_main_category,
            {main_category_confidence_sql} AS main_category_confidence,
            {main_category_confidence_label_sql} AS main_category_confidence_label,
            {main_category_review_reason_sql} AS main_category_review_reason,
            {main_category_review_group_sql} AS main_category_review_group,
            {user_rating_sql} AS user_rating,
            {user_tags_sql} AS user_tags,
            {user_marks_sql} AS user_marks,
            {audit_intent_label_sql} AS audit_intent_label,
            {audit_intent_confidence_sql} AS audit_intent_confidence,
            {audit_intent_score_sql} AS audit_intent_score,
            {audit_rule_code_sql} AS audit_rule_code,
            {audit_recommended_action_sql} AS audit_recommended_action,
            {audit_evidence_json_sql} AS audit_evidence_json
    """

    if limit is not None:
        # Sort only the narrow Track ID set before LIMIT. Sorting the original
        # wide rows carried Lyrics, Prompt, image URLs and other long text
        # through SQLite's temporary sorter, which made All types and Cover
        # disproportionately slow. The outer query expands only the selected
        # rows and preserves the same final ordering.
        sql = f"""
            WITH selected_track_ids AS MATERIALIZED (
                SELECT t.id AS track_id
                FROM tracks_compat t
                LEFT JOIN track_ui tu ON tu.track_id = t.id
                {where_sql}
                ORDER BY {order_sql}
                {limit_sql}
            )
            {full_select_sql}
            FROM selected_track_ids selected
            JOIN tracks_compat t ON t.id = selected.track_id
            LEFT JOIN track_ui tu ON tu.track_id = t.id
            {audit_join_sql}
            ORDER BY {order_sql};
        """
    else:
        sql = f"""
            {full_select_sql}
            FROM tracks_compat t
            LEFT JOIN track_ui tu ON tu.track_id = t.id
            {audit_join_sql}
            {where_sql}
            ORDER BY {order_sql};
        """

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def count_tracks(query="", style_query="", workspace="", kind_filter="", category_filter="", local_family_filter="", like_filter="", local_audio_filter="", search_name=True, search_lyrics=False, search_prompt=False, search_marks=False, search_tags=False, flag_filter="", tag_filter="", track_ids_filter="", family_group_track_ids=None):
    """Count matching rows with the same shared filters as search_tracks()."""
    conn = get_connection()
    cur = conn.cursor()

    where_sql, params, _ui_columns, _intent_audit_available = (
        build_track_filter_query_parts(
            query=query,
            style_query=style_query,
            workspace=workspace,
            kind_filter=kind_filter,
            category_filter=category_filter,
            local_family_filter=local_family_filter,
            like_filter=like_filter,
            local_audio_filter=local_audio_filter,
            search_name=search_name,
            search_lyrics=search_lyrics,
            search_prompt=search_prompt,
            search_marks=search_marks,
            search_tags=search_tags,
            flag_filter=flag_filter,
            tag_filter=tag_filter,
            track_ids_filter=track_ids_filter,
            family_group_track_ids=family_group_track_ids,
        )
    )

    cur.execute(f"""
        SELECT COUNT(*)
        FROM tracks_compat t
        LEFT JOIN track_ui tu ON tu.track_id = t.id
        {where_sql};
    """, params)
    total = cur.fetchone()[0]
    conn.close()
    return total


def get_stem_counts_for_track_ids(track_ids):
    ids = [str(x or "").lower() for x in track_ids if x]
    if not ids or not table_exists("local_audio_files"):
        return {}

    conn = get_connection()
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(ids))
    cur.execute(f"""
        SELECT lower(track_id) AS track_id, COUNT(*) AS count
        FROM local_audio_files
        WHERE is_stem = 1
          AND lower(track_id) IN ({placeholders})
        GROUP BY lower(track_id);
    """, ids)
    result = {row["track_id"]: row["count"] for row in cur.fetchall()}
    conn.close()
    return result


def get_stems_for_track(track_id):
    track_id = str(track_id or "").strip().lower()
    if not track_id or not table_exists("local_audio_files"):
        return []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, track_id, path, filename, folder, extension, size_bytes, stem_label
        FROM local_audio_files
        WHERE lower(track_id) = ?
          AND is_stem = 1
        ORDER BY stem_label COLLATE NOCASE, filename COLLATE NOCASE;
    """, (track_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    rows.sort(key=stem_sort_key)
    return rows


def get_best_local_audio_path_for_track(track_id):
    """Return the real linked local WAV/MP3 path for this track, not an edit_cache copy."""
    track_id = str(track_id or "").strip()
    if not track_id:
        return ""

    conn = get_connection()
    cur = conn.cursor()
    try:
        track_title = ""
        track_workspace = ""

        cur.execute("""
            SELECT title, workspace, local_wav, local_mp3
            FROM tracks_compat
            WHERE lower(id) = lower(?);
        """, (track_id,))
        row = cur.fetchone()
        if row:
            track_title = str(row["title"] or "").strip()
            track_workspace = str(row["workspace"] or "").strip()
            for value in [row["local_wav"], row["local_mp3"]]:
                path = str(value or "").strip()
                if path and os.path.exists(path):
                    return path

        if table_exists("local_audio_files"):
            # 1) Properly linked non-stem local audio.
            cur.execute("""
                SELECT path
                FROM local_audio_files
                WHERE lower(track_id) = lower(?)
                  AND IFNULL(is_stem, 0) = 0
                  AND path IS NOT NULL
                  AND TRIM(path) != ''
                ORDER BY
                  CASE lower(extension)
                    WHEN 'wav' THEN 0
                    WHEN 'flac' THEN 1
                    WHEN 'mp3' THEN 2
                    ELSE 9
                  END,
                  id DESC
                LIMIT 1;
            """, (track_id,))
            row2 = cur.fetchone()
            if row2:
                path = str(row2["path"] or "").strip()
                if path and os.path.exists(path):
                    return path

            # 2) Fallback for old scans where the file exists in local_audio_files
            # but was not linked to this Suno track_id. Match by exact filename stem.
            if track_title:
                normalized_title = track_title.lower()
                name_candidates = [
                    normalized_title + ".wav",
                    normalized_title + ".flac",
                    normalized_title + ".mp3",
                    normalized_title + ".m4a",
                    normalized_title + ".aac",
                    normalized_title + ".ogg",
                ]
                placeholders = ",".join(["?"] * len(name_candidates))
                cur.execute(f"""
                    SELECT path, filename, folder
                    FROM local_audio_files
                    WHERE IFNULL(is_stem, 0) = 0
                      AND path IS NOT NULL
                      AND TRIM(path) != ''
                      AND filename IS NOT NULL
                      AND lower(filename) IN ({placeholders})
                    ORDER BY
                      CASE
                        WHEN lower(extension) = 'wav' THEN 0
                        WHEN lower(extension) = 'flac' THEN 1
                        WHEN lower(extension) = 'mp3' THEN 2
                        ELSE 9
                      END,
                      CASE
                        WHEN ? != '' AND lower(folder) LIKE '%' || lower(?) || '%' THEN 0
                        ELSE 1
                      END,
                      id DESC
                    LIMIT 1;
                """, name_candidates + [track_workspace, track_workspace])
                row3 = cur.fetchone()
                if row3:
                    path = str(row3["path"] or "").strip()
                    if path and os.path.exists(path):
                        return path

        # 3) Last resort: scan the configured audio root for an exact filename.
        # This matches the way the Stem player succeeds from local filesystem paths.
        path = find_existing_audio_by_exact_title(track_title, track_workspace)
        if path:
            return path

        return ""
    finally:
        conn.close()


def get_confirmed_local_audio_paths_for_render(rows):
    """Return exact Track ID local-audio links without touching the filesystem.

    Suno Library rendering must not synchronously probe every WAV/MP3 path.
    The DB association controls the black Play state; the real file is checked
    only when the user explicitly starts playback, Compare, Edit or deletion.
    """
    result = {}
    unresolved_ids = []

    for row in rows or []:
        try:
            track_id = str(row["id"] or "").strip()
        except Exception:
            continue
        if not track_id:
            continue

        track_key = track_id.lower()
        linked_path = ""
        for key in ("local_wav", "local_mp3"):
            try:
                candidate = str(row[key] or "").strip()
            except Exception:
                candidate = ""
            if candidate:
                linked_path = candidate
                break

        if linked_path:
            result[track_key] = linked_path
        else:
            unresolved_ids.append(track_key)

    if not unresolved_ids or not table_exists("local_audio_files"):
        return result

    conn = get_connection()
    cur = conn.cursor()
    try:
        for start_index in range(0, len(unresolved_ids), 800):
            id_chunk = unresolved_ids[start_index:start_index + 800]
            if not id_chunk:
                continue
            placeholders = ",".join(["?"] * len(id_chunk))
            cur.execute(f"""
                SELECT lower(track_id) AS track_id, path, extension, id
                FROM local_audio_files
                WHERE IFNULL(is_stem, 0) = 0
                  AND lower(track_id) IN ({placeholders})
                  AND path IS NOT NULL
                  AND TRIM(path) != ''
                ORDER BY
                  CASE lower(extension)
                    WHEN 'wav' THEN 0
                    WHEN 'flac' THEN 1
                    WHEN 'mp3' THEN 2
                    WHEN 'm4a' THEN 3
                    WHEN 'aac' THEN 4
                    WHEN 'ogg' THEN 5
                    ELSE 9
                  END,
                  id DESC;
            """, id_chunk)
            for item in cur.fetchall():
                track_key = str(item["track_id"] or "").lower()
                path = str(item["path"] or "").strip()
                if track_key and track_key not in result and path:
                    result[track_key] = path
    finally:
        conn.close()

    return result


def get_best_local_audio_paths_for_render(rows, confirmed_paths=None):
    """Resolve render-time paths from DB values only.

    No ``exists``/``isfile`` call is allowed in the normal Library request.
    Filename-based legacy matches may still be shown for Compare, but their
    physical existence is validated only when the user invokes the action.
    """
    result = {
        str(track_id or "").lower(): str(path or "")
        for track_id, path in (confirmed_paths or {}).items()
        if str(track_id or "").strip() and str(path or "").strip()
    }
    unresolved = []

    for row in rows or []:
        try:
            track_id = str(row["id"] or "").strip()
        except Exception:
            continue
        if not track_id:
            continue

        track_key = track_id.lower()
        if track_key in result:
            continue

        linked_path = ""
        for key in ("local_wav", "local_mp3"):
            try:
                candidate = str(row[key] or "").strip()
            except Exception:
                candidate = ""
            if candidate:
                linked_path = candidate
                break

        if linked_path:
            result[track_key] = linked_path
        else:
            unresolved.append(row)

    if not unresolved or not table_exists("local_audio_files"):
        return result

    conn = get_connection()
    cur = conn.cursor()
    try:
        ids = [
            str(row["id"] or "").lower()
            for row in unresolved
            if str(row["id"] or "").strip()
        ]
        for start_index in range(0, len(ids), 800):
            id_chunk = ids[start_index:start_index + 800]
            if not id_chunk:
                continue
            placeholders = ",".join(["?"] * len(id_chunk))
            cur.execute(f"""
                SELECT lower(track_id) AS track_id, path, extension, id
                FROM local_audio_files
                WHERE IFNULL(is_stem, 0) = 0
                  AND lower(track_id) IN ({placeholders})
                  AND path IS NOT NULL
                  AND TRIM(path) != ''
                ORDER BY
                  CASE lower(extension)
                    WHEN 'wav' THEN 0
                    WHEN 'flac' THEN 1
                    WHEN 'mp3' THEN 2
                    WHEN 'm4a' THEN 3
                    WHEN 'aac' THEN 4
                    WHEN 'ogg' THEN 5
                    ELSE 9
                  END,
                  id DESC;
            """, id_chunk)
            for item in cur.fetchall():
                track_key = str(item["track_id"] or "").lower()
                path = str(item["path"] or "").strip()
                if track_key and track_key not in result and path:
                    result[track_key] = path

        still_unresolved = [
            row
            for row in unresolved
            if str(row["id"] or "").lower() not in result
        ]
        title_to_rows = {}
        filename_candidates = set()
        extensions = (".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg")
        for row in still_unresolved:
            title = str(row["title"] or "").strip()
            if not title:
                continue
            title_key = normalize_filename_for_match(title)
            title_to_rows.setdefault(title_key, []).append(row)
            for extension in extensions:
                filename_candidates.add(
                    normalize_filename_for_match(title + extension)
                )

        candidate_list = list(filename_candidates)
        for start_index in range(0, len(candidate_list), 800):
            candidate_chunk = candidate_list[start_index:start_index + 800]
            if not candidate_chunk:
                continue
            placeholders = ",".join(["?"] * len(candidate_chunk))
            cur.execute(f"""
                SELECT path, filename, folder, extension
                FROM local_audio_files
                WHERE IFNULL(is_stem, 0) = 0
                  AND path IS NOT NULL
                  AND TRIM(path) != ''
                  AND filename IS NOT NULL
                  AND lower(filename) IN ({placeholders})
                ORDER BY
                  CASE lower(extension)
                    WHEN 'wav' THEN 0
                    WHEN 'flac' THEN 1
                    WHEN 'mp3' THEN 2
                    WHEN 'm4a' THEN 3
                    WHEN 'aac' THEN 4
                    WHEN 'ogg' THEN 5
                    ELSE 9
                  END,
                  id DESC;
            """, candidate_chunk)
            for item in cur.fetchall():
                path = str(item["path"] or "").strip()
                filename = str(item["filename"] or "").strip()
                if not path or not filename:
                    continue
                stem_key = normalize_filename_for_match(Path(filename).stem)
                for row in title_to_rows.get(stem_key, []):
                    track_key = str(row["id"] or "").lower()
                    if track_key and track_key not in result:
                        result[track_key] = path
    finally:
        conn.close()

    return result


def add_stem_folder_to_track(track_id, folder_path):
    track_id = (track_id or "").strip()
    folder_path = urllib.parse.unquote(str(folder_path or "")).strip().strip('"')
    if not track_id:
        return False, "Missing Track ID"
    if not folder_path:
        return False, "Missing stem folder"

    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return False, "Stem folder not found"

    files = [
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in _DATA_AUDIO_EXTENSIONS
    ]
    files.sort(key=lambda p: stem_sort_key({
        "stem_label": detect_stem_label(p),
        "filename": p.name,
    }))
    if not files:
        return False, "No audio stem files found in selected folder"

    variant_folder = folder.parent if folder.name.casefold() == "stems" else folder
    variant_no = None
    try:
        parsed_no = int(variant_folder.name)
        if parsed_no > 0:
            variant_no = parsed_no
    except Exception:
        pass

    conn = get_connection()
    cur = conn.cursor()
    try:
        if cur.execute(
            "SELECT COUNT(*) FROM main.tracks WHERE id = ?;", (track_id,)
        ).fetchone()[0] == 0:
            return False, "Track ID not found"

        matches = cur.execute("""
            SELECT id
              FROM main.track_variants
             WHERE track_id = ?
               AND lower(folder_path) = lower(?)
             ORDER BY id;
        """, (track_id, str(variant_folder))).fetchall()

        if len(matches) == 1:
            variant_id = int(matches[0][0])
        else:
            mains = cur.execute("""
                SELECT tv.id
                  FROM main.track_variants tv
                 WHERE tv.track_id = ?
                   AND EXISTS (
                       SELECT 1 FROM main.media_files mf
                        WHERE mf.variant_id = tv.id AND mf.role = 'main'
                   )
                 ORDER BY tv.id;
            """, (track_id,)).fetchall()
            if len(mains) == 1:
                variant_id = int(mains[0][0])
            else:
                cur.execute("""
                    INSERT INTO main.track_variants(
                        track_id, variant_no, label, folder_path, variant_kind
                    ) VALUES (?, ?, ?, ?, 'stems_only');
                """, (
                    track_id,
                    variant_no,
                    variant_folder.name,
                    str(variant_folder),
                ))
                variant_id = int(cur.lastrowid)

        cur.execute(
            "DELETE FROM main.media_files WHERE variant_id = ? AND role = 'stem';",
            (variant_id,),
        )

        inserted = 0
        for path_obj in files:
            stat = path_obj.stat()
            modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            file_created_at = (
                datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds")
                if os.name == "nt" else None
            )
            chronology_at = file_created_at or modified_at
            chronology_source = "filesystem_created_at" if file_created_at else "modified_time"
            cur.execute("""
                INSERT INTO main.media_files(
                    variant_id, path, role, format, stem_label, size_bytes,
                    modified_at, file_created_at, file_created_at_source,
                    chronology_at
                ) VALUES (?, ?, 'stem', ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    variant_id = excluded.variant_id,
                    role = 'stem',
                    format = excluded.format,
                    stem_label = excluded.stem_label,
                    size_bytes = excluded.size_bytes,
                    modified_at = excluded.modified_at,
                    file_created_at = excluded.file_created_at,
                    file_created_at_source = excluded.file_created_at_source,
                    chronology_at = excluded.chronology_at;
            """, (
                variant_id,
                str(path_obj),
                path_obj.suffix.lower().lstrip("."),
                detect_stem_label(path_obj),
                int(stat.st_size or 0),
                modified_at,
                file_created_at,
                chronology_source,
                chronology_at,
            ))
            inserted += 1

        conn.commit()
        return True, f"Added {inserted} stem audio files from: {folder}"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def ensure_local_inventory_schema():
    conn = get_local_inventory_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_files_raw (
                full_path TEXT PRIMARY KEY COLLATE NOCASE,
                root_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                folder_path TEXT NOT NULL,
                relative_folder TEXT NOT NULL,
                filename TEXT NOT NULL,
                filename_stem TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                modified_time TEXT NOT NULL DEFAULT '',
                created_time TEXT NOT NULL DEFAULT '',
                scan_id TEXT NOT NULL DEFAULT '',
                scan_time TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_local_files_raw_filename ON local_files_raw(filename COLLATE NOCASE);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_local_files_raw_extension ON local_files_raw(extension COLLATE NOCASE);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_local_files_raw_root ON local_files_raw(root_path COLLATE NOCASE);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_scan_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );
        """)
        conn.commit()
    finally:
        conn.close()


def scan_local_inventory():
    """Create a RAW snapshot of every file under the known local audio roots.

    This is a read-only filesystem scan. It does not rename, move, delete, or edit
    any user file, and it does not write to suno_finder_v4.db. The derived snapshot
    is stored separately in suno_local_inventory.db and can always be rebuilt.
    """
    ensure_local_inventory_schema()
    roots = get_local_inventory_roots()
    scan_time = now_iso_local()
    scan_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    rows = []
    errors = []

    for root_text in roots:
        root_path = Path(root_text)

        def on_walk_error(exc):
            errors.append(str(exc))

        for current_folder, dirnames, filenames in os.walk(str(root_path), onerror=on_walk_error):
            # Preserve the exact filesystem names. Sorting is only for stable scan order.
            dirnames.sort(key=lv_sort_key)
            filenames.sort(key=lv_sort_key)
            current_folder_path = Path(current_folder)

            for filename in filenames:
                full_path = current_folder_path / filename
                try:
                    stat = full_path.stat()
                    relative_path = os.path.relpath(str(full_path), str(root_path))
                    relative_folder = os.path.relpath(str(current_folder_path), str(root_path))
                    if relative_folder == ".":
                        relative_folder = ""
                    extension = full_path.suffix
                    rows.append((
                        str(full_path),
                        str(root_path),
                        relative_path,
                        str(current_folder_path),
                        relative_folder,
                        filename,
                        full_path.stem,
                        extension,
                        int(stat.st_size or 0),
                        _local_inventory_iso_from_timestamp(stat.st_mtime),
                        _local_inventory_iso_from_timestamp(stat.st_ctime),
                        scan_id,
                        scan_time,
                    ))
                except Exception as exc:
                    errors.append(f"{full_path}: {exc}")

    conn = get_local_inventory_connection()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute("DELETE FROM local_files_raw;")
        if rows:
            cur.executemany("""
                INSERT INTO local_files_raw (
                    full_path, root_path, relative_path, folder_path, relative_folder,
                    filename, filename_stem, extension, size_bytes,
                    modified_time, created_time, scan_id, scan_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, rows)

        meta = {
            "scan_id": scan_id,
            "scan_time": scan_time,
            "file_count": str(len(rows)),
            "root_count": str(len(roots)),
            "roots_json": json.dumps(roots, ensure_ascii=False),
            "error_count": str(len(errors)),
            "errors_json": json.dumps(errors[:100], ensure_ascii=False),
        }
        for key, value in meta.items():
            cur.execute("INSERT OR REPLACE INTO local_scan_meta (key, value) VALUES (?, ?);", (key, value))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "ok": True,
        "scan_id": scan_id,
        "scan_time": scan_time,
        "roots": roots,
        "root_count": len(roots),
        "file_count": len(rows),
        "error_count": len(errors),
        "errors": errors[:20],
        "db_path": str(LOCAL_INVENTORY_DB_PATH),
    }


def get_track_row_for_meta(track_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM tracks_compat WHERE lower(id)=lower(?);", (str(track_id or "").strip(),))
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def get_meta_candidate_rows(limit=80):
    columns = get_table_columns()
    checks = []
    if "lyrics" in columns:
        checks.append("TRIM(COALESCE(lyrics, '')) = ''")
    if "metadata_prompt" in columns or "prompt" in columns:
        prompt_parts = []
        if "metadata_prompt" in columns:
            prompt_parts.append("metadata_prompt")
        if "prompt" in columns:
            prompt_parts.append("prompt")
        checks.append("TRIM(COALESCE(" + ", ".join(prompt_parts + ["''"]) + ")) = ''")
    if "audio_url" in columns:
        checks.append("TRIM(COALESCE(audio_url, '')) = ''")
    if "created_at" in columns:
        checks.append("TRIM(COALESCE(created_at, '')) = ''")
    if not checks:
        checks.append("1=0")

    where_missing = " OR ".join(["(" + x + ")" for x in checks])
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT id, title, COALESCE(workspaceName, workspace, '') AS workspace
            FROM tracks_compat
            WHERE IFNULL(library_status, 'active') = 'active'
              AND IFNULL(kind, '') != 'Stem'
              AND ({where_missing})
            ORDER BY created_at DESC, title COLLATE NOCASE
            LIMIT ?;
        """, (int(limit),))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _collect_ls_structured_repair_plan():
    columns = set(get_table_columns())
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.*, tu.bpm_text AS ls_ui_bpm_text,
                   tu.model_badge AS ls_ui_model_badge
            FROM tracks_compat t
            LEFT JOIN track_ui tu ON tu.track_id = t.id
            WHERE IFNULL(t.library_status, 'active') = 'active'
            ORDER BY t.created_at DESC, t.title COLLATE NOCASE;
        """)
        rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    structured_updates = []
    prompt_updates = []
    bpm_migrations = []
    ui_updates = []
    field_counts = {field: 0 for field in _DATA_LS_PROVEN_STRUCTURED_FIELDS}
    excluded_stems = 0
    excluded_edits = 0
    invalid_raw_json = 0

    for current in rows:
        if is_ls_stem_metadata_row(current):
            excluded_stems += 1
            continue
        if is_ls_edit_section_row(current):
            excluded_edits += 1
            continue

        raw_json_text = str(current.get("raw_json") or "").strip()
        api_meta = {}
        if raw_json_text:
            try:
                raw_track = json.loads(raw_json_text)
                if not isinstance(raw_track, dict):
                    raise ValueError("raw_json is not an object")
                api_meta = extract_suno_metadata_for_ls(raw_track)
            except Exception:
                invalid_raw_json += 1

        updates = {}
        for field in _DATA_LS_PROVEN_STRUCTURED_FIELDS:
            if field not in columns:
                continue
            value = api_meta.get(field)
            if not metadata_value_present(value):
                continue
            if not metadata_values_equal(current.get(field), value):
                updates[field] = value
                field_counts[field] += 1
        if updates:
            structured_updates.append({
                "id": str(current.get("id") or ""),
                "title": str(current.get("title") or "[No title]"),
                "updates": updates,
            })

        track_id = str(current.get("id") or "").strip()
        if track_id.lower() in _DATA_LS_CONFIRMED_PROMPT_REPAIR_IDS:
            api_prompt = str(api_meta.get("metadata_prompt") or "").strip()
            current_prompt = str(current.get("prompt") or "").strip()
            current_metadata_prompt = str(
                current.get("metadata_prompt") or ""
            ).strip()
            current_lyrics = str(current.get("lyrics") or "").strip()
            if (
                api_prompt
                and current_prompt == "Elizabete Gaile"
                and current_metadata_prompt == "Elizabete Gaile"
                and current_lyrics == api_prompt
            ):
                prompt_updates.append({
                    "id": track_id,
                    "title": str(current.get("title") or "[No title]"),
                    "updates": {
                        "prompt": api_prompt,
                        "metadata_prompt": api_prompt,
                    },
                })

        track_bpm = normalize_ls_bpm_text(current.get("bpm"))
        avg_bpm = normalize_ls_bpm_text(current.get("metadata_avg_bpm"))
        ui_bpm = normalize_ls_bpm_text(current.get("ls_ui_bpm_text"))
        migrated_bpm = ""
        if not track_bpm and not avg_bpm and ui_bpm:
            migrated_bpm = ui_bpm
            bpm_migrations.append({
                "id": str(current.get("id") or ""),
                "title": str(current.get("title") or "[No title]"),
                "bpm": migrated_bpm,
            })

        desired_bpm = track_bpm or avg_bpm or migrated_bpm
        desired_model = str(
            current.get("major_model_version")
            or current.get("model_version")
            or ""
        ).strip()
        ui_patch = {}
        if desired_bpm and desired_bpm != ui_bpm:
            ui_patch["bpm_text"] = desired_bpm
        current_ui_model = str(current.get("ls_ui_model_badge") or "").strip()
        if desired_model and desired_model != current_ui_model:
            ui_patch["model_badge"] = desired_model
        if ui_patch:
            ui_updates.append({
                "id": str(current.get("id") or ""),
                "updates": ui_patch,
            })

    field_counts = {key: value for key, value in field_counts.items() if value}
    example_rows = [
        {
            "id": item["id"],
            "short_id": item["id"][:8],
            "title": item["title"],
            "fields": sorted(item["updates"]),
        }
        for item in structured_updates[:20]
    ]
    return {
        "ok": True,
        "active_total": len(rows),
        "eligible_total": len(rows) - excluded_stems - excluded_edits,
        "excluded_stems": excluded_stems,
        "excluded_edits": excluded_edits,
        "invalid_raw_json": invalid_raw_json,
        "structured_rows": len(structured_updates),
        "structured_field_updates": sum(field_counts.values()),
        "confirmed_prompt_rows": len(prompt_updates),
        "confirmed_prompt_fields": sum(
            len(item["updates"]) for item in prompt_updates
        ),
        "field_counts": field_counts,
        "bpm_migrations": len(bpm_migrations),
        "ui_cache_rows": len(ui_updates),
        "example_rows": example_rows,
        "_structured_updates": structured_updates,
        "_prompt_updates": prompt_updates,
        "_bpm_migrations": bpm_migrations,
        "_ui_updates": ui_updates,
    }


def backup_db_before_structured_repair():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{DB_PATH.stem}_BEFORE_PROVEN_META_REPAIR_{stamp}{DB_PATH.suffix}"
    source = get_connection()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA quick_check;").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError("Structured-repair backup integrity check failed")
    finally:
        destination.close()
        source.close()
    return target


def apply_ls_structured_repair():
    """Legacy repair is obsolete after migration into the canonical schema."""
    return {
        "ok": True,
        "message": (
            "Canonical Local Suno DB already stores normalized structured fields; "
            "legacy track_ui/tracks repair is not applicable."
        ),
        "backup": "",
        "report": "",
        "applied_structured_rows": 0,
        "applied_structured_fields": 0,
        "applied_prompt_rows": 0,
        "applied_prompt_fields": 0,
        "applied_bpm_migrations": 0,
        "applied_ui_cache_rows": 0,
        "field_counts": {},
        "remaining": {},
    }

def _ls_intent_source_signature(conn):
    digest = hashlib.sha256()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.lyrics, t.metadata_prompt, t.prompt, t.metadata_task,
               t.metadata_cover_clip_id, t.metadata_make_instrumental,
               t.metadata_has_vocal, t.raw_make_instrumental, t.raw_has_vocal,
               t.raw_json, t.library_status, t.kind,
               tu.main_category, tu.main_category_review_group,
               tu.main_category_rule, tu.user_tags, tu.visible_in_finder
          FROM tracks_compat t
     LEFT JOIN track_ui tu ON tu.track_id = t.id
      ORDER BY t.id;
    """)
    for db_row in cur.fetchall():
        payload = json.dumps(
            list(db_row), ensure_ascii=False, separators=(",", ":")
        )
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _collect_ls_intent_audit_plan():
    conn = get_connection()
    try:
        check = conn.execute("PRAGMA quick_check;").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError("LS DB quick_check failed before intent audit")
        signature = _ls_intent_source_signature(conn)
        all_tracks = {
            row["id"]: dict(row)
            for row in conn.execute("""
                SELECT t.*,
                       tu.main_category AS ls_main_category,
                       tu.main_category_review_group AS ls_review_group
                  FROM tracks_compat t
             LEFT JOIN track_ui tu ON tu.track_id = t.id;
            """).fetchall()
        }
        active_rows = [
            dict(row)
            for row in conn.execute("""
                SELECT t.*,
                       tu.main_category AS ls_main_category,
                       tu.main_category_review_group AS ls_review_group,
                       tu.main_category_rule AS ls_rule,
                       tu.user_tags AS ls_user_tags
                  FROM tracks_compat t
             LEFT JOIN track_ui tu ON tu.track_id = t.id
                 WHERE IFNULL(t.library_status, 'active') = 'active'
                   AND IFNULL(t.kind, '') != 'Stem'
                   AND (tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)
              ORDER BY t.id;
            """).fetchall()
        ]
    finally:
        conn.close()

    analyzed_at = now_iso_local()
    audit_rows = [
        _ls_intent_analyze_row(row, all_tracks, analyzed_at)
        for row in active_rows
    ]
    intent_counts = {}
    relation_counts = {}
    action_counts = {}
    for item in audit_rows:
        intent_counts[item["intent_label"]] = (
            intent_counts.get(item["intent_label"], 0) + 1
        )
        relation_counts[item["relation_type"]] = (
            relation_counts.get(item["relation_type"], 0) + 1
        )
        action_counts[item["recommended_action"]] = (
            action_counts.get(item["recommended_action"], 0) + 1
        )
    conflicts = [
        item
        for item in audit_rows
        if item["recommended_action"] == "review_category_conflict"
    ]
    conflicts.sort(
        key=lambda item: (-int(item["intent_score"]), item["title"].casefold())
    )
    return {
        "ok": True,
        "engine_version": _DATA_LS_INTENT_AUDIT_ENGINE_VERSION,
        "analyzed_at": analyzed_at,
        "source_signature": signature,
        "active_rows": len(audit_rows),
        "intent_counts": dict(sorted(intent_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "action_counts": dict(sorted(action_counts.items())),
        "vocal_parts_rows": sum(
            item["audio_status"] == "vocal_parts" for item in audit_rows
        ),
        "manual_rows_preserved": sum(
            item["recommended_action"] == "preserve_manual_category"
            for item in audit_rows
        ),
        "proposed_main_category_updates": 0,
        "category_conflicts": len(conflicts),
        "conflict_preview": conflicts[:100],
        "_audit_rows": audit_rows,
    }


def backup_db_before_intent_audit():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = (
        backup_dir
        / f"{DB_PATH.stem}_BEFORE_INTENT_AUDIT_{stamp}{DB_PATH.suffix}"
    )
    source = get_connection()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA quick_check;").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError("Intent-audit backup integrity check failed")
    finally:
        destination.close()
        source.close()
    return target


def apply_ls_intent_audit(expected_signature=""):
    if not LS_INTENT_AUDIT_LOCK.acquire(blocking=False):
        raise RuntimeError("A Song / Instrumental intent audit is already running")
    try:
        job_state = read_suno_metadata_job_state()
        if job_state.get("running"):
            raise RuntimeError(
                "Automatic metadata backfill is still running. "
                "Wait for it to finish before writing the intent audit."
            )

        plan = _collect_ls_intent_audit_plan()
        expected_signature = str(expected_signature or "").strip()
        if expected_signature and expected_signature != plan["source_signature"]:
            raise RuntimeError(
                "LS DB changed after the shown preview. Run Preview again."
            )

        backup_path = backup_db_before_intent_audit()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA busy_timeout = 10000;")
            cur.execute("BEGIN IMMEDIATE;")
            check = cur.execute("PRAGMA quick_check;").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise RuntimeError("Live DB quick_check failed before audit write")
            live_signature = _ls_intent_source_signature(conn)
            if live_signature != plan["source_signature"]:
                raise RuntimeError(
                    "LS DB changed while preparing the audit. "
                    "Nothing was written; run Preview again."
                )

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {_DATA_LS_INTENT_AUDIT_TABLE} (
                    track_id TEXT PRIMARY KEY,
                    engine_version TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL,
                    current_category TEXT NOT NULL DEFAULT '',
                    intent_label TEXT NOT NULL,
                    intent_confidence TEXT NOT NULL,
                    intent_score INTEGER NOT NULL,
                    audio_status TEXT NOT NULL,
                    veto_reason TEXT NOT NULL DEFAULT '',
                    relation_type TEXT NOT NULL,
                    source_ids_json TEXT NOT NULL DEFAULT '[]',
                    source_found_count INTEGER NOT NULL DEFAULT 0,
                    rule_code TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '[]'
                );
            """)
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_ls_intent_label "
                f"ON {_DATA_LS_INTENT_AUDIT_TABLE}(intent_label, intent_confidence);"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_ls_intent_audio_status "
                f"ON {_DATA_LS_INTENT_AUDIT_TABLE}(audio_status);"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_ls_intent_action "
                f"ON {_DATA_LS_INTENT_AUDIT_TABLE}(recommended_action);"
            )
            cur.execute(f"DELETE FROM {_DATA_LS_INTENT_AUDIT_TABLE};")
            cur.executemany(f"""
                INSERT INTO {_DATA_LS_INTENT_AUDIT_TABLE} (
                    track_id, engine_version, analyzed_at, current_category,
                    intent_label, intent_confidence, intent_score, audio_status,
                    veto_reason, relation_type, source_ids_json,
                    source_found_count, rule_code, recommended_action,
                    evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                (
                    item["track_id"], item["engine_version"],
                    item["analyzed_at"], item["current_category"],
                    item["intent_label"], item["intent_confidence"],
                    item["intent_score"], item["audio_status"],
                    item["veto_reason"], item["relation_type"],
                    json.dumps(item["source_ids"], ensure_ascii=False),
                    item["source_found_count"], item["rule_code"],
                    item["recommended_action"],
                    json.dumps(item["evidence"], ensure_ascii=False),
                )
                for item in plan["_audit_rows"]
            ])
            check = cur.execute("PRAGMA quick_check;").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise RuntimeError("DB integrity check failed; audit was rolled back")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        backup_dir = backup_path.parent
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        report_path = backup_dir / f"LS_INTENT_AUDIT_{stamp}.json"
        report_payload = {
            key: value for key, value in plan.items() if not key.startswith("_")
        }
        report_payload.update({
            "app_version": APP_VERSION,
            "backup": str(backup_path),
            "audit_rows_written": len(plan["_audit_rows"]),
        })
        report_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "ok": True,
            "message": "Song / Instrumental intent audit layer written.",
            "backup": str(backup_path),
            "report": str(report_path),
            "audit_rows_written": len(plan["_audit_rows"]),
            "proposed_main_category_updates": 0,
            "summary": {
                key: value
                for key, value in plan.items()
                if not key.startswith("_") and key != "conflict_preview"
            },
        }
    finally:
        LS_INTENT_AUDIT_LOCK.release()


def _ls_category_assignment_source_signature(conn):
    """Sign every value used by the category-assignment preview."""
    digest = hashlib.sha256()
    digest.update(_ls_intent_source_signature(conn).encode("ascii"))
    if not conn.execute("""
        SELECT 1 FROM sqlite_master
         WHERE type = 'table' AND name = ? LIMIT 1;
    """, (_DATA_LS_INTENT_AUDIT_TABLE,)).fetchone():
        return ""
    for row in conn.execute(f"""
        SELECT track_id, current_category, intent_label, intent_score,
               audio_status, recommended_action, rule_code
          FROM {_DATA_LS_INTENT_AUDIT_TABLE}
      ORDER BY track_id;
    """).fetchall():
        digest.update(json.dumps(
            list(row), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _collect_ls_category_assignment_plan(conn=None):
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()
    try:
        check = conn.execute("PRAGMA quick_check;").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError("LS DB quick_check failed before category preview")
        signature = _ls_category_assignment_source_signature(conn)
        if not signature:
            raise RuntimeError(
                "Intent audit layer is missing. Write the intent audit first."
            )

        rows = conn.execute(f"""
            SELECT t.id AS track_id,
                   COALESCE(NULLIF(TRIM(t.title), ''), '[No title]') AS title,
                   TRIM(COALESCE(tu.main_category, '')) AS current_category,
                   COALESCE(tu.main_category_review_group, '') AS review_group,
                   sia.intent_label, sia.intent_score, sia.audio_status,
                   sia.rule_code, sia.recommended_action
              FROM tracks_compat t
              JOIN {_DATA_LS_INTENT_AUDIT_TABLE} sia
                ON lower(sia.track_id) = lower(t.id)
         LEFT JOIN track_ui tu ON tu.track_id = t.id
             WHERE IFNULL(t.library_status, 'active') = 'active'
               AND IFNULL(t.kind, '') != 'Stem'
               AND (tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)
               AND COALESCE(tu.main_category_review_group, '') != 'manual_toggle'
               AND sia.intent_label IN ('Song', 'Instrumental')
               AND sia.intent_label != TRIM(COALESCE(tu.main_category, ''))
          ORDER BY sia.intent_score DESC, lower(t.title), t.id;
        """).fetchall()

        updates = []
        for row in rows:
            score = max(0, min(100, int(row["intent_score"] or 0)))
            proposed = (
                str(row["intent_label"])
                if score >= _DATA_LS_CATEGORY_ASSIGNMENT_SCORE
                else "SongOrInstrumental"
            )
            updates.append({
                "track_id": str(row["track_id"] or ""),
                "title": str(row["title"] or "[No title]"),
                "current_category": str(row["current_category"] or ""),
                "intent_label": str(row["intent_label"] or ""),
                "intent_score": score,
                "proposed_category": proposed,
                "rule_code": str(row["rule_code"] or ""),
            })

        definite = [
            item for item in updates
            if item["proposed_category"] in {"Song", "Instrumental"}
        ]
        uncertain = [
            item for item in updates
            if item["proposed_category"] == "SongOrInstrumental"
        ]
        to_song = sum(item["proposed_category"] == "Song" for item in definite)
        to_instrumental = sum(
            item["proposed_category"] == "Instrumental" for item in definite
        )
        manual_preserved = conn.execute("""
            SELECT COUNT(*) FROM track_ui
             WHERE main_category_review_group = 'manual_toggle';
        """).fetchone()[0]
        vocal_parts_preserved = conn.execute(f"""
            SELECT COUNT(*) FROM {_DATA_LS_INTENT_AUDIT_TABLE}
             WHERE audio_status = 'vocal_parts';
        """).fetchone()[0]
        return {
            "ok": True,
            "source_signature": signature,
            "score_threshold": _DATA_LS_CATEGORY_ASSIGNMENT_SCORE,
            "candidate_rows": len(updates),
            "definite_updates": len(definite),
            "to_song": to_song,
            "to_instrumental": to_instrumental,
            "uncertain_updates": len(uncertain),
            "manual_rows_preserved": int(manual_preserved or 0),
            "vocal_parts_rows_preserved": int(vocal_parts_preserved or 0),
            "preview": updates[:100],
            "_updates": updates,
        }
    finally:
        if owns_connection:
            conn.close()


def backup_db_before_category_assignment():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = (
        backup_dir
        / f"{DB_PATH.stem}_BEFORE_CATEGORY_ASSIGNMENT_{stamp}{DB_PATH.suffix}"
    )
    source = get_connection()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA quick_check;").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError("Category-assignment backup integrity check failed")
    finally:
        destination.close()
        source.close()
    return target


def apply_ls_category_assignment(expected_signature=""):
    """Canonical DB persists only manual category overrides.

    Automatic category intent remains derived/recomputed data and is deliberately
    not written back into track_user.
    """
    return {
        "ok": True,
        "message": (
            "Canonical Local Suno DB keeps automatic Song/Instrumental intent "
            "derived; only manual overrides are persisted."
        ),
        "backup": "",
        "report": "",
        "applied_rows": 0,
        "to_song": 0,
        "to_instrumental": 0,
        "to_uncertain": 0,
    }

def backup_db_before_metadata_import():
    backup_dir = BASE_DIR / "Backup"
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"{DB_PATH.stem}_BEFORE_SUNO_META_REFRESH_{stamp}{DB_PATH.suffix}"
    # The live LS database uses WAL mode. SQLite's backup API includes committed
    # WAL pages and therefore creates a consistent snapshot; copying only the
    # main .db file could silently omit recent changes.
    source = get_connection()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        check = destination.execute("PRAGMA quick_check;").fetchone()
        if not check or str(check[0]).lower() != "ok":
            raise RuntimeError("Metadata backup integrity check failed")
    finally:
        destination.close()
        source.close()
    return target


def insert_suno_tracks_metadata_only(track_items):
    """Insert normalized Suno payloads into the canonical Local Suno schema."""
    if not track_items:
        return {"ok": False, "error": "No Suno tracks to import"}

    backup_path = backup_db_before_metadata_import()
    selected_ids = []
    selected_seen = set()
    for item in track_items:
        if not isinstance(item, dict):
            continue
        raw_track = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        selected_id = str(
            meta.get("id") or raw_track.get("id") or raw_track.get("clip_id") or ""
        ).strip()
        key = selected_id.lower()
        if selected_id and key not in selected_seen:
            selected_ids.append(selected_id)
            selected_seen.add(key)

    def number(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def bool_value(value, default=0):
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            return 1 if value else 0
        return 1 if str(value).strip().lower() in {"1", "true", "yes", "like", "liked"} else 0

    conn = get_connection()
    rows = []
    inserted = skipped_existing = skipped_stem = errors = 0
    inserted_ids = []
    try:
        cur = conn.cursor()
        for item in track_items:
            if not isinstance(item, dict):
                continue
            raw_track = item.get("raw") if isinstance(item.get("raw"), dict) else {}
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            md = raw_track.get("metadata") if isinstance(raw_track.get("metadata"), dict) else {}

            if bool(item.get("is_stem")):
                skipped_stem += 1
                continue

            tid = str(meta.get("id") or raw_track.get("id") or raw_track.get("clip_id") or "").strip()
            title = str(meta.get("title") or raw_track.get("title") or "(untitled)")
            if not tid:
                errors += 1
                rows.append({"track_id": "", "short_id": "", "title": title, "status": "ERROR", "error": "Missing Suno ID"})
                continue

            if cur.execute(
                "SELECT COUNT(*) FROM main.tracks WHERE lower(id)=lower(?)", (tid,)
            ).fetchone()[0] > 0:
                skipped_existing += 1
                rows.append({"track_id": tid, "short_id": tid[:8], "title": title, "status": "SKIPPED_EXISTS", "error": ""})
                continue

            lyrics = str(meta.get("lyrics") or raw_track.get("lyrics") or "")
            source_type = (
                meta.get("metadata_type") or raw_track.get("type") or md.get("type") or ""
            )
            source_task = (
                meta.get("metadata_task") or raw_track.get("task") or md.get("task") or ""
            )
            style_tags = (
                meta.get("metadata_tags") or meta.get("style") or md.get("tags") or ""
            )
            duration_seconds = number(
                meta.get("metadata_duration") or raw_track.get("duration") or md.get("duration")
            )
            kind = str(meta.get("kind") or "").strip()
            if not kind:
                title_lower = title.lower()
                lyrics_lower = lyrics.lower()
                kind = "Instrumental" if (
                    "instrumental" in lyrics_lower or "(instrumental" in title_lower
                ) else "Song"

            is_liked = bool_value(
                meta.get("is_liked")
                if meta.get("is_liked") is not None
                else raw_track.get("is_liked"),
                0,
            )

            cur.execute("""
                INSERT INTO main.tracks(
                    id, title, created_at, workspace_id, workspace_name, project_id,
                    audio_url, image_url, image_large_url, model_name,
                    major_model_version, source_type, source_task, style_tags,
                    negative_tags, prompt, duration_seconds, has_stem, has_vocal,
                    make_instrumental, is_remix, studio_project_id,
                    studio_project_version_id, edited_clip_id, cover_clip_id,
                    avg_bpm, min_bpm, max_bpm, is_liked, explicit, display_tags,
                    kind, caption, lyrics, library_status, updated_at
                ) VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                );
            """, (
                tid,
                title,
                meta.get("created_at") or raw_track.get("created_at") or None,
                meta.get("workspaceId") or meta.get("workspace_id") or None,
                meta.get("workspaceName") or meta.get("workspace_name") or None,
                meta.get("project_id") or raw_track.get("project_id") or None,
                meta.get("audio_url") or raw_track.get("audio_url") or None,
                meta.get("image_url") or raw_track.get("image_url") or None,
                meta.get("image_large_url") or raw_track.get("image_large_url") or None,
                meta.get("model_name") or None,
                meta.get("major_model_version") or meta.get("model_version") or None,
                source_type or None,
                source_task or None,
                style_tags or None,
                meta.get("metadata_negative_tags") or md.get("negative_tags") or None,
                meta.get("prompt") or meta.get("metadata_prompt") or md.get("prompt") or None,
                duration_seconds,
                bool_value(meta.get("metadata_has_stem") if meta.get("metadata_has_stem") is not None else md.get("has_stem"), 0),
                bool_value(meta.get("metadata_has_vocal") if meta.get("metadata_has_vocal") is not None else md.get("has_vocal"), 0),
                bool_value(meta.get("metadata_make_instrumental") if meta.get("metadata_make_instrumental") is not None else md.get("make_instrumental"), 0),
                bool_value(meta.get("metadata_is_remix") if meta.get("metadata_is_remix") is not None else md.get("is_remix"), 0),
                meta.get("metadata_studio_project_id") or None,
                meta.get("metadata_studio_project_version_id") or None,
                meta.get("metadata_edited_clip_id") or None,
                meta.get("metadata_cover_clip_id") or None,
                number(meta.get("metadata_avg_bpm") or meta.get("bpm")),
                number(meta.get("metadata_min_bpm")),
                number(meta.get("metadata_max_bpm")),
                is_liked,
                bool_value(meta.get("explicit") if meta.get("explicit") is not None else raw_track.get("explicit"), 0),
                meta.get("display_tags") or style_tags or None,
                kind,
                meta.get("caption") or raw_track.get("caption") or None,
                lyrics,
                "active",
                now_iso_local(),
            ))

            raw_json = meta.get("raw_json")
            if isinstance(raw_json, (dict, list)):
                raw_json = json.dumps(raw_json, ensure_ascii=False)
            if not raw_json:
                raw_json = json.dumps(raw_track, ensure_ascii=False)
            cur.execute("""
                INSERT INTO main.suno_source_payload(track_id, raw_json, captured_at)
                VALUES (?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    raw_json = excluded.raw_json,
                    captured_at = excluded.captured_at;
            """, (tid, str(raw_json), now_iso_local()))

            inserted += 1
            inserted_ids.append(tid)
            rows.append({"track_id": tid, "short_id": tid[:8], "title": title, "status": "INSERTED", "error": ""})

        conn.commit()
        if inserted_ids:
            set_last_imported_suno_ids(inserted_ids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"suno_tracklist_import_{stamp}.md"
    lines = [
        "# Suno Tracklist Import", "", f"- Backup: `{backup_path}`",
        f"- Inserted: **{inserted}**", f"- Skipped existing: **{skipped_existing}**",
        f"- Skipped stems: **{skipped_stem}**", f"- Errors: **{errors}**", "",
        "| ID | Title | Status | Error |", "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row.get('short_id','')}` | {row.get('title','')} | "
            f"{row.get('status','')} | {row.get('error','')} |"
        )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "ok": True,
        "backup": str(backup_path),
        "report": str(report_path),
        "inserted": inserted,
        "selected_ids": selected_ids,
        "selected_url": "/?" + urllib.parse.urlencode({
            "track_ids": ",".join(selected_ids),
            "rows": "all",
            "selected_from_suno": "1",
        }) if selected_ids else "",
        "last_imported_ids": inserted_ids,
        "last_imported_url": "/?kind_filter=__last_imported__&rows=all&last_imported=1" if inserted_ids else "",
        "skipped_existing": skipped_existing,
        "skipped_stem": skipped_stem,
        "errors": errors,
        "rows": rows,
    }

def build_suno_update_preview(limit=300):
    """Read-only metadata audit used by Downloader Update.

    Known Stem and Edit/Section rows are excluded. Rows with stored raw_json are
    inspected locally, so missing fields can be repaired without an API call and
    proven non-empty differences can be reported without overwriting them.
    """
    columns = set(get_table_columns())

    def missing_labels(row):
        labels = []
        if is_db_value_empty(row.get("title")):
            labels.append("title")
        if is_db_value_empty(row.get("lyrics")):
            labels.append("lyrics")
        if is_db_value_empty(row.get("metadata_prompt")):
            labels.append("metadata_prompt")
        if is_db_value_empty(row.get("prompt")):
            labels.append("prompt")
        if is_db_value_empty(row.get("metadata_tags")):
            labels.append("metadata_tags")
        if is_db_value_empty(row.get("style")):
            labels.append("style")
        if not metadata_value_present(row.get("image_url")) and not metadata_value_present(row.get("raw_image_url")):
            labels.append("image")
        if is_db_value_empty(row.get("model_name")):
            labels.append("model_name")
        if is_db_value_empty(row.get("major_model_version")):
            labels.append("model_version")
        if is_db_value_empty(row.get("metadata_type")):
            labels.append("metadata_type")
        if is_db_value_empty(row.get("metadata_task")):
            labels.append("metadata_task")
        if is_db_value_empty(row.get("bpm")) and row.get("metadata_avg_bpm") is None:
            labels.append("bpm")
        if is_db_value_empty(row.get("raw_json")):
            labels.append("raw_json")
        return labels

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT *
            FROM tracks_compat
            WHERE IFNULL(library_status, 'active') = 'active'
            ORDER BY created_at DESC, title COLLATE NOCASE;
        """)
        active_rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    total_active = len(active_rows)
    excluded_stems = 0
    excluded_edits = 0
    api_needed = 0
    stored_fillable = 0
    conflict_rows = 0
    invalid_raw_json = 0
    field_counts = {}
    candidates = []

    for current in active_rows:
        if is_ls_stem_metadata_row(current):
            excluded_stems += 1
            continue
        if is_ls_edit_section_row(current):
            excluded_edits += 1
            continue

        missing = missing_labels(current)
        raw_json_text = str(current.get("raw_json") or "").strip()
        source = "Suno API"
        fillable = []
        conflicts = []

        if raw_json_text:
            try:
                raw_track = json.loads(raw_json_text)
                if not isinstance(raw_track, dict):
                    raise ValueError("raw_json is not an object")
                stored_meta = extract_suno_metadata_for_ls(raw_track)
                pending, conflicts = collect_suno_metadata_changes(
                    current,
                    columns,
                    stored_meta,
                    overwrite=False,
                )
                fillable = sorted(column for column in pending if column != "raw_json")
                source = "Stored Suno data"
                if conflicts:
                    conflict_rows += 1
                # Conflict-only rows are informational. They must never return
                # to the actionable queue after their empty fields were filled.
                if not fillable:
                    continue
                stored_fillable += 1
            except Exception:
                invalid_raw_json += 1
                source = "Suno API"
                if "raw_json" not in missing:
                    missing.append("invalid raw_json")
                api_needed += 1
        else:
            api_needed += 1

        for label in missing:
            field_counts[label] = field_counts.get(label, 0) + 1

        candidates.append({
            "id": current.get("id") or "",
            "short_id": str(current.get("id") or "")[:8],
            "title": current.get("title") or "[No title]",
            "workspace": current.get("workspaceName") or current.get("workspace") or "",
            "created_at": current.get("created_at") or "",
            "missing": missing,
            "fillable": fillable,
            "conflicts": conflicts,
            "source": source,
        })

    # Stored-data repairs and proven conflicts are shown first because they need
    # no network request. API candidates keep newest-first DB order.
    candidates.sort(key=lambda item: (0 if item["source"] == "Stored Suno data" else 1))
    shown_rows = candidates[:max(1, int(limit))]

    return {
        "ok": True,
        "total_active": total_active,
        "eligible_total": total_active - excluded_stems - excluded_edits,
        "excluded_stems": excluded_stems,
        "excluded_edits": excluded_edits,
        "missing_total": len(candidates),
        "api_needed": api_needed,
        "stored_fillable": stored_fillable,
        "conflict_rows": conflict_rows,
        "invalid_raw_json": invalid_raw_json,
        "field_counts": dict(sorted(field_counts.items())),
        "rows": shown_rows,
        "shown": len(shown_rows),
        "limit": int(limit),
    }


def build_suno_update_preview_fallback(limit=300, error=""):
    """Safe fallback for Downloader Update preview.

    This path deliberately avoids parsing stored raw_json and avoids optional
    column assumptions. It keeps the Update button useful even when the full
    metadata audit hits one malformed row or an older DB schema variant.
    """
    columns = set(get_table_columns())

    def col_expr(name, fallback="''"):
        return name if name in columns else f"{fallback} AS {name}"

    where_parts = []
    if "library_status" in columns:
        where_parts.append("IFNULL(library_status, 'active') = 'active'")
    if "kind" in columns:
        where_parts.append("IFNULL(kind, '') != 'Stem'")

    checks = []
    if "title" in columns:
        checks.append("TRIM(COALESCE(title, '')) = ''")
    if "lyrics" in columns:
        checks.append("TRIM(COALESCE(lyrics, '')) = ''")
    prompt_candidates = [col for col in ("metadata_prompt", "prompt") if col in columns]
    if prompt_candidates:
        checks.append("TRIM(COALESCE(" + ", ".join(prompt_candidates + ["''"]) + ")) = ''")
    style_candidates = [col for col in ("metadata_tags", "style", "display_tags") if col in columns]
    if style_candidates:
        checks.append("TRIM(COALESCE(" + ", ".join(style_candidates + ["''"]) + ")) = ''")
    for column_name in (
        "audio_url",
        "created_at",
        "image_url",
        "model_name",
        "major_model_version",
        "metadata_type",
        "metadata_task",
        "raw_json",
    ):
        if column_name in columns:
            checks.append(f"TRIM(COALESCE({column_name}, '')) = ''")

    if not checks:
        checks.append("1 = 0")
    where_parts.append("(" + " OR ".join(checks) + ")")
    where_sql = "WHERE " + " AND ".join(where_parts) if where_parts else ""
    order_sql = "created_at DESC, title COLLATE NOCASE" if "created_at" in columns else "title COLLATE NOCASE"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT
                {col_expr('id')},
                {col_expr('title')},
                {col_expr('workspace')},
                {col_expr('workspaceName')},
                {col_expr('created_at')}
            FROM tracks_compat
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ?;
        """, (max(1, int(limit)),))
        rows = [dict(row) for row in cur.fetchall()]

        count_where = []
        if "library_status" in columns:
            count_where.append("IFNULL(library_status, 'active') = 'active'")
        if "kind" in columns:
            count_where.append("IFNULL(kind, '') != 'Stem'")
        count_sql = "WHERE " + " AND ".join(count_where) if count_where else ""
        cur.execute(f"SELECT COUNT(*) FROM tracks_compat {count_sql};")
        eligible_total = int(cur.fetchone()[0] or 0)
    finally:
        conn.close()

    shown_rows = []
    for row in rows:
        track_id = str(row.get("id") or "")
        shown_rows.append({
            "id": track_id,
            "short_id": track_id[:8],
            "title": row.get("title") or "[No title]",
            "workspace": row.get("workspaceName") or row.get("workspace") or "",
            "created_at": row.get("created_at") or "",
            "missing": ["metadata"],
            "fillable": [],
            "conflicts": [],
            "source": "Suno API",
        })

    return {
        "ok": True,
        "fallback": True,
        "fallback_error": shorten_text(str(error or "Full metadata audit failed"), 900),
        "total_active": eligible_total,
        "eligible_total": eligible_total,
        "excluded_stems": 0,
        "excluded_edits": 0,
        "missing_total": len(shown_rows),
        "api_needed": len(shown_rows),
        "stored_fillable": 0,
        "conflict_rows": 0,
        "invalid_raw_json": 0,
        "field_counts": {"metadata": len(shown_rows)} if shown_rows else {},
        "rows": shown_rows,
        "shown": len(shown_rows),
        "limit": int(limit),
    }


def apply_suno_metadata_to_db(track_id, api_meta, overwrite=False):
    """Update one canonical track from already fetched Suno API metadata."""
    track_id = str(track_id or "").strip()
    if not track_id:
        return {"updated_fields": [], "conflicts": [], "found": False}

    canonical_specs = [
        ("title", api_meta.get("title"), True),
        ("audio_url", api_meta.get("audio_url"), False),
        ("created_at", api_meta.get("created_at"), True),
        ("lyrics", api_meta.get("lyrics"), True),
        ("prompt", api_meta.get("metadata_prompt") or api_meta.get("prompt"), True),
        ("style_tags", api_meta.get("metadata_tags") or api_meta.get("style"), True),
        ("negative_tags", api_meta.get("metadata_negative_tags"), True),
        ("display_tags", api_meta.get("display_tags"), False),
        ("caption", api_meta.get("caption"), True),
        ("image_url", api_meta.get("image_url") or api_meta.get("raw_image_url"), False),
        ("image_large_url", api_meta.get("image_large_url") or api_meta.get("raw_image_large_url"), False),
        ("workspace_name", api_meta.get("workspaceName") or api_meta.get("workspace_name"), False),
        ("workspace_id", api_meta.get("workspaceId") or api_meta.get("workspace_id"), False),
        ("model_name", api_meta.get("model_name"), True),
        ("major_model_version", api_meta.get("major_model_version") or api_meta.get("model_version"), True),
        ("source_type", api_meta.get("metadata_type") or api_meta.get("raw_type"), True),
        ("source_task", api_meta.get("metadata_task") or api_meta.get("raw_task"), True),
        ("duration_seconds", api_meta.get("metadata_duration"), True),
        ("has_stem", api_meta.get("metadata_has_stem"), True),
        ("has_vocal", api_meta.get("metadata_has_vocal"), True),
        ("make_instrumental", api_meta.get("metadata_make_instrumental"), True),
        ("is_remix", api_meta.get("metadata_is_remix"), True),
        ("studio_project_id", api_meta.get("metadata_studio_project_id"), True),
        ("studio_project_version_id", api_meta.get("metadata_studio_project_version_id"), True),
        ("edited_clip_id", api_meta.get("metadata_edited_clip_id"), True),
        ("cover_clip_id", api_meta.get("metadata_cover_clip_id"), True),
        ("avg_bpm", api_meta.get("metadata_avg_bpm") or api_meta.get("bpm"), True),
        ("min_bpm", api_meta.get("metadata_min_bpm"), True),
        ("max_bpm", api_meta.get("metadata_max_bpm"), True),
        ("is_liked", api_meta.get("is_liked"), False),
        ("explicit", api_meta.get("explicit"), False),
    ]

    conn = get_connection()
    cur = conn.cursor()
    try:
        row = cur.execute(
            "SELECT * FROM main.tracks WHERE lower(id)=lower(?);", (track_id,)
        ).fetchone()
        if not row:
            return {"updated_fields": [], "conflicts": [], "found": False}

        current = dict(row)
        updates = {}
        conflicts = []
        for column, value, report_conflict in canonical_specs:
            if not metadata_value_present(value):
                continue
            current_value = current.get(column)
            if overwrite or is_db_value_empty(current_value):
                updates[column] = value
            elif report_conflict and not metadata_values_equal(current_value, value):
                conflicts.append(column)

        if updates:
            updates["updated_at"] = now_iso_local()
            sql = (
                "UPDATE main.tracks SET "
                + ", ".join([f'"{col}" = ?' for col in updates])
                + " WHERE lower(id)=lower(?)"
            )
            cur.execute(sql, list(updates.values()) + [track_id])

        raw_json = api_meta.get("raw_json")
        if raw_json:
            if isinstance(raw_json, (dict, list)):
                raw_json = json.dumps(raw_json, ensure_ascii=False)
            cur.execute("""
                INSERT INTO main.suno_source_payload(track_id, raw_json, captured_at)
                VALUES (?, ?, ?)
                ON CONFLICT(track_id) DO UPDATE SET
                    raw_json = excluded.raw_json,
                    captured_at = excluded.captured_at;
            """, (track_id, str(raw_json), now_iso_local()))

        conn.commit()
        return {
            "updated_fields": [key for key in updates if key != "updated_at"],
            "conflicts": sorted(set(conflicts)),
            "found": True,
        }
    finally:
        conn.close()

def get_track_download_info(track_id):
    track_id = str(track_id or "").strip()
    if not track_id:
        return {}

    ui_columns = get_track_ui_columns()
    category_parts = []
    if "main_category" in ui_columns:
        category_parts.append("NULLIF(TRIM(tu.main_category), '')")
    if "ui_type" in ui_columns:
        category_parts.append("NULLIF(TRIM(tu.ui_type), '')")
    category_parts.append("NULLIF(TRIM(t.kind), '')")
    category_sql = "COALESCE(" + ", ".join(category_parts + ["''"]) + ")"

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT
                t.id,
                t.title,
                t.audio_url,
                t.local_wav,
                t.local_mp3,
                t.lyrics,
                {category_sql} AS download_category
            FROM tracks_compat t
            LEFT JOIN track_ui tu ON tu.track_id = t.id
            WHERE lower(t.id) = lower(?)
            LIMIT 1;
        """, (track_id,))
        row = cur.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def choose_folder_dialog(initial_dir="", title="Select folder"):
    initial_dir = str(initial_dir or "").strip()
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if not initial_dir or not Path(initial_dir).exists():
            initial_dir = str(BASE_DIR)
        selected = filedialog.askdirectory(parent=root, initialdir=initial_dir, title=title)
        root.destroy()
        return selected or ""
    except Exception:
        return ""


def get_local_inventory_connection():
    conn = sqlite3.connect(LOCAL_INVENTORY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def copy_sqlite_snapshot(source_path, target_path):
    source_path = Path(source_path)
    target_path = Path(target_path)
    if not source_path.is_file():
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source_path.resolve().as_uri() + "?mode=ro"
    source_conn = sqlite3.connect(source_uri, uri=True)
    target_conn = sqlite3.connect(target_path)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()
    return True


def normalize_multi_filter_values(value):
    """Normalize repeated URL values while preserving punctuation in names."""
    raw_values = value if isinstance(value, (list, tuple, set)) else [value]
    result = []
    seen = set()
    for item in raw_values:
        text = str(item or "").strip()
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result

def normalize_family_group_mode(value):
    text = str(value or "").strip().lower()
    return "family_and" if text == "family_and" else "or"

def append_main_category_filter(where_parts, params, category_filter, ui_columns=None):
    selected_categories = normalize_multi_filter_values(category_filter)
    if not selected_categories:
        return

    ui_columns = ui_columns if ui_columns is not None else get_track_ui_columns()
    category_sql = get_main_category_filter_sql(ui_columns)
    conditions = []
    condition_params = []

    for category in selected_categories:
        if category in ("Song", "Instrumental", "SongOrInstrumental"):
            conditions.append(f"{category_sql} = ?")
            condition_params.append(category)
        elif category == "__unclassified__":
            conditions.append(
                f"{category_sql} NOT IN "
                "('Song', 'Instrumental', 'SongOrInstrumental')"
            )
        elif category == "__instrumental_review__":
            if "main_category_review_group" in ui_columns:
                conditions.append(
                    f"({category_sql} = 'Instrumental' AND "
                    "COALESCE(tu.main_category_review_group, '') != 'manual_toggle')"
                )
            else:
                conditions.append(f"{category_sql} = 'Instrumental'")

    if conditions:
        where_parts.append("(" + " OR ".join(conditions) + ")")
        params.extend(condition_params)

def normalize_limit(limit_value):
    limit_value = (limit_value or "300").strip().lower()

    if limit_value == "all":
        return None

    try:
        number = int(limit_value)
    except ValueError:
        return 300

    if number <= 0:
        return 300

    return number

def normalize_sort_by(value):
    value = str(value or "").strip().lower()
    return value if value in {"title", "created", "duration"} else ""

def normalize_sort_dir(value):
    value = str(value or "").strip().lower()
    return "desc" if value == "desc" else "asc"

def get_track_order_sql(sort_by="", sort_dir="asc"):
    sort_by = normalize_sort_by(sort_by)
    sort_dir = normalize_sort_dir(sort_dir)
    direction = "DESC" if sort_dir == "desc" else "ASC"

    if sort_by == "title":
        return (
            f"ls_sort_text(COALESCE(t.title, '')) {direction}, "
            "t.created_at DESC, lower(t.id) ASC"
        )

    if sort_by == "created":
        return (
            f"COALESCE(t.created_at, '') {direction}, "
            "ls_sort_text(COALESCE(t.title, '')) ASC, lower(t.id) ASC"
        )

    if sort_by == "duration":
        duration_sql = (
            "COALESCE("
            "tu.duration_seconds, "
            "t.metadata_duration, "
            "ls_duration_seconds(t.duration), "
            "0"
            ")"
        )
        return (
            f"{duration_sql} {direction}, "
            "ls_sort_text(COALESCE(t.title, '')) ASC, lower(t.id) ASC"
        )

    return (
        "ls_sort_text(COALESCE(t.workspaceName, t.workspace, '')) ASC, "
        "ls_sort_text(COALESCE(t.title, '')) ASC, "
        "COALESCE(t.created_at, '') DESC, lower(t.id) ASC"
    )

def normalize_display_count(value):
    value = (value or "300").strip().lower()

    if value == "all":
        return "all"

    try:
        number = int(value)
    except ValueError:
        return "300"

    if number <= 0:
        return "300"

    return str(number)

def split_search_tokens(value):
    """Everything-style search tokens.

    Separators such as spaces, underscores, hyphens, dots, slashes and brackets
    are treated alike. Example: "refresh db.py" -> refresh + db + py.
    All tokens must match somewhere in the row.
    """
    text = str(value or "").strip().lower()
    if not text:
        return []

    tokens = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    result = []
    seen = set()
    for token in tokens:
        token = token.strip().lower()
        if token and token not in seen:
            result.append(token)
            seen.add(token)
    return result

def append_token_search(where_parts, params, searchable_exprs, tokens):
    """Append SQL where parts for token search.

    Each token must be found, but it may be found in any searchable field.
    This keeps Search broad while still narrowing results when several words
    are typed.
    """
    for token in tokens:
        where_parts.append("(" + " OR ".join([f"{expr} LIKE ?" for expr in searchable_exprs]) + ")")
        params.extend([f"%{token}%"] * len(searchable_exprs))

def append_mark_tag_presence_filters(
    where_parts,
    search_marks=False,
    search_tags=False,
    ui_columns=None,
):
    """Apply ✶ and #tag as independent presence filters.

    ✶ checked    -> the row must have at least one active user mark.
    #tag checked -> the row must have at least one assigned user tag.
    Both checked -> both requirements must be true (AND).

    These filters apply with both empty and non-empty Ctrl+F text.
    """
    search_marks = normalize_search_scope_flag(search_marks, False)
    search_tags = normalize_search_scope_flag(search_tags, False)
    ui_columns = set(ui_columns or [])

    missing_requested_field = False

    if search_marks:
        if "user_marks" in ui_columns:
            where_parts.append("IFNULL(tu.user_marks, 0) != 0")
        else:
            missing_requested_field = True

    if search_tags:
        if "user_tags" in ui_columns:
            where_parts.append("TRIM(COALESCE(tu.user_tags, '')) != ''")
        else:
            missing_requested_field = True

    if missing_requested_field:
        # A requested filter field does not exist in this DB.
        where_parts.append("1 = 0")

def normalize_flag_filter(value):
    """Return the unique valid independent LS flag masks from a URL value."""
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = re.split(r"[,;\s]+", str(value or ""))

    result = []
    for part in raw_parts:
        try:
            mask = int(part)
        except (TypeError, ValueError):
            continue
        if mask in (1, 2, 4, 8, 16) and mask not in result:
            result.append(mask)
    return result

def normalize_tag_filter(value):
    """Return unique canonical #tags selected by the read-only library filter."""
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = re.split(r"[,;\s]+", str(value or ""))

    result = []
    seen = set()
    for part in raw_parts:
        tag = _normalize_single_user_tag(part)
        key = tag.lower()
        if tag and key not in seen:
            result.append(tag)
            seen.add(key)
    return result

def append_specific_user_review_filters(
    where_parts,
    params,
    flag_filter="",
    tag_filter="",
    ui_columns=None,
):
    """Apply exact Flags and Tags selections without writing to the DB.

    Multiple flags and tags use AND semantics: every selected condition must
    be present on a matching track.
    """
    ui_columns = set(ui_columns or [])
    selected_flags = normalize_flag_filter(flag_filter)
    selected_tags = normalize_tag_filter(tag_filter)

    if selected_flags:
        if "user_marks" not in ui_columns:
            where_parts.append("1 = 0")
        else:
            required_mask = 0
            for mask in selected_flags:
                required_mask |= mask
            where_parts.append("(IFNULL(tu.user_marks, 0) & ?) = ?")
            params.extend([required_mask, required_mask])

    if selected_tags:
        if "user_tags" not in ui_columns:
            where_parts.append("1 = 0")
        else:
            # LS stores tags as a normalized comma-separated list.  Padding
            # the normalized value with commas keeps matching exact and avoids
            # confusing #rock with #rockabilly.
            normalized_tags_sql = (
                "(',' || REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
                "lower(COALESCE(tu.user_tags, '')), ';', ','), ' ', ','), "
                "CHAR(9), ','), CHAR(10), ','), ',,', ',') || ',')"
            )
            for tag in selected_tags:
                where_parts.append(f"{normalized_tags_sql} LIKE ?")
                params.append(f"%,{tag.lower()},%")

def normalize_track_ids_filter(value):
    """Normalize a comma/space/newline separated Track ID filter into unique IDs."""
    if isinstance(value, (list, tuple, set)):
        raw_parts = []
        for item in value:
            raw_parts.extend(re.split(r"[\s,;]+", str(item or "")))
    else:
        raw_parts = re.split(r"[\s,;]+", str(value or ""))

    result = []
    seen = set()
    for item in raw_parts:
        track_id = str(item or "").strip()
        key = track_id.lower()
        if track_id and key not in seen:
            result.append(track_id)
            seen.add(key)
    return result

def build_searchable_parts(search_name=True, search_lyrics=False, search_prompt=False):
    """Build Ctrl+F text-search fields. Track ID is always searchable.

    ✶ and #tag are not text-search fields. They are independent presence
    filters added separately by append_mark_tag_presence_filters().
    """
    search_name = normalize_search_scope_flag(search_name, True)
    search_lyrics = normalize_search_scope_flag(search_lyrics, False)
    search_prompt = normalize_search_scope_flag(search_prompt, False)

    # Track ID is always included, independent of the optional text-field checkboxes.
    parts = ["lower(COALESCE(t.id, ''))"]
    if search_name:
        parts.append("lower(COALESCE(t.title, ''))")
    if search_lyrics:
        parts.append("lower(COALESCE(t.lyrics, ''))")
    if search_prompt:
        parts.append("lower(COALESCE(NULLIF(t.metadata_prompt, ''), t.prompt, ''))")

    return parts


def get_local_family_title():
    return str(get_settings().get("local_family_title") or "").strip()

def set_local_family_title(value):
    """Persist the initial Local family proposal for unassigned Track IDs.

    The stored value is a title, not a filesystem path. Windows-safe path conversion is
    deliberately deferred until a download target is actually built.
    """
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    save_settings({"local_family_title": text})
    return True, text

def clean_local_family_title(value):
    """Normalize a logical Local family title without changing its spelling."""
    title = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    title = re.sub(r"\s+", " ", title)
    return title

def _load_local_family_map():
    """Read the persistent Track ID -> Local family map."""
    default = {
        "version": 1,
        "tracks": {},
    }
    try:
        if not LOCAL_FAMILY_MAP_PATH.exists():
            return default
        data = json.loads(
            LOCAL_FAMILY_MAP_PATH.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )
        if not isinstance(data, dict):
            return default
        tracks = data.get("tracks")
        if not isinstance(tracks, dict):
            tracks = {}
        return {
            "version": 1,
            "tracks": tracks,
        }
    except Exception:
        return default

def _save_local_family_map(data):
    """Write the family map atomically."""
    tracks = data.get("tracks") if isinstance(data, dict) else {}
    if not isinstance(tracks, dict):
        tracks = {}

    clean = {
        "version": 1,
        "updated_at": now_iso_local(),
        "tracks": tracks,
    }
    LOCAL_FAMILY_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = LOCAL_FAMILY_MAP_PATH.with_suffix(
        LOCAL_FAMILY_MAP_PATH.suffix + ".tmp"
    )
    temp_path.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(LOCAL_FAMILY_MAP_PATH)
    return clean

def get_track_local_family_titles():
    """Return the confirmed Track ID -> Local Family titles in one map read."""
    data = _load_local_family_map()
    tracks = data.get("tracks") or {}
    result = {}
    for stored_id, payload in tracks.items():
        track_id = str(stored_id or "").strip().lower()
        if not track_id or not isinstance(payload, dict):
            continue
        family_title = clean_local_family_title(payload.get("family_title"))
        if family_title:
            result[track_id] = family_title
    return result


def get_track_local_family(track_id):
    track_id = str(track_id or "").strip()
    if not track_id:
        return {}

    data = _load_local_family_map()
    tracks = data.get("tracks") or {}
    wanted = track_id.lower()

    for stored_id, payload in tracks.items():
        if str(stored_id or "").strip().lower() != wanted:
            continue
        if not isinstance(payload, dict):
            return {}
        family_title = clean_local_family_title(
            payload.get("family_title")
        )
        if not family_title:
            return {}
        result = dict(payload)
        result["track_id"] = str(stored_id or track_id)
        result["family_title"] = family_title
        return result

    return {}

def set_track_local_family(track_id, family_title, category=""):
    """Persist one manually confirmed Track ID -> Local family association."""
    track_id = str(track_id or "").strip()
    family_title = clean_local_family_title(family_title)
    category = str(category or "").strip()

    if not track_id:
        return False, "Missing Track ID", {}
    if not family_title:
        return False, "Local family title cannot be empty", {}

    info = get_track_download_info(track_id)
    if not info:
        return False, "Track ID not found in LS DB", {}

    if category not in ("Song", "Instrumental"):
        category = normalize_download_category(info)

    data = _load_local_family_map()
    tracks = data.setdefault("tracks", {})

    stored_key = track_id
    for existing_key in list(tracks.keys()):
        if str(existing_key or "").strip().lower() == track_id.lower():
            stored_key = existing_key
            break

    old_payload = tracks.get(stored_key)
    if not isinstance(old_payload, dict):
        old_payload = {}

    history = old_payload.get("history")
    if not isinstance(history, list):
        history = []

    old_family = clean_local_family_title(old_payload.get("family_title"))
    if old_family and old_family.casefold() != family_title.casefold():
        history.append({
            "family_title": old_family,
            "category": str(old_payload.get("category") or ""),
            "changed_at": now_iso_local(),
        })
        history = history[-20:]

    payload = {
        "family_title": family_title,
        "category": category,
        "updated_at": now_iso_local(),
        "history": history,
    }
    tracks[stored_key] = payload
    _save_local_family_map(data)

    result = dict(payload)
    result["track_id"] = stored_key
    return True, "Local family confirmed", result

def _local_family_compare_key(value):
    """Accent-insensitive comparison key used only for suggestions."""
    title = clean_local_family_title(value).casefold()
    title = unicodedata.normalize("NFD", title)
    title = "".join(
        char
        for char in title
        if unicodedata.category(char) != "Mn"
    )
    title = re.sub(r"[^a-z0-9]+", " ", title)
    return re.sub(r"\s+", " ", title).strip()

def _local_family_similarity(left, right):
    left_key = _local_family_compare_key(left)
    right_key = _local_family_compare_key(right)
    if not left_key or not right_key:
        return 0.0
    if left_key == right_key:
        return 1.0

    ratio = difflib.SequenceMatcher(
        None,
        left_key,
        right_key,
    ).ratio()

    left_tokens = set(left_key.split())
    right_tokens = set(right_key.split())
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / max(
            1,
            len(left_tokens | right_tokens),
        )
        ratio = max(ratio, overlap)

    if left_key.startswith(right_key) or right_key.startswith(left_key):
        shorter = min(len(left_key), len(right_key))
        longer = max(len(left_key), len(right_key))
        prefix_score = 0.72 + 0.28 * (shorter / max(1, longer))
        ratio = max(ratio, prefix_score)

    return min(1.0, max(0.0, ratio))

def get_existing_local_families():
    """Collect logical family names from both category folders and saved mappings."""
    by_key = {}
    root = Path(get_audio_library_root_folder())

    for category in ("Song", "Instrumental"):
        category_folder = root / category
        try:
            children = list(category_folder.iterdir()) if category_folder.is_dir() else []
        except Exception:
            children = []

        for child in children:
            if not child.is_dir():
                continue
            family_title = clean_local_family_title(child.name)
            if not family_title:
                continue
            key = family_title.casefold()
            item = by_key.setdefault(
                key,
                {
                    "title": family_title,
                    "categories": [],
                    "source": "folder",
                },
            )
            if category not in item["categories"]:
                item["categories"].append(category)

    data = _load_local_family_map()
    for payload in (data.get("tracks") or {}).values():
        if not isinstance(payload, dict):
            continue
        family_title = clean_local_family_title(
            payload.get("family_title")
        )
        if not family_title:
            continue
        key = family_title.casefold()
        item = by_key.setdefault(
            key,
            {
                "title": family_title,
                "categories": [],
                "source": "map",
            },
        )
        category = str(payload.get("category") or "").strip()
        if category in ("Song", "Instrumental"):
            if category not in item["categories"]:
                item["categories"].append(category)

    result = list(by_key.values())
    for item in result:
        item["categories"] = sorted(item["categories"])
    result.sort(key=lambda item: lv_sort_key(item["title"]))
    return result

def get_local_family_options(proposed_title):
    proposed_title = clean_local_family_title(proposed_title)
    result = []

    for item in get_existing_local_families():
        score = _local_family_similarity(
            proposed_title,
            item.get("title") or "",
        )
        candidate = dict(item)
        candidate["similarity"] = round(score, 4)
        candidate["is_similar"] = score >= 0.58
        result.append(candidate)

    result.sort(
        key=lambda item: (
            0 if item.get("is_similar") else 1,
            -float(item.get("similarity") or 0),
            lv_sort_key(item.get("title") or ""),
        )
    )
    return result

def confirm_track_local_family(track_id, action, family_title):
    """Validate a manual family choice and return a refreshed WAV preview."""
    track_id = str(track_id or "").strip()
    action = str(action or "").strip().lower()
    requested_title = clean_local_family_title(family_title)

    if action not in ("existing", "new", "assign"):
        return {
            "ok": False,
            "error": "Choose Use existing family or Create new family.",
        }
    if not track_id:
        return {
            "ok": False,
            "error": "Missing Track ID",
        }
    if not requested_title:
        return {
            "ok": False,
            "error": "Local family title cannot be empty.",
        }

    catalog = get_existing_local_families()
    by_key = {
        str(item.get("title") or "").casefold(): item
        for item in catalog
    }
    existing_item = by_key.get(requested_title.casefold())

    if action == "existing":
        if not existing_item:
            return {
                "ok": False,
                "error": (
                    "The selected Local family no longer exists. "
                    "Refresh the preview and choose again."
                ),
            }
        requested_title = str(existing_item.get("title") or requested_title)
    elif action == "assign":
        # Quick F&T Local Family tab: assign either a known family or a new name.
        # If the name is already canonical in LS, preserve its exact spelling.
        if existing_item:
            requested_title = str(existing_item.get("title") or requested_title)
    elif existing_item:
        return {
            "ok": False,
            "error": (
                "A Local family with this exact name already exists. "
                "Choose Use existing family."
            ),
        }

    info = get_track_download_info(track_id)
    if not info:
        return {
            "ok": False,
            "error": "Track ID not found in LS DB",
        }
    category = normalize_download_category(info)

    ok, message, mapping = set_track_local_family(
        track_id,
        requested_title,
        category=category,
    )
    if not ok:
        return {
            "ok": False,
            "error": message,
        }

    return {
        "ok": True,
        "message": message,
        "mapping": mapping,
        "track_id": track_id,
    }

def _local_inventory_path_key(value):
    try:
        return os.path.normcase(os.path.abspath(str(value)))
    except Exception:
        return str(value or "").strip().lower()

def get_local_inventory_roots():
    """Return the actual local audio roots that currently exist on this PC.

    The configured LS audio root is checked first. The two historical library roots
    used in this project are also included when they exist. Duplicate paths are removed.
    No filesystem content is modified.
    """
    candidates = [get_audio_library_root_folder(), *_DATA_LOCAL_INVENTORY_KNOWN_ROOTS]
    result = []
    seen = set()
    for value in candidates:
        text_value = str(value or "").strip().strip('"')
        if not text_value:
            continue
        path_obj = Path(text_value)
        try:
            exists = path_obj.exists() and path_obj.is_dir()
        except Exception:
            exists = False
        if not exists:
            continue
        key = _local_inventory_path_key(path_obj)
        if key in seen:
            continue
        seen.add(key)
        result.append(str(path_obj))
    return result

def _local_inventory_iso_from_timestamp(value):
    try:
        return datetime.fromtimestamp(float(value)).isoformat(timespec="seconds")
    except Exception:
        return ""

def detect_stem_label(path_obj):
    name = path_obj.stem
    parens = re.findall(r"\(([^()]+)\)", name)
    if parens:
        candidate = parens[-1].strip()
        if candidate:
            return normalize_stem_label(candidate)

    low = name.lower()
    keyword_map = [
        ("backing vocal", "Backing Vocals"),
        ("backing-vocal", "Backing Vocals"),
        ("bgv", "Backing Vocals"),
        ("vocal", "Vocals"),
        ("bass", "Bass"),
        ("drum", "Drums"),
        ("percussion", "Percussion"),
        ("perc", "Percussion"),
        ("keyboard", "Keyboard"),
        ("keys", "Keyboard"),
        ("piano", "Piano"),
        ("guitar", "Guitar"),
        ("synth", "Synth"),
        ("string", "Strings"),
        ("woodwind", "Woodwinds"),
        ("fx", "FX"),
    ]
    for key, label in keyword_map:
        if key in low:
            return label
    return "Other"

def normalize_stem_label(value):
    text = str(value or "").strip()
    low = text.lower()
    mapping = {
        "backing vocals": "Backing Vocals",
        "backing vocal": "Backing Vocals",
        "vocals": "Vocals",
        "vocal": "Vocals",
        "bass": "Bass",
        "drums": "Drums",
        "drum": "Drums",
        "percussion": "Percussion",
        "keyboard": "Keyboard",
        "keys": "Keyboard",
        "piano": "Piano",
        "guitar": "Guitar",
        "synth": "Synth",
        "strings": "Strings",
        "woodwinds": "Woodwinds",
        "woodwind": "Woodwinds",
        "fx": "FX",
        "effects": "FX",
    }
    return mapping.get(low, text or "Other")

def stem_sort_key(item):
    label = item.get("stem_label") if isinstance(item, dict) else item["stem_label"]
    label = normalize_stem_label(label)
    try:
        order = _DATA_STEM_LABEL_ORDER.index(label)
    except ValueError:
        order = 999
    filename = item.get("filename") if isinstance(item, dict) else item["filename"]
    return (order, lv_sort_key(label), lv_sort_key(filename))

def normalize_filename_for_match(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text)
    return text

def find_existing_audio_by_exact_title(title, workspace=""):
    """Last-resort filesystem lookup under the configured audio root.
    Used only on demand for Edit / Copy path, not during page rendering.
    """
    title = str(title or "").strip()
    if not title:
        return ""

    root = Path(get_stem_root_folder())
    if not root.exists() or not root.is_dir():
        return ""

    wanted = [normalize_filename_for_match(title + ext) for ext in [".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg"]]
    workspace_key = normalize_filename_for_match(workspace)

    matches = []
    try:
        for path_obj in root.rglob("*"):
            if not path_obj.is_file():
                continue
            if path_obj.suffix.lower() not in _DATA_AUDIO_EXTENSIONS:
                continue
            if normalize_filename_for_match(path_obj.name) not in wanted:
                continue

            ext_order = {".wav": 0, ".flac": 1, ".mp3": 2, ".m4a": 3, ".aac": 4, ".ogg": 5}.get(path_obj.suffix.lower(), 9)
            folder_key = normalize_filename_for_match(str(path_obj.parent))
            workspace_order = 0 if workspace_key and workspace_key in folder_key else 1
            matches.append((workspace_order, ext_order, str(path_obj)))
    except Exception:
        return ""

    if not matches:
        return ""

    matches.sort(key=lambda item: (item[0], item[1], lv_sort_key(item[2])))
    return matches[0][2]


def ls_db_insert_column_value(columns, meta, raw_track, col):
    """Map Suno API metadata to LS DB columns for metadata-only import."""
    md = raw_track.get("metadata") if isinstance(raw_track.get("metadata"), dict) else {}

    def first(*values):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, (dict, list, tuple)):
                text = str(value).strip()
                if text:
                    return text
        return ""

    if col == "id":
        return meta.get("id") or ""
    if col == "title":
        return meta.get("title") or "(untitled)"
    if col == "audio_url":
        return meta.get("audio_url") or ""
    if col == "status":
        return first(raw_track.get("status"), "complete")
    if col == "created_at":
        return meta.get("created_at") or ""
    if col == "lyrics":
        return meta.get("lyrics") or ""
    if col == "metadata_prompt":
        return meta.get("prompt") or ""
    if col == "prompt":
        return meta.get("prompt") or ""
    if col == "metadata_tags":
        return meta.get("metadata_tags") or ""
    if col == "style":
        return meta.get("metadata_tags") or ""
    if col == "display_tags":
        return meta.get("metadata_tags") or ""
    if col == "image_url":
        return meta.get("image_url") or ""
    if col == "raw_image_url":
        return meta.get("image_url") or ""
    if col == "raw_image_large_url":
        return first(raw_track.get("image_large_url"), raw_track.get("image_url"), meta.get("image_url"))
    if col == "workspaceName":
        return meta.get("workspaceName") or ""
    if col == "workspace":
        return meta.get("workspaceName") or ""
    if col == "workspaceId":
        return meta.get("workspaceId") or ""
    if col == "workspace_id":
        return meta.get("workspaceId") or ""
    if col == "reaction_type":
        return meta.get("reaction_type") or ""
    if col == "model_name":
        return meta.get("model_name") or ""
    if col == "model_version":
        return meta.get("model_version") or meta.get("major_model_version") or ""
    if col == "major_model_version":
        return meta.get("major_model_version") or ""
    if col == "bpm":
        return meta.get("bpm") or ""
    if col == "key":
        return meta.get("key") or ""
    if col == "raw_json":
        return meta.get("raw_json") or json.dumps(raw_track, ensure_ascii=False)
    if col == "raw_is_liked":
        return str(raw_track.get("is_liked") or raw_track.get("liked") or "")
    if col == "is_liked":
        reaction = str(meta.get("reaction_type") or raw_track.get("reaction_type") or "").lower()
        return 1 if reaction in ("like", "liked") else 0
    if col == "is_stem":
        return 0
    if col == "library_status":
        return "active"
    if col == "kind":
        lyrics = (meta.get("lyrics") or "").lower()
        title = (meta.get("title") or "").lower()
        return "Instrumental" if "instrumental" in lyrics or "(instrumental" in title else "Song"
    if col == "type":
        return first(raw_track.get("type"), md.get("type"))
    if col == "metadata_type":
        return first(raw_track.get("type"), md.get("type"))
    if col == "metadata_duration":
        return raw_track.get("duration") or md.get("duration") or None
    if col == "duration":
        return first(raw_track.get("duration"), md.get("duration"))
    if col in ("created_local_at", "updated_at"):
        return now_iso_local()

    return None

def ls_column_exists(columns, candidates):
    for col in candidates:
        if col in columns:
            return col
    return ""

def normalize_ls_bpm_text(value):
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
    if not match:
        return ""
    try:
        number = float(match.group(0).replace(",", "."))
    except ValueError:
        return ""
    if not 30 <= number <= 300:
        return ""
    if abs(number - round(number)) < 0.01:
        shown = str(int(round(number)))
    else:
        shown = f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{shown} BPM"

def build_ls_structured_repair_preview():
    plan = _collect_ls_structured_repair_plan()
    return {key: value for key, value in plan.items() if not key.startswith("_")}

def _ls_intent_text(value):
    return str(value or "").strip()

def _ls_intent_normalize(value):
    return re.sub(r"\s+", " ", _ls_intent_text(value)).casefold()

def _ls_intent_first_present(*values):
    for value in values:
        if value is not None and _ls_intent_text(value) != "":
            return value
    return None

def _ls_intent_json_metadata(row):
    try:
        parsed = json.loads(_ls_intent_text(row.get("raw_json")) or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    metadata = parsed.get("metadata") if isinstance(parsed, dict) else None
    return metadata if isinstance(metadata, dict) else {}

def _ls_intent_slider_percent(value):
    """Normalize Suno slider values stored as either 0..1 or 0..100."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not 0 <= number <= 100:
        return None
    if number <= 1:
        number *= 100
    return round(number, 1)

def _ls_intent_control_sliders(row):
    """Read explainable Weirdness / Style / Audio values from raw Suno JSON."""
    metadata = _ls_intent_json_metadata(row)
    controls = metadata.get("control_sliders")
    if not isinstance(controls, dict):
        controls = {}

    def first_slider(*names):
        for source in (controls, metadata):
            for name in names:
                if name in source:
                    normalized = _ls_intent_slider_percent(source.get(name))
                    if normalized is not None:
                        return normalized
        return None

    return {
        "weirdness": first_slider(
            "weirdness_constraint", "weirdness", "weirdness_weight"
        ),
        "style_influence": first_slider(
            "style_weight", "style_influence", "style_influence_weight"
        ),
        "audio_influence": first_slider(
            "audio_weight", "audio_influence", "audio_influence_weight"
        ),
    }

def _ls_intent_user_tags(value):
    return {
        item.casefold()
        for item in re.split(r"[,;\s]+", _ls_intent_text(value))
        if item.strip()
    }

def _ls_intent_preferred_lyrics(row):
    return _ls_intent_text(
        row.get("lyrics") or row.get("metadata_prompt") or row.get("prompt")
    )

def _ls_intent_lyric_profile(row):
    value = _ls_intent_preferred_lyrics(row)
    content_lines = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or _DATA_LS_INTENT_BRACKET_LINE_RE.match(line):
            continue
        if re.match(
            r"^(?:is_max_mode|quality|realism|real_instruments)\s*:",
            line,
            re.IGNORECASE,
        ):
            continue
        if len(_DATA_LS_INTENT_WORD_RE.findall(line)) >= 2:
            content_lines.append(line)
    words = [
        word.casefold()
        for word in _DATA_LS_INTENT_WORD_RE.findall("\n".join(content_lines))
    ]
    has_structure = bool(_DATA_LS_INTENT_STRUCTURE_MARKER_RE.search(value))
    looks_like_lyrics = bool(
        words
        and (
            (has_structure and len(words) >= 2)
            or (len(content_lines) >= 2 and len(words) >= 6)
        )
    )
    return {
        "normalized": _ls_intent_normalize(value),
        "is_instrumental_marker": bool(
            _DATA_LS_INTENT_INSTRUMENTAL_ONLY_RE.fullmatch(value)
        ),
        "looks_like_lyrics": looks_like_lyrics,
        "word_set": set(words),
    }

def _ls_intent_source_relation(row):
    metadata = _ls_intent_json_metadata(row)
    mashup_ids = metadata.get("mashup_clip_ids")
    if isinstance(mashup_ids, list) and mashup_ids:
        return "mashup", [
            _ls_intent_text(item) for item in mashup_ids if _ls_intent_text(item)
        ]
    cover_id = _ls_intent_text(
        row.get("metadata_cover_clip_id") or metadata.get("cover_clip_id")
    )
    if cover_id:
        return "cover", [cover_id]
    return "none", []

def _ls_intent_word_jaccard(left, right):
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)

def _ls_intent_analyze_row(row, all_tracks, analyzed_at):
    relation_type, source_ids = _ls_intent_source_relation(row)
    sources = [
        all_tracks[source_id]
        for source_id in source_ids
        if source_id in all_tracks
    ]
    child = _ls_intent_lyric_profile(row)
    source_profiles = [_ls_intent_lyric_profile(source) for source in sources]
    tags = _ls_intent_user_tags(row.get("ls_user_tags"))
    current_category = _ls_intent_text(row.get("ls_main_category"))
    manual = _ls_intent_text(row.get("ls_review_group")) == "manual_toggle"
    vocal_parts = "#vocalparts" in tags or "vocalparts" in tags
    sliders = _ls_intent_control_sliders(row)

    any_source_lyrics = any(
        item["looks_like_lyrics"] for item in source_profiles
    )
    any_source_instrumental = any(
        item["is_instrumental_marker"] for item in source_profiles
    )
    exact_source = any(
        child["normalized"]
        and child["normalized"] == item["normalized"]
        for item in source_profiles
    )
    max_overlap = max(
        (
            _ls_intent_word_jaccard(child["word_set"], item["word_set"])
            for item in source_profiles
        ),
        default=0.0,
    )

    evidence = []
    song_score = 0
    instrumental_score = 0
    for slider_name, slider_value in sliders.items():
        if slider_value is not None:
            evidence.append(f"wsa_{slider_name}_{slider_value:g}")
    if child["looks_like_lyrics"]:
        song_score += 80
        evidence.append("child_has_lyric_structure")
    if exact_source and child["looks_like_lyrics"]:
        song_score += 15
        evidence.append("child_lyrics_match_source")
    elif max_overlap >= 0.70 and child["looks_like_lyrics"]:
        song_score += 10
        evidence.append("child_lyrics_strongly_overlap_source")
    if any_source_instrumental and child["looks_like_lyrics"]:
        song_score += 10
        evidence.append("lyrics_added_after_instrumental_source")

    if child["is_instrumental_marker"]:
        instrumental_score += 90
        evidence.append("child_exact_instrumental_marker")
    elif (
        relation_type in {"cover", "mashup"}
        and not child["looks_like_lyrics"]
        and not child["normalized"]
        and any_source_lyrics
    ):
        instrumental_score += 55
        evidence.append("source_lyrics_removed_in_child")

    make_instrumental = _ls_intent_bool_token(
        _ls_intent_first_present(
            row.get("metadata_make_instrumental"),
            row.get("raw_make_instrumental"),
        )
    )
    has_vocal = _ls_intent_bool_token(
        _ls_intent_first_present(
            row.get("metadata_has_vocal"), row.get("raw_has_vocal")
        )
    )
    if make_instrumental == "true":
        instrumental_score += 15
        evidence.append("metadata_make_instrumental_true")
    elif make_instrumental == "false":
        song_score += 5
        evidence.append("metadata_make_instrumental_false")
    if has_vocal == "true":
        song_score += 10
        evidence.append("metadata_has_vocal_true")
    elif has_vocal == "false":
        instrumental_score += 5
        evidence.append("metadata_has_vocal_false")
    if vocal_parts:
        evidence.append("human_tag_vocalparts")

    # A high Audio Influence can preserve the audible identity of a Cover,
    # but it is not proof by itself.  Propagate only a unanimous, manually
    # confirmed source category and only when the child has no contradictory
    # Lyrics / Instrumental marker.  W and S remain recorded evidence because
    # neither one alone establishes whether vocals are audible.
    audio_influence = sliders.get("audio_influence")
    manually_confirmed_source_categories = {
        _ls_intent_text(source.get("ls_main_category"))
        for source in sources
        if _ls_intent_text(source.get("ls_review_group")) == "manual_toggle"
        and _ls_intent_text(source.get("ls_main_category"))
        in {"Song", "Instrumental"}
    }
    inherited_source_category = ""
    if (
        relation_type == "cover"
        and audio_influence is not None
        and audio_influence >= 90
        and len(manually_confirmed_source_categories) == 1
    ):
        candidate = next(iter(manually_confirmed_source_categories))
        child_contradicts_source = (
            candidate == "Song" and child["is_instrumental_marker"]
        ) or (
            candidate == "Instrumental" and child["looks_like_lyrics"]
        )
        if child_contradicts_source:
            evidence.append("high_audio_source_category_blocked_by_child")
        else:
            inherited_source_category = candidate
            if candidate == "Song":
                song_score += 60
            else:
                instrumental_score += 60
            evidence.append(
                "high_audio_inherits_manual_source_"
                + candidate.casefold()
            )

    if child["looks_like_lyrics"] and child["is_instrumental_marker"]:
        intent_label = "Mixed"
        intent_score = max(song_score, instrumental_score)
        rule_code = "conflicting_child_lyrics"
    elif child["looks_like_lyrics"]:
        intent_label = "Song"
        intent_score = song_score
        rule_code = "child_lyrics"
    elif child["is_instrumental_marker"]:
        intent_label = "Instrumental"
        intent_score = instrumental_score
        rule_code = "child_instrumental_marker"
    elif inherited_source_category:
        intent_label = inherited_source_category
        intent_score = (
            song_score if inherited_source_category == "Song"
            else instrumental_score
        )
        rule_code = "high_audio_manual_cover_source"
    elif instrumental_score >= 50 and song_score < 50:
        intent_label = "Instrumental"
        intent_score = instrumental_score
        rule_code = "source_lyrics_removed"
    elif relation_type == "mashup" and any_source_lyrics and any_source_instrumental:
        intent_label = "Mixed"
        intent_score = 50
        rule_code = "mixed_mashup_sources"
    else:
        intent_label = "Unknown"
        intent_score = max(song_score, instrumental_score)
        rule_code = "insufficient_intent_evidence"

    intent_score = min(100, int(intent_score))
    if intent_score >= 85:
        intent_confidence = "strong"
    elif intent_score >= 55:
        intent_confidence = "medium"
    else:
        intent_confidence = "weak"

    if vocal_parts:
        audio_status = "vocal_parts"
        veto_reason = (
            "#VocalParts: audible vocals reported in an instrumental-intent track"
        )
        recommended_action = "preserve_category_review_vocal_parts"
    elif manual:
        audio_status = "manual_classified"
        veto_reason = ""
        recommended_action = "preserve_manual_category"
    else:
        audio_status = "unverified"
        veto_reason = ""
        if (
            intent_label in {"Song", "Instrumental"}
            and intent_label != current_category
        ):
            recommended_action = "review_category_conflict"
        elif intent_label in {"Mixed", "Unknown"}:
            recommended_action = "review_if_needed"
        else:
            recommended_action = "keep_current_category"

    return {
        "track_id": _ls_intent_text(row.get("id")),
        "title": _ls_intent_text(row.get("title")) or "[No title]",
        "engine_version": _DATA_LS_INTENT_AUDIT_ENGINE_VERSION,
        "analyzed_at": analyzed_at,
        "current_category": current_category,
        "intent_label": intent_label,
        "intent_confidence": intent_confidence,
        "intent_score": intent_score,
        "audio_status": audio_status,
        "veto_reason": veto_reason,
        "relation_type": relation_type,
        "source_ids": source_ids,
        "source_found_count": len(sources),
        "rule_code": rule_code,
        "recommended_action": recommended_action,
        "evidence": evidence,
        "control_sliders": sliders,
    }

def build_ls_intent_audit_preview():
    plan = _collect_ls_intent_audit_plan()
    return {key: value for key, value in plan.items() if not key.startswith("_")}

def build_ls_category_assignment_preview():
    plan = _collect_ls_category_assignment_plan()
    return {key: value for key, value in plan.items() if not key.startswith("_")}

def is_db_value_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False

def is_ls_edit_section_row(row):
    task = str((row or {}).get("metadata_task") or "").strip().lower()
    meta_type = str((row or {}).get("metadata_type") or "").strip().lower()
    return (
        "infill" in task
        or meta_type.startswith("edit_")
        or meta_type in ("concat_infilling", "rendered_context_window")
    )

def is_ls_stem_metadata_row(row):
    kind = str((row or {}).get("kind") or "").strip().lower()
    stem = str((row or {}).get("is_stem") or "").strip().lower()
    return kind == "stem" or stem in ("true", "1", "yes")

def metadata_value_present(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True

def normalized_metadata_compare_value(value):
    if value is None:
        return ("empty", "")
    if isinstance(value, bool):
        return ("bool", 1 if value else 0)
    if isinstance(value, (int, float)):
        try:
            return ("number", float(value))
        except Exception:
            pass
    text = str(value).strip()
    lower = text.lower()
    if lower in ("true", "yes"):
        return ("bool", 1)
    if lower in ("false", "no"):
        return ("bool", 0)
    try:
        return ("number", float(text))
    except Exception:
        return ("text", text.replace("\r\n", "\n").replace("\r", "\n"))

def metadata_values_equal(left, right):
    a_kind, a_value = normalized_metadata_compare_value(left)
    b_kind, b_value = normalized_metadata_compare_value(right)
    if {a_kind, b_kind} <= {"bool", "number"}:
        return float(a_value) == float(b_value)
    return a_value == b_value

def metadata_bpm_values_equal(left, right):
    def bpm_number(value):
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value or ""))
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", "."))
        except ValueError:
            return None

    left_number = bpm_number(left)
    right_number = bpm_number(right)
    if left_number is None or right_number is None:
        return False
    # LS displays whole BPM. A source value such as 116.99 is therefore the
    # same display value as the stored "117 BPM", not a DB conflict.
    return abs(left_number - right_number) <= 0.51

def default_suno_metadata_job_state():
    return {
        "ok": True,
        "status": "idle",
        "running": False,
        "message": "Automatic metadata backfill has not been started.",
        "started_at": "",
        "finished_at": "",
        "processed": 0,
        "total": 0,
        "remaining": 0,
        "percent": 0.0,
        "updated_tracks": 0,
        "total_fields": 0,
        "total_conflicts": 0,
        "errors": 0,
        "current_track_id": "",
        "current_title": "",
        "current_status": "",
        "current_source": "",
        "backup": "",
        "report": "",
        "csv": "",
        "app_version": APP_VERSION,
    }

def read_suno_metadata_job_state():
    state = default_suno_metadata_job_state()
    try:
        if SUNO_METADATA_JOB_PATH.exists():
            stored = json.loads(SUNO_METADATA_JOB_PATH.read_text(encoding="utf-8", errors="replace"))
            if isinstance(stored, dict):
                state.update(stored)
    except Exception as exc:
        log_ls_exception(
            "metadata",
            "read_job_state",
            exc,
            context={"path": str(SUNO_METADATA_JOB_PATH)},
            include_traceback=False,
        )
    return state

def write_suno_metadata_job_state(state):
    clean = default_suno_metadata_job_state()
    clean.update(state or {})
    clean["ok"] = True
    clean["app_version"] = APP_VERSION
    total = max(0, int(clean.get("total") or 0))
    processed = max(0, min(total, int(clean.get("processed") or 0)))
    clean["total"] = total
    clean["processed"] = processed
    clean["remaining"] = max(0, total - processed)
    clean["percent"] = round((processed * 100.0 / total), 1) if total else 0.0
    with SUNO_METADATA_JOB_LOCK:
        SUNO_METADATA_JOB_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = SUNO_METADATA_JOB_PATH.with_suffix(SUNO_METADATA_JOB_PATH.suffix + ".tmp")
        temp_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(SUNO_METADATA_JOB_PATH)
    return clean


def _ls_intent_bool_token(value):
    value = _ls_intent_normalize(value)
    if value in {"1", "true", "yes"}:
        return "true"
    if value in {"0", "false", "no"}:
        return "false"
    return "missing"


def normalize_download_category(info):
    category = str((info or {}).get("download_category") or "").strip()
    if category in ("Song", "Instrumental"):
        return category
    if category == "SongOrInstrumental":
        raise ValueError(
            "This track is SongOrInstrumental. Confirm Song or Instrumental "
            "before creating a Local family or downloading WAV."
        )

    title = str((info or {}).get("title") or "")
    lyrics = str((info or {}).get("lyrics") or "")
    haystack = (title + "\n" + lyrics).lower()
    if "[instrumental]" in haystack or "(instrumental" in haystack:
        return "Instrumental"
    return "Song"



def get_track_identity_snapshot():
    """Return the minimal Track-ID/title/workspace snapshot used by Suno previews."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT lower(id) AS id_key FROM tracks_compat WHERE id IS NOT NULL AND TRIM(id) != ''")
        ls_ids = {row["id_key"] for row in cur.fetchall() if row["id_key"]}
        cur.execute("""
            SELECT lower(id) AS id_key, title, COALESCE(workspaceName, workspace, '') AS workspace
            FROM tracks_compat
            WHERE id IS NOT NULL AND TRIM(id) != ''
        """)
        ls_map = {row["id_key"]: dict(row) for row in cur.fetchall() if row["id_key"]}
        return ls_ids, ls_map
    finally:
        conn.close()


def apply_suno_title_updates(selected_track_ids, changed_items):
    """Apply already-resolved Suno title changes to canonical tracks."""
    by_id = {str(item.get("id") or "").lower(): item for item in (changed_items or [])}
    backup_path = backup_db_before_metadata_import()
    conn = get_connection()
    rows = []
    updated = 0
    try:
        cur = conn.cursor()
        for tid in selected_track_ids or []:
            item = by_id.get(str(tid or "").lower())
            if not item:
                rows.append({"short_id": str(tid)[:8], "status": "SKIPPED", "ls_title": "", "suno_title": "", "error": "No current title change found"})
                continue
            suno_title = item.get("title") or ""
            ls_title = item.get("ls_title") or ""
            if not suno_title or suno_title == ls_title:
                rows.append({"short_id": str(tid)[:8], "status": "NO_CHANGE", "ls_title": ls_title, "suno_title": suno_title, "error": ""})
                continue
            cur.execute(
                "UPDATE main.tracks SET title = ?, updated_at = ? WHERE lower(id)=lower(?)",
                (suno_title, now_iso_local(), tid),
            )
            updated += cur.rowcount
            rows.append({"short_id": str(tid)[:8], "status": "UPDATED", "ls_title": ls_title, "suno_title": suno_title, "error": ""})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"ok": True, "backup": str(backup_path), "updated": updated, "rows": rows}

def extract_suno_metadata_for_ls(track_data):
    """Normalize one Suno API clip into the LS metadata column model.

    v5.35 keeps internal model_name separate from major_model_version and
    preserves booleans/numbers as typed values.  Suno stores the user-facing
    lyrics/instrument plan in metadata.prompt, so that value is also the safe
    fallback for the LS lyrics field when no more specific lyrics key exists.
    """
    md = track_data.get("metadata") if isinstance(track_data.get("metadata"), dict) else {}

    def first_value(*values):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
            if value is not None and not isinstance(value, (dict, list, tuple)):
                text = str(value).strip()
                if text:
                    return text
        return ""

    def first_raw(*values):
        for value in values:
            if value is not None and not isinstance(value, (dict, list, tuple)):
                if isinstance(value, str) and not value.strip():
                    continue
                return value
        return None

    def bool_int(value):
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return 1 if value else 0
        text = str(value).strip().lower()
        if text in ("true", "1", "yes", "y"):
            return 1
        if text in ("false", "0", "no", "n"):
            return 0
        return None

    def raw_text(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value).strip()

    metadata_prompt = first_value(
        md.get("prompt"),
        track_data.get("prompt"),
        track_data.get("gpt_description_prompt"),
        md.get("gpt_description_prompt"),
    )
    lyrics = first_value(
        md.get("infill_lyrics"),
        track_data.get("lyrics"),
        md.get("lyrics"),
        track_data.get("lyric"),
        metadata_prompt,
    )
    metadata_tags = first_value(md.get("tags"), track_data.get("tags"))
    image_url = first_value(
        track_data.get("image_url"),
        track_data.get("image_large_url"),
        track_data.get("cover_url"),
        md.get("image_url"),
        md.get("cover_url"),
    )
    image_large_url = first_value(
        track_data.get("image_large_url"),
        track_data.get("image_url"),
        track_data.get("cover_url"),
        md.get("image_large_url"),
        md.get("image_url"),
    )
    workspace = track_data.get("workspace") if isinstance(track_data.get("workspace"), dict) else {}
    model_badges = md.get("model_badges") if isinstance(md.get("model_badges"), dict) else {}
    songrow_badge = model_badges.get("songrow") if isinstance(model_badges.get("songrow"), dict) else {}
    major_model_version = first_value(
        track_data.get("major_model_version"),
        md.get("major_model_version"),
        songrow_badge.get("display_name"),
    )
    avg_bpm = first_raw(md.get("avg_bpm"), track_data.get("bpm"), md.get("bpm"), md.get("tempo"))

    return {
        "id": first_value(track_data.get("id"), track_data.get("clip_id")),
        "title": first_value(track_data.get("title")),
        "status": first_value(track_data.get("status")),
        "entity_type": first_value(track_data.get("entity_type")),
        "audio_url": first_value(track_data.get("audio_url"), track_data.get("audio_url_mp3"), track_data.get("mp3_url")),
        "video_url": first_value(track_data.get("video_url")),
        "created_at": first_value(track_data.get("created_at"), md.get("created_at")),
        "lyrics": lyrics,
        "metadata_prompt": metadata_prompt,
        "prompt": metadata_prompt,
        "metadata_tags": metadata_tags,
        "style": metadata_tags,
        "display_tags": raw_text(track_data.get("display_tags")) or metadata_tags,
        "caption": first_value(track_data.get("caption")),
        "image_url": image_url,
        "image_large_url": image_large_url,
        "raw_image_url": image_url,
        "raw_image_large_url": image_large_url,
        "workspaceName": first_value(track_data.get("workspaceName"), track_data.get("workspace_name"), workspace.get("name")),
        "workspaceId": first_value(track_data.get("workspaceId"), track_data.get("workspace_id"), workspace.get("id")),
        "reaction_type": first_value(track_data.get("reaction_type"), track_data.get("reaction")),
        "model_name": first_value(track_data.get("model_name"), md.get("model_name"), md.get("model"), track_data.get("model")),
        "major_model_version": major_model_version,
        "model_version": major_model_version,
        "metadata_type": first_value(md.get("type"), track_data.get("type")),
        "metadata_task": first_value(md.get("task"), track_data.get("task")),
        "metadata_negative_tags": raw_text(md.get("negative_tags")),
        "metadata_duration": first_raw(md.get("duration"), track_data.get("duration")),
        "metadata_has_stem": bool_int(md.get("has_stem")),
        "metadata_has_vocal": bool_int(md.get("has_vocal")),
        "metadata_make_instrumental": bool_int(md.get("make_instrumental")),
        "metadata_is_remix": bool_int(md.get("is_remix")),
        "metadata_studio_project_id": first_value(md.get("studio_project_id")),
        "metadata_studio_project_version_id": first_value(md.get("studio_project_version_id")),
        "metadata_edited_clip_id": first_value(md.get("edited_clip_id")),
        "metadata_cover_clip_id": first_value(md.get("cover_clip_id")),
        "metadata_avg_bpm": avg_bpm,
        "metadata_min_bpm": first_raw(md.get("min_bpm")),
        "metadata_max_bpm": first_raw(md.get("max_bpm")),
        "is_liked": bool_int(track_data.get("is_liked")),
        "is_public": bool_int(track_data.get("is_public")),
        "is_trashed": bool_int(track_data.get("is_trashed")),
        "is_hidden": bool_int(track_data.get("is_hidden")),
        "explicit": bool_int(track_data.get("explicit")),
        "raw_task": raw_text(md.get("task")),
        "raw_type": raw_text(md.get("type")),
        "raw_has_stem": raw_text(md.get("has_stem")),
        "raw_has_vocal": raw_text(md.get("has_vocal")),
        "raw_make_instrumental": raw_text(md.get("make_instrumental")),
        "raw_is_remix": raw_text(md.get("is_remix")),
        "raw_is_liked": raw_text(track_data.get("is_liked")),
        "raw_secondary_badges": raw_text(md.get("secondary_badges")),
        "raw_display_tags": raw_text(track_data.get("display_tags")),
        "raw_tags": raw_text(md.get("tags")),
        "raw_control_sliders": raw_text(md.get("control_sliders")),
        "bpm": avg_bpm,
        "key": first_value(track_data.get("key"), md.get("key"), md.get("musical_key")),
        "raw_json": json.dumps(track_data, ensure_ascii=False),
    }

def collect_suno_metadata_changes(current_row, columns, api_meta, overwrite=False):
    updates = {}
    conflicts = []
    for column, value, report_conflict in suno_metadata_column_specs(api_meta):
        if column not in columns or not metadata_value_present(value):
            continue
        current_value = current_row.get(column)
        if overwrite or is_db_value_empty(current_value):
            updates[column] = value
        elif (
            report_conflict
            and not (
                column == "bpm"
                and metadata_bpm_values_equal(current_value, value)
            )
            and not metadata_values_equal(current_value, value)
        ):
            conflicts.append(column)
    return updates, sorted(set(conflicts))


def suno_metadata_column_specs(api_meta):
    """Return explicit API -> DB mappings.

    Each field is mapped separately so v5.35 can fill every empty duplicate
    compatibility column without ever putting model_name into a version column.
    The final flag controls whether a non-empty difference is reported as a
    conflict. Mutable/local presentation fields are left alone without noise.
    """
    return [
        ("title", api_meta.get("title"), False),
        ("status", api_meta.get("status"), False),
        ("entity_type", api_meta.get("entity_type"), True),
        ("audio_url", api_meta.get("audio_url"), False),
        ("video_url", api_meta.get("video_url"), False),
        ("created_at", api_meta.get("created_at"), True),
        ("lyrics", api_meta.get("lyrics"), True),
        ("metadata_prompt", api_meta.get("metadata_prompt"), True),
        ("prompt", api_meta.get("prompt"), True),
        ("metadata_tags", api_meta.get("metadata_tags"), True),
        ("style", api_meta.get("style"), True),
        ("display_tags", api_meta.get("display_tags"), False),
        ("caption", api_meta.get("caption"), True),
        ("image_url", api_meta.get("image_url"), False),
        ("image_large_url", api_meta.get("image_large_url"), False),
        ("raw_image_url", api_meta.get("raw_image_url"), False),
        ("raw_image_large_url", api_meta.get("raw_image_large_url"), False),
        ("workspaceName", api_meta.get("workspaceName"), False),
        ("workspace", api_meta.get("workspaceName"), False),
        ("workspaceId", api_meta.get("workspaceId"), False),
        ("workspace_id", api_meta.get("workspaceId"), False),
        ("model_name", api_meta.get("model_name"), True),
        ("major_model_version", api_meta.get("major_model_version"), True),
        ("model_version", api_meta.get("model_version"), True),
        ("metadata_type", api_meta.get("metadata_type"), True),
        ("type", api_meta.get("metadata_type"), True),
        ("metadata_task", api_meta.get("metadata_task"), True),
        ("metadata_negative_tags", api_meta.get("metadata_negative_tags"), True),
        ("metadata_duration", api_meta.get("metadata_duration"), True),
        ("duration", api_meta.get("metadata_duration"), False),
        ("metadata_has_stem", api_meta.get("metadata_has_stem"), True),
        ("metadata_has_vocal", api_meta.get("metadata_has_vocal"), True),
        ("metadata_make_instrumental", api_meta.get("metadata_make_instrumental"), True),
        ("metadata_is_remix", api_meta.get("metadata_is_remix"), True),
        ("metadata_studio_project_id", api_meta.get("metadata_studio_project_id"), True),
        ("metadata_studio_project_version_id", api_meta.get("metadata_studio_project_version_id"), True),
        ("metadata_edited_clip_id", api_meta.get("metadata_edited_clip_id"), True),
        ("metadata_cover_clip_id", api_meta.get("metadata_cover_clip_id"), True),
        ("metadata_avg_bpm", api_meta.get("metadata_avg_bpm"), True),
        ("metadata_min_bpm", api_meta.get("metadata_min_bpm"), True),
        ("metadata_max_bpm", api_meta.get("metadata_max_bpm"), True),
        ("bpm", api_meta.get("bpm"), True),
        ("is_liked", api_meta.get("is_liked"), False),
        ("is_public", api_meta.get("is_public"), False),
        ("is_trashed", api_meta.get("is_trashed"), False),
        ("is_hidden", api_meta.get("is_hidden"), False),
        ("explicit", api_meta.get("explicit"), False),
        ("raw_task", api_meta.get("raw_task"), False),
        ("raw_type", api_meta.get("raw_type"), False),
        ("raw_has_stem", api_meta.get("raw_has_stem"), False),
        ("raw_has_vocal", api_meta.get("raw_has_vocal"), False),
        ("raw_make_instrumental", api_meta.get("raw_make_instrumental"), False),
        ("raw_is_remix", api_meta.get("raw_is_remix"), False),
        ("raw_is_liked", api_meta.get("raw_is_liked"), False),
        ("raw_secondary_badges", api_meta.get("raw_secondary_badges"), False),
        ("raw_display_tags", api_meta.get("raw_display_tags"), False),
        ("raw_tags", api_meta.get("raw_tags"), False),
        ("raw_control_sliders", api_meta.get("raw_control_sliders"), False),
        ("raw_json", api_meta.get("raw_json"), False),
    ]

