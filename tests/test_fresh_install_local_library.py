import sqlite3
from pathlib import Path

import pytest

from ls_data import repository


@pytest.fixture()
def isolated_repository(tmp_path, monkeypatch):
    data_dir = tmp_path / "Data"
    reports_dir = tmp_path / "Reports"
    db_path = data_dir / "local_suno.db"
    legacy_path = tmp_path / "suno_finder_v4.db"

    monkeypatch.setattr(repository, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "LEGACY_DB_PATH", legacy_path)
    monkeypatch.setattr(repository, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(repository, "LOCAL_INVENTORY_DB_PATH", data_dir / "suno_local_inventory.db")
    monkeypatch.setattr(repository, "lv_sort_key", lambda value: str(value or "").casefold(), raising=False)
    monkeypatch.setattr(repository, "duration_sort_value", lambda value: 0.0, raising=False)
    monkeypatch.setattr(repository, "now_iso_local", lambda: "2026-09-24T22:00:00+03:00", raising=False)
    monkeypatch.setattr(
        repository,
        "scan_local_inventory",
        lambda: {"ok": True, "file_count": 0},
        raising=False,
    )
    return {
        "root": tmp_path,
        "data_dir": data_dir,
        "db_path": db_path,
        "legacy_path": legacy_path,
    }


def test_fresh_install_creates_empty_canonical_database(isolated_repository):
    db_path = isolated_repository["db_path"]
    assert not db_path.exists()

    repository.ensure_local_suno_runtime_database()

    assert db_path.is_file()
    state = repository.get_local_library_database_state()
    assert state["ok"] is True
    assert state["track_count"] == 0
    assert state["media_count"] == 0
    assert state["is_empty"] is True

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        conn.close()

    assert {"tracks", "track_user", "track_variants", "media_files"} <= tables


def test_local_audio_import_handles_loose_files_and_structured_variants(
    isolated_repository,
    tmp_path,
):
    library = tmp_path / "Audio"
    library.mkdir()

    loose = library / "Loose Track.wav"
    loose.write_bytes(b"RIFF-local-test")

    variant = library / "Song" / "Family One" / "1"
    stems = variant / "Stems"
    stems.mkdir(parents=True)
    (variant / "Family One.wav").write_bytes(b"RIFF-family-main")
    (stems / "Family One (Vocals).wav").write_bytes(b"RIFF-family-vocal")

    first = repository.import_local_audio_library(str(library))

    assert first["ok"] is True
    assert first["audio_file_count"] == 3
    assert first["added_tracks"] == 2
    assert first["added_media"] == 3
    assert first["error_count"] == 0

    conn = sqlite3.connect(isolated_repository["db_path"])
    conn.row_factory = sqlite3.Row
    try:
        tracks = conn.execute(
            "SELECT id, title, kind, workspace_name, source_type FROM tracks ORDER BY title"
        ).fetchall()
        media = conn.execute(
            """
            SELECT t.title, mf.role, mf.stem_label, mf.path
              FROM media_files mf
              JOIN track_variants tv ON tv.id = mf.variant_id
              JOIN tracks t ON t.id = tv.track_id
             ORDER BY t.title, mf.role, mf.path
            """
        ).fetchall()
    finally:
        conn.close()

    assert [row["title"] for row in tracks] == ["Family One", "Loose Track"]
    family = next(row for row in tracks if row["title"] == "Family One")
    loose_row = next(row for row in tracks if row["title"] == "Loose Track")
    assert family["kind"] == "Song"
    assert family["workspace_name"] == "Local"
    assert family["source_type"] == "local"
    assert loose_row["kind"] is None
    assert {row["role"] for row in media if row["title"] == "Family One"} == {"main", "stem"}
    vocal = next(row for row in media if row["role"] == "stem")
    assert vocal["stem_label"] == "Vocals"

    second = repository.import_local_audio_library(str(library))
    assert second["ok"] is True
    assert second["added_tracks"] == 0
    assert second["existing_tracks"] == 2
    assert second["added_media"] == 0
    assert second["existing_media"] == 3


def test_local_audio_import_rejects_empty_or_missing_folder(isolated_repository, tmp_path):
    with pytest.raises(ValueError):
        repository.import_local_audio_library("")

    with pytest.raises(ValueError):
        repository.import_local_audio_library(str(tmp_path / "missing"))

    empty = tmp_path / "Empty"
    empty.mkdir()
    result = repository.import_local_audio_library(str(empty))
    assert result["ok"] is False
    assert result["audio_file_count"] == 0
