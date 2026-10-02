from pathlib import Path


def test_sidebar_stems_choice_is_removed():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")
    assert 'id="ls-sidebar-stems-btn"' not in template


def test_persistent_shell_uses_same_dom_for_library_and_playlists():
    script = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")
    assert 'const SAME_DOM_PATHS = new Set(["/my-library", "/music-db", "/playlists"]);' in script
    assert 'contentMain.id = "ls-shell-content-main"' in script
    assert "async function showSameDomScreen" in script
    assert "if (isSameDomRoute(target))" in script
    assert "fetch(fragmentUrl(target)" in script


def test_shared_view_assets_have_no_iframe_audio_bridge():
    script = Path("ls_web/static/shared_views.js").read_text(encoding="utf-8")
    assert "postMessage" not in script
    assert "window.LS?.player" in script
    assert "loadFromButton" in script
    assert "ls-track-playback-started" in script


def test_global_player_accepts_generic_same_dom_rows():
    script = Path("ls_player/static/suno_global_player_script_assets.js").read_text(
        encoding="utf-8"
    )
    assert 'button.closest("tr.track-row, [data-ls-player-row]")' in script
    assert 'currentTrackRow.closest("[data-ls-player-list]")' in script
    assert "current.lsSource" in script


def test_my_library_fragment_contract(monkeypatch):
    from ls_library import music_browser

    monkeypatch.setattr(
        music_browser,
        "list_music_databases",
        lambda: {"databases": [{"name": "Test", "track_count": 1}]},
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_albums",
        lambda *_args, **_kwargs: {
            "albums": [{
                "artist": "Artist",
                "album": "Album",
                "year": "2026",
                "track_count": 1,
                "cover_sha1": "a" * 40,
            }],
            "root_folder": r"D:\\Music",
            "total_tracks": 1,
        },
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_tracks",
        lambda *_args, **_kwargs: {
            "rows": [{
                "id": 1,
                "title": "Track",
                "artist": "Artist",
                "album_artist": "Artist",
                "album": "Album",
                "year": 2026,
                "track_no": 1,
                "disc_no": 1,
                "genre": "Jazz",
                "duration_seconds": 185,
                "format": "wav",
                "path": r"D:\\Music\\Track.wav",
                "cover_sha1": "a" * 40,
            }]
        },
    )
    monkeypatch.setattr(music_browser, "get_local_playlists", lambda: [])

    html = music_browser.render_music_database_page(
        "Test", "", "grid", "Album", "Artist", "2026", False, True
    ).decode("utf-8")

    assert "<!doctype html>" not in html
    assert 'id="ls-shared-view"' in html
    assert 'class="ls-shared-album-hero"' in html
    assert 'data-ls-player-row="1"' in html
    assert 'class="music-row-play play-btn ls-cover-play-btn"' in html
    assert 'data-ls-source="my-library"' in html
    assert "my-music-player" not in html


def test_playlist_fragment_contract(monkeypatch):
    from ls_library import playlists

    monkeypatch.setattr(
        playlists,
        "get_local_playlists",
        lambda: [{
            "id": "p1",
            "name": "Playlist One",
            "created_at": "",
            "updated_at": "",
            "track_ids": [],
            "track_count": 0,
        }],
    )
    monkeypatch.setattr(
        playlists,
        "get_local_playlist",
        lambda _playlist_id: {
            "id": "p1",
            "name": "Playlist One",
            "created_at": "",
            "updated_at": "",
            "track_ids": [],
            "track_count": 0,
        },
    )

    html = playlists.render_playlists_page("p1", "", True).decode("utf-8")
    assert "<!doctype html>" not in html
    assert 'id="ls-shared-view"' in html
    assert 'data-section="playlists"' in html
    assert 'class="playlist-hero ls-shared-playlist-hero"' in html
    assert "playlist-player" not in html
