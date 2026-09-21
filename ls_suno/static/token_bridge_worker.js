const LS_BASE = "http://127.0.0.1:8765";
let lastToken = "";
let lastSentAt = 0;
let lastTokenPageInstanceId = "";
let lastWorkerError = "";

async function postForm(path, values = {}) {
  const body = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    body.set(key, String(value ?? ""));
  });

  const response = await fetch(LS_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!response.ok) throw new Error("LS bridge HTTP " + response.status);
  return response;
}

async function pingBridge() {
  try {
    await postForm("/bridge-ping", {
      extension_version: chrome.runtime.getManifest().version,
      previous_worker_error: lastWorkerError,
    });
    lastWorkerError = "";
  } catch (error) {
    lastWorkerError = String(error && error.message || error || "LS connection failed").slice(0, 240);
  }
}

async function sendDiagnostic(diagnostic) {
  const safeDiagnostic = diagnostic && typeof diagnostic === "object" ? diagnostic : {};
  try {
    await postForm("/bridge-diagnostic", {
      extension_version: chrome.runtime.getManifest().version,
      diagnostic_json: JSON.stringify(safeDiagnostic),
    });
    lastWorkerError = "";
    return true;
  } catch (error) {
    lastWorkerError = String(error && error.message || error || "Diagnostic relay failed").slice(0, 240);
    return false;
  }
}

async function sendToken(token, captureSource = "page", pageInstanceId = "") {
  const clean = String(token || "").replace(/^Bearer\s+/i, "").trim();
  if (!clean) return false;
  const now = Date.now();
  if (clean === lastToken && String(pageInstanceId || "") === lastTokenPageInstanceId && now - lastSentAt < 30000) {
    return true;
  }
  try {
    await postForm("/bridge-set-suno-api-token", {
      suno_api_token: clean,
      extension_version: chrome.runtime.getManifest().version,
      capture_source: captureSource,
      page_instance_id: String(pageInstanceId || "").slice(0, 240),
    });
    lastToken = clean;
    lastSentAt = now;
    lastTokenPageInstanceId = String(pageInstanceId || "");
    lastWorkerError = "";
    return true;
  } catch (error) {
    lastWorkerError = String(error && error.message || error || "Token relay failed").slice(0, 240);
    return false;
  }
}

async function refreshOpenSunoTabs() {
  try {
    const tabs = await chrome.tabs.query({ url: "https://suno.com/*" });
    await Promise.all((tabs || []).map(async (tab) => {
      if (!tab || typeof tab.id !== "number") return;
      try { await chrome.tabs.reload(tab.id); } catch (error) {}
    }));
  } catch (error) {
    lastWorkerError = String(error && error.message || error || "Could not refresh Suno tabs").slice(0, 240);
  }
}

async function refreshSunoTabsForFreshExtensionContext() {
  const markerKey = "ls_bridge_context_initialized";
  try {
    const state = await chrome.storage.session.get(markerKey);
    if (state && state[markerKey]) {
      return;
    }
    await chrome.storage.session.set({ [markerKey]: Date.now() });
    await refreshOpenSunoTabs();
  } catch (error) {
    lastWorkerError = String(error && error.message || error || "Could not refresh stale Suno extension context").slice(0, 240);
  }
}

function ensurePingAlarm() {
  chrome.alarms.create("ls-token-bridge-ping", { periodInMinutes: 1 });
}

chrome.runtime.onInstalled.addListener(() => {
  ensurePingAlarm();
  pingBridge();
});
chrome.runtime.onStartup.addListener(() => { ensurePingAlarm(); pingBridge(); });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm && alarm.name === "ls-token-bridge-ping") pingBridge();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const type = String(message && message.type || "");
  const senderUrl = String(sender && (sender.url || (sender.tab && sender.tab.url)) || "");
  const fromSunoPage = /^https:\/\/suno\.com\//i.test(senderUrl);

  if (type === "LS_SUNO_BRIDGE_PAGE_READY") {
    pingBridge().then(() => sendResponse({ ok: true }));
    return true;
  }

  if (type === "LS_SUNO_DIAGNOSTIC") {
    if (!fromSunoPage) { sendResponse({ ok: false, error: "Rejected non-Suno sender" }); return false; }
    sendDiagnostic(message && message.diagnostic).then((ok) => sendResponse({ ok }));
    return true;
  }

  if (type !== "LS_SUNO_TOKEN_CAPTURED") return false;
  if (!fromSunoPage) { sendResponse({ ok: false, error: "Rejected non-Suno sender" }); return false; }

  const token = String(message && message.token || "");
  const captureSource = String(message && message.capture_source || "page");
  const pageInstanceId = String(message && message.page_instance_id || "");
  sendToken(token, captureSource, pageInstanceId).then((ok) => sendResponse({ ok }));
  return true;
});

ensurePingAlarm();
pingBridge();
refreshSunoTabsForFreshExtensionContext();
