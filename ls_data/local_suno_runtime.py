"""Runtime compatibility views for the canonical Local Suno database.

The canonical database stays clean.  Legacy-shaped objects are TEMP views
created per SQLite connection so existing read paths can be migrated without
re-introducing old persistent tables/columns.
"""
from __future__ import annotations

import sqlite3


def is_local_suno_schema(conn: sqlite3.Connection) -> bool:
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    return {"tracks", "track_user", "track_variants", "media_files"}.issubset(names)


def _path_name(value):
    text = str(value or "").replace("/", "\\").rstrip("\\")
    return text.rsplit("\\", 1)[-1] if text else ""


def _path_parent(value):
    text = str(value or "").replace("/", "\\").rstrip("\\")
    return text.rsplit("\\", 1)[0] if "\\" in text else ""


def configure_legacy_runtime_views(conn: sqlite3.Connection) -> None:
    """Expose legacy read contracts as TEMP views over the canonical schema."""
    if not is_local_suno_schema(conn):
        return

    conn.create_function("ls_path_name", 1, _path_name)
    conn.create_function("ls_path_parent", 1, _path_parent)

    conn.executescript(
        """
        DROP VIEW IF EXISTS temp.tracks;
        DROP VIEW IF EXISTS temp.track_ui;
        DROP VIEW IF EXISTS temp.local_audio_files;

        CREATE TEMP VIEW tracks AS
        SELECT
            t.id,
            t.title,
            t.created_at,
            t.workspace_id,
            t.workspace_name AS workspaceName,
            t.workspace_name AS workspace,
            t.workspace_id AS workspaceId,
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
            t.source_task AS metadata_task,
            t.style_tags AS metadata_tags,
            t.negative_tags AS metadata_negative_tags,
            t.prompt AS metadata_prompt,
            t.duration_seconds AS metadata_duration,
            t.has_stem AS metadata_has_stem,
            t.has_vocal AS metadata_has_vocal,
            t.make_instrumental AS metadata_make_instrumental,
            t.is_remix AS metadata_is_remix,
            t.studio_project_id AS metadata_studio_project_id,
            t.studio_project_version_id AS metadata_studio_project_version_id,
            t.edited_clip_id AS metadata_edited_clip_id,
            t.cover_clip_id AS metadata_cover_clip_id,
            t.avg_bpm AS metadata_avg_bpm,
            t.min_bpm AS metadata_min_bpm,
            t.max_bpm AS metadata_max_bpm,
            t.is_liked,
            CASE WHEN t.is_liked = 1 THEN 'True' ELSE 'False' END AS raw_is_liked,
            t.explicit,
            t.display_tags,
            CASE
                WHEN t.duration_seconds IS NULL THEN ''
                ELSE printf(
                    '%d:%02d',
                    CAST(t.duration_seconds / 60 AS INTEGER),
                    CAST(t.duration_seconds AS INTEGER) % 60
                )
            END AS duration,
            t.source_type AS type,
            t.kind,
            t.prompt,
            t.style_tags AS style,
            t.caption,
            t.lyrics,
            t.source_task AS raw_task,
            t.source_type AS raw_type,
            CAST(t.has_stem AS TEXT) AS raw_has_stem,
            CAST(t.has_vocal AS TEXT) AS raw_has_vocal,
            CAST(t.make_instrumental AS TEXT) AS raw_make_instrumental,
            CAST(t.is_remix AS TEXT) AS raw_is_remix,
            CASE WHEN t.is_liked = 1 THEN 'True' ELSE 'False' END AS raw_is_liked_legacy,
            t.display_tags AS raw_display_tags,
            t.style_tags AS raw_tags,
            CASE WHEN t.avg_bpm IS NULL THEN '' ELSE CAST(t.avg_bpm AS TEXT) END AS bpm,
            (
                SELECT sp.raw_json
                FROM main.suno_source_payload sp
                WHERE sp.track_id = t.id
            ) AS raw_json,
            (
                SELECT sp.captured_at
                FROM main.suno_source_payload sp
                WHERE sp.track_id = t.id
            ) AS imported_at,
            '' AS reaction_type,
            '' AS key,
            0 AS is_stem,
            (
                SELECT mf.path
                FROM main.track_variants tv
                JOIN main.media_files mf ON mf.variant_id = tv.id
                WHERE tv.track_id = t.id
                  AND mf.role = 'main'
                  AND lower(mf.format) = 'mp3'
                ORDER BY
                    COALESCE(tv.variant_no, 2147483647),
                    tv.id,
                    mf.id
                LIMIT 1
            ) AS local_mp3,
            (
                SELECT mf.path
                FROM main.track_variants tv
                JOIN main.media_files mf ON mf.variant_id = tv.id
                WHERE tv.track_id = t.id
                  AND mf.role = 'main'
                  AND lower(mf.format) = 'wav'
                ORDER BY
                    COALESCE(tv.variant_no, 2147483647),
                    tv.id,
                    mf.id
                LIMIT 1
            ) AS local_wav,
            '' AS notes,
            '' AS created_local_at,
            t.library_status,
            t.finder_hidden,
            t.finder_hidden_reason,
            t.updated_at
        FROM main.tracks t;

        CREATE TEMP VIEW track_ui AS
        SELECT
            t.id AS track_id,
            '' AS play_status,
            0 AS play_sort,
            COALESCE(NULLIF(t.source_task, ''), NULLIF(t.kind, ''), '') AS ui_type,
            0 AS ui_type_sort,
            COALESCE(NULLIF(t.style_tags, ''), NULLIF(t.display_tags, ''), '') AS ui_tags,
            COALESCE(t.duration_seconds, 0) AS duration_seconds,
            CASE
                WHEN t.duration_seconds IS NULL THEN ''
                ELSE printf(
                    '%d:%02d',
                    CAST(t.duration_seconds / 60 AS INTEGER),
                    CAST(t.duration_seconds AS INTEGER) % 60
                )
            END AS duration_text,
            CASE
                WHEN t.avg_bpm IS NULL THEN ''
                ELSE CAST(CAST(ROUND(t.avg_bpm) AS INTEGER) AS TEXT)
            END AS bpm_text,
            COALESCE(NULLIF(t.major_model_version, ''), NULLIF(t.model_name, ''), '') AS model_badge,
            (
                SELECT COUNT(*)
                FROM main.track_variants tv
                JOIN main.media_files mf ON mf.variant_id = tv.id
                WHERE tv.track_id = t.id AND mf.role = 'stem'
            ) AS stem_count,
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
                ORDER BY
                    CASE lower(mf.format)
                        WHEN 'wav' THEN 0
                        WHEN 'flac' THEN 1
                        WHEN 'mp3' THEN 2
                        ELSE 9
                    END,
                    COALESCE(tv.variant_no, 2147483647),
                    tv.id,
                    mf.id
                LIMIT 1
            ), '') AS best_local_audio_path,
            CASE WHEN COALESCE(t.finder_hidden, 0) = 1 THEN 0 ELSE 1 END AS visible_in_finder,
            COALESCE(NULLIF(u.manual_category, ''), CASE
                WHEN t.kind IN ('Song', 'Instrumental') THEN t.kind
                ELSE ''
            END) AS main_category,
            '' AS proposed_main_category,
            '' AS main_category_confidence,
            CASE WHEN COALESCE(u.manual_category, '') != '' THEN 'strong' ELSE '' END
                AS main_category_confidence_label,
            CASE WHEN COALESCE(u.manual_category, '') != '' THEN 100 ELSE 0 END
                AS main_category_score,
            '' AS main_category_review_reason,
            CASE WHEN COALESCE(u.manual_category, '') != '' THEN 'manual_toggle' ELSE '' END
                AS main_category_review_group,
            CASE WHEN COALESCE(u.manual_category, '') != ''
                THEN 'manual category toggle in LS' ELSE '' END
                AS main_category_rule,
            '' AS review_group,
            COALESCE(u.rating, 0) AS user_rating,
            COALESCE(u.tags, '') AS user_tags,
            COALESCE(u.marks, 0) AS user_marks,
            COALESCE(u.updated_at, t.updated_at) AS updated_at
        FROM main.tracks t
        LEFT JOIN main.track_user u ON u.track_id = t.id;

        CREATE TEMP VIEW local_audio_files AS
        SELECT
            mf.id,
            tv.track_id,
            mf.path,
            ls_path_name(mf.path) AS filename,
            ls_path_parent(mf.path) AS folder,
            mf.format AS extension,
            mf.size_bytes,
            mf.modified_at AS modified_time,
            CASE WHEN mf.role = 'stem' THEN 1 ELSE 0 END AS is_stem,
            mf.stem_label,
            mf.file_created_at AS created_at,
            mf.modified_at AS updated_at,
            '' AS linked_by,
            mf.suno_clip_id,
            mf.suno_project_token,
            mf.suno_created_at,
            mf.file_created_at_source AS suno_metadata_source,
            mf.embedded_suno_metadata AS suno_metadata_raw
        FROM main.media_files mf
        LEFT JOIN main.track_variants tv ON tv.id = mf.variant_id;
        """
    )
