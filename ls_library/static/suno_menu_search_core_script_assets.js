        function closeTopMenus() {
            document.querySelectorAll(".top-dropdown").forEach((menu) => {
                menu.classList.add("hidden");
            });
        }

        function toggleTopMenu(menuId) {
            const menu = document.getElementById(menuId);
            if (!menu) {
                return;
            }
            const wasHidden = menu.classList.contains("hidden");
            closeTopMenus();
            if (wasHidden) {
                menu.classList.remove("hidden");
            }
        }

        const mainMenuButton = document.getElementById("main-menu-btn");
        const profileMenuButton = document.getElementById("profile-menu-btn");

        const openHelpButton = document.getElementById("open-help-modal");
        const sidebarToolsWrap = document.getElementById("ls-sidebar-tools-wrap");
        const sidebarToolsTrigger = document.getElementById("ls-sidebar-tools-trigger");
        const sidebarToolsPopover = document.getElementById("ls-sidebar-tools-popover");
        const openStatsButton = document.getElementById("open-stats-modal");
        const statsModal = document.getElementById("stats-modal");
        const statsModalClose = document.getElementById("stats-modal-close");
        const openSettingsButton = document.getElementById("open-settings-modal");
        const openFreshInstallSetupButton = document.getElementById("open-fresh-install-setup-btn");
        const freshInstallModal = document.getElementById("fresh-install-modal");
        const freshInstallClose = document.getElementById("fresh-install-close");
        const freshInstallDbStatus = document.getElementById("fresh-install-db-status");
        const freshInstallRootInput = document.getElementById("fresh-install-root-input");
        const freshInstallChooseRoot = document.getElementById("fresh-install-choose-root");
        const freshInstallImport = document.getElementById("fresh-install-import");
        const freshInstallStatus = document.getElementById("fresh-install-status");
        const settingsModal = document.getElementById("settings-modal");
        const settingsModalClose = document.getElementById("settings-modal-close");
        const audioLibraryRootInput = document.getElementById("audio-library-root-input");
        const chooseAudioLibraryRootButton = document.getElementById("choose-audio-library-root-btn");
        const saveAudioLibraryRootButton = document.getElementById("save-audio-library-root-btn");
        const stemRootInput = document.getElementById("stem-root-input");
        const chooseStemRootButton = document.getElementById("choose-stem-root-btn");
        const saveStemRootButton = document.getElementById("save-stem-root-btn");
        const lsUpdateIntervalInput = document.getElementById("ls-update-interval-input");
        const saveLsUpdateIntervalButton = document.getElementById("save-ls-update-interval-btn");
        const audioOutputSpeakersSelect = document.getElementById("audio-output-speakers-select");
        const audioOutputHeadphonesSelect = document.getElementById("audio-output-headphones-select");
        const saveAudioOutputDevicesButton = document.getElementById("save-audio-output-devices-btn");
        const autoplayListCheckbox = document.getElementById("autoplay-list-checkbox");
        const autoplayTopButton = document.getElementById("autoplay-top-btn");
        const settingsStatus = document.getElementById("settings-status");
        const helpModal = document.getElementById("help-modal");
        const helpModalText = document.getElementById("help-modal-text");
        const helpModalClose = document.getElementById("help-modal-close");
        const finderSearchBox = document.getElementById("finder-search-box");
        const finderSearchInput = document.getElementById("finder-search-input");
        const finderSearchName = document.getElementById("finder-search-name");
        const finderSearchLyrics = document.getElementById("finder-search-lyrics");
        const finderSearchPrompt = document.getElementById("finder-search-prompt");
        const finderSearchMarks = document.getElementById("finder-search-marks");
        const finderSearchTags = document.getElementById("finder-search-tags");
        const finderSearchClose = document.getElementById("finder-search-close");
        const finderSearchPrev = document.getElementById("finder-search-prev");
        const finderSearchNext = document.getElementById("finder-search-next");
        const finderSearchCount = document.getElementById("finder-search-count");
        const openF4SearchButton = document.getElementById("open-f4-search-btn");
        const FINDER_SEARCH_HISTORY_KEY = "ls_finder_search_history_v506";
        const FINDER_SEARCH_HISTORY_LIMIT = 20;
        let finderCurrentIndex = -1;
        let finderSearchHistoryIndex = -1;
        let finderSearchDraft = "";
        function isFinderSearchOpen() {
            return finderSearchBox && finderSearchBox.style.display === "block";
        }

        function syncFinderSidebarChoiceState() {
            if (!openF4SearchButton) { return; }
            const isOpen = Boolean(isFinderSearchOpen());
            openF4SearchButton.classList.toggle("active", isOpen);
            openF4SearchButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
        }

        function readFinderSearchHistory() {
            try {
                const raw = JSON.parse(localStorage.getItem(FINDER_SEARCH_HISTORY_KEY) || "[]");
                if (!Array.isArray(raw)) { return []; }

                const result = [];
                const seen = new Set();
                raw.forEach((value) => {
                    const textValue = String(value || "").trim();
                    const key = textValue.toLocaleLowerCase();
                    if (textValue && !seen.has(key)) {
                        result.push(textValue);
                        seen.add(key);
                    }
                });
                return result.slice(0, FINDER_SEARCH_HISTORY_LIMIT);
            } catch (error) {
                return [];
            }
        }

        function saveFinderSearchHistory(history) {
            try {
                localStorage.setItem(
                    FINDER_SEARCH_HISTORY_KEY,
                    JSON.stringify((history || []).slice(0, FINDER_SEARCH_HISTORY_LIMIT))
                );
            } catch (error) {}
        }

        function rememberFinderSearchQuery(value) {
            const searchText = String(value || "").trim();
            if (!searchText) { return; }

            const searchKey = searchText.toLocaleLowerCase();
            const history = readFinderSearchHistory().filter(
                (item) => String(item || "").trim().toLocaleLowerCase() !== searchKey
            );
            history.unshift(searchText);
            saveFinderSearchHistory(history);
            finderSearchHistoryIndex = 0;
            finderSearchDraft = "";
        }

        function finderParamIsTrue(value) {
            return ["1", "true", "yes", "on"].includes(
                String(value || "").trim().toLowerCase()
            );
        }

        function parseFinderStructuredSearch(value) {
            const flagTokenMasks = new Map([
                ["1+*", 1],
                ["2+*", 2],
                ["3+*", 4],
                ["4+*", 8],
                ["5+*", 16],
            ]);
            const queryParts = [];
            const flagMasks = [];
            const tags = [];
            const seenTags = new Set();
            let anyMark = false;

            String(value || "").trim().split(/\s+/).filter(Boolean).forEach((part) => {
                const token = part.toLowerCase();
                if (token === "0+*") {
                    anyMark = true;
                    return;
                }
                if (flagTokenMasks.has(token)) {
                    const mask = flagTokenMasks.get(token);
                    if (!flagMasks.includes(mask)) { flagMasks.push(mask); }
                    return;
                }
                if (part.startsWith("#")) {
                    const tag = normalizeOneTagClient(part);
                    const key = userTagKey(tag);
                    if (tag && !seenTags.has(key)) {
                        tags.push(tag);
                        seenTags.add(key);
                        return;
                    }
                }
                queryParts.push(part);
            });

            return {
                query: queryParts.join(" ").trim(),
                flagMasks: flagMasks,
                tags: tags,
                anyMark: anyMark,
            };
        }

        function sameFinderFlagMasks(left, right) {
            const a = Array.from(left || []).map(Number).sort((x, y) => x - y);
            const b = Array.from(right || []).map(Number).sort((x, y) => x - y);
            return a.length === b.length && a.every((value, index) => value === b[index]);
        }

        function sameFinderTags(left, right) {
            const a = Array.from(left || []).map(userTagKey).sort();
            const b = Array.from(right || []).map(userTagKey).sort();
            return a.length === b.length && a.every((value, index) => value === b[index]);
        }

        function getAppliedFinderSearchState() {
            try {
                const url = new URL(window.location.href);
                const appliedMarkBits = parseLibraryFlagFilter(
                    url.searchParams.get("flag_filter") || ""
                );
                return {
                    query: (url.searchParams.get("q") || "").trim(),
                    styleQuery: (url.searchParams.get("style_q") || "").trim(),
                    marks: finderParamIsTrue(url.searchParams.get("search_marks")),
                    tagsAny: finderParamIsTrue(url.searchParams.get("search_tags")),
                    flagMasks: [1, 2, 4, 8, 16].filter(
                        (mask) => (appliedMarkBits & mask) !== 0
                    ),
                    specificTags: parseLibraryTagFilter(
                        url.searchParams.get("tag_filter") || ""
                    ),
                };
            } catch (error) {
                return {
                    query: "",
                    styleQuery: "",
                    marks: false,
                    tagsAny: false,
                    flagMasks: [],
                    specificTags: [],
                };
            }
        }

        function isAppliedFinderScopeOnlyFilter() {
            const applied = getAppliedFinderSearchState();
            return (
                !applied.query
                && !applied.styleQuery
                && (
                    applied.marks
                    || applied.tagsAny
                    || applied.flagMasks.length
                    || applied.specificTags.length
                )
            );
        }

        function getFinderResultRows() {
            const searchText = finderSearchInput ? (finderSearchInput.value || "").trim() : "";
            const applied = getAppliedFinderSearchState();
            const parsed = parseFinderStructuredSearch(searchText);
            if (parsed.query !== applied.query) { return []; }
            if (!sameFinderFlagMasks(parsed.flagMasks, applied.flagMasks)) { return []; }
            if (!sameFinderTags(parsed.tags, applied.specificTags)) { return []; }

            const marksChecked = !!(finderSearchMarks && finderSearchMarks.checked);
            const tagsChecked = !!(finderSearchTags && finderSearchTags.checked);
            const anyMarkRequested = (
                marksChecked || (parsed.anyMark && !parsed.flagMasks.length)
            );
            const hasRequestedFilter = Boolean(
                parsed.query
                || parsed.flagMasks.length
                || parsed.tags.length
                || anyMarkRequested
                || tagsChecked
            );
            if (!hasRequestedFilter) { return []; }
            if (anyMarkRequested !== applied.marks) { return []; }
            if (tagsChecked !== applied.tagsAny) { return []; }
            return getTrackRows();
        }

        function updateFinderCount() {
            if (!finderSearchCount) { return; }
            const rows = getFinderResultRows();
            if (!rows.length) {
                finderCurrentIndex = -1;
                finderSearchCount.innerText = "0/0";
                return;
            }
            if (finderCurrentIndex < 0) { finderCurrentIndex = 0; }
            if (finderCurrentIndex >= rows.length) { finderCurrentIndex = rows.length - 1; }
            finderSearchCount.innerText = String(finderCurrentIndex + 1) + "/" + String(rows.length);
        }

        function clearFinderHighlight() {
            document.querySelectorAll("tr.track-row.find-current").forEach((row) => {
                row.classList.remove("find-current");
            });
        }

        function goToFinderResult(index) {
            const rows = getFinderResultRows();
            clearFinderHighlight();
            if (!rows.length) {
                finderCurrentIndex = -1;
                updateFinderCount();
                return;
            }
            if (index < 0) { index = rows.length - 1; }
            if (index >= rows.length) { index = 0; }
            finderCurrentIndex = index;

            if (isFinite(visibleRows) && finderCurrentIndex >= visibleRows) {
                visibleRows = finderCurrentIndex + 1;
                applyVisibleRows();
            }

            const row = rows[finderCurrentIndex];
            row.classList.add("find-current");
            row.scrollIntoView({ block: "center", behavior: "smooth" });
            updateFinderCount();
        }

        function setFinderSearchInputFromHistory(value, historyIndex) {
            if (!finderSearchInput) { return; }
            finderSearchInput.value = String(value || "");
            finderSearchHistoryIndex = historyIndex;
            clearFinderHighlight();
            finderCurrentIndex = -1;
            updateFinderCount();
            finderSearchInput.select();
        }

        function navigateFinderSearchHistory(direction) {
            if (!finderSearchInput) { return; }
            const history = readFinderSearchHistory();
            if (!history.length) { return; }

            // direction > 0 = older (ArrowUp), direction < 0 = newer (ArrowDown).
            if (direction > 0) {
                if (finderSearchHistoryIndex < 0) {
                    finderSearchDraft = finderSearchInput.value || "";
                    finderSearchHistoryIndex = 0;
                } else if (finderSearchHistoryIndex < history.length - 1) {
                    finderSearchHistoryIndex += 1;
                }
                setFinderSearchInputFromHistory(
                    history[finderSearchHistoryIndex],
                    finderSearchHistoryIndex
                );
                return;
            }

            if (finderSearchHistoryIndex > 0) {
                finderSearchHistoryIndex -= 1;
                setFinderSearchInputFromHistory(
                    history[finderSearchHistoryIndex],
                    finderSearchHistoryIndex
                );
            } else if (finderSearchHistoryIndex === 0) {
                setFinderSearchInputFromHistory(finderSearchDraft, -1);
            }
        }

        function openFinderSearchBox() {
            if (!finderSearchBox || !finderSearchInput) { return; }
            closeTopMenus();
            closeRowMenus();

            const currentValue = (finderSearchInput.value || "").trim();
            const history = readFinderSearchHistory();
            const scopeOnlyActive = isAppliedFinderScopeOnlyFilter();

            // After Reset the URL no longer contains q, but the last question remains
            // available in localStorage and is restored when Ctrl+F is opened.
            // An active empty-text ✶ / #tag filter must stay empty.
            if (!currentValue && history.length && !scopeOnlyActive) {
                finderSearchInput.value = history[0];
                finderSearchHistoryIndex = 0;
                finderSearchDraft = "";
            } else if (currentValue) {
                const currentKey = currentValue.toLocaleLowerCase();
                const foundIndex = history.findIndex(
                    (item) => String(item || "").trim().toLocaleLowerCase() === currentKey
                );
                finderSearchHistoryIndex = foundIndex;
                finderSearchDraft = foundIndex < 0 ? finderSearchInput.value : "";
            }

            finderSearchBox.style.display = "block";
            syncFinderSidebarChoiceState();
            updateFinderCount();
            setTimeout(() => {
                finderSearchInput.focus();
                finderSearchInput.select();
            }, 30);
        }

        function closeFinderSearchBox() {
            if (finderSearchBox) { finderSearchBox.style.display = "none"; }
            syncFinderSidebarChoiceState();
        }

        function exitFinderSearch() {
            // Esc / × only hides the Ctrl+F panel. The applied selection remains.
            closeFinderSearchBox();
        }

        function submitFinderSearch() {
            const url = new URL(window.location.href);
            const searchText = finderSearchInput ? (finderSearchInput.value || "").trim() : "";
            const parsed = parseFinderStructuredSearch(searchText);
            if (searchText) {
                rememberFinderSearchQuery(searchText);
            }
            if (parsed.query) {
                url.searchParams.set("q", parsed.query);
            } else {
                url.searchParams.delete("q");
            }
            if (parsed.flagMasks.length) {
                url.searchParams.set("flag_filter", parsed.flagMasks.join(","));
            } else {
                url.searchParams.delete("flag_filter");
            }
            if (parsed.tags.length) {
                url.searchParams.set("tag_filter", parsed.tags.join(","));
            } else {
                url.searchParams.delete("tag_filter");
            }
            url.searchParams.delete("style_q");
            // A new F4 search leaves an exact selected-ID view and searches the whole LS DB.
            url.searchParams.delete("track_ids");
            url.searchParams.delete("selected_from_suno");
            url.searchParams.set("search_name", finderSearchName && finderSearchName.checked ? "1" : "0");
            url.searchParams.set("search_lyrics", finderSearchLyrics && finderSearchLyrics.checked ? "1" : "0");
            url.searchParams.set("search_prompt", finderSearchPrompt && finderSearchPrompt.checked ? "1" : "0");
            url.searchParams.set(
                "search_marks",
                (
                    (finderSearchMarks && finderSearchMarks.checked)
                    || (parsed.anyMark && !parsed.flagMasks.length)
                ) ? "1" : "0"
            );
            url.searchParams.set("search_tags", finderSearchTags && finderSearchTags.checked ? "1" : "0");
            url.searchParams.delete("rows");
            saveViewState();
            window.location.href = url.toString();
        }

        if (openF4SearchButton) {
            openF4SearchButton.addEventListener("click", openFinderSearchBox);
        }
        syncFinderSidebarChoiceState();
