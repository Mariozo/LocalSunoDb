from pathlib import Path

from ls_tools import launcher


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


def test_browser_tab_shortcut_does_not_use_chrome_app_mode(tmp_path):
    spec = launcher.build_browser_tab_launcher_shortcut_spec(
        python_executable=tmp_path / "pythonw.exe",
        launcher_path=tmp_path / "launcher.py",
        host_root=tmp_path,
    )

    assert launcher.LS_BROWSER_TAB_LAUNCH_FLAG in spec["arguments"]
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
