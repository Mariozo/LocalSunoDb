(() => {
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
