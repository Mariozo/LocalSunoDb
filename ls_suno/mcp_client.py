"""Read-only proof client for Suno's official MCP/OAuth connection.

This module does not write the LS database and does not invoke any Suno tool
that creates, edits, downloads, or otherwise spends credits.  The OAuth grant
includes Suno's currently advertised credits:spend scope because the official
MCP resource uses that scope set for account usage; the proof itself calls only
account-me, account-usage, and library-list.
"""

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ls_core.runtime import DATA_DIR, HOST, PORT


SUNO_MCP_RESOURCE = "https://api.suno.com/mcp"
SUNO_MCP_REGISTER_URL = (
    "https://studio-api-prod.suno.com/api/v2/external/oauth/register/"
)
SUNO_MCP_AUTHORIZE_URL = (
    "https://studio-api-prod.suno.com/api/v2/external/oauth/authorize/"
)
SUNO_MCP_TOKEN_URL = (
    "https://studio-api-prod.suno.com/api/v2/external/oauth/token/"
)
SUNO_MCP_PROTOCOL_VERSION = "2025-06-18"
SUNO_MCP_SCOPE = (
    "api:v0 profile:read library:read credits:spend offline_access"
)
SUNO_MCP_CREDENTIALS_PATH = DATA_DIR / "suno_mcp_oauth.json"
SUNO_MCP_REDIRECT_PATH = "/suno-mcp-oauth-callback"
SUNO_MCP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Safari/537.36"
)
SUNO_MCP_REFRESH_WINDOW_SECONDS = 300

_SUNO_MCP_LOCK = threading.RLock()
_SUNO_MCP_PENDING = {}
_SUNO_MCP_LAST_PROOF = {}


class SunoMcpError(RuntimeError):
    pass


def _redirect_uri():
    return f"http://{HOST}:{int(PORT)}{SUNO_MCP_REDIRECT_PATH}"


def _json_request(url, *, method="GET", payload=None, form=None, headers=None, timeout=30):
    body = None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": SUNO_MCP_USER_AGENT,
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    elif form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = int(response.getcode() or 0)
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise SunoMcpError(
            f"Suno OAuth HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SunoMcpError(f"Suno OAuth connection failed: {exc.reason}") from exc

    if status < 200 or status >= 300:
        raise SunoMcpError(f"Suno OAuth returned HTTP {status}")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise SunoMcpError("Suno OAuth returned invalid JSON") from exc
    return data, response_headers


def _save_credentials(credentials):
    payload = {
        "access_token": str(credentials.get("access_token") or ""),
        "refresh_token": str(credentials.get("refresh_token") or ""),
        "token_type": str(credentials.get("token_type") or "Bearer"),
        "expires_in": int(credentials.get("expires_in") or 0),
        "scope": str(credentials.get("scope") or SUNO_MCP_SCOPE),
        "client_id": str(credentials.get("client_id") or ""),
        "obtained_at": int(credentials.get("obtained_at") or time.time()),
    }
    if not payload["access_token"] or not payload["client_id"]:
        raise SunoMcpError("Suno OAuth credentials are incomplete")

    path = Path(SUNO_MCP_CREDENTIALS_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return payload


def _load_credentials():
    path = Path(SUNO_MCP_CREDENTIALS_PATH)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SunoMcpError("Stored Suno MCP OAuth credentials are unreadable") from exc
    if not isinstance(payload, dict) or not str(payload.get("access_token") or ""):
        raise SunoMcpError("Stored Suno MCP OAuth credentials are incomplete")
    return payload


def _refresh_credentials(credentials):
    refresh_token = str(credentials.get("refresh_token") or "")
    client_id = str(credentials.get("client_id") or "")
    if not refresh_token or not client_id:
        raise SunoMcpError("Suno MCP login must be renewed")

    data, _headers = _json_request(
        SUNO_MCP_TOKEN_URL,
        method="POST",
        form={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "resource": SUNO_MCP_RESOURCE,
        },
        headers={
            "Origin": "https://suno.com",
            "Referer": "https://suno.com/",
        },
        timeout=30,
    )
    if not str(data.get("access_token") or ""):
        raise SunoMcpError("Suno OAuth refresh returned no access token")
    if not str(data.get("refresh_token") or ""):
        data["refresh_token"] = refresh_token
    data["client_id"] = client_id
    if not str(data.get("scope") or ""):
        data["scope"] = str(credentials.get("scope") or SUNO_MCP_SCOPE)
    data["obtained_at"] = int(time.time())
    return _save_credentials(data)


def _valid_access_token():
    with _SUNO_MCP_LOCK:
        credentials = _load_credentials()
        if credentials is None:
            raise SunoMcpError("Suno MCP is not connected")

        obtained_at = int(credentials.get("obtained_at") or 0)
        expires_in = int(credentials.get("expires_in") or 0)
        expires_at = obtained_at + expires_in if expires_in > 0 else 0
        if (
            expires_at
            and expires_at - int(time.time()) <= SUNO_MCP_REFRESH_WINDOW_SECONDS
        ):
            credentials = _refresh_credentials(credentials)
        token = str(credentials.get("access_token") or "")
        if not token:
            raise SunoMcpError("Suno MCP access token is missing")
        return token


def start_suno_mcp_oauth():
    redirect_uri = _redirect_uri()
    registration, _headers = _json_request(
        SUNO_MCP_REGISTER_URL,
        method="POST",
        payload={
            "client_name": "LocalSunoDb MCP Proof",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": SUNO_MCP_SCOPE,
        },
        timeout=30,
    )
    client_id = str(registration.get("client_id") or "").strip()
    if not client_id:
        raise SunoMcpError("Suno client registration returned no client_id")

    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("utf-8")).digest()
    ).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(24)
    created_at = time.time()

    with _SUNO_MCP_LOCK:
        _SUNO_MCP_PENDING.clear()
        _SUNO_MCP_PENDING.update({
            "state": state,
            "verifier": verifier,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "created_at": created_at,
        })

    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "redirect_uri": redirect_uri,
        "scope": SUNO_MCP_SCOPE,
        "resource": SUNO_MCP_RESOURCE,
    })
    return {
        "ok": True,
        "authorization_url": SUNO_MCP_AUTHORIZE_URL + "?" + query,
        "redirect_uri": redirect_uri,
        "scope": SUNO_MCP_SCOPE,
        "read_only_proof": True,
    }


def complete_suno_mcp_oauth(params):
    error = str((params.get("error") or [""])[0] or "").strip()
    if error:
        description = str(
            (params.get("error_description") or [""])[0] or ""
        ).strip()
        raise SunoMcpError(
            "Suno authorization was denied"
            + (f": {description}" if description else "")
        )

    state = str((params.get("state") or [""])[0] or "").strip()
    code = str((params.get("code") or [""])[0] or "").strip()
    if not state or not code:
        raise SunoMcpError("Suno OAuth callback is missing state or code")

    with _SUNO_MCP_LOCK:
        pending = dict(_SUNO_MCP_PENDING)
        if not pending or state != str(pending.get("state") or ""):
            raise SunoMcpError("Suno OAuth callback state does not match")
        if time.time() - float(pending.get("created_at") or 0) > 600:
            _SUNO_MCP_PENDING.clear()
            raise SunoMcpError("Suno OAuth callback expired")
        _SUNO_MCP_PENDING.clear()

    token_data, _headers = _json_request(
        SUNO_MCP_TOKEN_URL,
        method="POST",
        form={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": str(pending.get("redirect_uri") or _redirect_uri()),
            "client_id": str(pending.get("client_id") or ""),
            "code_verifier": str(pending.get("verifier") or ""),
            "resource": SUNO_MCP_RESOURCE,
        },
        headers={
            "Origin": "https://suno.com",
            "Referer": "https://suno.com/",
        },
        timeout=30,
    )
    if not str(token_data.get("access_token") or ""):
        raise SunoMcpError("Suno OAuth exchange returned no access token")
    token_data["client_id"] = str(pending.get("client_id") or "")
    token_data["obtained_at"] = int(time.time())
    if not str(token_data.get("scope") or ""):
        token_data["scope"] = SUNO_MCP_SCOPE
    _save_credentials(token_data)

    with _SUNO_MCP_LOCK:
        _SUNO_MCP_LAST_PROOF.clear()

    return {
        "ok": True,
        "connected": True,
        "scope": str(token_data.get("scope") or SUNO_MCP_SCOPE),
    }


def _decode_rpc_response(raw_text, expected_id):
    stripped = str(raw_text or "").strip()
    candidates = []
    if stripped.startswith("{"):
        candidates.append(stripped)
    else:
        for line in stripped.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if line.startswith("{"):
                candidates.append(line)

    matched = None
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if payload.get("id") == expected_id:
            matched = payload
    if matched is None:
        raise SunoMcpError("Suno MCP returned no matching JSON-RPC response")
    if isinstance(matched.get("error"), dict):
        error = matched["error"]
        raise SunoMcpError(
            f"Suno MCP error {error.get('code')}: {error.get('message')}"
        )
    return matched.get("result")


class _McpSession:
    def __init__(self, token):
        self.token = str(token or "")
        self.session_id = ""
        self.protocol_version = SUNO_MCP_PROTOCOL_VERSION
        self.next_id = 1
        self.initialized = False

    def _post(self, method, params=None, notification=False):
        request_id = None if notification else self.next_id
        if request_id is not None:
            self.next_id += 1
        body = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if request_id is not None:
            body["id"] = request_id
        if params is not None:
            body["params"] = params

        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol_version,
            "User-Agent": "LocalSunoDb/" + SUNO_MCP_PROTOCOL_VERSION,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        request = urllib.request.Request(
            SUNO_MCP_RESOURCE,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8", errors="replace")
                session_id = str(response.headers.get("Mcp-Session-Id") or "")
                if session_id:
                    self.session_id = session_id
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            raise SunoMcpError(
                f"Suno MCP HTTP {exc.code}: {detail or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise SunoMcpError(f"Suno MCP connection failed: {exc.reason}") from exc

        if notification:
            return None
        return _decode_rpc_response(raw, request_id)

    def initialize(self):
        if self.initialized:
            return
        result = self._post(
            "initialize",
            {
                "protocolVersion": SUNO_MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "LocalSunoDb",
                    "version": "readonly-proof",
                },
            },
        )
        if isinstance(result, dict) and result.get("protocolVersion"):
            self.protocol_version = str(result.get("protocolVersion"))
        self._post("notifications/initialized", notification=True)
        self.initialized = True

    def call_tool(self, name, arguments=None):
        self.initialize()
        result = self._post(
            "tools/call",
            {
                "name": str(name),
                "arguments": arguments or {},
            },
        )
        if not isinstance(result, dict):
            raise SunoMcpError(f"Suno MCP tool {name} returned an invalid result")
        if result.get("isError"):
            raise SunoMcpError(
                f"Suno MCP tool {name} failed: {_tool_result_text(result)}"
            )
        if isinstance(result.get("structuredContent"), (dict, list)):
            return result["structuredContent"]
        for item in result.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            if text.startswith(("{", "[")):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
        text = _tool_result_text(result)
        if text:
            return {"text": text}
        return {}


def _tool_result_text(result):
    parts = []
    for item in (result or {}).get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            value = str(item.get("text") or "").strip()
            if value:
                parts.append(value)
    return "\n".join(parts)


def _account_summary(account):
    if not isinstance(account, dict):
        return {}
    return {
        "display_name": str(account.get("display_name") or ""),
        "handle": str(account.get("handle") or ""),
        "profile_url": str(account.get("profile_url") or ""),
    }


def _usage_summary(usage):
    if not isinstance(usage, dict):
        return {}
    account = usage.get("suno_account")
    if not isinstance(account, dict):
        account = {}
    plan = account.get("plan")
    if not isinstance(plan, dict):
        plan = {}
    return {
        "plan": str(plan.get("name") or ""),
        "period": str(plan.get("period") or ""),
        "credits_remaining": account.get("credits_remaining"),
        "download_credits_remaining": account.get("download_credits_remaining"),
        "monthly_usage": account.get("monthly_usage"),
        "monthly_limit": account.get("monthly_limit"),
        "renews_on": str(account.get("renews_on") or ""),
        "allowed_models": list(usage.get("allowed_models") or []),
        "features": list(usage.get("features") or []),
    }


def _library_summary(page, limit=5):
    if not isinstance(page, dict):
        return {"count": 0, "items": [], "next_cursor": ""}
    raw_items = page.get("items")
    if not isinstance(raw_items, list):
        raw_items = []
    items = []
    for raw in raw_items[: max(0, int(limit or 5))]:
        if not isinstance(raw, dict):
            continue
        metadata = raw.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        items.append({
            "id": str(raw.get("id") or ""),
            "title": str(raw.get("title") or ""),
            "status": str(raw.get("status") or ""),
            "created_at": str(raw.get("created_at") or ""),
            "style": str(metadata.get("style") or ""),
            "duration": metadata.get("duration"),
        })
    return {
        "count": len(items),
        "items": items,
        "next_cursor": str(page.get("next_cursor") or ""),
    }


def _mcp_page_items(page, *keys):
    if not isinstance(page, dict):
        return []
    for key in keys:
        value = page.get(key)
        if isinstance(value, list):
            return value
    return []


def _mcp_next_cursor(page):
    if not isinstance(page, dict):
        return ""
    return str(page.get("next_cursor") or page.get("cursor") or "")


def _mcp_clip_row(raw):
    if not isinstance(raw, dict):
        return {}
    clip = raw.get("clip")
    if isinstance(clip, dict):
        raw = clip
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "id": str(raw.get("id") or raw.get("clip_id") or ""),
        "title": str(raw.get("title") or ""),
        "status": str(raw.get("status") or ""),
        "created_at": str(raw.get("created_at") or ""),
        "visibility": str(raw.get("visibility") or ""),
        "style": str(metadata.get("style") or raw.get("style") or ""),
        "duration": metadata.get("duration", raw.get("duration")),
        "liked": bool(raw.get("liked", False)),
    }


def _mcp_playlist_row(raw):
    if not isinstance(raw, dict):
        return {}
    return {
        "id": str(raw.get("id") or raw.get("playlist_id") or ""),
        "name": str(raw.get("name") or raw.get("title") or ""),
        "description": str(raw.get("description") or ""),
        "visibility": str(raw.get("visibility") or ""),
        "clip_count": raw.get("clip_count", raw.get("count")),
        "created_at": str(raw.get("created_at") or ""),
        "updated_at": str(raw.get("updated_at") or ""),
    }


def read_suno_mcp_library(limit=50, cursor=""):
    token = _valid_access_token()
    session = _McpSession(token)
    try:
        limit = max(1, min(50, int(limit or 50)))
    except (TypeError, ValueError):
        limit = 50
    arguments = {"limit": limit}
    cursor = str(cursor or "").strip()
    if cursor:
        arguments["cursor"] = cursor
    page = session.call_tool("library-list", arguments)
    rows = [
        _mcp_clip_row(item)
        for item in _mcp_page_items(page, "items", "clips")
    ]
    rows = [item for item in rows if item.get("id")]
    return {
        "ok": True,
        "source": "suno_mcp",
        "read_only": True,
        "items": rows,
        "count": len(rows),
        "next_cursor": _mcp_next_cursor(page),
        "db_writes": 0,
    }


def read_suno_mcp_playlists(limit=50, cursor="", query=""):
    token = _valid_access_token()
    session = _McpSession(token)
    try:
        limit = max(1, min(50, int(limit or 50)))
    except (TypeError, ValueError):
        limit = 50
    arguments = {"limit": limit}
    cursor = str(cursor or "").strip()
    if cursor:
        arguments["cursor"] = cursor
    query = str(query or "").strip()
    if query:
        arguments["query"] = query[:200]
    page = session.call_tool("playlists-list", arguments)
    rows = [
        _mcp_playlist_row(item)
        for item in _mcp_page_items(page, "items", "playlists")
    ]
    rows = [item for item in rows if item.get("id")]
    return {
        "ok": True,
        "source": "suno_mcp",
        "read_only": True,
        "items": rows,
        "count": len(rows),
        "next_cursor": _mcp_next_cursor(page),
        "db_writes": 0,
    }


def read_suno_mcp_playlist_clips(playlist_id, limit=50, cursor=""):
    playlist_id = str(playlist_id or "").strip()
    if not playlist_id:
        raise SunoMcpError("Playlist ID is required")
    token = _valid_access_token()
    session = _McpSession(token)
    try:
        limit = max(1, min(50, int(limit or 50)))
    except (TypeError, ValueError):
        limit = 50
    arguments = {
        "id": playlist_id,
        "limit": limit,
    }
    cursor = str(cursor or "").strip()
    if cursor:
        arguments["cursor"] = cursor
    page = session.call_tool("playlists-list-clips", arguments)
    rows = [
        _mcp_clip_row(item)
        for item in _mcp_page_items(page, "items", "clips")
    ]
    rows = [item for item in rows if item.get("id")]
    return {
        "ok": True,
        "source": "suno_mcp",
        "read_only": True,
        "playlist_id": playlist_id,
        "items": rows,
        "count": len(rows),
        "next_cursor": _mcp_next_cursor(page),
        "db_writes": 0,
    }


def run_suno_mcp_readonly_proof():
    token = _valid_access_token()
    session = _McpSession(token)
    account = session.call_tool("account-me", {})
    usage = session.call_tool("account-usage", {})
    library = session.call_tool("library-list", {"limit": 5})
    result = {
        "ok": True,
        "connected": True,
        "proof": "account-me + account-usage + library-list",
        "account": _account_summary(account),
        "usage": _usage_summary(usage),
        "library": _library_summary(library, limit=5),
        "db_writes": 0,
        "credit_spend_calls": 0,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    with _SUNO_MCP_LOCK:
        _SUNO_MCP_LAST_PROOF.clear()
        _SUNO_MCP_LAST_PROOF.update(result)
    return result


def get_suno_mcp_status(run_proof=False):
    try:
        credentials = _load_credentials()
    except Exception as exc:
        return {
            "ok": False,
            "connected": False,
            "error": str(exc),
            "credential_path": str(SUNO_MCP_CREDENTIALS_PATH),
        }

    if credentials is None:
        return {
            "ok": True,
            "connected": False,
            "credential_path": str(SUNO_MCP_CREDENTIALS_PATH),
            "scope": SUNO_MCP_SCOPE,
            "proof": None,
        }

    if run_proof:
        try:
            return run_suno_mcp_readonly_proof()
        except Exception as exc:
            return {
                "ok": False,
                "connected": True,
                "error": str(exc),
                "scope": str(credentials.get("scope") or ""),
                "credential_path": str(SUNO_MCP_CREDENTIALS_PATH),
            }

    with _SUNO_MCP_LOCK:
        last_proof = dict(_SUNO_MCP_LAST_PROOF)
    return {
        "ok": True,
        "connected": True,
        "scope": str(credentials.get("scope") or ""),
        "credential_path": str(SUNO_MCP_CREDENTIALS_PATH),
        "proof": last_proof or None,
    }


def render_suno_mcp_oauth_callback_page(ok, message):
    safe_message = (
        str(message or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    status = "ok" if ok else "error"
    return f"""<!doctype html>
<html lang="lv">
<head><meta charset="utf-8"><title>Suno MCP</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;padding:32px">
<h2>{'Suno MCP pieslēgts' if ok else 'Suno MCP pieslēgums neizdevās'}</h2>
<p>{safe_message}</p>
<script>
try {{
  if (window.opener) {{
    window.opener.postMessage({{
      type: "LS_SUNO_MCP_OAUTH_COMPLETE",
      ok: {str(bool(ok)).lower()},
      status: "{status}"
    }}, window.location.origin);
  }}
}} catch (error) {{}}
if ({str(bool(ok)).lower()}) {{
  window.setTimeout(() => window.close(), 900);
}}
</script>
</body></html>"""
