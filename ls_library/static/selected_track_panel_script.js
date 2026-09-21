        // v5.20: Selected Track panel.
        // A blank-area row click and ArrowUp/ArrowDown use the same selection
        // function. Selection is UI-only and never changes the DB.
        const selectedTrackPanel = document.getElementById("selected-track-panel");
        const selectedTrackPanelCover = document.getElementById("selected-track-panel-cover");
        const selectedTrackPanelCoverPlaceholder = document.getElementById("selected-track-panel-cover-placeholder");
        const selectedTrackPanelTitle = document.getElementById("selected-track-panel-title");
        const selectedTrackPanelMeta = document.getElementById("selected-track-panel-meta");
        const selectedTrackOpenSuno = document.getElementById("selected-track-open-suno");
        const selectedTrackCompare = document.getElementById("selected-track-compare");
        const selectedTrackFlagsTags = selectedTrackPanel
            ? selectedTrackPanel.querySelector("#selected-track-flags-tags")
            : null;
        const selectedTrackLocalStatus = document.getElementById("selected-track-local-status");
        const selectedTrackStemsStatus = document.getElementById("selected-track-stems-status");
        const selectedTrackStyle = document.getElementById("selected-track-style");
        const selectedTrackLyrics = document.getElementById("selected-track-lyrics");
        const selectedTrackOpenStyle = document.getElementById("selected-track-open-style");
        const selectedTrackEditLyrics = document.getElementById("selected-track-edit-lyrics");

        let selectedTrackRow = null;
        let selectedTrackLoadSession = 0;

        // LS_LAST_PLAYED_STARTUP_SELECTION_V1_4
        const LS_LAST_PLAYED_TRACK_ID_KEY = "ls_last_played_track_id_v1";

        function selectedTrackReadLastPlayedId() {
            try {
                return String(localStorage.getItem(LS_LAST_PLAYED_TRACK_ID_KEY) || "").trim();
            } catch (error) {
                return "";
            }
        }

        function selectedTrackRememberLastPlayedId(trackId) {
            const value = String(trackId || "").trim();
            if (!value) { return; }
            try {
                localStorage.setItem(LS_LAST_PLAYED_TRACK_ID_KEY, value);
            } catch (error) {}
        }

        function selectedTrackVisibleRows() {
            return Array.from(
                table ? table.querySelectorAll("tbody tr.track-row") : []
            ).filter((row) => {
                if (row.classList.contains("hidden")) {
                    return false;
                }
                return row.offsetParent !== null;
            });
        }

        function selectedTrackRowFromElement(element) {
            if (!element || !element.closest) {
                return null;
            }
            const directRow = element.closest("tr.track-row");
            if (directRow) {
                return directRow;
            }
            const fragmentRow = element.closest("tr.fragment-row");
            const previousRow = fragmentRow
                ? fragmentRow.previousElementSibling
                : null;
            return previousRow &&
                previousRow.classList.contains("track-row")
                ? previousRow
                : null;
        }

        function selectedTrackSetText(node, value, emptyLabel) {
            if (!node) {
                return;
            }
            const textValue = String(value || "");
            if (textValue.trim()) {
                node.textContent = textValue;
                node.classList.remove("empty");
            } else {
                node.textContent = emptyLabel;
                node.classList.add("empty");
            }
        }

        function selectedTrackBuildMeta(row) {
            const parts = [];
            const kind = String(row.dataset.kind || "").trim();
            const durationNode = row.querySelector(".duration-cell");
            const workspaceNode = row.querySelector(".workspace-cell");
            const createdNode = row.querySelector(".created-cell");

            const duration = durationNode ? durationNode.textContent.trim() : "";
            const workspace = String(row.dataset.workspace || "").trim()
                || (workspaceNode ? workspaceNode.textContent.trim() : "");
            const created = createdNode ? createdNode.textContent.trim() : "";

            [kind, duration, workspace, created].forEach((value) => {
                if (value) {
                    parts.push(value);
                }
            });
            return parts.join(" · ");
        }

        function selectedTrackUpdateCover(row) {
            if (!selectedTrackPanelCover || !selectedTrackPanelCoverPlaceholder) {
                return;
            }

            const rowImage = row.querySelector("img.track-thumb");
            const rowImageFailed = Boolean(
                rowImage
                && rowImage.closest(".thumb-link")
                && rowImage.closest(".thumb-link").classList.contains("thumb-error")
            );
            const imageSource = rowImage && !rowImageFailed
                ? String(rowImage.currentSrc || rowImage.src || "").trim()
                : "";

            selectedTrackPanelCover.onerror = () => {
                selectedTrackPanelCover.style.display = "none";
                selectedTrackPanelCoverPlaceholder.style.display = "flex";
            };

            if (imageSource) {
                selectedTrackPanelCover.src = imageSource;
                selectedTrackPanelCover.style.display = "block";
                selectedTrackPanelCoverPlaceholder.style.display = "none";
            } else {
                selectedTrackPanelCover.removeAttribute("src");
                selectedTrackPanelCover.style.display = "none";
                selectedTrackPanelCoverPlaceholder.style.display = "flex";
            }
        }

        async function selectedTrackLoadText(row, trackId, session) {
            selectedTrackSetText(selectedTrackStyle, "", "Loading...");
            selectedTrackSetText(selectedTrackLyrics, "", "Loading...");

            try {
                const params = new URLSearchParams();
                params.set("track_id", trackId);
                const response = await fetch(
                    "/track-text-json?" + params.toString(),
                    { cache: "no-store" }
                );
                const data = await response.json();

                if (
                    session !== selectedTrackLoadSession ||
                    row !== selectedTrackRow ||
                    !response.ok ||
                    !data.ok
                ) {
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || "Could not load track text.");
                    }
                    return;
                }

                const fields = data.fields || {};
                const styleField = fields.style || {};
                const lyricsField = fields.lyrics || {};

                selectedTrackSetText(
                    selectedTrackStyle,
                    styleField.text || "",
                    "No Styles"
                );
                selectedTrackSetText(
                    selectedTrackLyrics,
                    lyricsField.text || "",
                    "No Lyrics"
                );
            } catch (error) {
                if (
                    session !== selectedTrackLoadSession ||
                    row !== selectedTrackRow
                ) {
                    return;
                }
                selectedTrackSetText(
                    selectedTrackStyle,
                    "",
                    "Could not load Styles"
                );
                selectedTrackSetText(
                    selectedTrackLyrics,
                    "",
                    "Could not load Lyrics"
                );
            }
        }

        function selectTrackRow(row, options={}) {
            if (!row || !row.classList.contains("track-row")) {
                return;
            }

            if (selectedTrackRow && selectedTrackRow !== row) {
                selectedTrackRow.classList.remove("selected-track-current");
            }

            selectedTrackRow = row;
            selectedTrackRow.classList.add("selected-track-current");

            const trackId = String(row.dataset.trackId || "").trim();
            const title = String(row.dataset.title || "").trim()
                || (
                    row.querySelector(".title-link")
                        ? row.querySelector(".title-link").textContent.trim()
                        : "Selected track"
                );
            const titleLink = row.querySelector(".title-link");
            const compareButton = row.querySelector(".compare-btn");
            const stemsButton = row.querySelector(".stems-btn");
            const playButton = row.querySelector(".play-btn");
            const hasLocalAudio = Boolean(
                playButton && playButton.dataset.hasLocalAudio === "true"
            );

            if (selectedTrackPanelTitle) {
                selectedTrackPanelTitle.textContent = title;
            }
            if (selectedTrackPanelMeta) {
                selectedTrackPanelMeta.textContent = selectedTrackBuildMeta(row);
            }
            if (selectedTrackOpenSuno) {
                selectedTrackOpenSuno.href = titleLink
                    ? titleLink.href
                    : (
                        trackId
                            ? "https://suno.com/song/" + encodeURIComponent(trackId)
                            : "https://suno.com"
                    );
            }
            if (selectedTrackCompare) {
                selectedTrackCompare.disabled = !compareButton;
                selectedTrackCompare.textContent = compareButton
                    ? "Compare"
                    : "Compare";
            }
            if (selectedTrackFlagsTags) {
                selectedTrackFlagsTags.disabled = !trackId;
                selectedTrackFlagsTags.dataset.trackId = trackId;
            }
            if (selectedTrackLocalStatus) {
                selectedTrackLocalStatus.textContent = hasLocalAudio
                    ? "Local: linked"
                    : "Local: none";
            }
            if (selectedTrackStemsStatus) {
                selectedTrackStemsStatus.textContent = stemsButton
                    ? stemsButton.textContent.trim()
                    : "Stems: none";
            }

            selectedTrackUpdateCover(row);

            selectedTrackLoadSession += 1;
            const session = selectedTrackLoadSession;
            selectedTrackLoadText(row, trackId, session);

            document.dispatchEvent(new CustomEvent(
                "ls-selected-track-changed",
                {
                    detail: {
                        trackId: trackId,
                        source: options.source || "selection"
                    }
                }
            ));

            if (options.scroll) {
                row.scrollIntoView({
                    block: "nearest",
                    behavior: "auto"
                });
            }
        }

        function selectTrackByDirection(direction) {
            const rows = selectedTrackVisibleRows();
            if (!rows.length) {
                return;
            }

            let currentIndex = selectedTrackRow
                ? rows.indexOf(selectedTrackRow)
                : -1;

            if (currentIndex < 0) {
                currentIndex = direction > 0 ? -1 : rows.length;
            }

            const nextIndex = Math.max(
                0,
                Math.min(rows.length - 1, currentIndex + direction)
            );
            selectTrackRow(rows[nextIndex], { scroll: true });
        }

        if (table) {
            table.addEventListener("click", (event) => {
                const row = selectedTrackRowFromElement(event.target);
                if (!row) {
                    return;
                }

                const interactive = event.target.closest(
                    "a, button, input, select, textarea, label, audio, .player-block, .stem-block"
                );
                if (!interactive) {
                    pausePlaybackForTrackSelection();
                }

                // Keep the right-hand Selected Track panel synchronized with the
                // exact Library row, even when the click lands on a row control.
                // The clicked control keeps its normal behavior.
                selectTrackRow(
                    row,
                    { scroll: false, source: "selection" }
                );
            });
        }

        // Keep the right panel synchronized when playback starts from Play,
        // Space, the embedded audio controls, Stems or Auto list.
        document.addEventListener("play", (event) => {
            const row = selectedTrackRowFromElement(event.target);
            if (!row) {
                return;
            }
            selectTrackRow(
                row,
                { scroll: false, source: "playback" }
            );
            document.dispatchEvent(new CustomEvent(
                "ls-track-playback-started",
                {
                    detail: {
                        trackId: String(row.dataset.trackId || "").trim()
                    }
                }
            ));
        }, true);


        // The global player also emits this event with its exact Track ID, so
        // persistence follows actual playback rather than title or mere selection.
        document.addEventListener("ls-track-playback-started", (event) => {
            const detail = event && event.detail ? event.detail : {};
            selectedTrackRememberLastPlayedId(detail.trackId || "");
        });

        // LS_STARTUP_SELECTION_READY_V1_5
        const LS_STARTUP_SELECTION_MAX_ATTEMPTS = 40;

        function selectedTrackStartupRows() {
            return Array.from(
                table ? table.querySelectorAll("tbody tr.track-row") : []
            ).filter((row) => (
                !row.classList.contains("hidden")
                && !row.classList.contains("row-hidden")
            ));
        }

        function selectedTrackRestoreStartupSelection(attempt=0) {
            if (selectedTrackRow) { return; }

            const rows = selectedTrackStartupRows();
            if (!rows.length) {
                if (attempt < LS_STARTUP_SELECTION_MAX_ATTEMPTS) {
                    window.setTimeout(
                        () => selectedTrackRestoreStartupSelection(attempt + 1),
                        50
                    );
                }
                return;
            }

            const lastPlayedId = selectedTrackReadLastPlayedId();
            const rememberedRow = lastPlayedId
                ? rows.find(
                    (row) => String(row.dataset.trackId || "").trim() === lastPlayedId
                )
                : null;
            const startupRow = rememberedRow || rows[0];
            if (!startupRow) { return; }

            selectTrackRow(
                startupRow,
                { scroll: false, source: "startup" }
            );
        }

        // Restore as soon as Library rows exist. Startup selection must not depend
        // on layout geometry (offsetParent), and it never starts audio or scrolls.
        if (document.readyState === "loading") {
            document.addEventListener(
                "DOMContentLoaded",
                () => selectedTrackRestoreStartupSelection(0),
                { once: true }
            );
        } else {
            window.setTimeout(() => selectedTrackRestoreStartupSelection(0), 0);
        }

        document.addEventListener("keydown", (event) => {
            if (event.key !== "ArrowUp" && event.key !== "ArrowDown") {
                return;
            }

            const active = document.activeElement;
            const activeTag = active
                ? String(active.tagName || "").toUpperCase()
                : "";
            if (
                active &&
                (
                    active.isContentEditable ||
                    ["INPUT", "TEXTAREA", "SELECT", "AUDIO", "BUTTON"].includes(activeTag)
                )
            ) {
                return;
            }

            event.preventDefault();
            selectTrackByDirection(event.key === "ArrowDown" ? 1 : -1);
        });

        if (selectedTrackCompare) {
            selectedTrackCompare.addEventListener("click", () => {
                if (!selectedTrackRow) {
                    return;
                }
                const compareButton = selectedTrackRow.querySelector(".compare-btn");
                if (compareButton) {
                    compareButton.click();
                }
            });
        }

        if (selectedTrackFlagsTags) {
            selectedTrackFlagsTags.addEventListener("click", () => {
                if (!selectedTrackRow) {
                    return;
                }
                const trackId = String(
                    selectedTrackFlagsTags.dataset.trackId ||
                    selectedTrackRow.dataset.trackId ||
                    ""
                ).trim();
                if (!trackId) {
                    return;
                }
                const detail = {
                    trackId,
                    source: "selected-track",
                    handled: false,
                };
                document.dispatchEvent(new CustomEvent(
                    "ls-library-open-flags-tags-track",
                    { detail }
                ));

                // Compatibility fallback for pages that have not installed the Library listener.
                // The existing Tags engine remains the single owner of TRACK MODE.
                if (!detail.handled) {
                    const libraryApi = window.LS && window.LS.library;
                    if (
                        libraryApi &&
                        typeof libraryApi.openFlagsAndTagsForTrack === "function"
                    ) {
                        detail.handled = Boolean(
                            libraryApi.openFlagsAndTagsForTrack(trackId)
                        );
                    }
                }
            });
        }

        if (selectedTrackOpenStyle) {
            selectedTrackOpenStyle.addEventListener("click", () => {
                if (!selectedTrackRow) {
                    return;
                }
                openTrackTextForTrack(
                    selectedTrackRow.dataset.trackId || "",
                    selectedTrackRow.dataset.title || "",
                    "style"
                );
            });
        }

        if (selectedTrackEditLyrics) {
            selectedTrackEditLyrics.addEventListener("click", () => {
                if (!selectedTrackRow) {
                    return;
                }
                openTrackTextForTrack(
                    selectedTrackRow.dataset.trackId || "",
                    selectedTrackRow.dataset.title || "",
                    "lyrics"
                );
            });
        }

