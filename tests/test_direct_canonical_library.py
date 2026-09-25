import sqlite3
from pathlib import Path

import pytest

from ls_data import database_context, repository
from ls_data.local_suno_migration import create_schema


@pytest.fixture()
def direct_db(tmp_path, monkeypatch):
    db_path = tmp_path / "Data" / "local_suno.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    rows = [
        ("t1", "Alpha Cover", "2026-01-03T10:00:00Z", "w-a", "Studio A", "Cover", "Song", 120.0, 110.0, 1, "jazz bright"),
        ("t2", "Beta Instrumental", "2026-01-02T10:00:00Z", "w-a", "Studio A", "Extend", "Instrumental", 90.0, 95.0, 0, "ambient"),
        ("t3", "Gamma Song", "2026-01-01T10:00:00Z", "w-b", "Studio B", "Cover", "Instrumental", 180.0, 128.0, 0, "rock"),
        ("t4", "Delta Hidden", "2025-12-31T10:00:00Z", "w-b", "Studio B", "Cover", "Song", 60.0, 100.0, 1, "hidden"),
    ]
    for row in rows:
        conn.execute(
            """
            INSERT INTO tracks(
                id,title,created_at,workspace_id,workspace_name,
                model_name,major_model_version,source_type,source_task,
                style_tags,prompt,duration_seconds,avg_bpm,is_liked,
                display_tags,kind,lyrics,library_status,finder_hidden
            ) VALUES (?,?,?,?,?,'chirp-test','v5','gen',?,?,?, ?,?,?,?,?,'lyrics','active',?)
            """,
            (
                row[0], row[1], row[2], row[3], row[4], row[5],
                row[10], "prompt " + row[1], row[7], row[8], row[9],
                row[10], row[6], 1 if row[0] == "t4" else 0,
            ),
        )

    conn.execute(
        "INSERT INTO track_user(track_id,rating,tags,marks,manual_category) VALUES ('t1',5,'#fav, #mix',1,'')"
    )
    conn.execute(
        "INSERT INTO track_user(track_id,rating,tags,marks,manual_category) VALUES ('t2',3,'#mix',3,'Song')"
    )
    conn.execute(
        "INSERT INTO track_user(track_id,rating,tags,marks,manual_category) VALUES ('t3',4,'#rock',5,'')"
    )

    variant = conn.execute(
        """
        INSERT INTO track_variants(track_id,variant_no,label,folder_path,variant_kind)
        VALUES ('t1',1,'1',?,'main')
        """,
        (str(tmp_path),),
    ).lastrowid
    audio_path = tmp_path / "Alpha Cover.wav"
    audio_path.write_bytes(b"RIFF")
    conn.execute(
        """
        INSERT INTO media_files(
            variant_id,path,role,format,stem_label,size_bytes,
            modified_at,file_created_at_source,chronology_at
        ) VALUES (?,?,'main','wav','',4,'2026-01-03T10:00:00Z','modified_time','2026-01-03T10:00:00Z')
        """,
        (variant, str(audio_path)),
    )
    conn.execute(
        """
        INSERT INTO media_files(
            variant_id,path,role,format,stem_label,size_bytes,
            modified_at,file_created_at_source,chronology_at
        ) VALUES (?,?,'stem','wav','Vocals',4,'2026-01-03T10:00:00Z','modified_time','2026-01-03T10:00:00Z')
        """,
        (variant, str(tmp_path / "Alpha Cover (Vocals).wav")),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(repository, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "LEGACY_DB_PATH", tmp_path / "legacy.db")
    monkeypatch.setattr(repository, "REPORTS_DIR", tmp_path / "Reports")
    monkeypatch.setattr(database_context, "DB_PATH", db_path)
    monkeypatch.setattr(database_context, "DATABASE_REGISTRY_PATH", tmp_path / "Data" / "ls_database_registry.json")
    monkeypatch.setattr(repository, "lv_sort_key", lambda value: str(value or "").casefold(), raising=False)
    monkeypatch.setattr(repository, "duration_sort_value", lambda value: float(value or 0), raising=False)
    monkeypatch.setattr(repository, "get_last_imported_suno_ids", lambda: [], raising=False)
    monkeypatch.setattr(repository, "get_track_ids_for_local_family_filter", lambda value: [], raising=False)

    return db_path, audio_path


def ids(rows):
    return [row["id"] for row in rows]


def test_canonical_connection_has_no_legacy_temp_views(direct_db):
    conn = repository.get_canonical_connection()
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_temp_master WHERE type='view'"
            )
        }
    finally:
        conn.close()
    assert "tracks" not in names
    assert "track_ui" not in names
    assert "local_audio_files" not in names


def test_direct_library_filters_use_canonical_fields(direct_db):
    assert ids(repository.search_tracks(limit_value="all")) == ["t1", "t2", "t3"]
    assert ids(repository.search_tracks(query="Gamma", limit_value="all")) == ["t3"]
    assert ids(repository.search_tracks(kind_filter="Cover", limit_value="all")) == ["t1", "t3"]
    assert ids(repository.search_tracks(category_filter=["Song"], limit_value="all")) == ["t1", "t2"]
    assert ids(repository.search_tracks(category_filter=["Instrumental"], limit_value="all")) == ["t3"]
    assert ids(repository.search_tracks(kind_filter="__liked__", limit_value="all")) == ["t1"]
    assert ids(repository.search_tracks(search_marks=True, limit_value="all")) == ["t1", "t2", "t3"]
    assert ids(repository.search_tracks(flag_filter="1,2", limit_value="all")) == ["t2"]
    assert ids(repository.search_tracks(tag_filter="#rock", limit_value="all")) == ["t3"]
    assert ids(repository.search_tracks(workspace=["Studio B"], limit_value="all")) == ["t3"]
    assert ids(repository.search_tracks(local_audio_filter="with", limit_value="all")) == ["t1"]
    assert ids(repository.search_tracks(local_audio_filter="without", limit_value="all")) == ["t2", "t3"]


def test_direct_library_sort_cursor_and_count_match(direct_db):
    assert ids(repository.search_tracks(sort_by="title", sort_dir="asc", limit_value="all")) == ["t1", "t2", "t3"]
    assert ids(repository.search_tracks(sort_by="created", sort_dir="desc", limit_value="all")) == ["t1", "t2", "t3"]
    assert ids(repository.search_tracks(sort_by="duration", sort_dir="asc", limit_value="all")) == ["t2", "t1", "t3"]

    first = repository.search_tracks(sort_by="duration", sort_dir="asc", limit_value="2")
    cursor = repository.encode_track_page_cursor(first[-1], "duration", "asc")
    second = repository.search_tracks(
        sort_by="duration",
        sort_dir="asc",
        limit_value="2",
        cursor_value=cursor,
    )
    assert ids(first) == ["t2", "t1"]
    assert ids(second) == ["t3"]

    cases = [
        {},
        {"query": "Alpha"},
        {"kind_filter": "Cover"},
        {"category_filter": ["Song"]},
        {"flag_filter": "1"},
        {"tag_filter": "#mix"},
        {"workspace": ["Studio A"]},
        {"local_audio_filter": "with"},
    ]
    for kwargs in cases:
        rows = repository.search_tracks(limit_value="all", **kwargs)
        assert repository.count_tracks(**kwargs) == len(rows)


def test_direct_library_returns_canonical_values_and_audio(direct_db):
    _db_path, audio_path = direct_db
    row = repository.search_tracks(query="Alpha", limit_value="all")[0]

    assert row["workspace"] == "Studio A"
    assert row["kind"] == "Cover"
    assert row["type"] == "Cover"
    assert row["main_category"] == "Song"
    assert row["is_liked"] == 1
    assert row["user_rating"] == 5
    assert row["user_tags"] == "#fav, #mix"
    assert row["user_marks"] == 1
    assert row["sort_duration_seconds"] == 120.0
    assert row["bpm"] == "110"
    assert row["model_name"] == "chirp-test"
    assert row["major_model_version"] == "v5"
    assert row["style"] == "jazz bright"
    assert "raw_is_liked" not in row.keys()
    assert "ui_type" not in row.keys()
    assert "local_wav" not in row.keys()
    assert "local_mp3" not in row.keys()

    linked = repository.get_confirmed_local_audio_paths_for_render([row])
    assert linked["t1"] == str(audio_path)
    assert repository.get_stem_counts_for_track_ids(["t1"]) == {"t1": 1}
    assert repository.get_best_local_audio_path_for_track("t1") == str(audio_path)


def test_workspace_and_type_options_are_canonical(direct_db):
    workspaces = {row["workspace"]: row["count"] for row in repository.get_workspaces()}
    types = {row["ui_type"]: row["count"] for row in repository.get_ui_type_counts()}

    assert workspaces == {"Studio A": 2, "Studio B": 1}
    assert types == {"Cover": 2, "Extend": 1}
