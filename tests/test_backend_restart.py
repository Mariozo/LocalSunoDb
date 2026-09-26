from pathlib import Path
import re

from ls_tools import launcher
from ls_core import runtime
from ls_web import render as web_render
from ls_upgrade.package import is_direct_successor, parse_version


def test_entrypoint_and_runtime_versions_are_aligned():
    root = Path(__file__).resolve().parents[1]
    entry_source = (root / "LocalSunoDb.py").read_text(encoding="utf-8")
    entry_version = re.search(r'^APP_VERSION = "([^"]+)"', entry_source, re.M)
    entry_based_on = re.search(r'^APP_BASED_ON = "([^"]+)"', entry_source, re.M)

    assert entry_version is not None
    assert entry_based_on is not None
    assert entry_version.group(1) == runtime.APP_VERSION
    assert entry_based_on.group(1) == runtime.APP_BASED_ON


def test_upgrade_version_parser_accepts_visible_test_iteration_suffix():
    assert parse_version("v2.27.1") == (2, 27)
    assert parse_version("2.27.9") == (2, 27)
    assert is_direct_successor("v2.28", "v2.27.1") is True


def test_popup_theme_is_loaded_last_in_library_head():
    style_block = web_render.render_suno_page_style_block()
    deferred_assets = web_render.render_ls_popup_theme_assets()

    popup_url_marker = "ls_web/static/popup_theme.css"
    assert popup_url_marker in style_block
    assert style_block.rfind(popup_url_marker) > style_block.rfind("ls_player/static/suno_global_player_style_assets.css")
    assert popup_url_marker not in deferred_assets


def test_popup_theme_has_strong_settings_and_flags_selectors():
    root = Path(__file__).resolve().parents[1]
    popup_css = (root / "ls_web" / "static" / "popup_theme.css").read_text(encoding="utf-8")

    assert "#ls-library #settings-modal > .modal" in popup_css
    assert "#ls-library #stats-modal > .ls-stats-modal-card" in popup_css
    assert "#ls-library #user-tag-panel.user-tag-panel" in popup_css


def test_explicit_restart_replaces_same_version_backend():
    events = []
    old = {
        "process_id": 111,
        "running_version": launcher.APP_VERSION,
    }
    new = {
        "process_id": 222,
        "running_version": launcher.APP_VERSION,
        "server_ready": True,
    }
    calls = {"status": 0}

    def status_getter():
        calls["status"] += 1
        return old if calls["status"] == 1 else new

    result = launcher.restart_localsunodb_backend(
        status_getter=status_getter,
        backend_starter=lambda: events.append("start"),
        backend_waiter=lambda: True,
        backend_terminator=lambda status: events.append(("terminate", status["process_id"])) or True,
        backend_stop_waiter=lambda **_kwargs: True,
        supervisor_starter=lambda: events.append("supervisor"),
        restart_guard_setter=lambda active: events.append(("guard", active)),
    )

    assert events == [("guard", True), ("terminate", 111), "start", ("guard", False)]
    assert result["previous_process_id"] == 111
    assert result["process_id"] == 222
    assert result["running_version"] == launcher.APP_VERSION


def test_explicit_restart_can_recover_when_backend_is_down():
    events = []
    new = {
        "process_id": 333,
        "running_version": launcher.APP_VERSION,
        "server_ready": True,
    }
    calls = {"status": 0}

    def status_getter():
        calls["status"] += 1
        return None if calls["status"] == 1 else new

    result = launcher.restart_localsunodb_backend(
        status_getter=status_getter,
        backend_starter=lambda: events.append("start"),
        backend_waiter=lambda: True,
        backend_terminator=lambda _status: events.append("terminate") or True,
        backend_stop_waiter=lambda **_kwargs: True,
        supervisor_starter=lambda: events.append("supervisor"),
        restart_guard_setter=lambda active: events.append(("guard", active)),
    )

    assert events == [("guard", True), "start", ("guard", False)]
    assert result["previous_process_id"] == 0
    assert result["process_id"] == 333



def test_supervisor_does_not_replace_responding_different_version_backend():
    events = []
    status = {
        "process_id": 444,
        "running_version": "v99.99",
        "server_ready": True,
    }

    action = launcher.supervise_localsunodb_backend_once(
        status_getter=lambda: status,
        backend_ensurer=lambda: events.append("ensure"),
        restart_guard_checker=lambda: False,
    )

    assert action == "backend_present"
    assert events == []


def test_supervisor_waits_during_explicit_restart():
    events = []

    action = launcher.supervise_localsunodb_backend_once(
        status_getter=lambda: events.append("status") or None,
        backend_ensurer=lambda: events.append("ensure"),
        restart_guard_checker=lambda: True,
    )

    assert action == "restart_in_progress"
    assert events == []



def test_persistent_backend_supervisor_entrypoint_is_disabled():
    result = launcher.run_localsunodb_backend_supervisor(initial_delay=0, poll_interval=0)
    assert result == {"ok": True, "action": "supervisor_disabled"}


def test_browser_tab_launcher_waits_for_backend_before_opening():
    events = []
    status = {
        "process_id": 555,
        "running_version": launcher.APP_VERSION,
        "server_ready": True,
        "last_view_url": "/library",
    }

    result = launcher.run_localsunodb_browser_tab(
        autostart_cleaner=lambda: events.append("cleanup"),
        backend_ensurer=lambda: events.append("backend_ready") or (status, True),
        browser_opener=lambda url: events.append(("browser", url)) or True,
    )

    assert events[0:2] == ["cleanup", "backend_ready"]
    assert events[2][0] == "browser"
    assert events[2][1].endswith("/library")
    assert result["action"] == "backend_started_and_browser_opened"
    assert result["browser_opened"] is True


def test_browser_tab_shortcut_uses_stable_sf_style_cmd_launcher(tmp_path):
    cmd = tmp_path / "Start_LocalSunoDb.cmd"
    spec = launcher.build_browser_tab_launcher_shortcut_spec(
        launcher_path=cmd,
        host_root=tmp_path,
    )

    assert spec["target_path"] == str(cmd.resolve())
    assert spec["arguments"] == ""
    assert "--app=" not in spec["arguments"]
    assert spec["working_directory"] == str(tmp_path.resolve())


def test_web_runtime_uses_suno_finder_browser_tab_lifecycle():
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "ls_web" / "app.py").read_text(encoding="utf-8")
    entry_source = (root / "LocalSunoDb.py").read_text(encoding="utf-8")

    assert "import webbrowser" in app_source
    assert "webbrowser.open(url)" in app_source
    assert "start_localsunodb_chrome_window_watcher" not in app_source
    assert "open_or_focus_localsunodb_chrome_app" not in app_source
    assert "start_localsunodb_backend_supervisor" not in entry_source
    assert "install_localsunodb_backend_run_entry" not in entry_source
