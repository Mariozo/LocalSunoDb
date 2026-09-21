import sqlite3
from datetime import datetime

from ls_data import local_suno_migration as migration
from ls_data import repository


def _canonical_db(path, audio_path=""):
    conn = sqlite3.connect(path)
    migration.create_schema(conn)
    conn.execute(
        """
        INSERT INTO tracks(
            id,title,created_at,workspace_id,workspace_name,audio_url,
            model_name,major_model_version,source_type,source_task,
            style_tags,prompt,duration_seconds,avg_bpm,is_liked,
            display_tags,kind,lyrics,library_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "t1", "Track 1", "2026-09-21T10:00:00Z", "w1", "Studio",
            "https://example.invalid/audio", "chirp-test", "v6", "gen",
            "cover", "jazz", "prompt", 125.0, 120.0, 0, "jazz",
            "Song", "lyrics", "active",
        ),
    )
    conn.execute(
        """
        INSERT INTO track_user(track_id,rating,tags,marks,manual_category,updated_at)
        VALUES ('t1',2,'#old',1,'','2026-09-21T10:00:00')
        """
    )
    cur = conn.execute(
        """
        INSERT INTO track_variants(track_id,variant_no,label,folder_path,variant_kind)
        VALUES ('t1',1,'1',?,'main')
        """,
        (str(path.parent),),
    )
    variant_id = cur.lastrowid
    if audio_path:
        conn.execute(
            """
            INSERT INTO media_files(
                variant_id,path,role,format,stem_label,size_bytes,modified_at,
                file_created_at_source,chronology_at
            ) VALUES (?,?,'main','wav','',1,'2026-09-21T10:00:00',
                      'modified_time','2026-09-21T10:00:00')
            """,
            (variant_id, audio_path),
        )
    conn.execute(
        """
        INSERT INTO suno_source_payload(track_id,raw_json,captured_at)
        VALUES ('t1','{"id":"t1"}','2026-09-21T10:00:00')
        """
    )
    conn.commit()
    conn.close()


def _wire_repository(monkeypatch, db_path, tmp_path):
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "LEGACY_DB_PATH", tmp_path / "legacy.db")
    monkeypatch.setattr(repository, "REPORTS_DIR", tmp_path / "Reports")
    monkeypatch.setattr(repository, "BACKUP_DIR", tmp_path / "Backup")
    monkeypatch.setattr(repository, "BASE_DIR", tmp_path)
    monkeypatch.setattr(repository, "lv_sort_key", lambda value: str(value or "").casefold())
    monkeypatch.setattr(
        repository,
        "duration_sort_value",
        lambda value: float(value or 0) if str(value or "").replace(".", "", 1).isdigit() else 0.0,
    )
    monkeypatch.setattr(
        repository,
        "now_iso_local",
        lambda: "2026-09-21T12:00:00+03:00",
    )


def test_canonical_db_exposes_legacy_read_contracts(tmp_path, monkeypatch):
    db_path = tmp_path / "local_suno.db"
    audio_path = tmp_path / "Track 1.wav"
    audio_path.write_bytes(b"x")
    _canonical_db(db_path, str(audio_path))
    _wire_repository(monkeypatch, db_path, tmp_path)

    conn = repository.get_connection()
    try:
        track = conn.execute(
            """
            SELECT id,title,workspaceName,metadata_tags,metadata_duration,
                   raw_json,local_wav
              FROM tracks
             WHERE id='t1'
            """
        ).fetchone()
        ui = conn.execute(
            """
            SELECT track_id,user_rating,user_tags,user_marks,main_category,
                   has_local_audio,best_local_audio_path
              FROM track_ui
             WHERE track_id='t1'
            """
        ).fetchone()
        media = conn.execute(
            """
            SELECT track_id,path,extension,is_stem
              FROM local_audio_files
             WHERE track_id='t1'
            """
        ).fetchone()
    finally:
        conn.close()

    assert track["workspaceName"] == "Studio"
    assert track["metadata_tags"] == "jazz"
    assert track["metadata_duration"] == 125.0
    assert '"id":"t1"' in track["raw_json"]
    assert track["local_wav"] == str(audio_path)
    assert ui["user_rating"] == 2
    assert ui["user_tags"] == "#old"
    assert ui["user_marks"] == 1
    assert ui["main_category"] == "Song"
    assert ui["has_local_audio"] == 1
    assert ui["best_local_audio_path"] == str(audio_path)
    assert media["track_id"] == "t1"
    assert media["extension"] == "wav"
    assert media["is_stem"] == 0


def test_user_writes_land_in_canonical_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "local_suno.db"
    _canonical_db(db_path)
    _wire_repository(monkeypatch, db_path, tmp_path)

    assert repository.update_track_like("t1", True)[0]
    assert repository.update_track_user_review(
        "t1", rating=5, tags="#keep #mix", marks=7
    )[0]
    assert repository.update_track_main_category("t1", "Instrumental")[0]
    assert repository.update_track_title("t1", "Renamed")[0]
    assert repository.update_track_lyrics("t1", "new lyrics")[0]
    assert repository.update_track_style("t1", "fusion")[0]

    conn = sqlite3.connect(db_path)
    try:
        track = conn.execute(
            """
            SELECT title,lyrics,style_tags,prompt,is_liked
              FROM tracks WHERE id='t1'
            """
        ).fetchone()
        user = conn.execute(
            """
            SELECT rating,tags,marks,manual_category
              FROM track_user WHERE track_id='t1'
            """
        ).fetchone()
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()

    assert track == ("Renamed", "new lyrics", "fusion", "fusion", 1)
    assert user == (5, "#keep #mix", 7, "Instrumental")
    assert "track_ui" not in names
    assert "local_audio_files" not in names
