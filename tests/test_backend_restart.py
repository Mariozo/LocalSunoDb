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

    assert events == [("guard", True), ("terminate", 111), "start", ("guard", False), "supervisor"]
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

    assert events == [("guard", True), "start", ("guard", False), "supervisor"]
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
