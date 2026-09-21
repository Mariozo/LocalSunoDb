        const MAIN_VIEW_POSITION_KEY = "ls_main_view_position_v472";
        const MAIN_VIEW_PENDING_POSITION_KEY = "ls_main_view_pending_position_v259";
        let mainViewSaveTimer = null;
        const mainScrollContainer = document.querySelector(".table-wrap") || document.querySelector("main");

        function getMainViewKey() {
            return window.location.pathname + window.location.search;
        }

        function getMainScrollTop() {
            if (mainScrollContainer) {
                return mainScrollContainer.scrollTop || 0;
            }
            return window.scrollY || 0;
        }

        function scrollMainTo(y) {
            const targetY = Math.max(0, Number(y || 0));
            if (mainScrollContainer) {
                mainScrollContainer.scrollTo(0, targetY);
                return;
            }
            window.scrollTo(0, targetY);
        }

        function scrollMainBy(deltaY) {
            const delta = Number(deltaY || 0);
            if (mainScrollContainer) {
                mainScrollContainer.scrollBy(0, delta);
                return;
            }
            window.scrollBy(0, delta);
        }

        function getMainViewAnchorRow() {
            const containerTop = mainScrollContainer
                ? mainScrollContainer.getBoundingClientRect().top
                : 0;
            const stickyTop = containerTop + 74;
            const rows = getTrackRows().filter((row) => row.style.display !== "none");
            for (const row of rows) {
                const rect = row.getBoundingClientRect();
                if (rect.bottom > stickyTop) {
                    return row;
                }
            }
            return rows.length ? rows[rows.length - 1] : null;
        }

        function getSelectedMainViewRow() {
            if (
                typeof selectedTrackRow === "undefined"
                || !selectedTrackRow
                || !selectedTrackRow.classList.contains("track-row")
                || selectedTrackRow.classList.contains("row-hidden")
                || selectedTrackRow.offsetParent === null
            ) {
                return null;
            }
            return selectedTrackRow;
        }

        function buildMainViewPosition(viewKey) {
            const selectedAnchor = getSelectedMainViewRow();
            const anchor = selectedAnchor || getMainViewAnchorRow();
            const rect = anchor ? anchor.getBoundingClientRect() : null;
            const containerTop = mainScrollContainer
                ? mainScrollContainer.getBoundingClientRect().top
                : 0;
            return {
                view_key: String(viewKey || getMainViewKey()),
                scroll_y: getMainScrollTop(),
                track_id: anchor ? String(anchor.dataset.trackId || "") : "",
                selected_track_id: selectedAnchor
                    ? String(selectedAnchor.dataset.trackId || "")
                    : "",
                anchor_mode: selectedAnchor ? "selected" : "viewport",
                anchor_top: rect ? rect.top - containerTop : 0,
                saved_at: Date.now()
            };
        }

        function saveMainViewPosition() {
            try {
                const state = buildMainViewPosition(getMainViewKey());
                localStorage.setItem(MAIN_VIEW_POSITION_KEY, JSON.stringify(state));

                // Keep the older keys updated for backward compatibility with older LS versions.
                localStorage.setItem("ls_scroll_y", String(state.scroll_y));
                localStorage.setItem("ls_suno_database_scroll_y", String(state.scroll_y));
            } catch (error) {}
        }

        function savePendingMainViewPosition(targetHref) {
            try {
                const targetUrl = new URL(String(targetHref || ""), window.location.href);
                const targetViewKey = targetUrl.pathname + targetUrl.search;
                const state = buildMainViewPosition(targetViewKey);
                state.reason = "show_more";
                localStorage.setItem(MAIN_VIEW_PENDING_POSITION_KEY, JSON.stringify(state));
            } catch (error) {}
        }

        function restoreMainViewPosition() {
            try {
                if ("scrollRestoration" in history) {
                    history.scrollRestoration = "manual";
                }

                let state = JSON.parse(localStorage.getItem(MAIN_VIEW_POSITION_KEY) || "{}");
                const pendingState = JSON.parse(
                    localStorage.getItem(MAIN_VIEW_PENDING_POSITION_KEY) || "{}"
                );
                if (pendingState && pendingState.view_key === getMainViewKey()) {
                    state = pendingState;
                    localStorage.removeItem(MAIN_VIEW_PENDING_POSITION_KEY);
                } else if (
                    pendingState
                    && Number(pendingState.saved_at || 0) > 0
                    && Date.now() - Number(pendingState.saved_at || 0) > 300000
                ) {
                    localStorage.removeItem(MAIN_VIEW_PENDING_POSITION_KEY);
                }

                if (!state || state.view_key !== getMainViewKey()) {
                    return;
                }

                const restoreOnce = () => {
                    const rows = getTrackRows();
                    // LS_VIEW_LAST_PLAYED_SELECTION_V1_6
                    let lastPlayedId = "";
                    try {
                        lastPlayedId = String(
                            localStorage.getItem("ls_last_played_track_id_v1") || ""
                        ).trim().toLowerCase();
                    } catch (error) {}
                    const savedSelectedId = String(
                        state.selected_track_id || ""
                    ).trim().toLowerCase();
                    const explicitUserSelection = (
                        typeof lastExplicitUserTagTrackId !== "undefined"
                        && String(lastExplicitUserTagTrackId || "").trim()
                    );
                    if (!explicitUserSelection) {
                        const lastPlayedRow = lastPlayedId
                            ? rows.find((row) =>
                                String(row.dataset.trackId || "").trim().toLowerCase() === lastPlayedId
                                && !row.classList.contains("row-hidden")
                                && row.offsetParent !== null
                            )
                            : null;
                        const savedSelectedRow = (!lastPlayedId && savedSelectedId)
                            ? rows.find((row) =>
                                String(row.dataset.trackId || "").trim().toLowerCase() === savedSelectedId
                                && !row.classList.contains("row-hidden")
                                && row.offsetParent !== null
                            )
                            : null;
                        const selectedRow = lastPlayedRow || savedSelectedRow;
                        if (
                            selectedRow
                            && typeof selectTrackRow === "function"
                            && (
                                selectedTrackRow !== selectedRow
                                || !selectedRow.classList.contains("selected-track-current")
                            )
                        ) {
                            selectTrackRow(
                                selectedRow,
                                { scroll: false, source: "view-restore" }
                            );
                        }
                    }

                    let restoredByAnchor = false;
                    const wantedId = String(state.track_id || "").toLowerCase();
                    if (wantedId) {
                        const anchor = rows.find((row) =>
                            String(row.dataset.trackId || "").toLowerCase() === wantedId
                            && !row.classList.contains("row-hidden")
                            && row.offsetParent !== null
                        );
                        if (anchor) {
                            const wantedTop = Number(state.anchor_top || 0);
                            const containerTop = mainScrollContainer
                                ? mainScrollContainer.getBoundingClientRect().top
                                : 0;
                            const currentTop = anchor.getBoundingClientRect().top - containerTop;
                            scrollMainBy(currentTop - wantedTop);
                            restoredByAnchor = true;
                        }
                    }

                    if (!restoredByAnchor) {
                        const y = parseInt(state.scroll_y || "0", 10) || 0;
                        scrollMainTo(y);
                    }
                };

                // Restore after sorting/visibility work and repeat while delayed layout settles.
                requestAnimationFrame(() => {
                    restoreOnce();
                    setTimeout(restoreOnce, 120);
                    setTimeout(restoreOnce, 360);
                    setTimeout(restoreOnce, 900);
                });
            } catch (error) {}
        }

        function saveViewState() {
            try {
                localStorage.setItem("ls_sort_state", JSON.stringify(currentSort));
            } catch (error) {}
            saveMainViewPosition();
        }

        function restoreScrollState() {
            restoreMainViewPosition();
        }

        // F5 / Ctrl+R and normal navigation: save continuously and again immediately
        // before reload. The anchor Track ID + viewport offset keeps the same visual
        // position even when a newly-added #tag changes row height after reload.
        const mainScrollEventTarget = mainScrollContainer || window;
        mainScrollEventTarget.addEventListener("scroll", () => {
            if (mainViewSaveTimer) { clearTimeout(mainViewSaveTimer); }
            mainViewSaveTimer = setTimeout(saveMainViewPosition, 90);
        }, { passive: true });
        window.addEventListener("pagehide", saveMainViewPosition);
        window.addEventListener("beforeunload", saveMainViewPosition);

        const showMoreButton = document.querySelector(".show-more-btn");
        if (showMoreButton) {
            showMoreButton.addEventListener("click", () => {
                savePendingMainViewPosition(showMoreButton.href);
            });
        }

        document.addEventListener("keydown", (event) => {
            const key = String(event.key || "").toLowerCase();
            if (event.key === "F5" || ((event.ctrlKey || event.metaKey) && key === "r")) {
                saveMainViewPosition();
            }
        }, true);

        function restoreSortState() {
            if (currentSort.column === null || !currentSort.direction) {
                return;
            }
            setSortIndicators(currentSort.column, currentSort.direction);
        }

        function nextSortDirection(column) {
            if (currentSort.column === column) {
                return currentSort.direction === "asc" ? "desc" : "asc";
            }
            return "asc";
        }

        function sortKeyForColumn(column) {
            if (column === 2) return "title";
            if (column === 4) return "created";
            if (column === 5) return "duration";
            return "";
        }

        function openServerSortedView(column, fullDatabase=false) {
            const sortKey = sortKeyForColumn(column);
            if (!sortKey) {
                return;
            }

            const direction = nextSortDirection(column);
            const params = fullDatabase
                ? new URLSearchParams()
                : new URLSearchParams(window.location.search);

            // Sort is performed in SQLite for every lazy-loaded batch.
            params.set("sort_by", sortKey);
            params.set("sort_dir", direction);
            params.delete("rows");
            params.delete("limit");
            params.delete("db_refresh");

            try {
                localStorage.setItem("ls_sort_state", JSON.stringify({
                    column: column,
                    direction: direction
                }));
            } catch (error) {}

            window.location.href = "/?" + params.toString();
        }

        function toggleSortColumn(column, type) {
            openServerSortedView(column, false);
        }

        function sortFullDatabase(column) {
            openServerSortedView(column, true);
        }

        headers.forEach((header) => {
            header.addEventListener("click", (event) => {
                const column = parseInt(header.dataset.column, 10);

                if (event.shiftKey) {
                    sortFullDatabase(column);
                    return;
                }

                toggleSortColumn(column, header.dataset.type);
            });
        });

        // Duration badges are appended lazily, so use delegated handling.
        document.addEventListener("click", (event) => {
            const badge = event.target.closest(".duration-sort-trigger");
            if (!badge) { return; }
            event.preventDefault();
            event.stopPropagation();
            if (event.shiftKey) {
                sortFullDatabase(5);
                return;
            }
            toggleSortColumn(5, "number");
        });

        restoreSortState();
        applyVisibleRows();
        restoreScrollState();

