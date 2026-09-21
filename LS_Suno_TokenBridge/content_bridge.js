(() => {
  "use strict";

  const BRIDGE_SOURCE = "ls-suno-token-bridge-v2";

  function runtimeIsAvailable() {
    try {
      return Boolean(chrome && chrome.runtime && chrome.runtime.id);
    } catch (error) {
      return false;
    }
  }

  async function safeSendMessage(message) {
    if (!runtimeIsAvailable()) return false;
    try {
      await chrome.runtime.sendMessage(message);
      return true;
    } catch (error) {
      return false;
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== window.location.origin) return;
    const data = event.data;
    if (!data || data.source !== BRIDGE_SOURCE) return;

    if (data.type === "LS_SUNO_DIAGNOSTIC") {
      safeSendMessage({
        type: "LS_SUNO_DIAGNOSTIC",
        diagnostic: data.diagnostic && typeof data.diagnostic === "object" ? data.diagnostic : {},
      });
      return;
    }

    if (data.type !== "LS_SUNO_TOKEN") return;
    const token = String(data.token || "").trim();
    if (!token) return;

    safeSendMessage({
      type: "LS_SUNO_TOKEN_CAPTURED",
      token,
      capture_source: String(data.captureSource || "page"),
      page_instance_id: String(data.pageInstanceId || ""),
    });
  });

  window.postMessage({ source: BRIDGE_SOURCE, type: "LS_SUNO_DIAGNOSTIC_REQUEST" }, window.location.origin);
  safeSendMessage({ type: "LS_SUNO_BRIDGE_PAGE_READY" });
})();
