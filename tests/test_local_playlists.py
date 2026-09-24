import json
from pathlib import Path

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



def test_playlist_add_songs_opens_shared_local_library_flow(isolated_store, monkeypatch):
    monkeypatch.setattr(playlists, "esc", lambda value: str(value), raising=False)
    playlist = playlists.create_local_playlist("Vārda diena")
    page = playlists.render_playlists_page(playlist["id"]).decode("utf-8")

    assert "local_audio_filter=with" in page
    assert "playlist_add=" not in page
    assert "atzīmē dziesmas ar apli uz Cover" in page


def test_library_playlist_script_uses_cover_selection_and_playlist_list():
    script = playlists.render_playlist_library_actions_script()

    assert "getSelectedTrackIds" in script
    assert 'params.get("playlist_add")' not in script
    assert 'table.classList.remove("selection-mode")' not in script
    assert '"+ Add song (1)"' in script
    assert '"+ Add songs (" + count + ")"' in script
    assert 'selectedButton.title = "Add songs to Playlist"' in script
    assert 'menu.id = "playlist-add-chooser"' in script
    assert 'playlist.track_count' in script
    assert 'String(playlist.name || "Playlist") + " (" + count + ")"' in script
    assert '"/playlist-add-tracks"' in script



def test_single_track_add_uses_native_playlist_chooser(isolated_store, monkeypatch):
    monkeypatch.setattr(playlists, "esc", lambda value: str(value), raising=False)
    playlist = playlists.create_local_playlist("Vārda diena")

    html = playlists._playlist_catalog_html(
        playlists.get_local_playlists(),
        "track-native-1",
    )

    assert 'method="post" action="/playlist-add-track-open"' in html
    assert 'name="playlist_id" value="' + playlist["id"] + '"' in html
    assert 'name="track_id" value="track-native-1"' in html
    assert "3 songs now · +1 selected" not in html
    assert "1 selected" in html


def test_single_row_playlist_add_is_not_exposed_in_three_dot_menu():
    render_source = (Path(__file__).resolve().parents[1] / "ls_library" / "render.py").read_text(encoding="utf-8")
    script = playlists.render_playlist_library_actions_script()

    assert 'menu-add-playlist' not in render_source
    assert '/playlists?add_track=' not in render_source
    assert 'event.target.closest(".menu-add-playlist")' not in script

def test_v216_selection_ui_contract_keeps_compare_only_in_player():
    root = Path(__file__).resolve().parents[1]
    template = (root / "ls_library" / "templates" / "library.html").read_text(encoding="utf-8")
    state_script = (root / "ls_library" / "static" / "suno_selection_state_script.js").read_text(encoding="utf-8")
    actions_script = (root / "ls_library" / "static" / "suno_selection_actions_script.js").read_text(encoding="utf-8")
    list_css = (root / "ls_library" / "static" / "suno_page_suno_library_list_style_assets.css").read_text(encoding="utf-8")
    player_script = (root / "ls_player" / "static" / "suno_global_player_script_assets.js").read_text(encoding="utf-8")
    render_source = (root / "ls_library" / "render.py").read_text(encoding="utf-8")

    assert 'id="audio-selection-label"' in template
    assert ">Select Audio</span>" in template
    assert 'id="compare-this-btn"' not in template
    assert 'title="Add songs to Playlist"' in template
    assert "getSelectedTrackIds()" in state_script
    assert 'table.classList.add("selection-mode")' not in actions_script
    assert 'table.classList.remove("selection-mode")' not in actions_script
    assert ".ls-track-select-control" in list_css
    assert "opacity: 1;" in list_css
    assert 'class="small-action compare-btn"' not in render_source
    assert 'document.getElementById("ls-global-player-compare")' in player_script
    assert '"ls-library-wav-selection-changed"' in player_script
    assert "isLocalWavCompareReady" in player_script


def test_v216_release_identity():
    root = Path(__file__).resolve().parents[1]
    entrypoint = (root / "LocalSunoDb.py").read_text(encoding="utf-8")
    runtime = (root / "ls_core" / "runtime.py").read_text(encoding="utf-8")

    assert '# Based on: v2.15' in entrypoint
    assert 'APP_VERSION = "v2.16"' in entrypoint
    assert 'APP_BASED_ON = "v2.15"' in entrypoint
    assert 'APP_VERSION = "v2.16"' in runtime
    assert 'APP_BASED_ON = "v2.15"' in runtime


@pytest.mark.parametrize(
    "relative_path",
    [
        "LocalSunoDb.py",
        "ls_core/runtime.py",
        "ls_library/playlists.py",
        "ls_library/render.py",
        "ls_library/templates/library.html",
        "ls_library/static/suno_selection_state_script.js",
        "ls_library/static/suno_selection_actions_script.js",
        "ls_library/static/suno_page_suno_library_list_style_assets.css",
        "ls_library/static/suno_filter_layout_dock_style_assets.css",
        "tests/test_local_playlists.py",
    ],
)
def test_v216_changed_text_files_have_consistent_line_endings(relative_path):
    root = Path(__file__).resolve().parents[1]
    data = (root / relative_path).read_bytes()
    assert b"\r" not in data.replace(b"\r\n", b"")

