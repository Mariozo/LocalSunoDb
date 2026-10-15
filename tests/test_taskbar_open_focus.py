import sys
from pathlib import Path

from ls_tools import launcher


def test_chrome_app_launcher_ensures_backend_then_focuses_existing():
    events = []
    status = {
        "process_id": 777,
        "running_version": launcher.APP_VERSION,
        "server_ready": True,
        "last_view_url": "/downloader",
    }

    result = launcher.run_localsunodb_chrome_app(
        autostart_cleaner=lambda: events.append("cleanup"),
        backend_ensurer=lambda: events.append("backend") or (status, False),
        app_opener=lambda **kwargs: events.append(("app", kwargs["url"])) or {
            "ok": True,
            "action": "focused_existing",
        },
    )

    assert events[0:2] == ["cleanup", "backend"]
    assert events[2][0] == "app"
    assert events[2][1].endswith("/downloader")
    assert result["action"] == "focused_existing"
    assert result["running_version"] == launcher.APP_VERSION


def test_rebind_taskbar_writes_native_launcher_and_chrome_app_identity(tmp_path, monkeypatch):
    pin = tmp_path / "LocalSunoDb.lnk"
    pin.write_bytes(b"placeholder")
    writes = []
    identities = []

    monkeypatch.setattr(
        launcher,
        "build_browser_tab_launcher_shortcut_spec",
        lambda: {"target_path": "pythonw.exe", "arguments": "--launch-chrome-app"},
    )
    monkeypatch.setattr(
        launcher,
        "_chrome_last_used_profile_directory",
        lambda: "Default",
    )
    monkeypatch.setattr(
        launcher,
        "expected_chrome_app_url_aumid",
        lambda url, profile_directory=None: "Chrome.LocalSunoDb.Test",
    )
    monkeypatch.setattr(
        launcher,
        "set_localsunodb_shortcut_app_id",
        lambda path, app_user_model_id, **_kwargs: identities.append(
            (Path(path), app_user_model_id)
        ) or True,
    )

    changed = launcher.rebind_taskbar_localsunodb_shortcuts(
        pinned_paths=[pin],
        shortcut_writer=lambda path, spec: writes.append((Path(path), dict(spec))),
    )

    assert changed == 1
    assert writes == [(pin, {"target_path": "pythonw.exe", "arguments": "--launch-chrome-app"})]
    assert identities == [(pin, "Chrome.LocalSunoDb.Test")]


def test_main_routes_chrome_app_flag_to_open_focus_path(monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "run_localsunodb_chrome_app", lambda: calls.append("app"))
    monkeypatch.setattr(launcher, "run_localsunodb_browser_tab", lambda: calls.append("tab"))
    monkeypatch.setattr(sys, "argv", ["launcher.py", launcher.LS_CHROME_APP_LAUNCH_FLAG])

    assert launcher.main() == 0
    assert calls == ["app"]


def test_main_routes_browser_tab_flag_separately(monkeypatch):
    calls = []
    monkeypatch.setattr(launcher, "run_localsunodb_chrome_app", lambda: calls.append("app"))
    monkeypatch.setattr(launcher, "run_localsunodb_browser_tab", lambda: calls.append("tab"))
    monkeypatch.setattr(sys, "argv", ["launcher.py", launcher.LS_BROWSER_TAB_LAUNCH_FLAG])

    assert launcher.main() == 0
    assert calls == ["tab"]


def test_taskbar_repair_flag_requires_existing_pin(monkeypatch):
    monkeypatch.setattr(
        launcher,
        "create_localsunodb_launcher_shortcut",
        lambda: {"taskbar_shortcuts_rewritten": 1},
    )
    monkeypatch.setattr(sys, "argv", ["launcher.py", launcher.LS_TASKBAR_REPAIR_FLAG])

    assert launcher.main() == 0
