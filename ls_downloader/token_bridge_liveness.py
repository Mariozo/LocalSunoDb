from __future__ import annotations

import json
from pathlib import Path

from ls_suno.service import ensure_suno_token_bridge_files


TOKEN_BRIDGE_LIVENESS_VERSION = "2.4.2"
LOCAL_LS_MATCH = "http://127.0.0.1:8765/*"
LOCAL_PROBE_FILENAME = "local_probe.js"


_LOCAL_PROBE_SCRIPT = r'''(() => {
  "use strict";

  const MARKER_ID = "ls-suno-token-bridge-liveness";
  const extensionVersion = chrome.runtime.getManifest().version;

  function publishHeartbeat() {
    try {
      const root = document.documentElement || document.head || document.body;
      if (!root) {
        return;
      }

      let marker = document.getElementById(MARKER_ID);
      if (!marker) {
        marker = document.createElement("meta");
        marker.id = MARKER_ID;
        marker.setAttribute("name", "ls-suno-token-bridge-liveness");
        root.appendChild(marker);
      }

      marker.setAttribute("data-extension-version", extensionVersion);
      marker.setAttribute("data-seen-at", String(Date.now()));
    } catch (error) {
      // Next heartbeat retries. No network request is required for liveness.
    }
  }

  publishHeartbeat();
  window.setInterval(publishHeartbeat, 1000);
})();
'''


def _patched_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("Token Bridge manifest root must be an object")

    manifest = dict(manifest)
    # The generator owns the extension version. Liveness must never downgrade it.

    permissions = list(manifest.get("host_permissions") or [])
    if LOCAL_LS_MATCH not in permissions:
        permissions.append(LOCAL_LS_MATCH)
    manifest["host_permissions"] = permissions

    scripts = []
    for item in manifest.get("content_scripts") or []:
        if not isinstance(item, dict):
            continue
        js = item.get("js") or []
        if isinstance(js, list) and LOCAL_PROBE_FILENAME in js:
            continue
        scripts.append(item)
    scripts.append({
        "matches": [LOCAL_LS_MATCH],
        "js": [LOCAL_PROBE_FILENAME],
        "run_at": "document_start",
        "world": "ISOLATED",
    })
    manifest["content_scripts"] = scripts
    return manifest


def _write_if_changed(path: Path, content: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8", errors="replace") == content:
        return
    path.write_text(content, encoding="utf-8")


def ensure_token_bridge_liveness_files() -> dict:
    """Refresh the generated extension and add the local active-liveness probe.

    The legacy Suno generator remains the authority for token-capture files. This
    function only adds a local, token-free content script that proves the unpacked
    extension is currently enabled in the LS tab. Chrome still requires the user to
    reload/enable the unpacked extension after its manifest changes.
    """
    folder = Path(ensure_suno_token_bridge_files()).resolve()
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("Token Bridge manifest was not generated")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    manifest = _patched_manifest(manifest)
    _write_if_changed(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    _write_if_changed(folder / LOCAL_PROBE_FILENAME, _LOCAL_PROBE_SCRIPT)

    return {
        "ok": True,
        "folder": str(folder),
        "liveness_extension_version": str(manifest.get("version") or TOKEN_BRIDGE_LIVENESS_VERSION),
        "requires_extension_reload": True,
        "local_probe": str(folder / LOCAL_PROBE_FILENAME),
    }
