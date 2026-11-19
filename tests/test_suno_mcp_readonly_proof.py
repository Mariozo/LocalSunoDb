import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ls_suno import mcp_client


def test_oauth_start_uses_pkce_and_readonly_proof_scope(monkeypatch):
    calls = []

    def fake_json_request(url, **kwargs):
        calls.append((url, kwargs))
        return {"client_id": "client-123"}, {}

    monkeypatch.setattr(mcp_client, "_json_request", fake_json_request)
    result = mcp_client.start_suno_mcp_oauth()

    assert result["ok"] is True
    parsed = urlparse(result["authorization_url"])
    query = parse_qs(parsed.query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client-123"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == [mcp_client.SUNO_MCP_RESOURCE]
    scope = query["scope"][0].split()
    assert "api:v0" in scope
    assert "profile:read" in scope
    assert "library:read" in scope
    assert "credits:spend" in scope
    assert "offline_access" in scope
    assert "library:write" not in scope
    assert "download" not in scope
    assert calls[0][0] == mcp_client.SUNO_MCP_REGISTER_URL


def test_oauth_callback_exchanges_code_and_saves_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mcp_client,
        "SUNO_MCP_CREDENTIALS_PATH",
        tmp_path / "oauth.json",
    )
    responses = [
        ({"client_id": "client-abc"}, {}),
        ({
            "access_token": "access-xyz",
            "refresh_token": "refresh-xyz",
            "token_type": "Bearer",
            "expires_in": 900,
            "scope": mcp_client.SUNO_MCP_SCOPE,
        }, {}),
    ]

    def fake_json_request(url, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(mcp_client, "_json_request", fake_json_request)
    start = mcp_client.start_suno_mcp_oauth()
    state = parse_qs(urlparse(start["authorization_url"]).query)["state"][0]

    result = mcp_client.complete_suno_mcp_oauth({
        "state": [state],
        "code": ["auth-code"],
    })

    assert result["ok"] is True
    saved = json.loads(
        Path(mcp_client.SUNO_MCP_CREDENTIALS_PATH).read_text(encoding="utf-8")
    )
    assert saved["client_id"] == "client-abc"
    assert saved["access_token"] == "access-xyz"
    assert saved["refresh_token"] == "refresh-xyz"
    assert saved["obtained_at"] > 0


def test_readonly_proof_calls_only_read_tools(monkeypatch):
    called = []

    class FakeSession:
        def __init__(self, token):
            assert token == "token"

        def call_tool(self, name, arguments=None):
            called.append((name, arguments or {}))
            if name == "account-me":
                return {
                    "display_name": "M",
                    "handle": "m",
                    "profile_url": "https://suno.com/@m",
                }
            if name == "account-usage":
                return {
                    "allowed_models": ["v6"],
                    "features": [],
                    "suno_account": {
                        "credits_remaining": 10,
                        "download_credits_remaining": 3,
                        "monthly_usage": 1,
                        "monthly_limit": 10,
                        "renews_on": "2026-12-01",
                        "plan": {"name": "Pro", "period": "monthly"},
                    },
                }
            if name == "library-list":
                return {
                    "items": [{
                        "id": "track-1",
                        "title": "Song",
                        "status": "complete",
                        "created_at": "2026-11-17T00:00:00Z",
                        "metadata": {"style": "folk", "duration": 123},
                    }],
                    "next_cursor": "next",
                }
            raise AssertionError("unexpected tool: " + name)

    monkeypatch.setattr(mcp_client, "_valid_access_token", lambda: "token")
    monkeypatch.setattr(mcp_client, "_McpSession", FakeSession)

    result = mcp_client.run_suno_mcp_readonly_proof()

    assert [name for name, _args in called] == [
        "account-me",
        "account-usage",
        "library-list",
    ]
    assert called[-1][1] == {"limit": 5}
    assert result["db_writes"] == 0
    assert result["credit_spend_calls"] == 0
    assert result["library"]["items"][0]["id"] == "track-1"


def test_ui_and_routes_are_present():
    controller = Path("ls_downloader/controller.py").read_text(encoding="utf-8")
    template = Path(
        "ls_downloader/templates/connection_section.html"
    ).read_text(encoding="utf-8")
    script = Path(
        "ls_downloader/static/downloader_suno_mcp_proof_script.js"
    ).read_text(encoding="utf-8")

    assert '"/suno-mcp-connect"' in controller
    assert '"/suno-mcp-proof-status"' in controller
    assert '"/suno-mcp-oauth-callback"' in controller
    assert 'id="suno-mcp-connect-btn"' in template
    assert 'id="suno-mcp-proof-btn"' in template
    assert "/suno-mcp-connect" in script
    assert "/suno-mcp-proof-status?run=" in script

def test_library_and_playlist_readers_call_only_read_tools(monkeypatch):
    calls = []

    class FakeSession:
        def __init__(self, token):
            assert token == "token"

        def call_tool(self, name, arguments=None):
            calls.append((name, dict(arguments or {})))
            if name == "library-list":
                return {
                    "items": [{
                        "id": "lib-1",
                        "title": "Library song",
                        "status": "complete",
                        "created_at": "2026-11-19T10:00:00Z",
                        "metadata": {"style": "folk", "duration": 120},
                    }],
                    "next_cursor": "lib-next",
                }
            if name == "playlists-list":
                return {
                    "items": [{
                        "id": "playlist-1",
                        "name": "New Folk",
                        "description": "Test playlist",
                        "visibility": "private",
                        "clip_count": 10,
                    }],
                }
            if name == "playlists-list-clips":
                return {
                    "clips": [{
                        "id": "clip-1",
                        "title": "Playlist song",
                        "status": "complete",
                        "metadata": {"style": "jazz", "duration": 140},
                    }],
                    "next_cursor": "clip-next",
                }
            raise AssertionError("unexpected tool: " + name)

    monkeypatch.setattr(mcp_client, "_valid_access_token", lambda: "token")
    monkeypatch.setattr(mcp_client, "_McpSession", FakeSession)

    library = mcp_client.read_suno_mcp_library(limit=999)
    playlists = mcp_client.read_suno_mcp_playlists(limit=50, query="New")
    clips = mcp_client.read_suno_mcp_playlist_clips("playlist-1", limit=50)

    assert calls == [
        ("library-list", {"limit": 50}),
        ("playlists-list", {"limit": 50, "query": "New"}),
        ("playlists-list-clips", {"id": "playlist-1", "limit": 50}),
    ]
    assert library["items"][0]["title"] == "Library song"
    assert library["items"][0]["style"] == "folk"
    assert library["next_cursor"] == "lib-next"
    assert playlists["items"][0]["name"] == "New Folk"
    assert playlists["items"][0]["clip_count"] == 10
    assert clips["items"][0]["title"] == "Playlist song"
    assert clips["next_cursor"] == "clip-next"
    for payload in (library, playlists, clips):
        assert payload["read_only"] is True
        assert payload["source"] == "suno_mcp"
        assert payload["db_writes"] == 0


def test_playlist_reader_requires_playlist_id(monkeypatch):
    monkeypatch.setattr(mcp_client, "_valid_access_token", lambda: "token")
    try:
        mcp_client.read_suno_mcp_playlist_clips("")
    except mcp_client.SunoMcpError as exc:
        assert "Playlist ID" in str(exc)
    else:
        raise AssertionError("missing playlist ID must fail")


def test_mcp_readonly_ui_and_routes_are_present():
    controller = Path("ls_downloader/controller.py").read_text(encoding="utf-8")
    template = Path(
        "ls_downloader/templates/connection_section.html"
    ).read_text(encoding="utf-8")
    script = Path(
        "ls_downloader/static/downloader_suno_mcp_proof_script.js"
    ).read_text(encoding="utf-8")

    for route in (
        "/suno-mcp-library-read",
        "/suno-mcp-playlists-read",
        "/suno-mcp-playlist-clips-read",
    ):
        assert route in controller
        assert route in script

    assert 'id="suno-mcp-library-btn"' in template
    assert 'id="suno-mcp-playlists-btn"' in template
    assert 'id="suno-mcp-playlist-list"' in template
    assert "playlists-create" not in script
    assert "playlists-add-clips" not in script
    assert "playlists-remove-clips" not in script

