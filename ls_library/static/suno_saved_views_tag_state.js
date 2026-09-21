        let userTagCatalog = (window.LS_LIBRARY_BOOTSTRAP.userTags || []);
        let pinnedUserTags = new Set((window.LS_LIBRARY_BOOTSTRAP.pinnedUserTags || []).map((tag) => String(tag || "").toLowerCase()));
        let tagSortAscending = true;
        let activeTagBlock = null;
        let activeTagTrackId = "";
        let activeTagSession = 0;
        let userTagPanelMode = "edit";
        let lastExplicitUserTagTrackId = "";
        let libraryFilterMarks = 0;
        let libraryFilterTags = [];

        const userTagPanel = document.getElementById("user-tag-panel");
        const userTagPanelTitle = document.getElementById("user-tag-panel-title");
        const userTagPanelTrack = document.getElementById("user-tag-panel-track");
        const userTagPanelModeLabel = document.getElementById("user-tag-panel-mode");
        const userTagPanelClose = document.getElementById("user-tag-panel-close");
        const userTagPanelFlags = document.getElementById("user-flag-panel-stars");
        const userTagNewInput = document.getElementById("user-tag-new-input");
        const userTagAddBtn = document.getElementById("user-tag-add-btn");
        const userTagSearchInput = document.getElementById("user-tag-search-input");
        const userTagNewClear = document.getElementById("user-tag-new-clear");
        const userTagSearchClear = document.getElementById("user-tag-search-clear");
        const userTagSortBtn = document.getElementById("user-tag-sort-btn");
        const userTagPanelStatus = document.getElementById("user-tag-panel-status");
        const userTagSelectedTitle = document.getElementById("user-tag-selected-title");
        const userTagSelectedList = document.getElementById("user-tag-selected-list");
        const userTagPinnedTitle = document.getElementById("user-tag-pinned-title");
        const userTagPinnedList = document.getElementById("user-tag-pinned-list");
        const userTagAllList = document.getElementById("user-tag-all-list");
        const addLibraryFilterButton = document.getElementById("ls-add-filter-button");
        const userTagFilterClear = document.getElementById("user-tag-filter-clear");
        const userTagFilterApply = document.getElementById("user-tag-filter-apply");
        const savedViewsDetails = document.getElementById("ls-saved-views");
        const saveViewButton = document.getElementById("ls-save-view-button");
        const savedViewModal = document.getElementById("saved-view-modal");
        const savedViewModalClose = document.getElementById("saved-view-modal-close");
        const savedViewModalCancel = document.getElementById("saved-view-modal-cancel");
        const savedViewModalSave = document.getElementById("saved-view-modal-save");
        const savedViewModalTitle = document.getElementById("saved-view-modal-title");
        const savedViewModalHelp = document.getElementById("saved-view-modal-help");
        const savedViewNameInput = document.getElementById("saved-view-name-input");
        const savedViewModalStatus = document.getElementById("saved-view-modal-status");
        function createGlobalPlayerFlagsTagsHost() {
            const host = document.getElementById("ls-global-player-flags-tags-host");
            if (!host) { return null; }
            host.innerHTML = `
                <div class="user-review-block ls-global-player-review-block" data-track-id="" data-marks="0">
                    <div class="review-stars ls-global-player-review-stars" data-marks="0" title="LS Flags">
                        <button type="button" class="review-star ls-global-player-review-star" data-mask="1" aria-label="Flag 1: Labs ritms" aria-pressed="false" title="1 · Labs ritms">✶</button>
                        <button type="button" class="review-star ls-global-player-review-star" data-mask="2" aria-label="Flag 2: Labs pavadījums" aria-pressed="false" title="2 · Labs pavadījums">✶</button>
                        <button type="button" class="review-star ls-global-player-review-star" data-mask="4" aria-label="Flag 3: Labs solo" aria-pressed="false" title="3 · Labs solo">✶</button>
                        <button type="button" class="review-star ls-global-player-review-star" data-mask="8" aria-label="Flag 4: Interesants" aria-pressed="false" title="4 · Interesants">✶</button>
                        <button type="button" class="review-star ls-global-player-review-star" data-mask="16" aria-label="Flag 5: Pievērst uzmanību" aria-pressed="false" title="5 · Pievērst uzmanību">✶</button>
                    </div>
                    <div class="review-tags-box ls-global-player-review-tags">
                        <button type="button" class="review-tags-open ls-global-player-review-open" data-current-tags="" title="Open Flags and Tags panel" disabled>Flags & Tags</button>
                        <div class="review-tags-current ls-global-player-review-current" title="LS Flags and Tags"></div>
                        <span class="review-save-status ls-global-player-review-status"></span>
                    </div>
                </div>`;
            return host.querySelector(".ls-global-player-review-block");
        }

        const globalPlayerReviewBlock = createGlobalPlayerFlagsTagsHost();
        const globalPlayerReviewStars = globalPlayerReviewBlock
            ? globalPlayerReviewBlock.querySelector(".review-stars")
            : null;
        const globalPlayerReviewOpen = globalPlayerReviewBlock
            ? globalPlayerReviewBlock.querySelector(".review-tags-open")
            : null;
        const globalPlayerReviewCurrent = globalPlayerReviewBlock
            ? globalPlayerReviewBlock.querySelector(".review-tags-current")
            : null;
        let savedViewEditingId = "";
        let savedViewPendingQuery = "";

        function userTagKey(value) {
            return String(value || "").trim().toLowerCase();
        }

        function normalizeOneTagClient(value) {
            let text = String(value || "").trim().replace(/^#+/, "").trim();
            text = text.replace(/\s+/g, "_").replace(/[,;]+/g, "").replace(/^[_#]+|[_#]+$/g, "");
            return text ? "#" + text : "";
        }

        function userTagSortKey(value) {
            return String(value || "")
                .normalize("NFD")
                .replace(/[̀-ͯ]/g, "")
                .toLowerCase();
        }

        function sortedUserTags(values) {
            return Array.from(values || []).sort((a, b) => {
                const aa = userTagSortKey(a);
                const bb = userTagSortKey(b);
                const result = aa.localeCompare(bb);
                return tagSortAscending ? result : -result;
            });
        }

        function findUserTagBlockByTrackId(trackId) {
            const idKey = String(trackId || "").trim().toLowerCase();
            if (!idKey) {
                return null;
            }

            // Primary TRACK MODE target is the current Library track row.
            // The legacy fragment-row review block is compatibility fallback only.
            const row = Array.from(
                document.querySelectorAll("tr.track-row")
            ).find((candidate) =>
                String(candidate.dataset.trackId || "").trim().toLowerCase() === idKey
            );
            if (row) {
                return row;
            }

            return Array.from(
                document.querySelectorAll(".user-review-block")
            ).find((block) =>
                !block.classList.contains("compare-this-review-editor") &&
                !block.classList.contains("ls-global-player-review-block") &&
                String(block.dataset.trackId || "").trim().toLowerCase() === idKey
            ) || null;
        }

        function getActiveUserTagTarget() {
            const trackId = String(activeTagTrackId || "").trim();
            if (!trackId) {
                return { trackId: "", block: null, session: activeTagSession };
            }

            const block =
                findUserTagBlockByTrackId(trackId) ||
                (
                    activeTagBlock &&
                    String(activeTagBlock.dataset.trackId || "")
                        .trim()
                        .toLowerCase() === trackId.toLowerCase()
                        ? activeTagBlock
                        : null
                );

            return {
                trackId: trackId,
                block: block,
                session: activeTagSession
            };
        }

        function isCurrentUserTagTarget(target) {
            return Boolean(
                target &&
                target.trackId &&
                target.session === activeTagSession &&
                String(activeTagTrackId || "").trim().toLowerCase() ===
                    String(target.trackId || "").trim().toLowerCase()
            );
        }

        function updateUserTagClearButtons() {
            if (userTagNewClear && userTagNewInput) {
                userTagNewClear.disabled = !String(userTagNewInput.value || "");
            }
            if (userTagSearchClear && userTagSearchInput) {
                userTagSearchClear.disabled =
                    !String(userTagSearchInput.value || "");
            }
        }

        function getBlockTags(block) {
            if (!block) { return []; }
            const source = block.classList.contains("track-row")
                ? String(block.dataset.userTags || "")
                : (() => {
                    const current = block.querySelector(".review-tags-current");
                    return current ? current.innerText : "";
                })();
            const normalized = normalizeTagsClient(source);
            return normalized
                ? normalized.split(",").map((tag) => tag.trim()).filter(Boolean)
                : [];
        }

        function getBlockMarks(block) {
            if (!block) { return 0; }
            const stored = parseInt(block.dataset.marks || "", 10);
            if (Number.isFinite(stored)) { return stored; }
            const starsBox = block.querySelector(".review-stars");
            return starsBox
                ? (parseInt(starsBox.dataset.marks || "0", 10) || 0)
                : 0;
        }

        function resetGlobalPlayerFlagsTags() {
            if (!globalPlayerReviewBlock) { return; }
            globalPlayerReviewBlock.dataset.trackId = "";
            globalPlayerReviewBlock.dataset.marks = "0";
            if (globalPlayerReviewStars) {
                globalPlayerReviewStars.dataset.marks = "0";
                if (typeof updateReviewStars === "function") {
                    updateReviewStars(globalPlayerReviewStars, 0);
                }
            }
            if (globalPlayerReviewOpen) {
                globalPlayerReviewOpen.dataset.currentTags = "";
                globalPlayerReviewOpen.disabled = true;
            }
            if (globalPlayerReviewCurrent) {
                globalPlayerReviewCurrent.innerText = "";
            }
        }

        function syncGlobalPlayerFlagsTags(trackId) {
            if (!globalPlayerReviewBlock) { return false; }
            const requestedTrackId = String(trackId || "").trim();
            if (!requestedTrackId) {
                resetGlobalPlayerFlagsTags();
                return false;
            }
            const sourceBlock = findUserTagBlockByTrackId(requestedTrackId);
            if (!sourceBlock) {
                resetGlobalPlayerFlagsTags();
                return false;
            }
            const marks = getBlockMarks(sourceBlock);
            const tags = getBlockTags(sourceBlock);
            const tagText = tags.join(", ");
            globalPlayerReviewBlock.dataset.trackId = requestedTrackId;
            globalPlayerReviewBlock.dataset.marks = String(marks);
            if (globalPlayerReviewStars) {
                globalPlayerReviewStars.dataset.marks = String(marks);
                if (typeof updateReviewStars === "function") {
                    updateReviewStars(globalPlayerReviewStars, marks);
                }
            }
            if (globalPlayerReviewOpen) {
                globalPlayerReviewOpen.dataset.currentTags = tagText;
                globalPlayerReviewOpen.disabled = false;
            }
            if (globalPlayerReviewCurrent) {
                globalPlayerReviewCurrent.innerText = tagText;
            }
            return true;
        }

        function syncTrackMarksClient(trackId, marks) {
            const idKey = String(trackId || "").trim().toLowerCase();
            const value = parseInt(marks || "0", 10) || 0;
            if (!idKey) { return; }

            document.querySelectorAll("tr.track-row").forEach((row) => {
                if (String(row.dataset.trackId || "").trim().toLowerCase() === idKey) {
                    row.dataset.marks = String(value);
                }
            });

            document.querySelectorAll(".user-review-block").forEach((block) => {
                if (
                    String(block.dataset.trackId || "").trim().toLowerCase() !==
                    idKey
                ) {
                    return;
                }
                block.dataset.marks = String(value);
                block.querySelectorAll(".review-stars").forEach((starsBox) => {
                    updateReviewStars(starsBox, value);
                });
            });

            if (
                userTagPanelFlags &&
                String(activeTagTrackId || "").trim().toLowerCase() === idKey
            ) {
                updateReviewStars(userTagPanelFlags, value);
            }
        }

        function findTrackRowForReviewBlock(block) {
            if (!block) { return null; }
            if (block.classList.contains("track-row")) { return block; }
            const trackId = String(block.dataset.trackId || "").trim().toLowerCase();
            if (!trackId) { return null; }

            // The #Tags review block lives inside the separate fragment-row, while
            // the visible title badges live in the preceding track-row. Therefore
            // block.closest("tr.track-row") can never find the target row. Match the
            // main row by the shared Track ID instead.
            return Array.from(document.querySelectorAll("tr.track-row")).find((row) =>
                String(row.dataset.trackId || "").trim().toLowerCase() === trackId
            ) || null;
        }

        function refreshTrackTitleTagBadges(block, tags) {
            const trackId = String(
                block ? (block.dataset.trackId || "") : ""
            ).trim();
            const row = findTrackRowForReviewBlock(block);
            if (!row) { return; }

            row.querySelectorAll(".user-tag-badge").forEach((badge) => badge.remove());

            const finalTags = Array.isArray(tags) ? tags.filter(Boolean).slice(0, 4) : [];
            let metaLine = row.querySelector(".title-meta-line");
            let meta = row.querySelector(".title-meta");

            // A track that had no badges when the page was rendered has no title-meta
            // container yet. Create it immediately so the first assigned #tag becomes
            // visible without F5 / page reload.
            if (!meta && finalTags.length) {
                const titleStack = row.querySelector(".title-stack");
                if (!titleStack) { return; }

                metaLine = document.createElement("div");
                metaLine.className = "title-meta-line";
                meta = document.createElement("span");
                meta.className = "title-meta";
                metaLine.appendChild(meta);

                const titleLine = titleStack.querySelector(".title-line");
                if (titleLine && titleLine.nextSibling) {
                    titleStack.insertBefore(metaLine, titleLine.nextSibling);
                } else {
                    titleStack.appendChild(metaLine);
                }
            }

            if (!meta) { return; }

            const beforeNode = meta.querySelector(".model-badge") || null;
            finalTags.forEach((tag) => {
                const span = document.createElement("span");
                span.className = "title-badge user-tag-badge";
                span.dataset.userTag = tag;
                span.innerText = tag;
                if (beforeNode) {
                    meta.insertBefore(document.createTextNode(" "), beforeNode);
                    meta.insertBefore(span, beforeNode);
                } else {
                    meta.appendChild(document.createTextNode(" "));
                    meta.appendChild(span);
                }
            });

            // If the last tag was removed and there are no other badges left, remove
            // the now-empty metadata line as well.
            if (!finalTags.length && meta.children.length === 0 && metaLine) {
                metaLine.remove();
            }

            if (typeof refreshCompareThisTagBadges === "function") {
                refreshCompareThisTagBadges(trackId, finalTags);
            }
        }

        function setBlockTags(block, tags) {
            if (!block) { return; }
            const normalized = normalizeTagsClient((tags || []).join(", "));
            const finalTags = normalized
                ? normalized.split(",").map((tag) => tag.trim()).filter(Boolean)
                : [];

            if (block.classList.contains("track-row")) {
                block.dataset.userTags = finalTags.join(", ");
            } else {
                const current = block.querySelector(".review-tags-current");
                const openButton = block.querySelector(".review-tags-open");
                if (current) { current.innerText = finalTags.join(", "); }
                if (openButton) { openButton.dataset.currentTags = finalTags.join(", "); }
            }

            const trackId = String(block.dataset.trackId || "").trim().toLowerCase();
            if (trackId) {
                document.querySelectorAll("tr.track-row").forEach((row) => {
                    if (String(row.dataset.trackId || "").trim().toLowerCase() === trackId) {
                        row.dataset.userTags = finalTags.join(", ");
                    }
                });
                document.querySelectorAll(".user-review-block").forEach((legacy) => {
                    if (String(legacy.dataset.trackId || "").trim().toLowerCase() !== trackId) { return; }
                    const current = legacy.querySelector(".review-tags-current");
                    const openButton = legacy.querySelector(".review-tags-open");
                    if (current) { current.innerText = finalTags.join(", "); }
                    if (openButton) { openButton.dataset.currentTags = finalTags.join(", "); }
                });
            }

            refreshTrackTitleTagBadges(block, finalTags);
        }

