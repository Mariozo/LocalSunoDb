import json

import pytest

from ls_library import playlists


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    data_dir = tmp_path / "Data"
    path = data_dir / "localsunodb_playlists.json"
    monkeypatch.setattr(playlists, "DATA_DIR", data_dir)
    monkeypatch.setattr(playlists, "PLAYLISTS_PATH", path)
    return path


def test_playlist_crud_and_manual_order(isolated_store):
    created = playlists.create_local_playlist("Virtual Disc")
    playlist_id = created["id"]

    playlists.add_track_to_local_playlist(playlist_id, "track-a")
    playlists.add_track_to_local_playlist(playlist_id, "track-b")
    playlists.add_track_to_local_playlist(playlist_id, "track-c")
    playlists.add_track_to_local_playlist(playlist_id, "TRACK-B")

    current = playlists.get_local_playlist(playlist_id)
    assert current["track_ids"] == ["track-a", "track-b", "track-c"]

    reordered = playlists.reorder_local_playlist(
        playlist_id,
        ["track-c", "track-a", "track-b"],
    )
    assert reordered["track_ids"] == ["track-c", "track-a", "track-b"]

    renamed = playlists.rename_local_playlist(playlist_id, "Disc 1")
    assert renamed["name"] == "Disc 1"

    removed = playlists.remove_track_from_local_playlist(playlist_id, "TRACK-A")
    assert removed["track_ids"] == ["track-c", "track-b"]

    payload = json.loads(isolated_store.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["playlists"][0]["track_ids"] == ["track-c", "track-b"]

    playlists.delete_local_playlist(playlist_id)
    assert playlists.get_local_playlists() == []


def test_playlist_reorder_rejects_missing_or_duplicate_members(isolated_store):
    playlist_id = playlists.create_local_playlist("Order Test")["id"]
    playlists.add_track_to_local_playlist(playlist_id, "a")
    playlists.add_track_to_local_playlist(playlist_id, "b")

    with pytest.raises(ValueError):
        playlists.reorder_local_playlist(playlist_id, ["a"])

    with pytest.raises(ValueError):
        playlists.reorder_local_playlist(playlist_id, ["a", "a"])



def test_playlist_bulk_add_preserves_input_order_and_deduplicates(isolated_store):
    playlist_id = playlists.create_local_playlist("Bulk")["id"]

    result = playlists.add_tracks_to_local_playlist(
        playlist_id,
        ["track-c", "track-a", "TRACK-C", "track-b"],
    )
    assert result["track_ids"] == ["track-c", "track-a", "track-b"]
    assert result["added_count"] == 3
    assert result["added_track_ids"] == ["track-c", "track-a", "track-b"]

    second = playlists.add_tracks_to_local_playlist(
        playlist_id,
        ["TRACK-A", "track-d"],
    )
    assert second["track_ids"] == ["track-c", "track-a", "track-b", "track-d"]
    assert second["added_count"] == 1
    assert second["added_track_ids"] == ["track-d"]


def test_playlist_bulk_add_rejects_empty_selection(isolated_store):
    playlist_id = playlists.create_local_playlist("Bulk")["id"]
    with pytest.raises(ValueError):
        playlists.add_tracks_to_local_playlist(playlist_id, [])
