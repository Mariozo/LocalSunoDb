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
    assert current["track_ids"] == ["track-c", "track-b", "track-a"]

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
    assert second["track_ids"] == ["track-d", "track-c", "track-a", "track-b"]
    assert second["added_count"] == 1
    assert second["added_track_ids"] == ["track-d"]


def test_playlist_bulk_add_rejects_empty_selection(isolated_store):
    playlist_id = playlists.create_local_playlist("Bulk")["id"]
    with pytest.raises(ValueError):
        playlists.add_tracks_to_local_playlist(playlist_id, [])



def test_playlist_add_songs_restores_remembered_library_view(isolated_store, monkeypatch):
    monkeypatch.setattr(playlists, "esc", lambda value: str(value), raising=False)
    playlist = playlists.create_local_playlist("Vārda diena")
    page = playlists.render_playlists_page(playlist["id"]).decode("utf-8")

    assert '<a class="playlist-secondary" data-library-return href="/">＋ Add songs</a>' in page
    assert 'sessionStorage.getItem("ls.library.returnUrl")' in page
    assert "playlist_add=" not in page
    assert "atzīmē dziesmas ar apli uz Cover" in page


def test_library_playlist_script_uses_select_audio_playlist_dropdown():
    script = playlists.render_playlist_library_actions_script()

    assert "LSPlaylistLibraryActionsInstalled" in script
    assert "let addInFlight = false" in script
    assert "if (addInFlight || button.disabled) return" in script
    assert "getSelectedTrackIds" in script
    assert 'document.getElementById("audio-playlist-select")' in script
    assert 'document.getElementById("audio-playlist-summary")' in script
    assert 'document.getElementById("audio-playlist-menu")' in script
    assert 'selector.classList.toggle("is-enabled", enabled)' in script
    assert 'summary.setAttribute("aria-disabled", enabled ? "false" : "true")' in script
    assert 'heading.textContent = "Playlists (" + playlists.length + ")"' in script
    assert 'String(playlist.name || "Playlist") + " (" + count + ")"' in script
    assert '"/playlist-add-tracks"' in script
    assert "clearSelectedTracks" in script
    assert '"+ Add song (1)"' not in script
    assert '"+ Add songs ("' not in script
    assert 'table.classList.contains("selection-mode")' not in script
    assert 'params.get("playlist_add")' not in script
    assert "playlist-add-mode-banner" not in script


def test_playlist_rows_expose_clear_remove_and_playback_feedback(isolated_store, monkeypatch):
    monkeypatch.setattr(playlists, "esc", lambda value: str(value), raising=False)
    monkeypatch.setattr(playlists, "format_duration", lambda value: str(value), raising=False)
    playlist = playlists.create_local_playlist("Feedback")
    playlists.add_track_to_local_playlist(playlist["id"], "feedback-track")
    monkeypatch.setattr(
        playlists,
        "_playlist_track_rows",
        lambda track_ids: [{
            "id": "feedback-track",
            "title": "Feedback Track",
            "workspace": "Test",
            "duration": "3:15",
            "missing": False,
            "play_source": "local",
        }],
    )
    page = playlists.render_playlists_page(playlist["id"]).decode("utf-8")

    assert 'aria-label="Remove from Playlist">×</button>' in page
    assert "playlist-track-eq" in page
    assert ".playlist-track-row.is-current" in page
    assert ".playlist-track-row.is-playing" in page
    assert 'audio?.addEventListener("play"' in page


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


def test_single_row_playlist_add_is_exposed_in_three_dot_menu():
    render_source = (Path(__file__).resolve().parents[1] / "ls_library" / "render.py").read_text(encoding="utf-8")
    script = playlists.render_playlist_library_actions_script()

    assert 'class="row-menu-item menu-add-playlist">Add to Playlist...</button>' in render_source
    assert 'event.target?.closest?.(".menu-add-playlist")' in script
    assert 'sessionStorage.setItem("ls.library.returnUrl", returnUrl || "/")' in script
    assert '"/playlists?add_track=" + encodeURIComponent(trackId)' in script

def test_v228_identity_is_based_on_v227():
    root = Path(__file__).resolve().parents[1]
    entrypoint = (root / "LocalSunoDb.py").read_text(encoding="utf-8")
    runtime = (root / "ls_core" / "runtime.py").read_text(encoding="utf-8")

    assert "# Based on: v2.27" in entrypoint
    assert 'APP_VERSION = "v2.28.5"' in entrypoint
    assert 'APP_BASED_ON = "v2.27"' in entrypoint
    assert 'APP_VERSION = "v2.28.5"' in runtime
    assert 'APP_BASED_ON = "v2.27"' in runtime


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

def test_v221_playlist_player_uses_row_source(monkeypatch):
    monkeypatch.setattr(playlists, "format_duration", lambda value: str(value), raising=False)
    monkeypatch.setattr(playlists, "esc", lambda value: str(value), raising=False)
    monkeypatch.setattr(
        playlists,
        "_playlist_track_rows",
        lambda _ids: [
            {
                "id": "local-1",
                "title": "Local Track",
                "workspace": "Browser",
                "duration": "3:00",
                "missing": False,
                "play_source": "local",
            }
        ],
    )
    html = playlists._playlist_detail_rows({"track_ids": ["local-1"]})
    script = playlists._playlist_page_script("playlist-1")

    assert 'data-play-source="local"' in html
    assert 'row.dataset.playSource || "suno"' in script
    assert '"&source=" + encodeURIComponent(source)' in script


def test_v221_library_selection_has_public_clear_api():
    root = Path(__file__).resolve().parents[1]
    selection_source = (
        root / "ls_library" / "static" / "suno_selection_state_script.js"
    ).read_text(encoding="utf-8")

    assert "clearSelectedTracks()" in selection_source
    assert "check.checked = false" in selection_source
    assert "saveSunoSelection();" in selection_source


def test_v221_f4_and_bfcache_contracts_present():
    root = Path(__file__).resolve().parents[1]
    search_events = (
        root
        / "ls_library"
        / "static"
        / "suno_sidebar_stats_search_events_script_assets.js"
    ).read_text(encoding="utf-8")
    lazy_loader = (
        root / "ls_library" / "static" / "suno_library_lazy_loader.js"
    ).read_text(encoding="utf-8")

    assert 'event.key === "F4"' in search_events
    assert "openFinderSearchBox();" in search_events
    assert 'window.addEventListener("pageshow"' in lazy_loader
    assert "event.persisted" in lazy_loader


def test_my_library_album_hybrid_layout_contract(monkeypatch):
    from ls_library import music_browser

    monkeypatch.setattr(
        music_browser,
        "list_music_databases",
        lambda: {"databases": [{"name": "Jazz", "track_count": 2}]},
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_albums",
        lambda *_args, **_kwargs: {
            "albums": [],
            "root_folder": r"D:\\Music",
            "total_tracks": 2,
        },
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_tracks",
        lambda *_args, **_kwargs: {
            "rows": [
                {
                    "id": 1,
                    "title": "First",
                    "artist": "Artist",
                    "album_artist": "Artist",
                    "album": "Album",
                    "year": 2024,
                    "track_no": 1,
                    "duration_seconds": 65,
                    "format": "mp3",
                    "genre": "Jazz",
                    "path": r"D:\\Music\\01 - First.mp3",
                    "cover_sha1": "a" * 40,
                },
                {
                    "id": 2,
                    "title": "Second",
                    "artist": "Guest",
                    "album_artist": "Artist",
                    "album": "Album",
                    "year": 2024,
                    "track_no": 2,
                    "duration_seconds": 125,
                    "format": "flac",
                    "genre": "Jazz",
                    "path": r"D:\\Music\\02 - Second.flac",
                    "cover_sha1": "a" * 40,
                },
            ]
        },
    )
    monkeypatch.setattr(music_browser, "get_local_playlists", lambda: [])

    rendered = music_browser.render_music_database_page(
        name="Jazz",
        album="Album",
        artist="Artist",
        year="2024",
    ).decode("utf-8")

    assert 'class="album-open-v2"' in rendered
    assert 'id="album-hero-v2"' in rendered
    assert 'id="album-play-all"' in rendered
    assert 'id="album-track-list"' in rendered
    assert 'id="album-inspector"' in rendered
    assert 'id="album-inspector-title"' in rendered
    assert 'id="album-now-playing"' in rendered
    assert 'id="album-google-track"' in rendered
    assert "Google: albums" in rendered
    assert 'class="album-layout-v3"' in rendered
    assert "2 dziesmas · 3 min 10 s" in rendered
    assert 'class="album-track-row music-track-row"' in rendered
    assert 'class="path-line"' not in rendered
    assert 'ls-elza-dock-slot' not in rendered
    assert "value * .80" not in rendered
    assert "v*.80" in rendered
    assert "background:#061f14" in rendered


def test_music_library_reads_wav_duration(tmp_path):
    import wave
    from ls_data import music_library

    path = tmp_path / "duration.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 8000)

    assert music_library._audio_duration_seconds(path) == pytest.approx(1.0, abs=0.01)


def test_main_sidebar_has_no_stems_choice():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")
    assert 'id="ls-sidebar-stems-btn"' not in template
    assert '<span class="ls-sidebar-label">Stems</span>' not in template


def test_persistent_shell_has_global_now_playing_indicator_and_alt_tab_title():
    script = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")
    style = Path("ls_web/static/persistent_shell.css").read_text(encoding="utf-8")

    assert "LS_SHELL_AUDIO_STATE" in script
    assert "ls-sidebar-audio-indicator" in script
    assert "is-audio-playing" in script
    assert "playbackWindowTitle" in script
    assert "▶ " in script
    assert "mediaPlaybackMetadata" in script
    assert ".ls-sidebar-audio-indicator" in style


def test_my_library_and_playlist_publish_now_playing_metadata():
    browser = Path("ls_library/music_browser.py").read_text(encoding="utf-8")
    playlists = Path("ls_library/playlists.py").read_text(encoding="utf-8")

    assert "playerAudio.dataset.lsTitle = title" in browser
    assert "playerAudio.dataset.lsArtist = artist" in browser
    assert "playerAudio.dataset.lsAlbum = album" in browser
    assert "audio.dataset.lsTitle = title" in playlists


def test_secondary_screens_reuse_parent_suno_panel_and_player():
    shell_js = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")
    shell_css = Path("ls_web/static/persistent_shell.css").read_text(encoding="utf-8")
    player_js = Path("ls_player/static/suno_global_player_script_assets.js").read_text(encoding="utf-8")
    panel_css = Path("ls_library/static/suno_page_selected_track_shell_style_assets.css").read_text(encoding="utf-8")
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")

    assert 'type === "LS_SHELL_SELECTED_TRACK"' in shell_js
    assert 'type === "LS_SHELL_EXTERNAL_PLAY"' in shell_js
    assert "setSharedPanelExternal" in shell_js
    assert 'loadExternalQueue' in player_js
    assert 'current.external' in player_js
    assert 'right: var(--ls-selected-panel-width, 330px);' in shell_css
    assert 'bottom: var(--ls-global-player-reserved, 78px);' in shell_css
    assert 'html.ls-shell-embedded .my-music-player' in shell_css
    assert 'html.ls-shell-embedded .playlist-player' in shell_css
    assert '.selected-track-panel.is-external-track' in panel_css
    assert 'id="ls-external-google-track"' in template
    assert 'id="ls-external-google-album"' in template


def test_my_library_and_playlists_route_embedded_playback_to_shared_shell():
    browser = Path("ls_library/music_browser.py").read_text(encoding="utf-8")
    playlists = Path("ls_library/playlists.py").read_text(encoding="utf-8")

    assert "LS_SHELL_SELECTED_TRACK" in browser
    assert "LS_SHELL_EXTERNAL_PLAY" in browser
    assert "section: 'my-library'" in browser
    assert "LS_SHELL_SELECTED_TRACK" in playlists
    assert "LS_SHELL_EXTERNAL_PLAY" in playlists
    assert 'section: "playlists"' in playlists
