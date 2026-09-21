        function closeSidebarToolsMenu() {
            if (sidebarToolsWrap) { sidebarToolsWrap.classList.remove("is-open"); }
            if (sidebarToolsPopover) { sidebarToolsPopover.hidden = true; }
            if (sidebarToolsTrigger) { sidebarToolsTrigger.setAttribute("aria-expanded", "false"); }
        }
        function toggleSidebarToolsMenu() {
            if (!sidebarToolsWrap || !sidebarToolsPopover || !sidebarToolsTrigger) { return; }
            const willOpen = sidebarToolsPopover.hidden;
            closeTopMenus();
            closeRowMenus();
            closeSidebarToolsMenu();
            if (willOpen) {
                sidebarToolsWrap.classList.add("is-open");
                sidebarToolsPopover.hidden = false;
                sidebarToolsTrigger.setAttribute("aria-expanded", "true");
            }
        }
        if (sidebarToolsTrigger) {
            sidebarToolsTrigger.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                toggleSidebarToolsMenu();
            });
        }
        document.addEventListener("click", (event) => {
            if (sidebarToolsWrap && !sidebarToolsWrap.contains(event.target)) {
                closeSidebarToolsMenu();
            }
        });
        if (openStatsButton && statsModal) {
            openStatsButton.addEventListener("click", () => {
                const isOpen = statsModal.getAttribute("aria-hidden") === "false";
                closeTopMenus();
                closeRowMenus();
                closeSidebarToolsMenu();
                if (isOpen) {
                    closeStatsModal();
                } else {
                    statsModal.style.display = "flex";
                    statsModal.setAttribute("aria-hidden", "false");
                }
            });
        }
        function closeStatsModal() {
            if (!statsModal) { return; }
            statsModal.style.display = "none";
            statsModal.classList.remove("open");
            statsModal.setAttribute("aria-hidden", "true");
        }
        if (statsModalClose && statsModal) {
            statsModalClose.addEventListener("click", closeStatsModal);
        }
        if (statsModal) {
            statsModal.addEventListener("click", (event) => {
                if (event.target === statsModal) {
                    closeStatsModal();
                }
            });
        }
        if (finderSearchClose) {
            finderSearchClose.addEventListener("click", exitFinderSearch);
        }
        if (finderSearchPrev) {
            finderSearchPrev.addEventListener("click", () => goToFinderResult(finderCurrentIndex - 1));
        }
        if (finderSearchNext) {
            finderSearchNext.addEventListener("click", () => goToFinderResult(finderCurrentIndex + 1));
        }
        if (finderSearchInput) {
            finderSearchInput.addEventListener("keydown", (event) => {
                if (event.key === "ArrowUp") {
                    event.preventDefault();
                    navigateFinderSearchHistory(1);
                    return;
                }
                if (event.key === "ArrowDown") {
                    event.preventDefault();
                    navigateFinderSearchHistory(-1);
                    return;
                }
                if (event.key === "Enter") {
                    event.preventDefault();
                    submitFinderSearch();
                    return;
                }
                if (event.key === "Escape") {
                    event.preventDefault();
                    exitFinderSearch();
                }
            });
            finderSearchInput.addEventListener("input", () => {
                finderSearchHistoryIndex = -1;
                finderSearchDraft = finderSearchInput.value || "";
                clearFinderHighlight();
                finderCurrentIndex = -1;
                updateFinderCount();
            });
        }

        [
            finderSearchName,
            finderSearchLyrics,
            finderSearchPrompt,
            finderSearchMarks,
            finderSearchTags,
        ].forEach((checkbox) => {
            if (!checkbox) { return; }
            checkbox.addEventListener("change", () => {
                clearFinderHighlight();
                finderCurrentIndex = -1;
                updateFinderCount();
            });
        });

        document.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "f") {
                event.preventDefault();
                event.stopPropagation();
                openFinderSearchBox();
                return;
            }
            if (event.key === "Escape") {
                closeSidebarToolsMenu();
                closeStatsModal();
                if (isFinderSearchOpen()) {
                    event.preventDefault();
                    exitFinderSearch();
                }
            }
        }, true);

        const finderScopeOnlyFilterActive = isAppliedFinderScopeOnlyFilter();
        if (
            finderSearchInput
            && (
                (finderSearchInput.value || "").trim()
                || finderScopeOnlyFilterActive
            )
        ) {
            if ((finderSearchInput.value || "").trim()) {
                rememberFinderSearchQuery(finderSearchInput.value);
            }
            if (finderSearchBox) { finderSearchBox.style.display = "block"; }
            setTimeout(() => { goToFinderResult(0); }, 180);
        }


