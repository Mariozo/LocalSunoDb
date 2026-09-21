        let visibleRows = Number.POSITIVE_INFINITY;

        let currentSort = {
            column: window.LS_LIBRARY_BOOTSTRAP.sortColumn,
            direction: String(window.LS_LIBRARY_BOOTSTRAP.sortDirection || "asc")
        };

        let lastActiveAudio = null;
        let currentStemBlock = null;
        let autoplayListEnabled = false;
        let autoplayStartedFromPlayButton = false;

        function updateAutoplayUi() {
            if (autoplayListCheckbox) {
                autoplayListCheckbox.checked = autoplayListEnabled;
            }
            if (autoplayTopButton) {
                autoplayTopButton.classList.toggle("active", autoplayListEnabled);
                autoplayTopButton.title = autoplayListEnabled
                    ? "Auto list ON. Toggle: P"
                    : "Auto list OFF. Toggle: P";
            }
        }

        function showAutoplaySaveStatus(message, isError=false) {
            const statusNode = document.getElementById("settings-status");
            const modalNode = document.getElementById("settings-modal");
            if (statusNode) {
                statusNode.innerText = String(message || "");
                statusNode.style.color = isError ? "#a50e0e" : "#188038";
            }
            const modalVisible = modalNode && modalNode.style.display === "flex";
            if (isError && !modalVisible) {
                window.alert(String(message || "Auto list setting was not saved."));
            }
        }

        async function persistAutoplayListSetting() {
            const requestedEnabled = autoplayListEnabled;
            const body = new URLSearchParams();
            body.set("autoplay_list", requestedEnabled ? "1" : "0");

            try {
                const response = await fetch("/set-autoplay-list", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                const text = await response.text();
                if (!response.ok) {
                    throw new Error(text || ("HTTP " + response.status));
                }
                try {
                    localStorage.setItem(
                        "ls_autoplay_list_enabled",
                        requestedEnabled ? "1" : "0"
                    );
                } catch (error) {}
                const modalNode = document.getElementById("settings-modal");
                if (modalNode && modalNode.style.display === "flex") {
                    showAutoplaySaveStatus("Auto list setting saved.", false);
                }
                return true;
            } catch (error) {
                showAutoplaySaveStatus(
                    "Auto list setting was not saved: " +
                    String(error && error.message ? error.message : error),
                    true
                );
                return false;
            }
        }

        async function setAutoplayListEnabled(enabled, persist=true) {
            autoplayListEnabled = !!enabled;
            updateAutoplayUi();
            if (persist) {
                return await persistAutoplayListSetting();
            }
            return true;
        }

        async function toggleAutoplayListEnabled() {
            await setAutoplayListEnabled(!autoplayListEnabled, true);
        }

        function formatTime(seconds) {
            if (!isFinite(seconds) || seconds < 0) {
                return "0:00";
            }

            const minutes = Math.floor(seconds / 60);
            const rest = Math.floor(seconds % 60).toString().padStart(2, "0");
            return minutes + ":" + rest;
        }

        function tryNextThumb(img) {
            const rawFallbacks = img.dataset.fallbacks || "";
            const fallbacks = rawFallbacks.split("|").filter((item) => item);
            const index = parseInt(img.dataset.fallbackIndex || "0", 10);

            if (index < fallbacks.length) {
                const nextUrl = fallbacks[index];
                img.dataset.fallbackIndex = index + 1;
                img.src = nextUrl;

                const link = img.closest(".thumb-link");

                if (link) {
                    link.dataset.largeCover = nextUrl;
                }

                return;
            }

            const link = img.closest(".thumb-link");

            if (link) {
                link.classList.add("thumb-error");
                link.removeAttribute("data-large-cover");
                link.title = "Suno did not generate an available cover image";
            }
        }

        function getTrackRows() {
            return Array.from(table.querySelectorAll("tbody tr.track-row"));
        }

        function getFragmentRow(trackRow) {
            if (!trackRow) { return null; }
            let candidate = trackRow.nextElementSibling;
            while (candidate) {
                if (candidate.classList.contains("fragment-row")) {
                    return candidate;
                }
                if (candidate.classList.contains("track-row")) {
                    return null;
                }
                candidate = candidate.nextElementSibling;
            }
            return null;
        }

        function applyVisibleRows() {}

        function getNextVisibleTrackRow(trackRow) {
            const rows = getTrackRows().filter((row) => !row.classList.contains("row-hidden"));
            const index = rows.indexOf(trackRow);
            if (index < 0 || index + 1 >= rows.length) {
                return null;
            }
            return rows[index + 1];
        }

        function playTrackRow(trackRow) {
            if (!trackRow) { return false; }
            const button = trackRow.querySelector(".play-btn");
            if (!button) { return false; }
            autoplayStartedFromPlayButton = true;
            button.click();
            return true;
        }

        function autoplayNextFromFragment(fragmentRow) {
            const currentAudio = fragmentRow ? fragmentRow.querySelector(".suno-block audio, .local-block audio") : null;
            if (currentAudio && currentAudio.loop) {
                return;
            }
            if (!autoplayListEnabled || !autoplayStartedFromPlayButton || !fragmentRow) {
                return;
            }
            const trackRow = fragmentRow.previousElementSibling;
            const nextRow = getNextVisibleTrackRow(trackRow);
            if (!nextRow) {
                autoplayStartedFromPlayButton = false;
                return;
            }
            setTimeout(() => {
                playTrackRow(nextRow);
            }, 350);
        }

