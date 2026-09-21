(() => {
        "use strict";
        const ACTIVE_SECTION = String((document.getElementById("ls-global-backfill-alert") || {}).dataset?.activeSection || "");
        const ALERT_STATUSES = new Set([
            "stopped_401", "stopped_429", "stopped_errors",
            "interrupted", "failed", "completed_with_errors"
        ]);
        const LAST_KEY = "ls_metadata_backfill_alert_last_v1";
        const PENDING_KEY = "ls_metadata_backfill_alert_pending_v1";
        const OWNER = String(Date.now()) + "-" + Math.random().toString(36).slice(2);
        const originalTitle = document.title;
        const alertBox = document.getElementById("ls-global-backfill-alert");
        const alertMessage = document.getElementById("ls-global-backfill-alert-message");
        const alertProgress = document.getElementById("ls-global-backfill-alert-progress");
        const closeButton = document.getElementById("ls-global-backfill-alert-close");

        function storageGet(key) {
            try { return localStorage.getItem(key) || ""; } catch (error) { return ""; }
        }

        function storageSet(key, value) {
            try { localStorage.setItem(key, value); return true; } catch (error) { return false; }
        }

        function storageRemove(key) {
            try { localStorage.removeItem(key); } catch (error) {}
        }

        function eventKey(data) {
            return [
                String(data.status || ""),
                String(data.started_at || ""),
                String(data.finished_at || ""),
                String(parseInt(data.processed || 0, 10) || 0),
                String(parseInt(data.total || 0, 10) || 0)
            ].join("|");
        }

        function eventMessage(data) {
            const status = String(data.status || "");
            const messages = {
                stopped_401: "Suno session expired. Renew Suno login, then continue the remaining rows.",
                stopped_429: "Suno rate limit was reached. Wait 5–10 minutes, then continue.",
                stopped_errors: "LS stopped after repeated errors. Check the report, then continue.",
                interrupted: "The LS process was interrupted. Start automatic backfill again to continue.",
                failed: "Automatic metadata backfill failed. Open Downloader to see the error.",
                completed_with_errors: "Metadata backfill finished with row errors. Open Downloader to review them."
            };
            return String(data.message || messages[status] || "Automatic metadata backfill stopped.");
        }

        function progressText(data) {
            const processed = parseInt(data.processed || 0, 10) || 0;
            const total = parseInt(data.total || 0, 10) || 0;
            const remaining = parseInt(data.remaining || 0, 10) || Math.max(0, total - processed);
            const errors = parseInt(data.errors || 0, 10) || 0;
            return "Progress: " + processed + " / " + total + " · remaining: " + remaining + " · errors: " + errors;
        }

        function claimEvent(key) {
            if (!key || storageGet(LAST_KEY) === key) { return false; }
            const claimKey = key + "::" + OWNER;
            if (!storageSet(LAST_KEY, claimKey)) { return true; }
            if (storageGet(LAST_KEY) !== claimKey) { return false; }
            storageSet(LAST_KEY, key);
            return storageGet(LAST_KEY) === key;
        }

        function showPageAlert(data) {
            if (!alertBox) { return; }
            alertMessage.textContent = eventMessage(data);
            alertProgress.textContent = progressText(data);
            alertBox.style.display = "block";
            if (!document.title.startsWith("⚠ ")) { document.title = "⚠ " + originalTitle; }
        }

        function showSystemNotification(data) {
            if (!("Notification" in window) || Notification.permission !== "granted") { return false; }
            try {
                const notification = new Notification("LocalSunoDb: metadata process stopped", {
                    body: eventMessage(data) + "\n" + progressText(data),
                    tag: "ls-metadata-backfill-stopped",
                    renotify: true,
                    requireInteraction: true
                });
                notification.onclick = () => {
                    try { window.focus(); } catch (error) {}
                    window.location.href = "/downloader";
                    notification.close();
                };
                return true;
            } catch (error) {
                return false;
            }
        }

        function savePending(key, data) {
            storageSet(PENDING_KEY, JSON.stringify({ key, data }));
        }

        function consumePendingAlert() {
            if (document.hidden) { return; }
            const raw = storageGet(PENDING_KEY);
            if (!raw) { return; }
            try {
                const pending = JSON.parse(raw);
                storageRemove(PENDING_KEY);
                if (pending && pending.key && claimEvent(String(pending.key))) {
                    showPageAlert(pending.data || {});
                }
            } catch (error) {
                storageRemove(PENDING_KEY);
            }
        }

        function handleStoppedState(data) {
            const status = String(data && data.status || "");
            if (!ALERT_STATUSES.has(status)) { return; }
            const key = eventKey(data);
            const alreadyHandled = storageGet(LAST_KEY);
            if (alreadyHandled === key || alreadyHandled.startsWith(key + "::")) {
                storageRemove(PENDING_KEY);
                return;
            }

            if (document.hidden) {
                if ("Notification" in window && Notification.permission === "granted") {
                    if (claimEvent(key)) {
                        storageRemove(PENDING_KEY);
                        showSystemNotification(data);
                    }
                } else {
                    savePending(key, data);
                }
                return;
            }

            if (ACTIVE_SECTION !== "downloader" && claimEvent(key)) {
                storageRemove(PENDING_KEY);
                showPageAlert(data);
            }
        }

        async function pollMetadataBackfillAlert() {
            try {
                const response = await fetch("/suno-metadata-backfill-status", { cache: "no-store" });
                const data = await response.json();
                if (response.ok && data && data.ok) { handleStoppedState(data); }
            } catch (error) {
                // A normal LS restart can briefly make this endpoint unavailable.
            }
        }

        window.lsRequestBackfillNotificationPermission = async function() {
            if (!("Notification" in window) || Notification.permission !== "default") {
                return ("Notification" in window) ? Notification.permission : "unsupported";
            }
            try { return await Notification.requestPermission(); }
            catch (error) { return Notification.permission; }
        };

        if (closeButton) {
            closeButton.addEventListener("click", () => {
                alertBox.style.display = "none";
                document.title = originalTitle;
            });
        }
        document.addEventListener("visibilitychange", consumePendingAlert);
        window.addEventListener("storage", (event) => {
            if (event.key === PENDING_KEY && !document.hidden) { consumePendingAlert(); }
        });
        consumePendingAlert();
        pollMetadataBackfillAlert();
        setInterval(pollMetadataBackfillAlert, 4000);
    })();
