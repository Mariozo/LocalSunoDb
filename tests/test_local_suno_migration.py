import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path

from ls_data import local_suno_migration as migration


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _legacy_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE tracks (
            id TEXT PRIMARY KEY, title TEXT, created_at TEXT,
            workspaceId TEXT, workspaceName TEXT, workspace_id TEXT, workspace TEXT,
            project_id TEXT, audio_url TEXT, image_url TEXT, image_large_url TEXT,
            raw_image_url TEXT, raw_image_large_url TEXT, model_name TEXT,
            major_model_version TEXT, model_version TEXT, metadata_type TEXT,
            metadata_task TEXT, metadata_tags TEXT, metadata_negative_tags TEXT,
            metadata_prompt TEXT, metadata_duration REAL, metadata_has_stem INTEGER,
            metadata_has_vocal INTEGER, metadata_make_instrumental INTEGER,
            metadata_is_remix INTEGER, metadata_studio_project_id TEXT,
            metadata_studio_project_version_id TEXT, metadata_edited_clip_id TEXT,
            metadata_cover_clip_id TEXT, metadata_avg_bpm REAL, metadata_min_bpm REAL,
            metadata_max_bpm REAL, is_liked INTEGER, explicit INTEGER, display_tags TEXT,
            duration TEXT, type TEXT, kind TEXT, prompt TEXT, style TEXT, caption TEXT,
            lyrics TEXT, raw_task TEXT, raw_type TEXT, raw_has_stem TEXT,
            raw_has_vocal TEXT, raw_make_instrumental TEXT, raw_is_remix TEXT,
            raw_is_liked TEXT, raw_display_tags TEXT, raw_tags TEXT, bpm TEXT,
            raw_json TEXT, imported_at TEXT, updated_at TEXT, library_status TEXT,
            finder_hidden INTEGER, finder_hidden_reason TEXT
        );

        CREATE TABLE track_ui (
            track_id TEXT PRIMARY KEY, main_category TEXT,
            main_category_review_group TEXT, user_rating INTEGER,
            user_tags TEXT, user_marks INTEGER, updated_at TEXT
        );

        CREATE TABLE local_audio_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT, track_id TEXT, path TEXT,
            filename TEXT, folder TEXT, extension TEXT, size_bytes INTEGER,
            modified_time TEXT, is_stem INTEGER DEFAULT 0, stem_label TEXT,
            linked_by TEXT, created_at TEXT, updated_at TEXT, suno_clip_id TEXT,
            suno_project_token TEXT, suno_created_at TEXT,
            suno_metadata_source TEXT, suno_metadata_raw TEXT
        );
        """
    )

    raw = {
        "id": "t1",
        "title": "Track 1",
        "metadata": {"task": "cover", "tags": "fusion"},
    }
    conn.execute(
        """
        INSERT INTO tracks (
            id,title,created_at,workspaceId,workspaceName,audio_url,model_name,
            major_model_version,metadata_type,metadata_task,metadata_tags,
            metadata_prompt,metadata_duration,metadata_has_stem,metadata_has_vocal,
            raw_has_vocal,is_liked,display_tags,kind,lyrics,raw_json,updated_at,
            library_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "t1", "Track 1", "2026-09-13T17:30:51Z", "w1", "Studio",
            "https://studio-api.prod.suno.com/api/forbidden", "chirp-hawk", "v6",
            "gen", "cover", "fusion", "prompt", 194.8, 1, 0, "1", 1, "jazz",
            "Song", "lyrics", json.dumps(raw), "2026-09-20T10:00:00", "active",
        ),
    )
    conn.execute(
        """
        INSERT INTO tracks (id,title,kind,raw_json,library_status)
        VALUES (?,?,?,?,?)
        """,
        ("t2", "Track 2", "Song", "{}", "active"),
    )

    conn.execute(
        "INSERT INTO track_ui VALUES (?,?,?,?,?,?,?)",
        ("t1", "Instrumental", "manual_toggle", 4, "#keep", 3, "2026-09-20T10:00:00"),
    )

    for ext in (".wav", "wav"):
        conn.execute(
            """
            INSERT INTO local_audio_files(
                track_id,path,extension,size_bytes,modified_time,is_stem,suno_created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                "t1", r"D:\Lib\Track 1\1\Track 1.wav", ext, 100,
                "2026-09-20T09:00:00", 0, "2026-09-13T17:30:51Z",
            ),
        )

    conn.execute(
        """
        INSERT INTO local_audio_files(
            track_id,path,extension,size_bytes,modified_time,is_stem,stem_label
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            "t1", r"D:\Lib\Track 1\1\Stems\Vocals.wav", ".wav", 40,
            "2026-09-20T09:01:00", 1, "Vocals",
        ),
    )

    conn.execute(
        """
        INSERT INTO local_audio_files(track_id,path,extension,is_stem)
        VALUES (?,?,?,0)
        """,
        ("t1", r"D:\Lib\Ambiguous.wav", ".wav"),
    )
    conn.execute(
        """
        INSERT INTO local_audio_files(track_id,path,extension,is_stem)
        VALUES (?,?,?,0)
        """,
        ("t2", r"D:\Lib\Ambiguous.wav", "wav"),
    )
    conn.commit()
    conn.close()


def test_migration_preserves_source_and_normalizes(tmp_path):
    source = tmp_path / "legacy.db"
    destination = tmp_path / "local_suno.db"
    report_path = tmp_path / "report.json"
    _legacy_db(source)
    before = _sha(source)

    report = migration.migrate(source, destination, report_path)

    assert _sha(source) == before
    assert report["source_unchanged"] is True
    assert report["checks"]["integrity_check"] == "ok"
    assert report["checks"]["foreign_key_errors"] == 0
    assert report["counts"]["duplicate_rows_removed"] == 1
    assert report["counts"]["ambiguous_multi_track_paths"] == 1
    assert report["counts"]["unsafe_audio_urls_cleared"] == 1

    conn = sqlite3.connect(destination)
    assert conn.execute(
        "SELECT audio_url,has_vocal FROM tracks WHERE id='t1'"
    ).fetchone() == (None, 0)
    assert conn.execute("SELECT COUNT(*) FROM track_user").fetchone()[0] == 1
    assert conn.execute(
        "SELECT manual_category FROM track_user WHERE track_id='t1'"
    ).fetchone()[0] == "Instrumental"
    assert conn.execute(
        "SELECT COUNT(*) FROM media_files WHERE path LIKE '%Track 1.wav'"
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT format FROM media_files WHERE path LIKE '%Track 1.wav'"
    ).fetchone()[0] == "wav"
    assert conn.execute(
        "SELECT role FROM media_files WHERE path LIKE '%Ambiguous.wav'"
    ).fetchone()[0] == "unresolved"

    main_variant = conn.execute(
        "SELECT variant_id FROM media_files WHERE path LIKE '%Track 1.wav'"
    ).fetchone()[0]
    stem_variant = conn.execute(
        "SELECT variant_id FROM media_files WHERE path LIKE '%Vocals.wav'"
    ).fetchone()[0]
    assert main_variant == stem_variant

    raw = json.loads(
        conn.execute(
            "SELECT raw_json FROM suno_source_payload WHERE track_id='t1'"
        ).fetchone()[0]
    )
    assert raw["metadata"]["task"] == "cover"
    conn.close()


def test_chronology_prefers_suno(monkeypatch):
    monkeypatch.setattr(
        migration,
        "_filesystem_created_at",
        lambda path: "2026-09-21T12:00:00+03:00",
    )
    file_created, chronology, source = migration._chronology_fields(
        {
            "suno_created_at": "2026-09-13T17:30:51Z",
            "modified_time": "2026-09-20T09:00:00",
        },
        r"D:\Lib\Track.wav",
    )
    assert file_created == "2026-09-21T12:00:00+03:00"
    assert chronology == "2026-09-13T17:30:51Z"
    assert source == "suno_created_at"
