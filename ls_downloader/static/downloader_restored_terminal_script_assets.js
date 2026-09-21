        async function clearSavedDownloaderView() {
            try {
                const response = await fetch("/clear-downloader-state", { method: "POST" });
                let data = {};
                try {
                    data = await response.json();
                } catch (error) {
                    throw new Error("Nederīga servera atbilde (HTTP " + response.status + ")");
                }
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || ("HTTP " + response.status));
                }

                if (downloaderSaveTimer) {
                    clearTimeout(downloaderSaveTimer);
                    downloaderSaveTimer = null;
                }
                downloaderStateCleared = true;
                suppressDownloaderStateSave = true;
                try {
                    localStorage.removeItem(DOWNLOADER_STATE_KEY);
                } catch (error) {
                    throw new Error(
                        "Servera stāvoklis tika notīrīts, bet pārlūka stāvokli neizdevās notīrīt: " +
                        String(error && error.message ? error.message : error)
                    );
                }

                downloaderRestoredView = false;
                metaResult.dataset.restoredView = "0";
                metaResult.innerHTML = "";
                setStatus("Saglabātais Importa skats notīrīts. Vēlreiz atjauno dziesmu sarakstu.", "ok");
                setTimeout(() => {
                    suppressDownloaderStateSave = false;
                }, 0);
            } catch (error) {
                downloaderStateCleared = false;
                suppressDownloaderStateSave = false;
                setStatus(
                    "Neizdevās notīrīt saglabāto Importa skatu: " +
                    String(error && error.message ? error.message : error),
                    "error"
                );
            }
        }

        metaResult.addEventListener("change", (event) => {
            if (!downloaderRestoredView) { return; }
            const target = event.target;
            if (target && target.id === "update-check-all") {
                const checks = Array.from(metaResult.querySelectorAll(".update-row-check"));
                checks.forEach((check) => { check.checked = false; });
                if (target.checked) { limitCurrentChecks(checks).forEach((check) => { check.checked = true; }); }
            }
            updateRestoredSelectedCount();
            saveDownloaderState(false);
        });

        metaResult.addEventListener("click", async (event) => {
            const button = event.target.closest("button");
            if (button && button.id === "restore-selected-ignored-btn" && metaResult.contains(button)) {
                event.preventDefault();
                await restoreSelectedIgnoredTracklist();
                return;
            }
            if (!downloaderRestoredView) { return; }
            if (!button || !metaResult.contains(button)) { return; }

            if (button.id === "refresh-selected-meta-btn") {
                event.preventDefault();
                await refreshSelectedMetadataFromRestoredView(button);
            } else if (button.id === "preview-first-selected-btn") {
                const ids = getCurrentSelectedUpdateIds(false);
                if (!ids.length) { setStatus("Nav atzīmēta neviena rinda.", "error"); return; }
                trackIdInput.value = ids[0];
                previewMetaBtn.click();
            } else if (button.id === "select-all-shown-btn") {
                const checks = Array.from(metaResult.querySelectorAll(".update-row-check"));
                checks.forEach((check) => { check.checked = false; });
                limitCurrentChecks(checks).forEach((check) => { check.checked = true; });
                updateRestoredSelectedCount();
                saveDownloaderState(false);
            } else if (button.id === "select-none-btn") {
                metaResult.querySelectorAll(".update-row-check").forEach((check) => { check.checked = false; });
                updateRestoredSelectedCount();
                saveDownloaderState(false);
            } else if (button.id === "select-lyrics-prompt-btn") {
                const checks = Array.from(metaResult.querySelectorAll(".update-row-check"));
                checks.forEach((check) => { check.checked = false; });
                const matches = checks.filter((check) => {
                    const missing = String(check.dataset.missing || "").toLowerCase();
                    return missing.includes("lyrics") || missing.includes("prompt");
                });
                limitCurrentChecks(matches).forEach((check) => { check.checked = true; });
                updateRestoredSelectedCount();
                saveDownloaderState(false);
            } else if (button.classList.contains("small-preview-btn")) {
                trackIdInput.value = button.dataset.id || "";
                previewMetaBtn.click();
            } else if (button.id === "tracklist-select-all-btn") {
                metaResult.querySelectorAll(".tracklist-new-check").forEach((check) => { check.checked = true; });
                saveDownloaderState(false);
            } else if (button.id === "tracklist-select-none-btn") {
                metaResult.querySelectorAll(".tracklist-new-check").forEach((check) => { check.checked = false; });
                saveDownloaderState(false);
            } else if (button.id === "listen-selected-tracklist-btn") {
                listenSelectedFromRestoredView();
            } else if (button.id === "update-selected-titles-btn") {
                await updateSelectedTitlesFromRestoredView();
            } else if (button.id === "ignore-selected-tracklist-btn") {
                await ignoreSelectedFromRestoredView();
            } else if (button.id === "show-ignored-tracklist-btn") {
                await showIgnoredTracklist();
            } else if (button.id === "restore-selected-ignored-btn") {
                await restoreSelectedIgnoredTracklist();
            } else if (button.id === "import-selected-tracklist-btn") {
                await importSelectedFromRestoredView();
            } else if (button.id === "clear-downloader-state-btn") {
                await clearSavedDownloaderView();
            } else if (button.id === "meta-preview-close-btn") {
                markDownloaderViewFresh();
                metaResult.innerHTML = "";
                setStatus("Priekšskatījums aizvērts.", "ok");
            }
        });
