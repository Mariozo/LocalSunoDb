from pathlib import Path

import pytest


def test_my_library_grid_fragment_contains_only_central_view(monkeypatch):
    from ls_library import music_browser

    monkeypatch.setattr(
        music_browser,
        "list_music_databases",
        lambda: {"databases": [{"name": "Best Music", "track_count": 16}]},
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_albums",
        lambda *_args, **_kwargs: {
            "albums": [
                {
                    "artist": "Joshua Bell",
                    "album": "Musical Gifts",
                    "year": "2013",
                    "track_count": 16,
                    "cover_sha1": "a" * 40,
                }
            ],
            "root_folder": r"D:\Music",
            "total_tracks": 16,
        },
    )
    monkeypatch.setattr(music_browser, "get_local_playlists", lambda: [])

    html = music_browser.render_music_database_page(
        "Best Music",
        "",
        "grid",
        "",
        "",
        "",
        False,
        True,
    ).decode("utf-8")

    assert '<section' in html
    assert 'id="ls-my-library-view"' in html
    assert 'class="ls-my-library-toolbar"' in html
    assert "Musical Gifts" in html
    assert "Joshua Bell" in html
    assert 'id="new-db-modal"' in html
    assert "<!doctype html>" not in html
    assert 'id="ls-global-player"' not in html
    assert 'class="side"' not in html
    assert 'class="my-music-player' not in html


def test_my_library_album_fragment_uses_shared_shell_and_list_stays_legacy(monkeypatch):
    from ls_library import music_browser

    monkeypatch.setattr(
        music_browser,
        "list_music_databases",
        lambda: {"databases": [{"name": "Best Music", "track_count": 1}]},
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_albums",
        lambda *_args, **_kwargs: {
            "albums": [],
            "root_folder": r"D:\Music",
            "total_tracks": 1,
        },
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_tracks",
        lambda *_args, **_kwargs: {
            "rows": [{
                "id": 7,
                "title": "Track One",
                "artist": "Artist",
                "album_artist": "Artist",
                "album": "Album",
                "year": 2026,
                "track_no": 1,
                "disc_no": 1,
                "genre": "Jazz",
                "duration_seconds": 185,
                "format": "mp3",
                "path": r"D:\Music\Track One.mp3",
                "cover_sha1": "b" * 40,
            }]
        },
    )
    monkeypatch.setattr(music_browser, "get_local_playlists", lambda: [])

    album_html = music_browser.render_music_database_page(
        "Best Music", "", "grid", "Album", "Artist", "2026", False, True
    ).decode("utf-8")
    list_html = music_browser.render_music_database_page(
        "Best Music", "", "list", "", "", "", False, True
    ).decode("utf-8")

    assert "<!doctype html>" not in album_html
    assert 'class="ls-my-library-album-hero"' in album_html
    assert 'id="my-library-track-table"' in album_html
    assert 'class="music-row-play play-btn ls-cover-play-btn"' in album_html
    assert 'data-ls-source="my-library"' in album_html
    assert "Track One" in album_html
    assert "P58-S1.2" in album_html
    assert "<!doctype html>" in list_html


def test_persistent_shell_uses_fragment_content_for_my_library_grid_and_album():
    script = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")

    assert 'const FRAGMENT_PARAM = "ls_fragment";' in script
    assert "function isMyLibraryContentTarget" in script
    assert "function fragmentUrl" in script
    assert 'contentMain.id = "ls-shell-content-main"' in script
    assert "async function showMyLibraryContent" in script
    assert 'fetch(fragmentUrl(target)' in script
    assert 'window.LSMyLibrarySelectionView?.init(contentMain)' in script
    assert "if (isMyLibraryContentTarget(target))" in script
    assert 'P58-S1.2' in script


def test_shared_my_library_assets_are_scoped_and_present():
    style = Path("ls_library/static/my_library_shared_view.css").read_text(encoding="utf-8")
    script = Path("ls_library/static/my_library_shared_view.js").read_text(encoding="utf-8")

    assert ".ls-my-library-view" in style
    assert ".ls-my-library-scroll" in style
    assert "window.LSMyLibrarySelectionView" in script
    assert "my-library-search-form" in script
    assert "music-db-import" in script
    assert "selectLocalTrack" in script
    assert "my-library-track-table" in script
    assert ".ls-my-library-album-hero" in style
    assert ".ls-preview-build" in style


def test_shared_global_player_accepts_my_library_rows():
    script = Path("ls_player/static/suno_global_player_script_assets.js").read_text(encoding="utf-8")

    assert 'currentTrackRow?.closest("table") || table' in script
    assert 'currentTrackRow.dataset.lsSource' in script
    assert 'const externalSource = String(button.dataset.lsSource || "").trim();' in script


def test_shared_navigation_no_longer_shows_stems_choice():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")

    assert 'id="ls-sidebar-stems-btn"' not in template
