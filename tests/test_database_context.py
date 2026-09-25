import sqlite3

import pytest

from ls_data import database_context, repository
from ls_data.local_suno_migration import create_schema


@pytest.fixture()
def isolated_database_context(tmp_path, monkeypatch):
    data_dir = tmp_path / "Data"
    primary = data_dir / "local_suno.db"
    registry = data_dir / "ls_database_registry.json"
    legacy = tmp_path / "suno_finder_v4.db"
    reports = tmp_path / "Reports"

    monkeypatch.setattr(database_context, "DATABASE_REGISTRY_PATH", registry)
    monkeypatch.setattr(database_context, "DB_PATH", primary)
    monkeypatch.setattr(repository, "DB_PATH", primary)
    monkeypatch.setattr(repository, "LEGACY_DB_PATH", legacy)
    monkeypatch.setattr(repository, "REPORTS_DIR", reports)
    monkeypatch.setattr(
        repository,
        "lv_sort_key",
        lambda value: str(value or "").casefold(),
        raising=False,
    )
    monkeypatch.setattr(
        repository,
        "duration_sort_value",
        lambda value: 0.0,
        raising=False,
    )

    return {
        "data_dir": data_dir,
        "primary": primary,
        "registry": registry,
        "legacy": legacy,
        "reports": reports,
    }


def create_compatible_database(path, track_id="", title=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        create_schema(conn)
        if track_id:
            conn.execute(
                "INSERT INTO tracks(id, title, library_status) VALUES (?, ?, 'active')",
                (track_id, title),
            )
        conn.commit()
    finally:
        conn.close()


def test_registry_defaults_to_builtin_primary_without_writing_file(
    isolated_database_context,
):
    state = database_context.get_database_registry_state()

    assert state["active_database_id"] == database_context.PRIMARY_DATABASE_ID
    assert state["configured_active_database_id"] == database_context.PRIMARY_DATABASE_ID
    assert state["fell_back_to_primary"] is False
    assert state["databases"] == [{
        "id": database_context.PRIMARY_DATABASE_ID,
        "label": database_context.PRIMARY_DATABASE_LABEL,
        "path": str(isolated_database_context["primary"]),
        "kind": "suno",
        "built_in": True,
    }]
    assert not isolated_database_context["registry"].exists()


def test_register_and_activate_secondary_database_without_touching_its_content(
    isolated_database_context,
    tmp_path,
):
    secondary = tmp_path / "Libraries" / "jazz.db"
    original = b"existing-database-bytes"
    secondary.parent.mkdir(parents=True)
    secondary.write_bytes(original)

    registered = database_context.register_database_target(
        "jazz",
        secondary,
        label="Jazz",
        kind="music",
    )

    assert registered["id"] == "jazz"
    assert registered["path"] == str(secondary)
    assert secondary.read_bytes() == original

    active = database_context.set_active_database("jazz")
    state = database_context.get_database_registry_state()

    assert active["id"] == "jazz"
    assert state["configured_active_database_id"] == "jazz"
    assert state["active_database_id"] == "jazz"
    assert state["active_database_path"] == str(secondary)
    assert state["fell_back_to_primary"] is False
    assert secondary.read_bytes() == original


def test_repository_connection_factory_uses_active_or_explicit_database(
    isolated_database_context,
    tmp_path,
):
    primary = isolated_database_context["primary"]
    secondary = tmp_path / "Libraries" / "archive.db"
    create_compatible_database(secondary, "external-1", "External track")

    database_context.register_database_target(
        "archive",
        secondary,
        label="Archive",
        kind="music",
    )
    database_context.set_active_database("archive")

    conn = repository.get_connection()
    try:
        row = conn.execute("SELECT id, title FROM tracks").fetchone()
        assert row["id"] == "external-1"
        assert row["title"] == "External track"
    finally:
        conn.close()

    assert not primary.exists()

    primary_conn = repository.get_connection("main")
    try:
        assert primary.exists()
        assert primary_conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0
    finally:
        primary_conn.close()

    explicit_secondary = repository.get_connection("archive")
    try:
        assert explicit_secondary.execute(
            "SELECT COUNT(*) FROM tracks WHERE id='external-1'"
        ).fetchone()[0] == 1
    finally:
        explicit_secondary.close()


def test_missing_active_secondary_falls_back_to_primary_without_deleting_registry(
    isolated_database_context,
    tmp_path,
):
    secondary = tmp_path / "Libraries" / "portable.db"
    create_compatible_database(secondary)

    database_context.register_database_target("portable", secondary, "Portable")
    database_context.set_active_database("portable")
    secondary.unlink()

    state = database_context.get_database_registry_state()

    assert state["configured_active_database_id"] == "portable"
    assert state["active_database_id"] == database_context.PRIMARY_DATABASE_ID
    assert state["fell_back_to_primary"] is True

    conn = repository.get_connection()
    try:
        assert isolated_database_context["primary"].exists()
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0
    finally:
        conn.close()


def test_unregister_only_removes_registry_entry_and_never_database_file(
    isolated_database_context,
    tmp_path,
):
    secondary = tmp_path / "Libraries" / "keep-me.db"
    create_compatible_database(secondary)

    database_context.register_database_target("keep", secondary, "Keep")
    database_context.set_active_database("keep")

    assert database_context.unregister_database_target("keep") is True
    assert secondary.is_file()
    assert database_context.get_database_registry_state()["active_database_id"] == "main"
    assert database_context.unregister_database_target("keep") is False

    with pytest.raises(ValueError):
        database_context.unregister_database_target("main")
