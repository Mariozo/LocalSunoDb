from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

SCHEMA_VERSION = 1
_FORBIDDEN_AUDIO_HOSTS = {"studio-api.prod.suno.com", "studio-api-prod.suno.com"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _first(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            value = row.get(name)
            if value is not None and _text(value) != "":
                return value
    return None


def _bool_or_none(value: Any) -> int | None:
    if value is None or _text(value) == "":
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    text = _text(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return 1
    if text in {"0", "false", "no", "off"}:
        return 0
    return None


def _bool_int(value: Any) -> int:
    parsed = _bool_or_none(value)
    return 0 if parsed is None else parsed


def _float_or_none(value: Any) -> float | None:
    if value is None or _text(value) == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_audio_url(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        host = (urllib.parse.urlparse(text).hostname or "").lower()
    except Exception:
        host = ""
    return None if host in _FORBIDDEN_AUDIO_HOSTS else text


def _normalize_format(path: str, extension: Any) -> str:
    ext = _text(extension).lower().lstrip(".")
    return ext or PureWindowsPath(path).suffix.lower().lstrip(".")


def _norm_path(value: Any) -> str:
    return _text(value).replace("/", "\\").rstrip("\\").casefold()


def _variant_folder(path: str, role: str) -> str:
    folder = PureWindowsPath(path).parent
    if role == "stem" and folder.name.casefold() == "stems":
        folder = folder.parent
    return str(folder)


def _variant_number(path: str, role: str) -> int | None:
    folder = PureWindowsPath(_variant_folder(path, role))
    try:
        value = int(folder.name)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _filesystem_created_at(path: str) -> str:
    # On Windows st_ctime is file creation time; on POSIX it is inode-change time.
    if os.name != "nt":
        return ""
    try:
        ts = Path(path).stat().st_ctime
    except OSError:
        return ""
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def _chronology_fields(row: dict[str, Any], path: str) -> tuple[str, str, str]:
    file_created = _filesystem_created_at(path)
    suno_created = _text(row.get("suno_created_at"))
    modified = _text(row.get("modified_time"))
    if suno_created:
        return file_created, suno_created, "suno_created_at"
    if file_created:
        return file_created, file_created, "filesystem_created_at"
    if modified:
        return file_created, modified, "modified_time"
    return file_created, "", "none"


def _source_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone() is not None


def _rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not _table_exists(conn, table):
        return []
    return [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')]


def create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE tracks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT,
            workspace_id TEXT,
            workspace_name TEXT,
            project_id TEXT,
            audio_url TEXT,
            image_url TEXT,
            image_large_url TEXT,
            model_name TEXT,
            major_model_version TEXT,
            source_type TEXT,
            source_task TEXT,
            style_tags TEXT,
            negative_tags TEXT,
            prompt TEXT,
            duration_seconds REAL,
            has_stem INTEGER NOT NULL DEFAULT 0 CHECK(has_stem IN (0,1)),
            has_vocal INTEGER CHECK(has_vocal IN (0,1) OR has_vocal IS NULL),
            make_instrumental INTEGER CHECK(make_instrumental IN (0,1) OR make_instrumental IS NULL),
            is_remix INTEGER CHECK(is_remix IN (0,1) OR is_remix IS NULL),
            studio_project_id TEXT,
            studio_project_version_id TEXT,
            edited_clip_id TEXT,
            cover_clip_id TEXT,
            avg_bpm REAL,
            min_bpm REAL,
            max_bpm REAL,
            is_liked INTEGER NOT NULL DEFAULT 0 CHECK(is_liked IN (0,1)),
            explicit INTEGER NOT NULL DEFAULT 0 CHECK(explicit IN (0,1)),
            display_tags TEXT,
            kind TEXT,
            caption TEXT,
            lyrics TEXT,
            library_status TEXT NOT NULL DEFAULT 'active',
            finder_hidden INTEGER NOT NULL DEFAULT 0 CHECK(finder_hidden IN (0,1)),
            finder_hidden_reason TEXT,
            updated_at TEXT
        );

        CREATE TABLE track_user (
            track_id TEXT PRIMARY KEY,
            rating INTEGER NOT NULL DEFAULT 0,
            tags TEXT NOT NULL DEFAULT '',
            marks INTEGER NOT NULL DEFAULT 0,
            manual_category TEXT NOT NULL DEFAULT '',
            updated_at TEXT,
            FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
        );

        CREATE TABLE track_variants (
            id INTEGER PRIMARY KEY,
            track_id TEXT NOT NULL,
            variant_no INTEGER,
            folder_path TEXT NOT NULL DEFAULT '',
            variant_kind TEXT NOT NULL DEFAULT 'main'
                CHECK(variant_kind IN ('main','stems_only')),
            FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
        );

        CREATE TABLE media_files (
            id INTEGER PRIMARY KEY,
            variant_id INTEGER,
            path TEXT NOT NULL COLLATE NOCASE UNIQUE,
            role TEXT NOT NULL CHECK(role IN ('main','stem','unresolved')),
            format TEXT NOT NULL DEFAULT '',
            stem_label TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER,
            modified_at TEXT,
            file_created_at TEXT,
            chronology_at TEXT,
            chronology_source TEXT NOT NULL DEFAULT 'none',
            suno_clip_id TEXT,
            suno_project_token TEXT,
            suno_created_at TEXT,
            embedded_suno_metadata TEXT,
            FOREIGN KEY(variant_id) REFERENCES track_variants(id) ON DELETE SET NULL
        );

        CREATE TABLE suno_source_payload (
            track_id TEXT PRIMARY KEY,
            raw_json TEXT NOT NULL,
            captured_at TEXT,
            FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
        );

        CREATE TABLE local_playlists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE local_playlist_items (
            playlist_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            added_at TEXT NOT NULL,
            PRIMARY KEY (playlist_id, track_id),
            FOREIGN KEY(playlist_id) REFERENCES local_playlists(id) ON DELETE CASCADE,
            FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE
        );

        CREATE INDEX idx_tracks_created_at ON tracks(created_at, id);
        CREATE INDEX idx_tracks_workspace ON tracks(workspace_name, id);
        CREATE INDEX idx_variants_track ON track_variants(track_id, id);
        CREATE INDEX idx_media_variant ON media_files(variant_id, role);
        CREATE UNIQUE INDEX idx_media_one_main_per_variant
            ON media_files(variant_id) WHERE role='main';
        CREATE INDEX idx_media_chronology ON media_files(chronology_at, id);
        CREATE INDEX idx_media_suno_clip ON media_files(suno_clip_id);
        CREATE INDEX idx_playlist_items_position
            ON local_playlist_items(playlist_id, position);
        """
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _migrate_tracks(
    source: sqlite3.Connection,
    dest: sqlite3.Connection,
    report: dict[str, Any],
) -> set[str]:
    ids: set[str] = set()
    raw_count = invalid_raw = unsafe_audio_urls_cleared = 0

    for row in _rows(source, "tracks"):
        track_id = _text(row.get("id"))
        if not track_id:
            report["issues"].append({"type": "track_missing_id"})
            continue

        ids.add(track_id.casefold())
        original_audio = _text(row.get("audio_url"))
        safe_audio = _safe_audio_url(original_audio)
        if original_audio and not safe_audio:
            unsafe_audio_urls_cleared += 1

        dest.execute(
            """
            INSERT INTO tracks (
                id,title,created_at,workspace_id,workspace_name,project_id,audio_url,
                image_url,image_large_url,model_name,major_model_version,source_type,
                source_task,style_tags,negative_tags,prompt,duration_seconds,has_stem,
                has_vocal,make_instrumental,is_remix,studio_project_id,
                studio_project_version_id,edited_clip_id,cover_clip_id,avg_bpm,min_bpm,
                max_bpm,is_liked,explicit,display_tags,kind,caption,lyrics,library_status,
                finder_hidden,finder_hidden_reason,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                track_id,
                _text(row.get("title")),
                _text(row.get("created_at")) or None,
                _text(_first(row, "workspace_id", "workspaceId")) or None,
                _text(_first(row, "workspaceName", "workspace")) or None,
                _text(row.get("project_id")) or None,
                safe_audio,
                _text(_first(row, "image_url", "raw_image_url")) or None,
                _text(_first(row, "image_large_url", "raw_image_large_url")) or None,
                _text(row.get("model_name")) or None,
                _text(_first(row, "major_model_version", "model_version")) or None,
                _text(_first(row, "metadata_type", "raw_type", "type")) or None,
                _text(_first(row, "metadata_task", "raw_task")) or None,
                _text(_first(row, "metadata_tags", "style", "raw_tags")) or None,
                _text(row.get("metadata_negative_tags")) or None,
                _text(_first(row, "metadata_prompt", "prompt")) or None,
                _float_or_none(_first(row, "metadata_duration", "duration")),
                _bool_int(_first(row, "metadata_has_stem", "raw_has_stem")),
                _bool_or_none(_first(row, "metadata_has_vocal", "raw_has_vocal")),
                _bool_or_none(_first(
                    row, "metadata_make_instrumental", "raw_make_instrumental"
                )),
                _bool_or_none(_first(row, "metadata_is_remix", "raw_is_remix")),
                _text(row.get("metadata_studio_project_id")) or None,
                _text(row.get("metadata_studio_project_version_id")) or None,
                _text(row.get("metadata_edited_clip_id")) or None,
                _text(row.get("metadata_cover_clip_id")) or None,
                _float_or_none(_first(row, "metadata_avg_bpm", "bpm")),
                _float_or_none(row.get("metadata_min_bpm")),
                _float_or_none(row.get("metadata_max_bpm")),
                _bool_int(_first(row, "is_liked", "raw_is_liked")),
                _bool_int(row.get("explicit")),
                _text(_first(row, "display_tags", "raw_display_tags")) or None,
                _text(row.get("kind")) or None,
                _text(row.get("caption")) or None,
                str(row.get("lyrics") or ""),
                _text(row.get("library_status")) or "active",
                _bool_int(row.get("finder_hidden")),
                _text(row.get("finder_hidden_reason")) or None,
                _text(row.get("updated_at")) or None,
            ),
        )

        raw = row.get("raw_json")
        if raw is not None and str(raw) != "":
            raw_text = str(raw)
            raw_count += 1
            try:
                json.loads(raw_text)
            except Exception:
                invalid_raw += 1
            dest.execute(
                """
                INSERT INTO suno_source_payload(track_id,raw_json,captured_at)
                VALUES (?,?,?)
                """,
                (
                    track_id,
                    raw_text,
                    _text(_first(row, "updated_at", "imported_at", "created_at"))
                    or None,
                ),
            )

    report["counts"].update(
        tracks=len(ids),
        raw_payloads=raw_count,
        invalid_raw_payloads_preserved=invalid_raw,
        unsafe_audio_urls_cleared=unsafe_audio_urls_cleared,
    )
    return ids


def _migrate_track_user(
    source: sqlite3.Connection,
    dest: sqlite3.Connection,
    track_ids: set[str],
    report: dict[str, Any],
) -> None:
    count = skipped = 0

    for row in _rows(source, "track_ui"):
        track_id = _text(row.get("track_id"))
        if not track_id or track_id.casefold() not in track_ids:
            skipped += 1
            continue

        rating = int(row.get("user_rating") or 0)
        tags = _text(row.get("user_tags"))
        marks = int(row.get("user_marks") or 0)
        manual_category = (
            _text(row.get("main_category"))
            if _text(row.get("main_category_review_group")) == "manual_toggle"
            else ""
        )

        if rating == 0 and not tags and marks == 0 and not manual_category:
            continue

        dest.execute(
            """
            INSERT INTO track_user(
                track_id,rating,tags,marks,manual_category,updated_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                track_id,
                rating,
                tags,
                marks,
                manual_category,
                _text(row.get("updated_at")) or None,
            ),
        )
        count += 1

    report["counts"]["track_user"] = count
    if skipped:
        report["issues"].append(
            {"type": "track_ui_missing_track", "count": skipped}
        )


def _merge_media_rows(group: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        group,
        key=lambda r: (_text(r.get("updated_at")), int(r.get("id") or 0)),
        reverse=True,
    )
    result = dict(ordered[0])
    for row in ordered[1:]:
        for key, value in row.items():
            if (
                result.get(key) is None or _text(result.get(key)) == ""
            ) and value is not None and _text(value) != "":
                result[key] = value
    return result


def _insert_variant(
    dest: sqlite3.Connection,
    track_id: str,
    path: str,
    kind: str,
    role: str,
) -> int:
    cur = dest.execute(
        """
        INSERT INTO track_variants(
            track_id,variant_no,folder_path,variant_kind
        ) VALUES (?,?,?,?)
        """,
        (
            track_id,
            _variant_number(path, role),
            _variant_folder(path, role),
            kind,
        ),
    )
    return int(cur.lastrowid)


def _insert_media(
    dest: sqlite3.Connection,
    row: dict[str, Any],
    path: str,
    role: str,
    variant_id: int | None,
) -> None:
    file_created, chronology_at, chronology_source = _chronology_fields(row, path)
    dest.execute(
        """
        INSERT INTO media_files (
            variant_id,path,role,format,stem_label,size_bytes,modified_at,
            file_created_at,chronology_at,chronology_source,suno_clip_id,
            suno_project_token,suno_created_at,embedded_suno_metadata
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            variant_id,
            path,
            role,
            _normalize_format(path, row.get("extension")),
            _text(row.get("stem_label")) if role == "stem" else "",
            row.get("size_bytes"),
            _text(row.get("modified_time")) or None,
            file_created or None,
            chronology_at or None,
            chronology_source,
            _text(row.get("suno_clip_id")) or None,
            _text(row.get("suno_project_token")) or None,
            _text(row.get("suno_created_at")) or None,
            str(row.get("suno_metadata_raw") or "") or None,
        ),
    )


def _migrate_media(
    source: sqlite3.Connection,
    dest: sqlite3.Connection,
    track_ids: set[str],
    report: dict[str, Any],
) -> None:
    original = _rows(source, "local_audio_files")
    by_path: dict[str, list[dict[str, Any]]] = {}
    empty_path = 0

    for row in original:
        path = _text(row.get("path"))
        if not path:
            empty_path += 1
            continue
        by_path.setdefault(_norm_path(path), []).append(row)

    physical: list[dict[str, Any]] = []
    duplicate_rows_removed = 0
    path_issues: list[dict[str, Any]] = []
    unresolved_keys: set[str] = set()

    for group in by_path.values():
        merged = _merge_media_rows(group)
        merged["_source_ids"] = [int(r.get("id") or 0) for r in group]
        tracks = sorted(
            {_text(r.get("track_id")) for r in group if _text(r.get("track_id"))},
            key=str.casefold,
        )
        roles = sorted({int(r.get("is_stem") or 0) for r in group})
        key = _norm_path(merged.get("path"))

        if len(tracks) > 1:
            unresolved_keys.add(key)
            path_issues.append({
                "type": "path_multi_track",
                "path": _text(merged.get("path")),
                "track_ids": tracks,
                "source_row_ids": merged["_source_ids"],
            })
        elif len(roles) > 1:
            unresolved_keys.add(key)
            path_issues.append({
                "type": "path_role_conflict",
                "path": _text(merged.get("path")),
                "track_ids": tracks,
                "source_row_ids": merged["_source_ids"],
            })
        elif len(group) > 1:
            duplicate_rows_removed += len(group) - 1

        physical.append(merged)

    if empty_path:
        report["issues"].append(
            {"type": "empty_media_path", "count": empty_path}
        )

    mains_by_track: dict[str, list[dict[str, Any]]] = {}
    stems_by_track: dict[str, list[dict[str, Any]]] = {}
    unresolved: list[dict[str, Any]] = []

    for row in physical:
        path = _text(row.get("path"))
        if _norm_path(path) in unresolved_keys:
            _insert_media(dest, row, path, "unresolved", None)
            continue

        track_id = _text(row.get("track_id"))
        if not track_id:
            unresolved.append({
                "type": "media_without_track",
                "path": path,
                "source_row_ids": row["_source_ids"],
            })
            _insert_media(dest, row, path, "unresolved", None)
            continue

        if track_id.casefold() not in track_ids:
            unresolved.append({
                "type": "media_missing_track",
                "path": path,
                "track_id": track_id,
                "source_row_ids": row["_source_ids"],
            })
            _insert_media(dest, row, path, "unresolved", None)
            continue

        target = (
            stems_by_track
            if int(row.get("is_stem") or 0) == 1
            else mains_by_track
        )
        target.setdefault(track_id, []).append(row)

    track_variants: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for track_id, mains in sorted(
        mains_by_track.items(), key=lambda kv: kv[0].casefold()
    ):
        for row in sorted(mains, key=lambda r: _norm_path(r.get("path"))):
            path = _text(row.get("path"))
            variant_id = _insert_variant(dest, track_id, path, "main", "main")
            track_variants.setdefault(track_id, []).append((variant_id, row))
            _insert_media(dest, row, path, "main", variant_id)

    stems_only: dict[tuple[str, str], int] = {}
    ambiguous_stems = 0

    for track_id, stems in sorted(
        stems_by_track.items(), key=lambda kv: kv[0].casefold()
    ):
        mains = track_variants.get(track_id, [])
        for row in sorted(stems, key=lambda r: _norm_path(r.get("path"))):
            path = _text(row.get("path"))
            stem_folder = _norm_path(_variant_folder(path, "stem"))
            matches = [
                (variant_id, main_row)
                for variant_id, main_row in mains
                if _norm_path(
                    _variant_folder(_text(main_row.get("path")), "main")
                ) == stem_folder
            ]

            variant_id: int | None = None
            if len(matches) == 1:
                variant_id = matches[0][0]
            elif len(mains) == 1:
                variant_id = mains[0][0]
            elif not mains:
                key = (track_id.casefold(), stem_folder)
                if key not in stems_only:
                    stems_only[key] = _insert_variant(
                        dest, track_id, path, "stems_only", "stem"
                    )
                variant_id = stems_only[key]
            else:
                ambiguous_stems += 1
                unresolved.append({
                    "type": "stem_variant_ambiguous",
                    "path": path,
                    "track_id": track_id,
                    "candidate_main_paths": [
                        _text(main.get("path")) for _, main in mains
                    ],
                    "source_row_ids": row["_source_ids"],
                })

            _insert_media(
                dest,
                row,
                path,
                "stem" if variant_id is not None else "unresolved",
                variant_id,
            )

    report["issues"].extend(path_issues)
    report["issues"].extend(unresolved)
    report["counts"].update(
        source_local_audio_rows=len(original),
        unique_physical_paths=len(physical),
        duplicate_rows_removed=duplicate_rows_removed,
        ambiguous_multi_track_paths=sum(
            1 for item in path_issues if item["type"] == "path_multi_track"
        ),
        path_role_conflicts=sum(
            1 for item in path_issues if item["type"] == "path_role_conflict"
        ),
        unresolved_media=dest.execute(
            "SELECT COUNT(*) FROM media_files WHERE role='unresolved'"
        ).fetchone()[0],
        track_variants=dest.execute(
            "SELECT COUNT(*) FROM track_variants"
        ).fetchone()[0],
        media_files=dest.execute(
            "SELECT COUNT(*) FROM media_files"
        ).fetchone()[0],
        main_media=dest.execute(
            "SELECT COUNT(*) FROM media_files WHERE role='main'"
        ).fetchone()[0],
        stem_media=dest.execute(
            "SELECT COUNT(*) FROM media_files WHERE role='stem'"
        ).fetchone()[0],
        stems_only_variants=dest.execute(
            """
            SELECT COUNT(*) FROM track_variants
            WHERE variant_kind='stems_only'
            """
        ).fetchone()[0],
        ambiguous_stems=ambiguous_stems,
    )


def _migrate_playlists(
    source: sqlite3.Connection,
    dest: sqlite3.Connection,
    track_ids: set[str],
    report: dict[str, Any],
) -> None:
    playlists = _rows(source, "local_playlists")
    items = _rows(source, "local_playlist_items")

    for row in playlists:
        dest.execute(
            """
            INSERT INTO local_playlists(id,name,created_at,updated_at)
            VALUES (?,?,?,?)
            """,
            (
                _text(row.get("id")),
                _text(row.get("name")),
                _text(row.get("created_at")),
                _text(row.get("updated_at")),
            ),
        )

    skipped = 0
    for row in items:
        track_id = _text(row.get("track_id"))
        if track_id.casefold() not in track_ids:
            skipped += 1
            continue

        dest.execute(
            """
            INSERT INTO local_playlist_items(
                playlist_id,track_id,position,added_at
            ) VALUES (?,?,?,?)
            """,
            (
                _text(row.get("playlist_id")),
                track_id,
                int(row.get("position") or 0),
                _text(row.get("added_at")),
            ),
        )

    report["counts"]["local_playlists"] = len(playlists)
    report["counts"]["local_playlist_items"] = len(items) - skipped
    if skipped:
        report["issues"].append(
            {"type": "playlist_item_missing_track", "count": skipped}
        )


def migrate(
    source_path: str | Path,
    destination_path: str | Path,
    report_path: str | Path | None = None,
    replace_output: bool = False,
) -> dict[str, Any]:
    source_path = Path(source_path).resolve()
    destination_path = Path(destination_path).resolve()

    if source_path == destination_path:
        raise ValueError("Source and destination must be different files")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    if destination_path.exists():
        if not replace_output:
            raise FileExistsError(destination_path)
        destination_path.unlink()

    before_hash = _sha256(source_path)
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "migrated_at": _now_utc(),
        "source_path": str(source_path),
        "destination_path": str(destination_path),
        "source_sha256_before": before_hash,
        "source_sha256_after": "",
        "source_unchanged": False,
        "counts": {},
        "issues": [],
        "legacy_not_migrated": [
            "workspace_links",
            "sf_category_intent_audit",
            "sync_log",
            "schema_info",
            "track_ui derived/cache fields",
            "local_audio_files.linked_by",
            "file move/reconstruction reports",
        ],
        "checks": {},
    }

    source = _source_connect(source_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    dest = sqlite3.connect(destination_path)

    try:
        create_schema(dest)
        dest.execute("BEGIN IMMEDIATE")
        track_ids = _migrate_tracks(source, dest, report)
        _migrate_track_user(source, dest, track_ids, report)
        _migrate_media(source, dest, track_ids, report)
        _migrate_playlists(source, dest, track_ids, report)
        dest.commit()

        integrity = dest.execute("PRAGMA integrity_check").fetchone()[0]
        fk_rows = [
            tuple(row)
            for row in dest.execute("PRAGMA foreign_key_check").fetchall()
        ]
        report["checks"].update(
            integrity_check=integrity,
            foreign_key_errors=len(fk_rows),
            foreign_key_error_rows=fk_rows,
            foreign_keys_enabled=(
                int(dest.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
            ),
            destination_user_version=int(
                dest.execute("PRAGMA user_version").fetchone()[0]
            ),
        )
    finally:
        dest.close()
        source.close()

    after_hash = _sha256(source_path)
    report["source_sha256_after"] = after_hash
    report["source_unchanged"] = before_hash == after_hash
    report["destination_sha256"] = _sha256(destination_path)

    if report_path is not None:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create local_suno.db from legacy suno_finder_v4.db without "
            "modifying the source DB or audio files."
        )
    )
    parser.add_argument("source_db")
    parser.add_argument("destination_db")
    parser.add_argument("--report")
    parser.add_argument("--replace-output", action="store_true")
    args = parser.parse_args()

    report = migrate(
        args.source_db,
        args.destination_db,
        args.report,
        args.replace_output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    return (
        0
        if report["checks"].get("integrity_check") == "ok"
        and report["checks"].get("foreign_key_errors") == 0
        and report.get("source_unchanged")
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
