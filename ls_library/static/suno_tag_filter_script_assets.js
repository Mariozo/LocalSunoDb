        function parseLibraryFlagFilter(value) {
            let marks = 0;
            String(value || "").split(/[,;\s]+/).forEach((part) => {
                const mask = parseInt(part, 10) || 0;
                if ([1, 2, 4, 8, 16].includes(mask)) { marks |= mask; }
            });
            return marks;
        }

        function parseLibraryTagFilter(value) {
            const normalized = normalizeTagsClient(value || "");
            return normalized
                ? normalized.split(",").map((tag) => tag.trim()).filter(Boolean)
                : [];
        }

        function finishOpeningUserTagFilterPanel() {
            userTagPanel.classList.add("filter-mode");
            userTagPanel.classList.remove("hidden");
            userTagPanel.setAttribute("aria-hidden", "false");
            if (userTagPanelTitle) { userTagPanelTitle.innerText = "Flags and Tags"; }
            if (userTagPanelModeLabel) { userTagPanelModeLabel.innerText = "FILTER MODE"; }
            if (userTagPanelFlags) {
                updateReviewStars(userTagPanelFlags, libraryFilterMarks);
            }
            setTagPanelStatus("Read-only filter — the database is not changed.");
            renderUserTagPanel();
            updateUserTagClearButtons();
            if (userTagSearchInput) {
                userTagSearchInput.focus();
                userTagSearchInput.select();
            }
        }

        function openUserTagFilterPanelForTrack(trackId) {
            if (!userTagPanel) { return false; }
            const requestedTrackId = String(trackId || "").trim();
            const exactBlock = findUserTagBlockByTrackId(requestedTrackId);
            if (!requestedTrackId || !exactBlock) {
                return false;
            }
            activeTagSession += 1;
            userTagPanelMode = "filter";
            activeTagTrackId = requestedTrackId;
            activeTagBlock = exactBlock;
            libraryFilterMarks = getBlockMarks(exactBlock);
            libraryFilterTags = getBlockTags(exactBlock);
            setUserTagPanelTrackLabel(exactBlock, requestedTrackId);
            finishOpeningUserTagFilterPanel();
            return true;
        }

        function openUserTagFilterPanel() {
            if (!userTagPanel) { return; }
            if (
                lastExplicitUserTagTrackId &&
                openUserTagFilterPanelForTrack(lastExplicitUserTagTrackId)
            ) {
                return;
            }

            const url = new URL(window.location.href);
            activeTagSession += 1;
            userTagPanelMode = "filter";
            activeTagTrackId = "";
            activeTagBlock = null;
            libraryFilterMarks = parseLibraryFlagFilter(
                url.searchParams.get("flag_filter") || ""
            );
            libraryFilterTags = parseLibraryTagFilter(
                url.searchParams.get("tag_filter") || ""
            );
            if (userTagPanelTrack) {
                userTagPanelTrack.innerText = "Flags and Tags · all selected conditions must match";
            }
            finishOpeningUserTagFilterPanel();
        }

        function toggleLibraryTagFilter(tag) {
            const key = userTagKey(tag);
            const hasTag = libraryFilterTags.some(
                (item) => userTagKey(item) === key
            );
            libraryFilterTags = hasTag
                ? libraryFilterTags.filter((item) => userTagKey(item) !== key)
                : libraryFilterTags.concat([tag]);
            renderUserTagPanel();
            setTagPanelStatus("Read-only filter — click Apply filters.");
        }

        function clearLibraryReviewFilters() {
            libraryFilterMarks = 0;
            libraryFilterTags = [];
            if (userTagPanelFlags) { updateReviewStars(userTagPanelFlags, 0); }
            renderUserTagPanel();
            setTagPanelStatus("Flags and Tags selection cleared. Click Apply filters.");
        }

        function applyLibraryReviewFilters() {
            const url = new URL(window.location.href);
            const masks = [1, 2, 4, 8, 16].filter(
                (mask) => (libraryFilterMarks & mask) !== 0
            );
            if (masks.length) {
                url.searchParams.set("flag_filter", masks.join(","));
            } else {
                url.searchParams.delete("flag_filter");
            }
            if (libraryFilterTags.length) {
                url.searchParams.set("tag_filter", libraryFilterTags.join(","));
            } else {
                url.searchParams.delete("tag_filter");
            }
            url.searchParams.delete("rows");
            saveViewState();
            window.location.href = url.toString();
        }

        function closeUserTagPanel() {
            if (!userTagPanel) { return; }
            userTagPanel.classList.add("hidden");
            userTagPanel.setAttribute("aria-hidden", "true");
            activeTagSession += 1;
            activeTagBlock = null;
            activeTagTrackId = "";
            userTagPanelMode = "edit";
            userTagPanel.classList.remove("filter-mode");
            if (userTagPanelModeLabel) { userTagPanelModeLabel.innerText = "TRACK MODE"; }
        }

