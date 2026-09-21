# LS Elza - read-only LocalSunoDb data access
# Created: 13.jul.2026
# Purpose: Provide a small whitelist of safe LS database queries for LS Elza
# ver. 1.2 - package path isolation; canonical LS root DB path

# 1.  ------ Imports -----

import json
import re
import sqlite3
from pathlib import Path

from .host_paths import DATA_DIR, HOST_ROOT, LEGACY_DATA_DIR


# 2.  ------ Paths and limits -----

BASE_DIR = HOST_ROOT
DB_PATH = HOST_ROOT / "suno_finder_v4.db"
LOCAL_FAMILY_MAP_PATH = LEGACY_DATA_DIR / "suno_local_family_map.json"

MAX_QUERY_CHARS = 200
MAX_TRACK_ID_CHARS = 160
MAX_WORKSPACE_CHARS = 300
MAX_RESULTS = 50


# 3.  ------ Errors and validation -----

class LSElzaReadOnlyError(RuntimeError):
    def __init__(self, message, code="readonly_error"):
        super().__init__(message)
        self.code = str(code or "readonly_error")


def _clean_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) > int(max_chars):
        text = text[: int(max_chars)].rstrip()
    return text


def _bounded_limit(value, default=20):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(1, min(number, MAX_RESULTS))


def _require_arguments(arguments, allowed):
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise LSElzaReadOnlyError(
            "Read-only action arguments must be a JSON object.",
            code="invalid_arguments",
        )

    unexpected = sorted(set(arguments) - set(allowed))
    if unexpected:
        raise LSElzaReadOnlyError(
            "Unsupported read-only arguments: " + ", ".join(unexpected),
            code="unsupported_arguments",
        )
    return arguments


# 4.  ------ Read-only SQLite connection -----

def _first_word(value):
    match = re.search(r"\w+", str(value or ""), flags=re.UNICODE)
    return match.group(0).casefold() if match else ""


def open_readonly_connection(db_path=DB_PATH):
    path = Path(db_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise LSElzaReadOnlyError(
            f"LocalSunoDb database was not found: {path}",
            code="database_not_found",
        )

    try:
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.create_function("ls_first_word", 1, _first_word, deterministic=True)
        conn.execute("PRAGMA query_only = ON;")
        conn.execute("PRAGMA busy_timeout = 3000;")
        return conn
    except sqlite3.Error as error:
        raise LSElzaReadOnlyError(
            "LocalSunoDb database could not be opened in read-only mode.",
            code="database_open_failed",
        ) from error


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1;",
        (str(table_name),),
    ).fetchone()
    return row is not None


def _table_columns(conn, table_name):
    if not _table_exists(conn, table_name):
        return set()
    return {
        str(row["name"])
        for row in conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    }


def _schema(conn):
    tracks = _table_columns(conn, "tracks")
    if not tracks or "id" not in tracks or "title" not in tracks:
        raise LSElzaReadOnlyError(
            "The LS tracks table is missing required columns.",
            code="unsupported_database_schema",
        )
    return {
        "tracks": tracks,
        "track_ui": _table_columns(conn, "track_ui"),
        "local_audio_files": _table_columns(conn, "local_audio_files"),
    }


# 5.  ------ Schema-adaptive SQL fragments -----

def _workspace_expr(schema):
    columns = schema["tracks"]
    if "workspaceName" in columns and "workspace" in columns:
        return "COALESCE(NULLIF(t.workspaceName, ''), t.workspace, '')"
    if "workspaceName" in columns:
        return "COALESCE(t.workspaceName, '')"
    if "workspace" in columns:
        return "COALESCE(t.workspace, '')"
    return "''"


def _category_expr(schema):
    track_columns = schema["tracks"]
    ui_columns = schema["track_ui"]
    choices = []
    if "main_category" in ui_columns:
        choices.append("NULLIF(TRIM(tu.main_category), '')")
    if "ui_type" in ui_columns:
        choices.append("NULLIF(TRIM(tu.ui_type), '')")
    if "kind" in track_columns:
        choices.append("NULLIF(TRIM(t.kind), '')")
    choices.append("''")
    if len(choices) == 1:
        return choices[0]
    return "COALESCE(" + ", ".join(choices) + ")"


def _liked_expr(schema):
    columns = schema["tracks"]
    parts = []
    if "is_liked" in columns:
        parts.append("IFNULL(t.is_liked, 0) = 1")
    if "raw_is_liked" in columns:
        parts.append("lower(COALESCE(t.raw_is_liked, '')) = 'true'")
    return "(" + " OR ".join(parts) + ")" if parts else "0"


def _has_local_audio_expr(schema):
    track_columns = schema["tracks"]
    ui_columns = schema["track_ui"]
    local_columns = schema["local_audio_files"]
    parts = []
    if "has_local_audio" in ui_columns:
        parts.append("IFNULL(tu.has_local_audio, 0) = 1")
    if "local_wav" in track_columns:
        parts.append("TRIM(COALESCE(t.local_wav, '')) != ''")
    if "local_mp3" in track_columns:
        parts.append("TRIM(COALESCE(t.local_mp3, '')) != ''")
    if {"track_id", "is_stem"}.issubset(local_columns):
        parts.append(
            "EXISTS (SELECT 1 FROM local_audio_files laf "
            "WHERE lower(laf.track_id) = lower(t.id) AND IFNULL(laf.is_stem, 0) = 0)"
        )
    return "(" + " OR ".join(parts) + ")" if parts else "0"


def _stem_count_expr(schema):
    ui_columns = schema["track_ui"]
    local_columns = schema["local_audio_files"]
    if "stem_count" in ui_columns:
        return "IFNULL(tu.stem_count, 0)"
    if {"track_id", "is_stem"}.issubset(local_columns):
        return (
            "(SELECT COUNT(*) FROM local_audio_files lafs "
            "WHERE lower(lafs.track_id) = lower(t.id) AND IFNULL(lafs.is_stem, 0) = 1)"
        )
    return "0"


def _style_expr(schema):
    columns = schema["tracks"]
    choices = []
    for name in ("metadata_tags", "style", "display_tags"):
        if name in columns:
            choices.append(f"NULLIF(TRIM(t.{name}), '')")
    choices.append("''")
    if len(choices) == 1:
        return choices[0]
    return "COALESCE(" + ", ".join(choices) + ")"


def _join_ui(schema):
    if "track_id" in schema["track_ui"]:
        return "LEFT JOIN track_ui tu ON lower(tu.track_id) = lower(t.id)"
    return ""


def _base_where(schema):
    track_columns = schema["tracks"]
    ui_columns = schema["track_ui"]
    where = []
    if "library_status" in track_columns:
        where.append("IFNULL(t.library_status, 'active') = 'active'")
    if "kind" in track_columns:
        where.append("IFNULL(t.kind, '') != 'Stem'")
    if "finder_hidden" in track_columns:
        where.append("IFNULL(t.finder_hidden, 0) != 1")
    if "visible_in_finder" in ui_columns:
        where.append("(tu.visible_in_finder IS NULL OR tu.visible_in_finder = 1)")
    return where


def _track_select_sql(schema):
    workspace = _workspace_expr(schema)
    category = _category_expr(schema)
    liked = _liked_expr(schema)
    local_audio = _has_local_audio_expr(schema)
    stem_count = _stem_count_expr(schema)
    style = _style_expr(schema)
    audio_url = (
        "CASE WHEN TRIM(COALESCE(t.audio_url, '')) != '' THEN 1 ELSE 0 END"
        if "audio_url" in schema["tracks"]
        else "0"
    )
    return f"""
        SELECT
            t.id AS track_id,
            COALESCE(t.title, '') AS title,
            {workspace} AS workspace,
            {category} AS category,
            CASE WHEN {liked} THEN 1 ELSE 0 END AS liked,
            CASE WHEN {local_audio} THEN 1 ELSE 0 END AS has_local_audio,
            {stem_count} AS stem_count,
            CASE WHEN {audio_url} THEN 1 ELSE 0 END AS has_suno_audio,
            {style} AS style
        FROM tracks t
        {_join_ui(schema)}
    """


def _public_track(row):
    return {
        "track_id": str(row["track_id"] or ""),
        "title": str(row["title"] or ""),
        "workspace": str(row["workspace"] or ""),
        "category": str(row["category"] or "") or None,
        "liked": bool(row["liked"]),
        "has_local_audio": bool(row["has_local_audio"]),
        "stem_count": int(row["stem_count"] or 0),
        "has_suno_audio": bool(row["has_suno_audio"]),
        "style": str(row["style"] or ""),
    }


# 6.  ------ Local family map (read only) -----

def _load_family_map(map_path=LOCAL_FAMILY_MAP_PATH):
    path = Path(map_path)
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    tracks = data.get("tracks") if isinstance(data, dict) else None
    return tracks if isinstance(tracks, dict) else {}


def get_confirmed_local_family(track_id, map_path=LOCAL_FAMILY_MAP_PATH):
    wanted = _clean_text(track_id, MAX_TRACK_ID_CHARS).casefold()
    if not wanted:
        return {}
    for stored_id, payload in _load_family_map(map_path).items():
        if str(stored_id or "").strip().casefold() != wanted:
            continue
        if not isinstance(payload, dict):
            return {}
        family_title = _clean_text(payload.get("family_title"), 500)
        if not family_title:
            return {}
        return {
            "track_id": str(stored_id or track_id),
            "family_title": family_title,
            "category": _clean_text(payload.get("category"), 80) or None,
            "updated_at": _clean_text(payload.get("updated_at"), 100) or None,
        }
    return {}


# 7.  ------ Whitelisted read-only actions -----

def database_summary(db_path=DB_PATH):
    conn = open_readonly_connection(db_path)
    try:
        schema = _schema(conn)
        join_ui = _join_ui(schema)
        where_parts = _base_where(schema)
        where_sql = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        category = _category_expr(schema)
        liked = _liked_expr(schema)
        local_audio = _has_local_audio_expr(schema)
        stem_count = _stem_count_expr(schema)
        workspace = _workspace_expr(schema)

        row = conn.execute(f"""
            SELECT
                COUNT(*) AS active_main_tracks,
                SUM(CASE WHEN {category} = 'Song' THEN 1 ELSE 0 END) AS songs,
                SUM(CASE WHEN {category} = 'Instrumental' THEN 1 ELSE 0 END) AS instrumentals,
                SUM(CASE WHEN {liked} THEN 1 ELSE 0 END) AS liked,
                SUM(CASE WHEN {local_audio} THEN 1 ELSE 0 END) AS with_local_audio,
                SUM(CASE WHEN {stem_count} > 0 THEN 1 ELSE 0 END) AS with_stems,
                COUNT(DISTINCT NULLIF(TRIM({workspace}), '')) AS workspaces
            FROM tracks t
            {join_ui}
            {where_sql};
        """).fetchone()

        total_db = conn.execute("SELECT COUNT(*) FROM tracks;").fetchone()[0]
        return {
            "total_db_rows": int(total_db or 0),
            "active_main_tracks": int(row["active_main_tracks"] or 0),
            "songs": int(row["songs"] or 0),
            "instrumentals": int(row["instrumentals"] or 0),
            "liked": int(row["liked"] or 0),
            "with_local_audio": int(row["with_local_audio"] or 0),
            "with_stems": int(row["with_stems"] or 0),
            "workspaces": int(row["workspaces"] or 0),
        }
    except sqlite3.Error as error:
        raise LSElzaReadOnlyError(
            "LS database summary query failed.",
            code="database_query_failed",
        ) from error
    finally:
        conn.close()


def search_titles(
    query,
    match_mode="contains",
    workspace="",
    limit=20,
    db_path=DB_PATH,
    family_map_path=LOCAL_FAMILY_MAP_PATH,
):
    query = _clean_text(query, MAX_QUERY_CHARS)
    workspace = _clean_text(workspace, MAX_WORKSPACE_CHARS)
    match_mode = _clean_text(match_mode, 40).lower() or "contains"
    limit = _bounded_limit(limit)

    if not query:
        raise LSElzaReadOnlyError(
            "A title search query is required.",
            code="empty_query",
        )
    if match_mode not in {"exact", "prefix", "contains", "first_word"}:
        raise LSElzaReadOnlyError(
            "Unsupported title match mode.",
            code="unsupported_match_mode",
        )

    conn = open_readonly_connection(db_path)
    try:
        schema = _schema(conn)
        where = _base_where(schema)
        params = []

        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        if match_mode == "exact":
            where.append("lower(TRIM(t.title)) = lower(?)")
            params.append(query)
        elif match_mode == "prefix":
            where.append("lower(TRIM(t.title)) LIKE lower(?) ESCAPE '\\'")
            params.append(escaped + "%")
        elif match_mode == "contains":
            where.append("lower(t.title) LIKE lower(?) ESCAPE '\\'")
            params.append("%" + escaped + "%")
        else:
            where.append("ls_first_word(t.title) = ls_first_word(?)")
            params.append(query)

        if workspace:
            where.append(f"lower(TRIM({_workspace_expr(schema)})) = lower(?)")
            params.append(workspace)

        where_sql = "WHERE " + " AND ".join(where)
        base_sql = _track_select_sql(schema)
        total = conn.execute(
            f"SELECT COUNT(*) FROM tracks t {_join_ui(schema)} {where_sql};",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            base_sql
            + " "
            + where_sql
            + " ORDER BY t.title COLLATE NOCASE, t.id COLLATE NOCASE LIMIT ?;",
            params + [limit],
        ).fetchall()

        tracks = []
        for row in rows:
            item = _public_track(row)
            family = get_confirmed_local_family(item["track_id"], family_map_path)
            item["confirmed_local_family"] = family.get("family_title") or None
            tracks.append(item)

        return {
            "query": query,
            "match_mode": match_mode,
            "workspace": workspace or None,
            "matched_count": int(total or 0),
            "returned_count": len(tracks),
            "limit": limit,
            "tracks": tracks,
        }
    except sqlite3.Error as error:
        raise LSElzaReadOnlyError(
            "LS title search query failed.",
            code="database_query_failed",
        ) from error
    finally:
        conn.close()


def track_summary(track_id, db_path=DB_PATH, family_map_path=LOCAL_FAMILY_MAP_PATH):
    track_id = _clean_text(track_id, MAX_TRACK_ID_CHARS)
    if not track_id:
        raise LSElzaReadOnlyError(
            "A Track ID is required.",
            code="missing_track_id",
        )

    conn = open_readonly_connection(db_path)
    try:
        schema = _schema(conn)
        where = _base_where(schema)
        where.append("lower(t.id) = lower(?)")
        row = conn.execute(
            _track_select_sql(schema) + " WHERE " + " AND ".join(where) + " LIMIT 1;",
            (track_id,),
        ).fetchone()
        if row is None:
            return {
                "found": False,
                "track_id": track_id,
            }

        result = _public_track(row)
        result["found"] = True
        result["confirmed_local_family"] = (
            get_confirmed_local_family(track_id, family_map_path) or None
        )
        return result
    except sqlite3.Error as error:
        raise LSElzaReadOnlyError(
            "LS Track ID query failed.",
            code="database_query_failed",
        ) from error
    finally:
        conn.close()


def local_family_status(
    track_id,
    current_family_title="",
    db_path=DB_PATH,
    family_map_path=LOCAL_FAMILY_MAP_PATH,
):
    current_family_title = _clean_text(current_family_title, 500)
    track = track_summary(track_id, db_path, family_map_path)
    confirmed = track.get("confirmed_local_family") if track.get("found") else None
    confirmed_title = confirmed.get("family_title") if isinstance(confirmed, dict) else ""

    if not track.get("found"):
        status = "track_not_found"
    elif not confirmed_title:
        status = "not_confirmed"
    elif not current_family_title:
        status = "confirmed_but_current_value_missing"
    elif confirmed_title.casefold() == current_family_title.casefold():
        status = "confirmed_match"
    else:
        status = "confirmed_mismatch"

    return {
        "status": status,
        "track_id": _clean_text(track_id, MAX_TRACK_ID_CHARS),
        "track_title": track.get("title") if track.get("found") else None,
        "current_family_title": current_family_title or None,
        "confirmed_family": confirmed,
        "safe_to_assume_membership": status == "confirmed_match",
        "note": (
            "Title similarity alone is not proof of Local family membership; "
            "only the persistent Track ID mapping is treated as confirmation."
        ),
    }


# 8.  ------ Tool definitions and dispatcher -----

def get_readonly_tool_definitions():
    return [
        {
            "type": "function",
            "name": "ls_database_summary",
            "description": "Return aggregate counts from the active LS database.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ls_search_titles",
            "description": (
                "Search or count active LS tracks by title using exact, prefix, "
                "contains, or first_word matching."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "match_mode": {
                        "type": "string",
                        "enum": ["exact", "prefix", "contains", "first_word"],
                    },
                    "workspace": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RESULTS},
                },
                "required": ["query", "match_mode"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ls_track_summary",
            "description": "Return read-only LS facts for one exact Track ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string"},
                },
                "required": ["track_id"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ls_local_family_status",
            "description": (
                "Compare the current Local family title with the persistent "
                "Track ID to Local family confirmation map."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "track_id": {"type": "string"},
                    "current_family_title": {"type": "string"},
                },
                "required": ["track_id"],
                "additionalProperties": False,
            },
        },
    ]


def run_readonly_action(
    action,
    arguments=None,
    db_path=DB_PATH,
    family_map_path=LOCAL_FAMILY_MAP_PATH,
):
    action = _clean_text(action, 80)

    if action == "ls_database_summary":
        _require_arguments(arguments, set())
        return database_summary(db_path)

    if action == "ls_search_titles":
        args = _require_arguments(
            arguments,
            {"query", "match_mode", "workspace", "limit"},
        )
        return search_titles(
            query=args.get("query"),
            match_mode=args.get("match_mode", "contains"),
            workspace=args.get("workspace", ""),
            limit=args.get("limit", 20),
            db_path=db_path,
            family_map_path=family_map_path,
        )

    if action == "ls_track_summary":
        args = _require_arguments(arguments, {"track_id"})
        return track_summary(
            args.get("track_id"),
            db_path=db_path,
            family_map_path=family_map_path,
        )

    if action == "ls_local_family_status":
        args = _require_arguments(
            arguments,
            {"track_id", "current_family_title"},
        )
        return local_family_status(
            track_id=args.get("track_id"),
            current_family_title=args.get("current_family_title", ""),
            db_path=db_path,
            family_map_path=family_map_path,
        )

    raise LSElzaReadOnlyError(
        "Unknown LS Elza read-only action.",
        code="unknown_readonly_action",
    )
