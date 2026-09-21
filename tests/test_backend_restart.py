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
    )

    assert events == [("terminate", 111), "start", "supervisor"]
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
    )

    assert events == ["start", "supervisor"]
    assert result["previous_process_id"] == 0
    assert result["process_id"] == 333
