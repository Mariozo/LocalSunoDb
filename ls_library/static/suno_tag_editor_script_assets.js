        function setTagPanelStatus(message, ok=true) {
            if (!userTagPanelStatus) { return; }
            userTagPanelStatus.innerText = message || "";
            userTagPanelStatus.style.color = ok ? "#188038" : "#a50e0e";
        }

        function tagMatchesSearch(tag) {
            const query = String(userTagSearchInput ? userTagSearchInput.value : "").trim().toLowerCase();
            return !query || String(tag || "").toLowerCase().includes(query);
        }

        function createUserTagItem(tag, assigned) {
            const item = document.createElement("div");
            item.className = "user-tag-item";

            const pin = document.createElement("button");
            pin.type = "button";
            pin.className = "user-tag-pin";
            pin.dataset.tag = tag;
            pin.title = pinnedUserTags.has(userTagKey(tag)) ? "Unpin tag" : "Pin tag";
            pin.innerText = pinnedUserTags.has(userTagKey(tag)) ? "★" : "☆";

            const toggle = document.createElement("button");
            toggle.type = "button";
            toggle.className = "user-tag-toggle" + (assigned ? " active" : "");
            toggle.dataset.tag = tag;
            toggle.title = userTagPanelMode === "filter"
                ? (assigned ? "Remove tag filter" : "Require this tag")
                : (assigned ? "Remove tag from this track" : "Add tag to this track");
            toggle.innerText = tag;

            const del = document.createElement("button");
            del.type = "button";
            del.className = "user-tag-delete";
            del.dataset.tag = tag;
            del.title = "Delete tag from catalog and remove its marker from all tracks";
            del.innerText = "×";

            item.appendChild(pin);
            item.appendChild(toggle);
            item.appendChild(del);
            return item;
        }

        function renderUserTagPanel() {
            if (!userTagSelectedList || !userTagPinnedList || !userTagAllList) { return; }
            const target = getActiveUserTagTarget();
            const assigned = new Set(
                (userTagPanelMode === "filter"
                    ? libraryFilterTags
                    : getBlockTags(target.block)
                ).map(userTagKey)
            );
            const filtered = userTagCatalog.filter(tagMatchesSearch);
            const selected = sortedUserTags(
                filtered.filter((tag) => assigned.has(userTagKey(tag)))
            );
            const pinned = sortedUserTags(
                filtered.filter(
                    (tag) =>
                        !assigned.has(userTagKey(tag)) &&
                        pinnedUserTags.has(userTagKey(tag))
                )
            );
            const regular = sortedUserTags(
                filtered.filter(
                    (tag) =>
                        !assigned.has(userTagKey(tag)) &&
                        !pinnedUserTags.has(userTagKey(tag))
                )
            );

            userTagSelectedList.innerHTML = "";
            userTagPinnedList.innerHTML = "";
            userTagAllList.innerHTML = "";

            if (selected.length) {
                userTagSelectedTitle.style.display = "";
                selected.forEach((tag) =>
                    userTagSelectedList.appendChild(
                        createUserTagItem(tag, true)
                    )
                );
            } else {
                userTagSelectedTitle.style.display = "none";
            }

            if (pinned.length) {
                userTagPinnedTitle.style.display = "";
                pinned.forEach((tag) => userTagPinnedList.appendChild(createUserTagItem(tag, assigned.has(userTagKey(tag)))));
            } else {
                userTagPinnedTitle.style.display = "none";
            }

            if (regular.length) {
                regular.forEach((tag) => userTagAllList.appendChild(createUserTagItem(tag, assigned.has(userTagKey(tag)))));
            } else {
                const empty = document.createElement("div");
                empty.className = "user-tag-empty";
                empty.innerText = filtered.length
                    ? "All matching tags are selected or pinned."
                    : "No matching tags.";
                userTagAllList.appendChild(empty);
            }

            if (userTagSortBtn) {
                userTagSortBtn.innerText = tagSortAscending ? "A–Z" : "Z–A";
            }
        }

        function setUserTagPanelTrackLabel(block, trackId) {
            if (!userTagPanelTrack) { return; }
            const exactTrackId = String(trackId || "").trim();
            const row = findTrackRowForReviewBlock(block);
            const title = row
                ? (row.querySelector(".title-link")?.innerText || "")
                : "";
            userTagPanelTrack.innerText = title
                ? title + " · " + exactTrackId.slice(0, 8)
                : exactTrackId.slice(0, 8);
        }

        function openUserTagTrackModeForTrack(trackId) {
            const requestedTrackId = String(trackId || "").trim();
            if (!requestedTrackId || !userTagPanel) {
                return false;
            }
            if (
                !userTagPanel.classList.contains("hidden") &&
                userTagPanelMode === "edit" &&
                String(activeTagTrackId || "").trim().toLowerCase() ===
                    requestedTrackId.toLowerCase()
            ) {
                return true;
            }
            const block = findUserTagBlockByTrackId(requestedTrackId);
            if (!block) {
                return false;
            }
            openUserTagPanel(block);
            return true;
        }

        // Public LIBRARY API for Selected Track and other Library-owned entry points.
        // The Tags engine remains single-owner; callers pass only an exact Track ID.
        window.LS = window.LS || {};
        window.LS.library = Object.assign(window.LS.library || {}, {
            openFlagsAndTagsForTrack(trackId) {
                return openUserTagTrackModeForTrack(trackId);
            }
        });

        function openUserTagPanel(block) {
            if (!block || !userTagPanel) { return; }

            const requestedTrackId = String(
                block.dataset.trackId || ""
            ).trim();
            if (!requestedTrackId) {
                setTagPanelStatus("Missing Track ID.", false);
                return;
            }

            const exactBlock =
                findUserTagBlockByTrackId(requestedTrackId) ||
                block;

            activeTagSession += 1;
            userTagPanelMode = "edit";
            activeTagTrackId = requestedTrackId;
            activeTagBlock = exactBlock;
            userTagPanel.classList.remove("filter-mode");
            if (userTagPanelTitle) { userTagPanelTitle.innerText = "Flags and Tags"; }
            if (userTagPanelModeLabel) { userTagPanelModeLabel.innerText = "TRACK MODE"; }

            if (userTagPanelFlags) {
                updateReviewStars(
                    userTagPanelFlags,
                    getBlockMarks(exactBlock)
                );
            }

            setUserTagPanelTrackLabel(exactBlock, requestedTrackId);

            userTagPanel.classList.remove("hidden");
            userTagPanel.setAttribute("aria-hidden", "false");
            setTagPanelStatus("");
            renderUserTagPanel();
            updateUserTagClearButtons();

            if (userTagSearchInput) {
                userTagSearchInput.focus();
                userTagSearchInput.select();
            }
        }

        // Explicit Library entry-point contract for Selected Track -> Flags & Tags.
        // The exact Track ID is carried by the event; FILTER MODE state is untouched.
        document.addEventListener("ls-library-open-flags-tags-track", (event) => {
            const detail = event && event.detail ? event.detail : {};
            const trackId = String(detail.trackId || "").trim();
            if (!trackId) {
                return;
            }
            detail.handled = openUserTagTrackModeForTrack(trackId);
        });

        document.addEventListener("ls-selected-track-changed", (event) => {
            const detail = event && event.detail ? event.detail : {};
            syncGlobalPlayerFlagsTags(detail.trackId || "");
            if (detail.source === "playback") {
                return;
            }
            const trackId = String(
                detail.trackId || ""
            ).trim();
            if (!trackId) {
                return;
            }
            if (detail.source === "selection") {
                lastExplicitUserTagTrackId = trackId;
            }
            if (
                !userTagPanel ||
                userTagPanel.classList.contains("hidden")
            ) {
                return;
            }
            // Selection may follow the active track editor, but must never rewrite
            // FILTER MODE state while the user is building Library filters.
            if (userTagPanelMode === "edit") {
                openUserTagTrackModeForTrack(trackId);
            }
        });

        document.addEventListener("ls-track-playback-started", (event) => {
            const playbackTrackId = String(
                event && event.detail ? (event.detail.trackId || "") : ""
            ).trim();
            syncGlobalPlayerFlagsTags(playbackTrackId);
            if (
                !userTagPanel ||
                userTagPanel.classList.contains("hidden")
            ) {
                return;
            }
            if (playbackTrackId) {
                openUserTagTrackModeForTrack(playbackTrackId);
            }
        });

        // LS_LOCAL_FAMILY_TAB_QUICK_V1
        // LS_LOCAL_FAMILY_TAB_QUICK_V1_1
        // LS_LOCAL_FAMILY_TAB_QUICK_V1_2
        // One Flags & Tags panel, two TRACK MODE tabs.  Local Family uses
        // D:\Local-Suno-Library names as a quick seed catalog and persists only
        // the existing LS Track ID -> Local Family mapping.
        {
            const lsLfFlagsTab = document.getElementById("user-tag-tab-flags");
            const lsLfFamilyTab = document.getElementById("user-tag-tab-local-family");
            const lsLfSection = document.getElementById("local-family-panel-section");
            const lsLfInput = document.getElementById("local-family-search-input");
            const lsLfClear = document.getElementById("local-family-search-clear");
            const lsLfAccept = document.getElementById("local-family-accept");
            const lsLfCurrent = document.getElementById("local-family-current");
            const lsLfStatus = document.getElementById("local-family-status");
            const lsLfList = document.getElementById("local-family-list");
            let lsLfCatalog = [];
            let lsLfAssigned = "";
            let lsLfRequestSerial = 0;
            // LS_LOCAL_FAMILY_SHORTCUT_STATE_V1_6
            const LS_LF_PREFERRED_MODE_KEY = "ls_local_family_preferred_mode_v1";

            function lsLfReadPreferredMode() {
                try {
                    const saved = String(
                        localStorage.getItem(LS_LF_PREFERRED_MODE_KEY) || ""
                    ).trim().toLowerCase();
                    if (saved === "flags" || saved === "family") { return saved; }
                } catch (error) {}
                return "family";
            }

            function lsLfRememberPreferredMode(mode) {
                try {
                    localStorage.setItem(
                        LS_LF_PREFERRED_MODE_KEY,
                        mode === "family" ? "family" : "flags"
                    );
                } catch (error) {}
            }

            let lsLfPreferredMode = lsLfReadPreferredMode();

            const lsLfStyle = document.createElement("style");
            lsLfStyle.textContent = `
                .user-tag-panel-tabs{display:flex;gap:4px;align-items:center;margin-bottom:4px}
                .user-tag-panel-tab{border:0;border-bottom:2px solid transparent;background:transparent;color:inherit;font:inherit;font-weight:700;padding:5px 9px;cursor:pointer;opacity:.72}
                .user-tag-panel-tab.active{border-bottom-color:currentColor;opacity:1}
                .user-tag-panel:not(.filter-mode) .user-tag-panel-title{display:none}
                .user-tag-panel.filter-mode .user-tag-panel-tabs{display:none}
                .user-tag-panel.local-family-mode .user-tag-panel-body>.user-flag-panel-section,
                .user-tag-panel.local-family-mode .user-tag-panel-body>.user-tag-section-divider,
                .user-tag-panel.local-family-mode .user-tag-panel-body>.user-tag-editor-title,
                .user-tag-panel.local-family-mode .user-tag-panel-body>.user-tag-add-row.user-tag-edit-only,
                .user-tag-panel.local-family-mode .user-tag-panel-body>.user-tag-tools,
                .user-tag-panel.local-family-mode .user-tag-panel-body>#user-tag-panel-status,
                .user-tag-panel.local-family-mode .user-tag-panel-body>.user-tag-panel-scroll,
                .user-tag-panel.local-family-mode .user-tag-panel-body>#user-tag-filter-actions{display:none!important}
                .user-tag-panel.local-family-mode #local-family-panel-section{display:flex!important;flex-direction:column;min-height:0;gap:8px}
                .local-family-entry-row{margin-top:2px}
                .local-family-accept{min-width:46px;font-size:20px;line-height:1}
                .local-family-current{font-weight:600;min-height:20px}
                .local-family-scroll{min-height:150px;max-height:52vh;overflow:auto}
                #local-family-list .user-tag-toggle{width:100%;text-align:left}
                .ls-local-family-badge{border-color:#B5E61D!important;color:#fff!important;background:#198539!important}
            `;
            document.head.appendChild(lsLfStyle);

            function lsLfKey(value) {
                return String(value || "").trim().toLocaleLowerCase();
            }

            function lsLfIsMode() {
                return Boolean(userTagPanel && userTagPanel.classList.contains("local-family-mode"));
            }

            function lsLfSetStatus(message, ok=true) {
                if (!lsLfStatus) { return; }
                lsLfStatus.textContent = String(message || "");
                lsLfStatus.style.color = ok ? "" : "#a50e0e";
            }

            function lsLfSyncClear() {
                if (lsLfClear && lsLfInput) {
                    lsLfClear.disabled = !String(lsLfInput.value || "");
                }
            }

            function lsLfRender() {
                if (!lsLfList || !lsLfInput) { return; }
                const rawQuery = String(lsLfInput.value || "").trim();
                const query = lsLfKey(rawQuery);
                const families = Array.isArray(lsLfCatalog) ? lsLfCatalog : [];
                const filtered = query.length >= 3
                    ? families.filter((title) => lsLfKey(title).startsWith(query))
                    : families.slice();

                lsLfList.innerHTML = "";
                filtered.forEach((title) => {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "user-tag-toggle" + (
                        lsLfKey(title) === lsLfKey(lsLfAssigned) ? " active" : ""
                    );
                    button.textContent = title;
                    button.title = "Piešķirt šo Local Family";
                    button.addEventListener("click", () => lsLfAssign(title));
                    lsLfList.appendChild(button);
                });

                if (!filtered.length) {
                    const empty = document.createElement("div");
                    empty.className = "user-tag-empty";
                    empty.textContent = rawQuery
                        ? "Nav atrasts — ✓ piešķirs ievadīto jauno Local Family."
                        : "Local Family katalogs ir tukšs.";
                    lsLfList.appendChild(empty);
                }

                if (lsLfCurrent) {
                    lsLfCurrent.textContent = lsLfAssigned
                        ? "Piešķirts: " + lsLfAssigned
                        : "Local Family vēl nav piešķirta.";
                }
                lsLfSyncClear();
            }

            function lsLfSyncRowBadge(trackId, familyTitle) {
                const idKey = String(trackId || "").trim().toLowerCase();
                const title = String(familyTitle || "").trim();
                if (!idKey) { return; }
                const row = Array.from(document.querySelectorAll("tr.track-row")).find((candidate) =>
                    String(candidate.dataset.trackId || "").trim().toLowerCase() === idKey
                );
                if (!row) { return; }
                let badge = Array.from(row.querySelectorAll(".title-badge")).find((candidate) =>
                    candidate.classList.contains("ls-local-family-badge") ||
                    String(candidate.textContent || "").trim() === "LocF"
                );
                if (!title) {
                    delete row.dataset.localFamily;
                    if (badge) { badge.remove(); }
                    return;
                }
                row.dataset.localFamily = title;
                if (!badge) {
                    let meta = row.querySelector(".title-meta");
                    if (!meta) {
                        const stack = row.querySelector(".title-stack");
                        if (!stack) { return; }
                        const metaLine = document.createElement("div");
                        metaLine.className = "title-meta-line";
                        meta = document.createElement("span");
                        meta.className = "title-meta";
                        metaLine.appendChild(meta);
                        const titleLine = stack.querySelector(".title-line");
                        if (titleLine && titleLine.nextSibling) {
                            stack.insertBefore(metaLine, titleLine.nextSibling);
                        } else {
                            stack.appendChild(metaLine);
                        }
                    }
                    badge = document.createElement("span");
                    badge.className = "title-badge ls-local-family-badge";
                    badge.textContent = "LocF";
                    meta.appendChild(document.createTextNode(" "));
                    meta.appendChild(badge);
                } else {
                    badge.classList.add("ls-local-family-badge");
                }
                badge.title = "Local Family: " + title;
            }

            async function lsLfPost(url, values) {
                const body = new URLSearchParams();
                Object.entries(values || {}).forEach(([key, value]) => {
                    body.set(key, String(value == null ? "" : value));
                });
                const response = await fetch(url, {
                    method: "POST",
                    headers: {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                    body: body.toString(),
                    cache: "no-store"
                });
                let data = null;
                try { data = await response.json(); }
                catch (error) { data = null; }
                if (!response.ok || !data || !data.ok) {
                    throw new Error((data && data.error) || ("HTTP " + response.status));
                }
                return data;
            }

            async function lsLfLoad() {
                if (!lsLfIsMode()) { return; }
                const trackId = String(activeTagTrackId || "").trim();
                if (!trackId) {
                    lsLfCatalog = [];
                    lsLfAssigned = "";
                    lsLfSetStatus("Izvēlies dziesmu.", false);
                    lsLfRender();
                    return;
                }
                const serial = ++lsLfRequestSerial;
                lsLfSetStatus("Ielādē Local Family…");
                try {
                    const data = await lsLfPost("/local-family-quick-catalog", {track_id: trackId});
                    if (serial !== lsLfRequestSerial || !lsLfIsMode()) { return; }
                    lsLfCatalog = Array.isArray(data.families) ? data.families : [];
                    lsLfAssigned = String(data.assigned_family || "").trim();
                    if (lsLfInput) { lsLfInput.value = lsLfAssigned; }
                    lsLfSyncRowBadge(trackId, lsLfAssigned);
                    lsLfSetStatus(data.root_exists === false
                        ? "D:\\Local-Suno-Library nav pieejama; rādu saglabātās Local Family."
                        : "");
                    lsLfRender();
                } catch (error) {
                    if (serial !== lsLfRequestSerial) { return; }
                    lsLfSetStatus(error.message || "Neizdevās ielādēt Local Family.", false);
                }
            }

            async function lsLfAssign(title) {
                const trackId = String(activeTagTrackId || "").trim();
                const familyTitle = String(title || "").trim();
                if (!trackId) {
                    lsLfSetStatus("Izvēlies dziesmu.", false);
                    return;
                }
                if (!familyTitle) {
                    lsLfSetStatus("Ieraksti vai izvēlies Local Family.", false);
                    return;
                }
                if (lsLfAccept) { lsLfAccept.disabled = true; }
                lsLfSetStatus("Saglabā Local Family…");
                try {
                    await lsLfPost("/confirm-local-family", {
                        track_id: trackId,
                        action: "assign",
                        family_title: familyTitle
                    });
                    lsLfAssigned = familyTitle;
                    if (!lsLfCatalog.some((value) => lsLfKey(value) === lsLfKey(familyTitle))) {
                        lsLfCatalog.push(familyTitle);
                        lsLfCatalog.sort((a, b) => String(a).localeCompare(String(b), "lv"));
                    }
                    if (lsLfInput) { lsLfInput.value = familyTitle; }
                    lsLfSyncRowBadge(trackId, familyTitle);
                    lsLfSetStatus("Piešķirts.");
                    lsLfRender();
                } catch (error) {
                    lsLfSetStatus(error.message || "Local Family neizdevās saglabāt.", false);
                } finally {
                    if (lsLfAccept) { lsLfAccept.disabled = false; }
                }
            }

            function lsLfSetMode(mode, remember=true) {
                const wantsFamily = mode === "family" && userTagPanelMode === "edit";
                if (remember) {
                    lsLfPreferredMode = wantsFamily ? "family" : "flags";
                    lsLfRememberPreferredMode(lsLfPreferredMode);
                }
                if (userTagPanel) {
                    userTagPanel.classList.toggle("local-family-mode", wantsFamily);
                }
                if (lsLfSection) { lsLfSection.hidden = !wantsFamily; }
                if (lsLfFlagsTab) {
                    lsLfFlagsTab.classList.toggle("active", !wantsFamily);
                    lsLfFlagsTab.setAttribute("aria-selected", wantsFamily ? "false" : "true");
                }
                if (lsLfFamilyTab) {
                    lsLfFamilyTab.classList.toggle("active", wantsFamily);
                    lsLfFamilyTab.setAttribute("aria-selected", wantsFamily ? "true" : "false");
                }
                if (wantsFamily) {
                    if (lsLfInput) {
                        lsLfInput.value = "";
                        lsLfInput.focus();
                    }
                    lsLfLoad();
                }
            }

            if (lsLfFlagsTab) {
                lsLfFlagsTab.addEventListener("click", () => lsLfSetMode("flags"));
            }
            if (lsLfFamilyTab) {
                lsLfFamilyTab.addEventListener("click", () => lsLfSetMode("family"));
            }
            if (lsLfInput) {
                lsLfInput.addEventListener("input", () => {
                    lsLfSyncClear();
                    lsLfRender();
                });
                lsLfInput.addEventListener("keydown", (event) => {
                    if (event.key !== "Enter") { return; }
                    event.preventDefault();
                    lsLfAssign(lsLfInput.value);
                });
            }
            if (lsLfClear) {
                lsLfClear.addEventListener("click", () => {
                    if (!lsLfInput) { return; }
                    lsLfInput.value = "";
                    lsLfInput.focus();
                    lsLfRender();
                });
            }
            if (lsLfAccept) {
                lsLfAccept.addEventListener("click", () => {
                    lsLfAssign(lsLfInput ? lsLfInput.value : "");
                });
            }

            document.addEventListener("ls-selected-track-changed", () => {
                const panelVisible = Boolean(
                    userTagPanel && !userTagPanel.classList.contains("hidden")
                );
                if (panelVisible && lsLfPreferredMode === "family") {
                    window.setTimeout(() => {
                        if (userTagPanelMode !== "edit") { return; }
                        lsLfSetMode("family", false);
                    }, 0);
                    return;
                }
                if (panelVisible && lsLfIsMode()) { lsLfLoad(); }
            });
            document.addEventListener("ls-track-playback-started", () => {
                const panelVisible = Boolean(
                    userTagPanel && !userTagPanel.classList.contains("hidden")
                );
                if (panelVisible && lsLfPreferredMode === "family") {
                    window.setTimeout(() => lsLfSetMode("family", false), 0);
                } else if (panelVisible && lsLfIsMode()) {
                    window.setTimeout(lsLfLoad, 0);
                }
            });

            function lsLfVisibleTrackRows() {
                return Array.from(document.querySelectorAll("tr.track-row")).filter((row) => (
                    !row.classList.contains("hidden")
                    && !row.classList.contains("row-hidden")
                ));
            }

            function lsLfVisibleTrackRowById(trackId) {
                const wanted = String(trackId || "").trim().toLowerCase();
                if (!wanted) { return null; }
                return lsLfVisibleTrackRows().find((row) =>
                    String(row.dataset.trackId || "").trim().toLowerCase() === wanted
                ) || null;
            }

            function lsLfReadLastPlayedTrackId() {
                try {
                    return String(
                        localStorage.getItem("ls_last_played_track_id_v1") || ""
                    ).trim();
                } catch (error) { return ""; }
            }

            function lsLfShortcutTrackId() {
                const selectedRow = document.querySelector(
                    "tr.track-row.selected-track-current:not(.hidden):not(.row-hidden)"
                );
                if (selectedRow) {
                    const value = String(selectedRow.dataset.trackId || "").trim();
                    if (value) { return value; }
                }

                const remembered = lsLfReadLastPlayedTrackId();
                if (remembered && lsLfVisibleTrackRowById(remembered)) { return remembered; }

                for (const candidate of [activeTagTrackId, lastExplicitUserTagTrackId]) {
                    const value = String(candidate || "").trim();
                    if (value && lsLfVisibleTrackRowById(value)) { return value; }
                }

                const first = lsLfVisibleTrackRows()[0];
                return first ? String(first.dataset.trackId || "").trim() : "";
            }

            function lsLfSynchronizeShortcutTrack(trackId) {
                const row = lsLfVisibleTrackRowById(trackId);
                if (!row) { return false; }
                if (
                    typeof selectTrackRow === "function" &&
                    (
                        typeof selectedTrackRow === "undefined"
                        || selectedTrackRow !== row
                        || !row.classList.contains("selected-track-current")
                    )
                ) {
                    selectTrackRow(row, { scroll: false, source: "shortcut" });
                }
                return true;
            }

            // Ctrl+Shift+F uses the same exact Track-ID selection as the Library row.
            // It never needs a preliminary physical row click.
            document.addEventListener("keydown", (event) => {
                const isShortcutKey = Boolean(event.key) && event.key.toLowerCase() === "f";
                if (!(event.ctrlKey && event.shiftKey && !event.altKey && !event.metaKey && isShortcutKey)) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                const trackId = lsLfShortcutTrackId();
                if (!trackId || !lsLfSynchronizeShortcutTrack(trackId)) { return; }
                if (!openUserTagTrackModeForTrack(trackId)) { return; }
                window.setTimeout(() => {
                    lsLfSetMode(lsLfPreferredMode, false);
                    if (lsLfPreferredMode === "family" && lsLfInput) {
                        lsLfInput.focus();
                    } else if (userTagSearchInput) {
                        userTagSearchInput.focus();
                    }
                }, 0);
            }, true);

            if (userTagPanel) {
                const lsLfModeObserver = new MutationObserver(() => {
                    if (userTagPanel.classList.contains("filter-mode") && lsLfIsMode()) {
                        lsLfSetMode("flags", false);
                    }
                });
                lsLfModeObserver.observe(userTagPanel, {
                    attributes: true,
                    attributeFilter: ["class"]
                });
            }
        }

