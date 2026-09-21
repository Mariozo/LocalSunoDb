        const DOWNLOADER_STATE_KEY = "ls_downloader_state_v2";
        const LEGACY_DOWNLOADER_STATE_KEYS = [
            "ls_downloader_meta_result_html",
            "ls_downloader_scroll_y",
            "ls_downloader_status_text",
            "ls_downloader_status_mode"
        ];
        let downloaderSaveTimer = null;
        let downloaderRestoredView = false;
        let suppressDownloaderStateSave = false;
        let downloaderStateCleared = false;

        function removeLegacyDownloaderStateKeys() {
            try {
                LEGACY_DOWNLOADER_STATE_KEYS.forEach((key) => localStorage.removeItem(key));
            } catch (error) {}
        }

        removeLegacyDownloaderStateKeys();

        function getDownloaderViewKind(htmlText="") {
            const text = String(htmlText || "");
            if (text.includes("Jaunākās Suno darba telpas — kas jauns?")) { return "tracklist"; }
            if (text.includes("LS metadatu pārbaudes priekšskatījums")) { return "update"; }
            if (text.includes("API metadatu kopsavilkums")) { return "meta_preview"; }
            return text.trim() ? "other" : "empty";
        }

        function collectDownloaderState() {
            const checkedControls = Array.from(metaResult.querySelectorAll('input[type="checkbox"]:checked')).map((item) => ({
                id: item.id || "",
                class_name: item.className || "",
                value: item.value || ""
            }));
            const selectValues = Array.from(metaResult.querySelectorAll("select")).map((item) => ({
                id: item.id || "",
                value: item.value || ""
            }));
            const htmlText = metaResult.innerHTML || "";
            return {
                html: htmlText,
                status_text: metaStatus.innerText || "",
                status_mode: String(metaStatus.className || "").replace(/^status\s*/, "").trim(),
                scroll_y: window.scrollY || 0,
                checked_controls: checkedControls,
                select_values: selectValues,
                view_kind: getDownloaderViewKind(htmlText),
                saved_at: new Date().toISOString()
            };
        }

        function isCompatibleDownloaderHtml(htmlText) {
            const savedHtml = String(htmlText || "");
            if (
                savedHtml
                && savedHtml.includes("Jaunie parastie Suno ieraksti")
                && (
                    !savedHtml.includes("listen-selected-tracklist-btn")
                    || !savedHtml.includes('data-tracklist-actions-version="2"')
                )
            ) {
                return false;
            }
            return true;
        }

        function normalizeDownloaderState(candidate) {
            if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
                return null;
            }
            const savedAt = String(candidate.saved_at || "").trim();
            const savedAtMs = Date.parse(savedAt);
            if (!savedAt || !Number.isFinite(savedAtMs)) {
                return null;
            }
            const htmlText = typeof candidate.html === "string" ? candidate.html : "";
            if (!isCompatibleDownloaderHtml(htmlText)) {
                return null;
            }
            return {
                html: htmlText,
                status_text: String(candidate.status_text || ""),
                status_mode: String(candidate.status_mode || ""),
                scroll_y: parseInt(candidate.scroll_y || 0, 10) || 0,
                checked_controls: Array.isArray(candidate.checked_controls) ? candidate.checked_controls : [],
                select_values: Array.isArray(candidate.select_values) ? candidate.select_values : [],
                view_kind: String(candidate.view_kind || getDownloaderViewKind(htmlText)),
                saved_at: savedAt
            };
        }

        function downloaderStateTimestamp(state) {
            if (!state) { return Number.NEGATIVE_INFINITY; }
            const value = Date.parse(String(state.saved_at || ""));
            return Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
        }

        function chooseNewestDownloaderState(browserState, serverState) {
            if (!browserState) { return serverState; }
            if (!serverState) { return browserState; }
            return downloaderStateTimestamp(serverState) > downloaderStateTimestamp(browserState)
                ? serverState
                : browserState;
        }

        function downloaderStatesMatch(first, second) {
            if (!first || !second) { return false; }
            try {
                return JSON.stringify(first) === JSON.stringify(second);
            } catch (error) {
                return false;
            }
        }

        function readDownloaderStateFromBrowser() {
            try {
                return normalizeDownloaderState(
                    JSON.parse(localStorage.getItem(DOWNLOADER_STATE_KEY) || "null")
                );
            } catch (error) {
                return null;
            }
        }

        function writeDownloaderStateToBrowser(state) {
            try {
                localStorage.setItem(DOWNLOADER_STATE_KEY, JSON.stringify(state || {}));
                return true;
            } catch (error) {
                return false;
            }
        }

        function applyDownloaderControlState(state) {
            const checked = Array.isArray(state.checked_controls) ? state.checked_controls : [];
            const selects = Array.isArray(state.select_values) ? state.select_values : [];

            metaResult.querySelectorAll('input[type="checkbox"]').forEach((item) => {
                item.checked = checked.some((saved) => {
                    if (saved.id && item.id) { return saved.id === item.id; }
                    return String(saved.class_name || "") === String(item.className || "")
                        && String(saved.value || "") === String(item.value || "");
                });
            });

            metaResult.querySelectorAll("select").forEach((item) => {
                const saved = selects.find((entry) => entry.id && entry.id === item.id);
                if (saved) { item.value = saved.value; }
            });
            updateRestoredSelectedCount();
        }

        let downloaderStateSaveError = "";

        function reportDownloaderStateSaveError(error) {
            const detail = String(
                error && error.message ? error.message : error || "Nezināma kļūda"
            );
            if (detail === downloaderStateSaveError) { return; }
            downloaderStateSaveError = detail;
            setStatus(
                "Importa skats saglabāts šajā pārlūkā, bet saglabāšana serverī neizdevās: " + detail,
                "error"
            );
        }

        async function writeDownloaderStateToServer(state) {
            try {
                const body = new URLSearchParams();
                body.set("state_json", JSON.stringify(state || {}));
                const response = await fetch("/save-downloader-state", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString(),
                    keepalive: true
                });
                let data = {};
                try {
                    data = await response.json();
                } catch (error) {
                    throw new Error("Nederīga servera atbilde (HTTP " + response.status + ")");
                }
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || ("HTTP " + response.status));
                }
                downloaderStateSaveError = "";
                return true;
            } catch (error) {
                reportDownloaderStateSaveError(error);
                return false;
            }
        }

        function saveDownloaderState(immediate=false) {
            if (suppressDownloaderStateSave || downloaderStateCleared) { return; }
            const state = collectDownloaderState();
            writeDownloaderStateToBrowser(state);

            if (downloaderSaveTimer) {
                clearTimeout(downloaderSaveTimer);
                downloaderSaveTimer = null;
            }
            if (immediate) {
                writeDownloaderStateToServer(state);
            } else {
                downloaderSaveTimer = setTimeout(() => writeDownloaderStateToServer(state), 350);
            }
        }

        async function readDownloaderStateFromServer() {
            try {
                const response = await fetch("/downloader-state", { cache: "no-store" });
                const data = await response.json();
                if (response.ok && data.ok && data.state && typeof data.state === "object") {
                    return normalizeDownloaderState(data.state);
                }
            } catch (error) {}
            return null;
        }

        async function restoreDownloaderState() {
            suppressDownloaderStateSave = true;
            try {
                const browserState = readDownloaderStateFromBrowser();
                const serverState = await readDownloaderStateFromServer();
                const state = chooseNewestDownloaderState(browserState, serverState);
                if (!state) { return; }

                if (!downloaderStatesMatch(browserState, state)) {
                    writeDownloaderStateToBrowser(state);
                }
                if (!downloaderStatesMatch(serverState, state)) {
                    writeDownloaderStateToServer(state);
                }

                if (state.status_text) {
                    metaStatus.className = "status " + (state.status_mode || "");
                    metaStatus.innerText = state.status_text;
                }
                const savedHtml = String(state.html || "");
                if (savedHtml) {
                    metaResult.innerHTML = savedHtml;
                    downloaderRestoredView = true;
                    metaResult.dataset.restoredView = "1";
                    const report = metaResult.querySelector(".last-refresh-report");
                    lastRefreshReportHtml = report ? report.outerHTML : "";
                    applyDownloaderControlState(state);
                    updateDownloaderEmptyActions();
                }
                const y = parseInt(state.scroll_y || 0, 10) || 0;
                if (y > 0) {
                    setTimeout(() => window.scrollTo(0, y), 150);
                }
            } finally {
                setTimeout(() => {
                    suppressDownloaderStateSave = false;
                }, 0);
            }
        }

        function markDownloaderViewFresh() {
            downloaderStateCleared = false;
            downloaderRestoredView = false;
            metaResult.dataset.restoredView = "0";
        }

        window.addEventListener("beforeunload", () => saveDownloaderState(true));
        window.addEventListener("scroll", () => saveDownloaderState(false), { passive: true });
        const downloaderStateObserver = new MutationObserver(() => saveDownloaderState(false));
        downloaderStateObserver.observe(metaResult, { childList: true, subtree: true });
        metaResult.addEventListener("change", () => saveDownloaderState(false));
        restoreDownloaderState();
