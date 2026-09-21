LS SUNO TOKEN BRIDGE v2.4.2

Purpose
-------
The extension runs only on https://suno.com/ and observes Suno page fetch/XHR calls
to https://studio-api-prod.suno.com/. When one of those calls carries the current
Authorization: Bearer token, the extension relays that token only to the local
LocalSunoDb endpoint:
http://127.0.0.1:8765/bridge-set-suno-api-token

Architecture
------------
page_capture.js  - MAIN world; reads Authorization before fetch/XHR is sent.
content_bridge.js - isolated content script; relays the captured token to the extension.
service_worker.js - sends the token only to local LocalSunoDb and keeps the bridge ping alive.

Self-diagnostics
----------------
The page bridge checks every two seconds that its fetch hook is still active. If Suno
replaces window.fetch, the bridge attaches itself again without replacing or bypassing
the current Suno request chain. A small diagnostic snapshot is sent only after a state
change and every 30 seconds. It contains no token and does not access the LS database.

Install / update
----------------
1. Start LocalSunoDb.
2. In LS Rīki → Suno savienojums click Bridge setup. This refreshes the files in:
   E:\LocalSunoDb\LS_Suno_TokenBridge
3. Open chrome://extensions/
4. On LS Suno Token Bridge click Reload.
   For a first install: enable Developer mode, click Load unpacked, and select the folder above.
5. Open Suno tabs are refreshed automatically once after the extension reloads.

After installation
------------------
Use Renew Suno login in LS or simply reload/open Suno Library. The next authenticated
Suno API request updates the token in LS automatically. F12 and manual token copying
are not needed.

Security
--------
The extension contains no remote code. It runs only on suno.com and can send data only
to the local LS address declared in host_permissions. The token is never logged by the
extension and is not sent to any third-party destination.
