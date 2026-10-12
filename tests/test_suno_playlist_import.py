import json
from pathlib import Path

import pytest

from ls_suno import service


PLAYLIST_ID = "37884258-b006-461d-8f0e-5721b80f03c7"
PLAYLIST_URL = f"https://suno.com/playlist/{PLAYLIST_ID}"


def test_normalize_suno_playlist_id_accepts_url_and_uuid():
    assert service.normalize_suno_playlist_id(PLAYLIST_URL) == PLAYLIST_ID
    assert service.normalize_suno_playlist_id(PLAYLIST_ID.upper()) == PLAYLIST_ID
    with pytest.raises(ValueError):
        service.normalize_suno_playlist_id("https://suno.com/song/not-a-playlist")


def test_fetch_suno_playlist_detail_unwraps_playlist_clips(monkeypatch):
    payload = {
        "id": PLAYLIST_ID,
        "name": "New Folk",
        "num_total_results": 2,
        "playlist_clips": [
            {"relative_index": 1, "clip": {"id": "track-a", "title": "A"}},
            {"relative_index": 2, "clip": {"id": "track-b", "title": "B"}},
        ],
    }
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    def fake_urlopen(request, timeout=0):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(service, "suno_api_headers", lambda: {"Authorization": "Bearer test"})
    monkeypatch.setattr(service.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(service, "mark_suno_api_token_valid", lambda: None)

    result = service.fetch_suno_playlist_detail(PLAYLIST_URL)

    assert seen["url"].endswith(f"/api/playlist/{PLAYLIST_ID}/")
    assert result["playlist_name"] == "New Folk"
    assert result["expected_count"] == 2
    assert result["complete"] is True
    assert [row["id"] for row in result["tracks"]] == ["track-a", "track-b"]


def test_build_suno_playlist_preview_marks_existing_and_new(monkeypatch):
    monkeypatch.setattr(
        service,
        "fetch_suno_playlist_detail",
        lambda _value: {
            "playlist_id": PLAYLIST_ID,
            "playlist_url": PLAYLIST_URL,
            "playlist_name": "New Folk",
            "expected_count": 2,
            "raw_count": 2,
            "complete": True,
            "tracks": [
                {"id": "track-a", "title": "A"},
                {"id": "track-b", "title": "B"},
            ],
        },
    )
    monkeypatch.setattr(service, "is_suno_stem_track", lambda _raw: False)
    monkeypatch.setattr(
        service,
        "extract_suno_metadata_for_ls",
        lambda raw: {
            "id": raw["id"],
            "title": raw["title"],
            "workspaceName": "My Workspace",
        },
    )
    monkeypatch.setattr(
        service,
        "get_track_identity_snapshot",
        lambda: ({"track-a"}, {"track-a": {"title": "A"}}),
    )

    result = service.build_suno_playlist_preview(PLAYLIST_URL)

    assert result["playlist_name"] == "New Folk"
    assert result["track_count"] == 2
    assert result["existing_count"] == 1
    assert result["new_count"] == 1
    assert [row["in_ls_db"] for row in result["items"]] == [True, False]


def test_import_suno_playlist_selected_uses_only_selected_playlist_members(monkeypatch):
    monkeypatch.setattr(
        service,
        "fetch_suno_playlist_detail",
        lambda _value: {
            "playlist_id": PLAYLIST_ID,
            "playlist_url": PLAYLIST_URL,
            "playlist_name": "New Folk",
            "expected_count": 2,
            "raw_count": 2,
            "complete": True,
            "tracks": [
                {"id": "track-a", "title": "A"},
                {"id": "track-b", "title": "B"},
            ],
        },
    )
    monkeypatch.setattr(service, "is_suno_stem_track", lambda _raw: False)
    monkeypatch.setattr(
        service,
        "extract_suno_metadata_for_ls",
        lambda raw: {"id": raw["id"], "title": raw["title"]},
    )
    captured = {}

    def fake_insert(items):
        captured["ids"] = [item["raw"]["id"] for item in items]
        return {
            "ok": True,
            "inserted": 1,
            "skipped_existing": 0,
            "errors": 0,
            "selected_ids": ["track-b"],
            "last_imported_ids": ["track-b"],
        }

    monkeypatch.setattr(service, "insert_suno_tracks_metadata_only", fake_insert)

    result = service.import_suno_playlist_selected(PLAYLIST_URL, ["track-b"])

    assert captured["ids"] == ["track-b"]
    assert result["playlist_name"] == "New Folk"
    assert result["playlist_track_ids"] == ["track-b"]


def test_downloader_ui_exposes_playlist_url_flow():
    root = Path(__file__).resolve().parents[1]
    template = (root / "ls_downloader" / "templates" / "metadata_section.html").read_text(encoding="utf-8")
    script = (root / "ls_downloader" / "static" / "downloader_update_workflows_script.js").read_text(encoding="utf-8")
    controller = (root / "ls_downloader" / "controller.py").read_text(encoding="utf-8")

    assert 'id="suno-playlist-url"' in template
    assert 'id="load-suno-playlist-btn"' in template
    assert "/suno-playlist-preview?playlist_url=" in script
    assert '"/suno-import-selected-playlist"' in script
    assert 'path == "/suno-playlist-preview"' in controller
    assert 'path == "/suno-import-selected-playlist"' in controller
