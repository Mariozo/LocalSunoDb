import sqlite3
import wave
from pathlib import Path

import pytest

from ls_data import database_context, repository
from ls_data.local_suno_migration import create_schema


@pytest.fixture()
def canonical_library(tmp_path, monkeypatch):
    data_dir = tmp_path / "Data"
    db_path = data_dir / "local_suno.db"
    registry_path = data_dir / "ls_database_registry.json"
    reports_dir = tmp_path / "Reports"
    legacy_path = tmp_path / "legacy.db"
    media_dir = tmp_path / "media"

    data_dir.mkdir(parents=True)
    media_dir.mkdir(parents=True)

    monkeypatch.setattr(database_context, "DATABASE_REGISTRY_PATH", registry_path)
    monkeypatch.setattr(database_context, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(repository, "LEGACY_DB_PATH", legacy_path)
    monkeypatch.setattr(
        repository,
        "lv_sort_key",
        lambda value: str(value or "").casefold(),
        raising=False,
    )
    monkeypatch.setattr(
        repository,
        "duration_sort_value",
        lambda value: float(value or 0),
        raising=False,
    )

    conn = sqlite3.connect(db_path)
    create_schema(conn)

    rows = [
        {
            "id": "alpha",
            "title": "Alpha Song",
            "created": "2026-09-20T10:00:00Z",
            "workspace": "Studio A",
            "task": "Cover",
            "kind": "Song",
            "liked": 1,
            "duration": 210.0,
            "bpm": 120.0,
            "style": "rock live",
            "model": "chirp-crow",
            "major": "v5.5",
            "rating": 5,
            "tags": "#rock, #live",
            "marks": 5,
            "manual": "",
            "local": True,
            "stem": True,
        },
        {
            "id": "beta",
            "title": "Beta Instrumental",
            "created": "2026-09-21T10:00:00Z",
            "workspace": "Studio B",
            "task": "Generate",
            "kind": "Instrumental",
            "liked": 0,
            "duration": 120.0,
            "bpm": 90.0,
            "style": "ambient",
            "model": "chirp",
            "major": "v5",
            "rating": 2,
            "tags": "#ambient",
            "marks": 2,
            "manual": "",
            "local": False,
            "stem": False,
        },
        {
            "id": "gamma",
            "title": "Gamma Override",
            "created": "2026-09-22T10:00:00Z",
            "workspace": "Studio A",
            "task": "Cover",
            "kind": "Song",
            "liked": 1,
            "duration": 330.0,
            "bpm": 130.0,
            "style": "jazz",
            "model": "chirp-crow",
            "major": "v5.5",
            "rating": 4,
            "tags": "#jazz, #live",
            "marks": 1,
            "manual": "Instrumental",
            "local": True,
            "stem": False,
        },
        {
            "id": "delta",
            "title": "Delta Song",
            "created": "2026-09-23T10:00:00Z",
            "workspace": "Studio C",
            "task": "Extend",
            "kind": "Song",
            "liked": 0,
            "duration": 60.0,
            "bpm": 110.0,
            "style": "folk",
            "model": "chirp",
            "major": "v4",
            "rating": 0,
            "tags": "",
            "marks": 0,
            "manual": "",
            "local": False,
            "stem": False,
        },
    ]

    for row in rows:
        conn.execute(
            """
            INSERT INTO tracks(
                id,title,created_at,workspace_id,workspace_name,audio_url,
                image_url,image_large_url,model_name,major_model_version,
                source_type,source_task,style_tags,prompt,duration_seconds,
                avg_bpm,is_liked,display_tags,kind,lyrics,library_status,
                finder_hidden
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                row["id"],
                row["title"],
                row["created"],
                "ws-" + row["workspace"].replace(" ", "-").lower(),
                row["workspace"],
                "https://example.invalid/" + row["id"] + ".mp3",
                "",
                "",
                row["model"],
                row["major"],
                "gen",
                row["task"],
                row["style"],
                "prompt " + row["title"],
                row["duration"],
                row["bpm"],
                row["liked"],
                row["style"],
                row["kind"],
                "lyrics " + row["title"],
                "active",
            ),
        )
        conn.execute(
            """
            INSERT INTO track_user(track_id,rating,tags,marks,manual_category,updated_at)
            VALUES (?,?,?,?,?,'2026-09-24T10:00:00Z')
            """,
            (
                row["id"],
                row["rating"],
                row["tags"],
                row["marks"],
                row["manual"],
            ),
        )

        if row["local"]:
            wav_path = media_dir / (row["id"] + ".wav")
            with wave.open(str(wav_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(8000)
                wav_file.writeframes(b"\x00\x00" * 800)
            variant = conn.execute(
                """
                INSERT INTO track_variants(track_id,variant_no,label,folder_path,variant_kind)
                VALUES (?,1,'1',?,'main')
                """,
                (row["id"], str(media_dir)),
            )
            conn.execute(
                """
                INSERT INTO media_files(
                    variant_id,path,role,format,stem_label,size_bytes,modified_at,
                    file_created_at_source,chronology_at
                ) VALUES (?,?,'main','wav','',1,'2026-09-24T10:00:00Z',
                          'modified_time','2026-09-24T10:00:00Z')
                """,
                (variant.lastrowid, str(wav_path)),
            )
            if row["stem"]:
                stem_path = media_dir / (row["id"] + " (Vocals).wav")
                stem_path.write_bytes(b"stem")
                conn.execute(
                    """
                    INSERT INTO media_files(
                        variant_id,path,role,format,stem_label,size_bytes,modified_at,
                        file_created_at_source,chronology_at
                    ) VALUES (?,?,'stem','wav','Vocals',1,'2026-09-24T10:00:00Z',
                              'modified_time','2026-09-24T10:00:00Z')
                    """,
                    (variant.lastrowid, str(stem_path)),
                )

    # Hidden rows must never leak into Direct Library.
    conn.execute(
        """
        INSERT INTO tracks(id,title,workspace_name,source_task,kind,library_status,finder_hidden)
        VALUES ('hidden','Hidden Track','Studio A','Cover','Song','active',1)
        """
    )
    conn.commit()
    conn.close()

    return {"db": db_path, "media": media_dir}


def ids(rows):
    return [str(row["id"]) for row in rows]


def test_canonical_connection_has_no_legacy_temp_views(canonical_library, monkeypatch):
    monkeypatch.setattr(
        repository,
        "configure_legacy_runtime_views",
        lambda _conn: (_ for _ in ()).throw(AssertionError("legacy view configured")),
    )

    conn = repository.get_canonical_connection()
    try:
        temp_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_temp_master WHERE type IN ('table','view')"
            ).fetchall()
        }
        assert "tracks" not in temp_names
        assert "track_ui" not in temp_names
        assert "local_audio_files" not in temp_names
        assert conn.execute("SELECT COUNT(*) FROM main.tracks").fetchone()[0] == 5
    finally:
        conn.close()


def test_direct_library_filters_use_canonical_columns(canonical_library, monkeypatch):
    monkeypatch.setattr(
        repository,
        "configure_legacy_runtime_views",
        lambda _conn: (_ for _ in ()).throw(AssertionError("legacy view configured")),
    )

    assert set(ids(repository.search_tracks(limit_value="all"))) == {
        "alpha", "beta", "gamma", "delta"
    }
    assert ids(repository.search_tracks(query="Alpha", limit_value="all")) == ["alpha"]

    # Category is manual_category, then tracks.kind.
    assert set(ids(repository.search_tracks(
        category_filter=["Instrumental"], limit_value="all"
    ))) == {"beta", "gamma"}
    assert set(ids(repository.search_tracks(
        category_filter=["Song"], limit_value="all"
    ))) == {"alpha", "delta"}

    # Type is source_task only. Gamma remains Cover although its category is Instrumental.
    assert set(ids(repository.search_tracks(
        kind_filter="Cover", limit_value="all"
    ))) == {"alpha", "gamma"}
    assert repository.search_tracks(kind_filter="Song", limit_value="all") == []

    assert set(ids(repository.search_tracks(
        kind_filter="__liked__", limit_value="all"
    ))) == {"alpha", "gamma"}
    assert set(ids(repository.search_tracks(
        flag_filter="1", limit_value="all"
    ))) == {"alpha", "gamma"}
    assert ids(repository.search_tracks(
        flag_filter="1,4", limit_value="all"
    )) == ["alpha"]
    assert set(ids(repository.search_tracks(
        tag_filter="#live", limit_value="all"
    ))) == {"alpha", "gamma"}
    assert set(ids(repository.search_tracks(
        workspace=["Studio A"], limit_value="all"
    ))) == {"alpha", "gamma"}
    assert set(ids(repository.search_tracks(
        local_audio_filter="with", limit_value="all"
    ))) == {"alpha", "gamma"}
    assert set(ids(repository.search_tracks(
        local_audio_filter="without", limit_value="all"
    ))) == {"beta", "delta"}

    row = repository.search_tracks(query="Gamma", limit_value="all")[0]
    assert row["workspace"] == "Studio A"
    assert row["kind"] == "Cover"
    assert row["main_category"] == "Instrumental"
    assert row["raw_is_liked"] == "True"
    assert row["user_rating"] == 4
    assert row["user_tags"] == "#jazz, #live"
    assert row["user_marks"] == 1
    assert row["duration"] == "5:30"
    assert row["bpm"] == "130"
    assert row["model_version"] == "v5.5"
    assert row["style"] == "jazz"


def test_direct_library_sort_cursor_count_and_local_media(canonical_library, monkeypatch):
    monkeypatch.setattr(
        repository,
        "configure_legacy_runtime_views",
        lambda _conn: (_ for _ in ()).throw(AssertionError("legacy view configured")),
    )

    assert ids(repository.search_tracks(
        limit_value="all", sort_by="title", sort_dir="asc"
    )) == ["alpha", "beta", "delta", "gamma"]
    assert ids(repository.search_tracks(
        limit_value="all", sort_by="created", sort_dir="desc"
    )) == ["delta", "gamma", "beta", "alpha"]
    assert ids(repository.search_tracks(
        limit_value="all", sort_by="duration", sort_dir="desc"
    )) == ["gamma", "alpha", "beta", "delta"]

    first = repository.search_tracks(
        limit_value="2", sort_by="title", sort_dir="asc"
    )
    cursor = repository.encode_track_page_cursor(
        first[-1], sort_by="title", sort_dir="asc"
    )
    second = repository.search_tracks(
        limit_value="2",
        sort_by="title",
        sort_dir="asc",
        cursor_value=cursor,
    )
    assert ids(first) == ["alpha", "beta"]
    assert ids(second) == ["delta", "gamma"]

    scenarios = [
        {},
        {"query": "Alpha"},
        {"category_filter": ["Instrumental"]},
        {"kind_filter": "Cover"},
        {"kind_filter": "__liked__"},
        {"flag_filter": "1,4"},
        {"tag_filter": "#live"},
        {"workspace": ["Studio A"]},
        {"local_audio_filter": "with"},
    ]
    for params in scenarios:
        rows = repository.search_tracks(limit_value="all", **params)
        assert repository.count_tracks(**params) == len(rows)

    rows = repository.search_tracks(limit_value="all")
    confirmed = repository.get_confirmed_local_audio_paths_for_render(rows)
    assert set(confirmed) == {"alpha", "gamma"}
    assert repository.get_stem_counts_for_track_ids(ids(rows)) == {"alpha": 1}
    assert repository.get_best_local_audio_path_for_track("alpha").endswith("alpha.wav")

    workspaces = {row["workspace"]: row["count"] for row in repository.get_workspaces()}
    assert workspaces == {"Studio A": 2, "Studio B": 1, "Studio C": 1}
    types = {row["ui_type"]: row["count"] for row in repository.get_ui_type_counts()}
    assert types == {"Cover": 2, "Extend": 1, "Generate": 1}
    stats = repository.get_stats()
    assert stats["total_main_active"] == 4
    assert stats["total_liked"] == 2
    assert stats["total_has_stems"] == 1
