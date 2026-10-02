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


def test_embedded_mode_is_available_before_deferred_shell_bootstrap():
    browser = Path("ls_library/music_browser.py").read_text(encoding="utf-8")
    playlists = Path("ls_library/playlists.py").read_text(encoding="utf-8")
    css = Path("ls_web/static/persistent_shell.css").read_text(encoding="utf-8")

    assert "ls_embedded" in browser
    assert "ls_embedded" in playlists
    assert "z-index: 1260;" in css


def test_global_external_queue_keeps_right_panel_in_sync():
    player = Path("ls_player/static/suno_global_player_script_assets.js").read_text(
        encoding="utf-8"
    )
    shell = Path("ls_web/static/persistent_shell.js").read_text(encoding="utf-8")

    assert 'CustomEvent("ls-global-external-track"' in player
    assert 'addEventListener("ls-global-external-track"' in shell
    assert "setSharedPanelExternal(item)" in shell


def test_my_library_album_hero_is_present_without_duplicate_inspector():
    browser = Path("ls_library/music_browser.py").read_text(encoding="utf-8")

    assert 'class="album-hero-v2"' in browser
    assert 'id="album-hero-cover"' in browser
    assert "--album-hero" in browser
    assert 'class="album-inspector-v2"' not in browser


def test_secondary_views_hide_parent_suno_main_surface():
    css = Path("ls_web/static/persistent_shell.css").read_text(encoding="utf-8")

    assert "html.ls-shell-secondary-active body#ls-library > main" in css
    assert "visibility: hidden !important;" in css


def test_shared_playback_uses_synchronous_same_origin_parent_player_first():
    browser = Path("ls_library/music_browser.py").read_text(encoding="utf-8")
    playlists = Path("ls_library/playlists.py").read_text(encoding="utf-8")

    assert "window.parent?.LS?.player" in browser
    assert "parentPlayer.loadExternalQueue(items, queueIndex, true)" in browser
    assert "window.parent?.LS?.player" in playlists
    assert "parentPlayer.loadExternalQueue(items, queueIndex, true)" in playlists
