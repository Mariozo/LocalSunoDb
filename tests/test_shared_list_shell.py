from pathlib import Path


def test_sidebar_stems_choice_is_removed_but_player_stems_remains():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")
    player = Path("ls_player/templates/global_player.html").read_text(encoding="utf-8")

    assert 'id="ls-sidebar-stems-btn"' not in template
    assert 'id="ls-global-player-stems"' in player


def test_secondary_list_views_reserve_shared_panel_and_player():
    css = Path("ls_web/static/persistent_shell.css").read_text(encoding="utf-8")

    assert "right: var(--ls-selected-panel-width, 330px);" in css
    assert "bottom: var(--ls-global-player-reserved, 78px);" in css
    assert "html.ls-shell-embedded .my-music-player" in css
    assert "html.ls-shell-embedded .playlist-player" in css
    assert "P1 list-view treatment" in css
    assert "body#ls-my-library .track-table" in css
    assert "body#ls-playlists .playlist-track-row" in css


def test_shared_shell_routes_selection_and_playback():
    shell = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")
    player = Path("ls_player/static/suno_global_player_script_assets.js").read_text(encoding="utf-8")
    browser = Path("ls_library/music_browser.py").read_text(encoding="utf-8")
    playlists = Path("ls_library/playlists.py").read_text(encoding="utf-8")

    assert 'event.data.type === "LS_SHELL_SELECTED_TRACK"' in shell
    assert 'event.data.type === "LS_SHELL_EXTERNAL_PLAY"' in shell
    assert "setSharedPanelExternal" in shell
    assert "loadExternalQueue" in player
    assert "LS_SHELL_SELECTED_TRACK" in browser
    assert "LS_SHELL_EXTERNAL_PLAY" in browser
    assert "section: 'my-library'" in browser
    assert "LS_SHELL_SELECTED_TRACK" in playlists
    assert "LS_SHELL_EXTERNAL_PLAY" in playlists
    assert 'section: "playlists"' in playlists


def test_shared_external_info_actions_exist():
    template = Path("ls_library/templates/library.html").read_text(encoding="utf-8")
    panel_css = Path(
        "ls_library/static/suno_page_selected_track_shell_style_assets.css"
    ).read_text(encoding="utf-8")

    assert 'id="ls-external-google-track"' in template
    assert 'id="ls-external-google-album"' in template
    assert ".selected-track-panel.is-external-track" in panel_css
