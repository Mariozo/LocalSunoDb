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



def test_playlist_add_songs_opens_local_library_without_target_mode(isolated_store, monkeypatch):
    monkeypatch.setattr(playlists, "esc", lambda value: str(value), raising=False)
    playlist = playlists.create_local_playlist("Vārda diena")
    page = playlists.render_playlists_page(playlist["id"]).decode("utf-8")

    assert "local_audio_filter=with" in page
    assert "playlist_add=" not in page
    assert "atzīmē dziesmas ar apli uz Cover" in page


def test_library_playlist_script_uses_select_audio_playlist_dropdown():
    script = playlists.render_playlist_library_actions_script()

    assert "getSelectedTrackIds" in script
    assert 'document.getElementById("audio-playlist-select")' in script
    assert 'document.getElementById("audio-playlist-summary")' in script
    assert 'document.getElementById("audio-playlist-menu")' in script
    assert 'selector.classList.toggle("is-enabled", enabled)' in script
    assert 'summary.setAttribute("aria-disabled", enabled ? "false" : "true")' in script
    assert 'heading.textContent = "Playlists (" + playlists.length + ")"' in script
    assert 'String(playlist.name || "Playlist") + " (" + count + ")"' in script
    assert '"/playlist-add-tracks"' in script
    assert '"+ Add song (1)"' not in script
    assert '"+ Add songs ("' not in script
    assert 'table.classList.contains("selection-mode")' not in script
    assert 'params.get("playlist_add")' not in script
    assert "playlist-add-mode-banner" not in script


def test_selection_starts_on_cover_and_compare_exists_only_in_player():
    root = Path(__file__).resolve().parents[1]
    template = (root / "ls_library" / "templates" / "library.html").read_text(encoding="utf-8")
    selection_source = (root / "ls_library" / "static" / "suno_selection_state_script.js").read_text(encoding="utf-8")
    actions_source = (root / "ls_library" / "static" / "suno_selection_actions_script.js").read_text(encoding="utf-8")
    list_css = (root / "ls_library" / "static" / "suno_page_suno_library_list_style_assets.css").read_text(encoding="utf-8")
    render_source = (root / "ls_library" / "render.py").read_text(encoding="utf-8")
    player_source = (root / "ls_player" / "static" / "suno_global_player_script_assets.js").read_text(encoding="utf-8")

    assert 'id="audio-playlist-select"' in template
    assert 'id="audio-playlist-summary"' in template
    assert '<span class="library-playlist-label">Select Audio</span>' in template
    assert 'id="audio-playlist-menu"' in template
    assert 'id="add-selected-playlist-btn"' not in template
    assert 'id="compare-this-btn"' not in template
    assert 'title="Select songs using the circle on each cover"' in template
    assert "getSelectedTrackIds()" in selection_source
    assert 'table.classList.add("selection-mode")' not in actions_source
    assert 'table.classList.remove("selection-mode")' not in actions_source
    assert ".ls-track-select-control" in list_css
    assert "opacity: 1;" in list_css
    assert 'class="small-action compare-btn"' not in render_source
    assert '>Compare</button>' not in render_source
    assert '"ls-library-wav-selection-changed"' in player_source
    assert 'libraryApi.isLocalWavCompareReady()' in player_source
    assert '"ls-library-open-selected-wav-compare"' in player_source



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

def test_v220_identity_is_based_on_v219():
    root = Path(__file__).resolve().parents[1]
    entrypoint = (root / "LocalSunoDb.py").read_text(encoding="utf-8")
    runtime = (root / "ls_core" / "runtime.py").read_text(encoding="utf-8")

    assert "# Based on: v2.19" in entrypoint
    assert 'APP_VERSION = "v2.20"' in entrypoint
    assert 'APP_BASED_ON = "v2.19"' in entrypoint
    assert 'APP_VERSION = "v2.20"' in runtime
    assert 'APP_BASED_ON = "v2.19"' in runtime


def test_v220_library_header_shows_visible_version_identity():
    root = Path(__file__).resolve().parents[1]
    template = (root / "ls_library" / "templates" / "library.html").read_text(encoding="utf-8")

    assert '<span class="ls-sidebar-title-full">LS @@LS0@@</span>' in template


def test_v219_library_tail_keeps_asset_boundaries_inside_script_and_playlist_assets_outside():
    root = Path(__file__).resolve().parents[1]
    template = (root / "ls_library" / "templates" / "library.html").read_text(encoding="utf-8")
    tail = template[template.rfind("@@LS94@@"):]

    assert "@@LS94@@\n@@LS95@@\n@@LS96@@\n    </script>" in tail
    assert "    @@LS97@@\n    @@LS98@@\n    @@LS99@@\n</body>" in tail


def test_v218_select_audio_dropdown_styles_are_selection_gated():
    root = Path(__file__).resolve().parents[1]
    css = (root / "ls_library" / "static" / "suno_filter_layout_dock_style_assets.css").read_text(encoding="utf-8")

    assert "#audio-playlist-select.is-enabled > summary" in css
    assert "#audio-playlist-select.is-enabled .library-playlist-arrow" in css
    assert ".library-playlist-menu-heading" in css
    assert ".library-playlist-menu-item" in css
