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


def test_my_library_album_and_list_keep_legacy_page_during_first_migration_stage(monkeypatch):
    from ls_library import music_browser

    monkeypatch.setattr(
        music_browser,
        "list_music_databases",
        lambda: {"databases": [{"name": "Best Music", "track_count": 0}]},
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_albums",
        lambda *_args, **_kwargs: {
            "albums": [],
            "root_folder": r"D:\Music",
            "total_tracks": 0,
        },
    )
    monkeypatch.setattr(
        music_browser,
        "music_database_tracks",
        lambda *_args, **_kwargs: {"rows": []},
    )
    monkeypatch.setattr(music_browser, "get_local_playlists", lambda: [])

    album_html = music_browser.render_music_database_page(
        "Best Music", "", "grid", "Album", "Artist", "2026", False, True
    ).decode("utf-8")
    list_html = music_browser.render_music_database_page(
        "Best Music", "", "list", "", "", "", False, True
    ).decode("utf-8")

    assert "<!doctype html>" in album_html
    assert "<!doctype html>" in list_html


def test_persistent_shell_uses_fragment_content_for_my_library_grid():
    script = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")

    assert 'const FRAGMENT_PARAM = "ls_fragment";' in script
    assert "function isMyLibraryContentTarget" in script
    assert "function fragmentUrl" in script
    assert 'contentMain.id = "ls-shell-content-main"' in script
    assert "async function showMyLibraryContent" in script
    assert 'fetch(fragmentUrl(target)' in script
    assert 'window.LSMyLibrarySelectionView?.init(contentMain)' in script
    assert "if (isMyLibraryContentTarget(target))" in script


def test_shared_my_library_assets_are_scoped_and_present():
    style = Path("ls_library/static/my_library_shared_view.css").read_text(encoding="utf-8")
    script = Path("ls_library/static/my_library_shared_view.js").read_text(encoding="utf-8")

    assert ".ls-my-library-view" in style
    assert ".ls-my-library-scroll" in style
    assert "window.LSMyLibrarySelectionView" in script
    assert "my-library-search-form" in script
    assert "music-db-import" in script
