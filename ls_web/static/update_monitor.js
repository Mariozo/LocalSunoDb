(() => {
        if (window.__lsUpgradeMonitorV3) { return; }
        window.__lsUpgradeMonitorV3 = true;

        const EXPECTED_KEY = "ls_upgrade_expected_version";
        const URL_KEY = "ls_upgrade_return_url";
        const scriptUrl = (() => {
            try { return new URL(document.currentScript && document.currentScript.src ? document.currentScript.src : "", window.location.href); }
            catch (error) { return null; }
        })();
        const pageVersion = scriptUrl ? String(scriptUrl.searchParams.get("v") || "") : "";
        let expectedVersion = "";
        let sawRestart = false;

        try {
            expectedVersion = sessionStorage.getItem(EXPECTED_KEY) || "";
        } catch (error) {}

        async function post(path, values={}) {
            const body = new URLSearchParams();
            Object.entries(values).forEach(([key, value]) => body.set(key, String(value ?? "")));
            const response = await fetch(path, {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                body,
                cache: "no-store"
            });
            return await response.json();
        }

        async function showNativeMessage(message, error=true) {
            try {
                await post("/ls-upgrade/native-message", {
                    message: String(message || ""),
                    title: "LocalSunoDb Upgrade",
                    error: error ? "1" : "0"
                });
            } catch (nativeError) {
                console.error("LocalSunoDb Upgrade notification failed", nativeError);
            }
        }

        window.LSRunToolsUpdateDirect = async function(event, button) {
            if (event) { event.preventDefault(); }
            if (button) { button.disabled = true; }
            try {
                const payload = await post("/open-ls-native-update-dialog");
                const openedVersion = String(payload.new_version || payload.version || payload.expected_version || "");
                if (payload.ok && openedVersion) {
                    rememberExpected(openedVersion);
                }
                if (!payload.ok && payload.error) {
                    await showNativeMessage(payload.error, true);
                }
            } catch (error) {
                await showNativeMessage("LocalSunoDb Upgrade logu neizdevās atvērt: " + error, true);
            } finally {
                if (button) { button.disabled = false; }
            }
            return false;
        };

        function rememberExpected(candidateVersion) {
            if (!candidateVersion) { return; }
            expectedVersion = candidateVersion;
            try {
                sessionStorage.setItem(EXPECTED_KEY, expectedVersion);
                if (!sessionStorage.getItem(URL_KEY)) {
                    sessionStorage.setItem(URL_KEY, window.location.href);
                }
            } catch (error) {}
        }

        function reloadPreservingUrl() {
            let returnUrl = window.location.href;
            try { returnUrl = sessionStorage.getItem(URL_KEY) || returnUrl; } catch (error) {}
            try {
                sessionStorage.removeItem(EXPECTED_KEY);
                sessionStorage.removeItem(URL_KEY);
            } catch (error) {}
            if (returnUrl === window.location.href) {
                window.location.reload();
            } else {
                window.location.replace(returnUrl);
            }
        }

        async function monitorUpgrade() {
            try {
                const statusResponse = await fetch("/ls-upgrade/status?_=" + Date.now(), {cache: "no-store"});
                const status = await statusResponse.json();
                const state = String(status.state || "");
                const candidateVersion = String(status.expected_version || "");

                // Do not depend on observing the short pre-restart state.  If the first
                // successful poll after restart already says completed, the old page can
                // still identify that it was rendered by the previous LS version from the
                // versioned script URL and reload itself exactly once.
                if (
                    candidateVersion &&
                    ["installing", "staged", "restarting", "verifying", "completed"].includes(state) &&
                    (!pageVersion || candidateVersion !== pageVersion)
                ) {
                    rememberExpected(candidateVersion);
                }

                if (expectedVersion) {
                    const versionResponse = await fetch("/app-version?ls_upgrade_app_probe=" + Date.now(), {cache: "no-store"});
                    const versionPayload = await versionResponse.json();
                    const running = String(versionPayload.app_version || versionPayload.running_version || "");
                    if (running === expectedVersion && (sawRestart || state === "completed")) {
                        reloadPreservingUrl();
                        return;
                    }
                }
            } catch (error) {
                if (expectedVersion) { sawRestart = true; }
            }
            window.setTimeout(monitorUpgrade, 900);
        }

        monitorUpgrade();
    })();
