from ls_web import app


def _repository_module():
    modules, _registry = app.compose_runtime(probe_mode=True)
    return next(module for module in modules if module.__name__ == "ls_data.repository")


def test_saved_views_runtime_constants_survive_repository_refactor(monkeypatch):
    repository = _repository_module()
    monkeypatch.setattr(repository, "get_settings", lambda: {"saved_views": []})

    assert repository.SAVED_VIEW_MAX_COUNT == 40
    assert repository.get_saved_views() == []
    assert repository.normalize_saved_view_query(
        "?workspace=A&workspace=B&sort_by=created"
    ) == "workspace=A&workspace=B&sort_by=created"


def test_saved_view_create_uses_restored_runtime_contract(monkeypatch):
    repository = _repository_module()
    stored = {}

    monkeypatch.setattr(repository, "get_settings", lambda: {"saved_views": []})
    monkeypatch.setattr(repository, "save_settings", lambda payload: stored.update(payload))

    item = repository.create_saved_view(
        "My view",
        "?workspace=A&category_filter=Song&sort_dir=desc",
    )

    assert item["name"] == "My view"
    assert item["query"] == "workspace=A&category_filter=Song&sort_dir=desc"
    assert stored["saved_views"] == [item]

def test_saved_view_preserves_long_exact_track_id_selection(monkeypatch):
    repository = _repository_module()
    stored = {}

    monkeypatch.setattr(repository, "get_settings", lambda: {"saved_views": []})
    monkeypatch.setattr(repository, "save_settings", lambda payload: stored.update(payload))

    track_ids = [
        f"00000000-0000-0000-0000-{index:012d}"
        for index in range(320)
    ]
    query = (
        "?track_ids=" + ",".join(track_ids)
        + "&rows=all&sort_by=title&sort_dir=asc"
    )

    item = repository.create_saved_view("Elza exact view", query)

    assert "track_ids=" in item["query"]
    assert "rows=" not in item["query"]
    assert "sort_by=title" in item["query"]
    assert "sort_dir=asc" in item["query"]

    parsed = __import__("urllib.parse", fromlist=["parse_qs"]).parse_qs(item["query"])
    saved_ids = parsed["track_ids"][0].split(",")
    assert saved_ids == track_ids
    assert stored["saved_views"] == [item]
