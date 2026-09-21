(() => {
  "use strict";

  const BRIDGE_SOURCE = "ls-suno-token-bridge-v2";
  const API_HOST = "studio-api-prod.suno.com";
  const FETCH_BRIDGE_MARKER = "__LS_SUNO_TOKEN_BRIDGE_FETCH_V2__";
  const FETCH_RECHECK_INTERVAL_MS = 2000;
  const DIAGNOSTIC_HEARTBEAT_MS = 30000;

  const diagnosticState = {
    pageLoaded: true,
    fetchRepairCount: 0,
    lastFetchRepairAt: "",
    lastApiRequestAt: "",
    lastAuthorizationAt: "",
    lastTokenEmitAt: "",
    pageInstanceId: (
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ) ? crypto.randomUUID() : String(Date.now()) + "-" + Math.random().toString(16).slice(2),
  };
  let fetchInstallCount = 0;
  let lastEmittedToken = "";
  let lastEmittedAt = 0;

  if (window.__LS_SUNO_TOKEN_BRIDGE_V2__) {
    return;
  }
  Object.defineProperty(window, "__LS_SUNO_TOKEN_BRIDGE_V2__", {
    value: true,
    configurable: false,
    enumerable: false,
    writable: false,
  });

  function isSunoApiUrl(value) {
    try {
      const url = new URL(String(value || ""), window.location.href);
      return url.hostname === API_HOST;
    } catch (error) {
      return false;
    }
  }

  function diagnosticSnapshot(eventName) {
    return {
      page_loaded: diagnosticState.pageLoaded,
      fetch_hook_active: Boolean(
        typeof window.fetch === "function" &&
        window.fetch[FETCH_BRIDGE_MARKER]
      ),
      fetch_repair_count: diagnosticState.fetchRepairCount,
      last_fetch_repair_at: diagnosticState.lastFetchRepairAt,
      last_api_request_at: diagnosticState.lastApiRequestAt,
      last_authorization_at: diagnosticState.lastAuthorizationAt,
      last_token_emit_at: diagnosticState.lastTokenEmitAt,
      last_diagnostic_event: String(eventName || "state"),
      page_instance_id: diagnosticState.pageInstanceId,
    };
  }

  function emitDiagnostic(eventName) {
    try {
      window.postMessage({
        source: BRIDGE_SOURCE,
        type: "LS_SUNO_DIAGNOSTIC",
        diagnostic: diagnosticSnapshot(eventName),
      }, window.location.origin);
    } catch (error) {
      // Diagnostics must never interfere with Suno.
    }
  }

  function markApiRequestSeen() {
    const firstRequest = !diagnosticState.lastApiRequestAt;
    diagnosticState.lastApiRequestAt = new Date().toISOString();
    if (firstRequest) {
      emitDiagnostic("api_request_seen");
    }
  }

  function authorizationFromHeaders(headersLike) {
    if (!headersLike) {
      return "";
    }

    try {
      const headers = new Headers(headersLike);
      return String(headers.get("authorization") || "");
    } catch (error) {
      // Continue with lightweight fallbacks below.
    }

    if (Array.isArray(headersLike)) {
      for (const item of headersLike) {
        if (!Array.isArray(item) || item.length < 2) {
          continue;
        }
        if (String(item[0] || "").toLowerCase() === "authorization") {
          return String(item[1] || "");
        }
      }
    }

    if (typeof headersLike === "object") {
      for (const [key, value] of Object.entries(headersLike)) {
        if (String(key || "").toLowerCase() === "authorization") {
          return String(value || "");
        }
      }
    }

    return "";
  }

  function emitAuthorization(value, captureSource) {
    const clean = String(value || "").replace(/^Bearer\s+/i, "").trim();
    if (!clean) {
      return;
    }

    const now = Date.now();
    diagnosticState.lastAuthorizationAt = new Date(now).toISOString();
    if (clean === lastEmittedToken && now - lastEmittedAt < 30000) {
      return;
    }

    lastEmittedToken = clean;
    lastEmittedAt = now;
    diagnosticState.lastTokenEmitAt = new Date(now).toISOString();

    window.postMessage({
      source: BRIDGE_SOURCE,
      type: "LS_SUNO_TOKEN",
      token: clean,
      captureSource: String(captureSource || "page"),
      pageInstanceId: diagnosticState.pageInstanceId,
    }, window.location.origin);
    emitDiagnostic("token_emitted");
  }

  function installFetchBridge() {
    const currentFetch = window.fetch;
    if (
      typeof currentFetch !== "function" ||
      currentFetch[FETCH_BRIDGE_MARKER]
    ) {
      return false;
    }

    function lsTokenBridgeFetch(input, init) {
      try {
        let requestUrl = "";
        if (typeof input === "string") {
          requestUrl = input;
        } else if (input instanceof URL) {
          requestUrl = input.href;
        } else if (input && typeof input.url === "string") {
          requestUrl = input.url;
        }

        if (isSunoApiUrl(requestUrl)) {
          markApiRequestSeen();
          let authorization = authorizationFromHeaders(init && init.headers);
          if (!authorization && typeof Request !== "undefined" && input instanceof Request) {
            authorization = authorizationFromHeaders(input.headers);
          }
          emitAuthorization(authorization, "fetch");
        }
      } catch (error) {
        // Never interfere with Suno requests.
      }

      return currentFetch.apply(this, arguments);
    }

    Object.defineProperty(lsTokenBridgeFetch, FETCH_BRIDGE_MARKER, {
      value: true,
      configurable: false,
      enumerable: false,
      writable: false,
    });

    window.fetch = lsTokenBridgeFetch;
    fetchInstallCount += 1;
    if (fetchInstallCount > 1) {
      diagnosticState.fetchRepairCount += 1;
      diagnosticState.lastFetchRepairAt = new Date().toISOString();
      emitDiagnostic("fetch_hook_repaired");
    } else {
      emitDiagnostic("fetch_hook_installed");
    }
    return true;
  }

  installFetchBridge();

  // Suno may replace window.fetch after document_start. Re-attach the bridge
  // to the latest function while preserving the complete existing fetch chain.
  window.setInterval(installFetchBridge, FETCH_RECHECK_INTERVAL_MS);
  window.setInterval(() => {
    installFetchBridge();
    emitDiagnostic("heartbeat");
  }, DIAGNOSTIC_HEARTBEAT_MS);
  window.addEventListener("pageshow", () => {
    installFetchBridge();
    emitDiagnostic("pageshow");
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      installFetchBridge();
      emitDiagnostic("visible");
    }
  });

  const xhrOpen = XMLHttpRequest.prototype.open;
  const xhrSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
  const xhrUrls = new WeakMap();

  XMLHttpRequest.prototype.open = function lsTokenBridgeXhrOpen(method, url) {
    try {
      xhrUrls.set(this, String(url || ""));
      if (isSunoApiUrl(url)) {
        markApiRequestSeen();
      }
    } catch (error) {
      // Ignore and preserve the original XHR behavior.
    }
    return xhrOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function lsTokenBridgeXhrHeader(name, value) {
    try {
      const requestUrl = xhrUrls.get(this) || "";
      if (
        isSunoApiUrl(requestUrl) &&
        String(name || "").toLowerCase() === "authorization"
      ) {
        emitAuthorization(value, "xhr");
      }
    } catch (error) {
      // Never interfere with Suno requests.
    }
    return xhrSetRequestHeader.apply(this, arguments);
  };

  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== window.location.origin) {
      return;
    }
    const data = event.data;
    if (
      data &&
      data.source === BRIDGE_SOURCE &&
      data.type === "LS_SUNO_DIAGNOSTIC_REQUEST"
    ) {
      installFetchBridge();
      emitDiagnostic("diagnostic_requested");
    }
  });

  emitDiagnostic("page_loaded");
})();
