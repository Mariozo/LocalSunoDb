        function updateReviewStars(starsBox, marks) {
            if (!starsBox) { return; }
            const value = parseInt(marks || "0", 10) || 0;
            starsBox.dataset.marks = String(value);
            starsBox.querySelectorAll(".review-star").forEach((button) => {
                const mask = parseInt(button.dataset.mask || "0", 10) || 0;
                const on = (value & mask) !== 0;
                button.classList.toggle("filled", on);
                button.setAttribute("aria-pressed", on ? "true" : "false");
            });
        }

        document.querySelectorAll(".review-stars").forEach((starsBox) => {
            updateReviewStars(starsBox, starsBox.dataset.marks || "0");
        });

        document.addEventListener("ls-library-rows-added", () => {
            document.querySelectorAll(".review-stars").forEach((starsBox) => {
                updateReviewStars(starsBox, starsBox.dataset.marks || "0");
            });
        });

        function normalizeTagsClient(text) {
            const seen = new Set();
            const result = [];
            String(text || "").split(/[,;\s]+/).forEach((part) => {
                let tag = part.trim();
                if (!tag) { return; }
                if (!tag.startsWith("#")) { tag = "#" + tag; }
                const key = tag.toLowerCase();
                if (!seen.has(key)) {
                    result.push(tag);
                    seen.add(key);
                }
            });
            return result.join(", ");
        }

        async function saveUserReview(trackId, marks, tags, statusElement) {
            const body = new URLSearchParams();
            body.set("track_id", trackId || "");
            if (marks !== null && marks !== undefined) {
                body.set("marks", String(marks));
            }
            if (tags !== null && tags !== undefined) {
                body.set("tags", String(tags || ""));
            }

            if (statusElement) {
                statusElement.innerText = "Saving...";
                statusElement.style.color = "#666";
            }

            try {
                const response = await fetch("/save-user-review", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                const text = await response.text();
                if (!response.ok) {
                    if (statusElement) {
                        statusElement.innerText = text || "Save failed";
                        statusElement.style.color = "#a50e0e";
                    } else {
                        alert(text || "Save failed");
                    }
                    return false;
                }
                if (statusElement) {
                    statusElement.innerText = "Saved";
                    statusElement.style.color = "#188038";
                    setTimeout(() => { statusElement.innerText = ""; }, 1200);
                }
                return true;
            } catch (error) {
                if (statusElement) {
                    statusElement.innerText = "Save failed";
                    statusElement.style.color = "#a50e0e";
                } else {
                    alert("Save failed");
                }
                return false;
            }
        }

        document.addEventListener("click", async (event) => {
            const star = event.target.closest(".review-star");
            if (star) {
                event.preventDefault();
                event.stopPropagation();

                const isFlagsPanelStar = Boolean(
                    star.closest("#user-tag-panel")
                );
                const mask = parseInt(star.dataset.mask || "0", 10) || 0;

                if (isFlagsPanelStar && userTagPanelMode === "filter") {
                    libraryFilterMarks ^= mask;
                    updateReviewStars(userTagPanelFlags, libraryFilterMarks);
                    setTagPanelStatus(
                        "Read-only filter — click Apply filters."
                    );
                    return;
                }

                const activeTarget = isFlagsPanelStar
                    ? getActiveUserTagTarget()
                    : null;
                const block = isFlagsPanelStar
                    ? activeTarget.block
                    : star.closest(".user-review-block");
                const starsBox = star.closest(".review-stars");
                const status = isFlagsPanelStar
                    ? userTagPanelStatus
                    : (block ? block.querySelector(".review-save-status") : null);
                const trackId = isFlagsPanelStar
                    ? String(activeTarget.trackId || "")
                    : (block ? (block.dataset.trackId || "") : "");

                if (!block || !trackId || !starsBox) {
                    if (isFlagsPanelStar) {
                        setTagPanelStatus("Choose a track first.", false);
                    }
                    return;
                }

                const oldMarks = isFlagsPanelStar
                    ? getBlockMarks(block)
                    : (parseInt(starsBox.dataset.marks || "0", 10) || 0);
                const newMarks = oldMarks ^ mask;
                syncTrackMarksClient(trackId, newMarks);
                if (typeof refreshTrackRatingBadge === "function") {
                    refreshTrackRatingBadge(trackId, newMarks);
                }
                const ok = await saveUserReview(
                    trackId,
                    newMarks,
                    null,
                    status
                );
                if (!ok) {
                    syncTrackMarksClient(trackId, oldMarks);
                    if (typeof refreshTrackRatingBadge === "function") {
                        refreshTrackRatingBadge(trackId, oldMarks);
                    }
                }
                return;
            }

        });

        document.addEventListener("click", async (event) => {
            const openButton = event.target.closest(".review-tags-open");
            if (openButton) {
                event.preventDefault();
                event.stopPropagation();
                openUserTagPanel(openButton.closest(".user-review-block"));
                return;
            }

            const toggle = event.target.closest(".user-tag-toggle");
            if (toggle) {
                event.preventDefault();
                if (userTagPanelMode === "filter") {
                    toggleLibraryTagFilter(toggle.dataset.tag || "");
                    return;
                }
                await toggleTagOnActiveTrack(toggle.dataset.tag || "");
                return;
            }

            const pin = event.target.closest(".user-tag-pin");
            if (pin) {
                event.preventDefault();
                if (userTagPanelMode === "filter") { return; }
                await togglePinnedUserTag(pin.dataset.tag || "");
                return;
            }

            const del = event.target.closest(".user-tag-delete");
            if (del) {
                event.preventDefault();
                if (userTagPanelMode === "filter") { return; }
                await deleteUserTagGlobally(del.dataset.tag || "");
                return;
            }
        });

        if (userTagPanelClose) {
            userTagPanelClose.addEventListener("click", closeUserTagPanel);
        }

        if (addLibraryFilterButton) {
            addLibraryFilterButton.addEventListener(
                "click",
                openUserTagFilterPanel
            );
        }

        if (userTagFilterClear) {
            userTagFilterClear.addEventListener(
                "click",
                clearLibraryReviewFilters
            );
        }

        if (userTagFilterApply) {
            userTagFilterApply.addEventListener(
                "click",
                applyLibraryReviewFilters
            );
        }

        if (userTagSearchInput) {
            userTagSearchInput.addEventListener("input", () => {
                updateUserTagClearButtons();
                renderUserTagPanel();
            });
        }

        if (userTagNewInput) {
            userTagNewInput.addEventListener(
                "input",
                updateUserTagClearButtons
            );
        }

        if (userTagNewClear) {
            userTagNewClear.addEventListener("click", () => {
                if (userTagNewInput) {
                    userTagNewInput.value = "";
                    userTagNewInput.focus();
                }
                updateUserTagClearButtons();
            });
        }

        if (userTagSearchClear) {
            userTagSearchClear.addEventListener("click", () => {
                if (userTagSearchInput) {
                    userTagSearchInput.value = "";
                    userTagSearchInput.focus();
                }
                updateUserTagClearButtons();
                renderUserTagPanel();
            });
        }

        if (userTagSortBtn) {
            userTagSortBtn.addEventListener("click", () => {
                tagSortAscending = !tagSortAscending;
                renderUserTagPanel();
            });
        }

        if (userTagAddBtn) {
            userTagAddBtn.addEventListener("click", addNewUserTagAndAssign);
        }

        if (userTagNewInput) {
            userTagNewInput.addEventListener("keydown", (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    addNewUserTagAndAssign();
                }
            });
        }

        document.addEventListener(
            "keydown",
            (event) => {
                const panelOpen =
                    userTagPanel &&
                    !userTagPanel.classList.contains("hidden");

                if (
                    panelOpen &&
                    (event.ctrlKey || event.metaKey) &&
                    event.key.toLowerCase() === "x"
                ) {
                    event.preventDefault();
                    event.stopPropagation();
                    closeUserTagPanel();
                }
            },
            true
        );

