from pathlib import Path

from ls_library import music_browser, playlists


ROOT = Path(__file__).resolve().parents[1]


def test_shared_shell_reserves_parent_right_panel_and_global_player():
    css = (ROOT / "ls_web" / "static" / "persistent_shell.css").read_text(encoding="utf-8")
    shell_js = (ROOT / "ls_web" / "static" / "persistent_shell.js").read_text(encoding="utf-8")
    player_js = (
        ROOT / "ls_player" / "static" / "suno_global_player_script_assets.js"
    ).read_text(encoding="utf-8")

    assert "right: var(--ls-selected-panel-width, 330px);" in css
    assert "bottom: var(--ls-global-player-reserved, 78px);" in css
    assert "z-index: 1100;" in css
    assert "LS_SHELL_SELECTED_TRACK" in shell_js
    assert "LS_SHELL_EXTERNAL_PLAY" in shell_js
    assert "setSharedPanelSelection" in shell_js
    assert "loadExternalQueue" in player_js


def test_shared_suno_template_owns_navigation_right_panel_and_player():
    template = (ROOT / "ls_library" / "templates" / "library.html").read_text(
        encoding="utf-8"
    )

    assert 'id="selected-track-panel"' in template
    assert 'id="selected-track-external-actions"' in template
    assert "@@LS62@@" in template
    assert 'id="ls-sidebar-stems-btn"' not in template


def test_my_library_embedded_view_has_content_but_no_private_chrome(monkeypatch):
    monkeypatch.setattr(
        music_browser,
        "list_music_databases",
        lambda: {"databases": [{"name": "Jazz", "track_count": 1}]},
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_albums",
        lambda *_args, **_kwargs: {
            "albums": [],
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
            }]
        },
    )
    monkeypatch.setattr(music_browser, "get_local_playlists", lambda: [])

    embedded = music_browser.render_music_database_page(
        name="Jazz",
        album="Album",
        artist="Artist",
        year="2024",
        embedded=True,
    ).decode("utf-8")
    standalone = music_browser.render_music_database_page(
        name="Jazz",
        album="Album",
        artist="Artist",
        year="2024",
        embedded=False,
    ).decode("utf-8")

    assert 'class="album-detail-v2"' in embedded
    assert "1 dziesmas · 1 min 5 s" in embedded
    assert 'class="side"' not in embedded
    assert 'id="my-music-player"' not in embedded
    assert 'class="side"' in standalone
    assert 'id="my-music-player"' in standalone
    assert "LS_SHELL_SELECTED_TRACK" in embedded
    assert "LS_SHELL_EXTERNAL_PLAY" in embedded


def test_playlists_embedded_view_has_content_but_no_private_chrome(monkeypatch):
    playlist = {
        "id": "p1",
        "name": "Test Playlist",
        "track_ids": ["t1"],
        "track_count": 1,
    }
    monkeypatch.setattr(playlists, "get_local_playlists", lambda: [playlist])
    monkeypatch.setattr(playlists, "get_local_playlist", lambda _playlist_id: playlist)
    monkeypatch.setattr(
        playlists,
        "_playlist_cover_html",
        lambda *_args, **_kwargs: '<div class="playlist-cover"></div>',
    )
    monkeypatch.setattr(
        playlists,
        "_playlist_detail_rows",
        lambda _playlist: (
            '<div class="playlist-track-row" data-track-id="t1" data-play-source="local">'
            '<span></span><span></span><img class="playlist-track-cover" src="">'
            '<button class="playlist-track-play" data-track-id="t1"></button>'
            '<span class="playlist-track-copy"><strong>Track</strong><span>Artist</span></span>'
            '<span class="playlist-track-duration">3:00</span></div>'
        ),
    )

    embedded = playlists.render_playlists_page("p1", embedded=True).decode("utf-8")
    standalone = playlists.render_playlists_page("p1", embedded=False).decode("utf-8")

    assert 'class="playlist-main"' in embedded
    assert 'class="playlist-topbar"' not in embedded
    assert 'class="playlist-player"' not in embedded
    assert 'class="playlist-topbar"' in standalone
    assert 'class="playlist-player"' in standalone
    assert "LS_SHELL_SELECTED_TRACK" in embedded
    assert "LS_SHELL_EXTERNAL_PLAY" in embedded


def test_imports_embedded_renderer_omits_duplicate_sidebar_and_elza():
    pages = (ROOT / "ls_web" / "pages.py").read_text(encoding="utf-8")
    handler = (ROOT / "ls_web" / "handler.py").read_text(encoding="utf-8")

    assert 'def render_downloader_page(message="", embedded=False):' in pages
    assert '"" if embedded else render_top_tabs' in pages
    assert '"" if embedded else render_downloader_side_panels_markup()' in pages
    assert '"" if embedded else render_ls_elza_assets' in pages
    assert "render_downloader_page(embedded=embedded_imports)" in handler
