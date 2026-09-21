        const headers = document.querySelectorAll(".sort-control");
        const mainFilterForm = document.getElementById("main-filter-form");
        const categoryFilterSearch = document.getElementById("category-filter-search");
        if (categoryFilterSearch) {
            const categoryOptions = document.querySelectorAll(
                '.library-multi-option[data-multi-filter-param="category_filter"]'
            );
            categoryFilterSearch.addEventListener("input", () => {
                const query = String(categoryFilterSearch.value || "")
                    .trim()
                    .toLocaleLowerCase();
                categoryOptions.forEach((button) => {
                    const value = String(button.dataset.multiFilterValue || "");
                    button.hidden = Boolean(
                        value &&
                        query &&
                        !value.toLocaleLowerCase().includes(query)
                    );
                });
            });
        }

        document.querySelectorAll(".library-multi-option").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const param = String(button.dataset.multiFilterParam || "");
                const value = String(button.dataset.multiFilterValue || "");
                if (!param) { return; }

                const url = new URL(window.location.href);
                const current = url.searchParams.getAll(param).filter(Boolean);
                const valueKey = value.toLocaleLowerCase();
                const additiveClick = event.ctrlKey || event.metaKey;
                let next = [];

                if (!value) {
                    next = [];
                } else if (additiveClick) {
                    const exists = current.some(
                        (item) => String(item).toLocaleLowerCase() === valueKey
                    );
                    next = exists
                        ? current.filter(
                            (item) => String(item).toLocaleLowerCase() !== valueKey
                        )
                        : current.concat([value]);
                } else {
                    next = [value];
                }

                let targetUrl = url;
                if (
                    param === "local_family_filter" &&
                    value &&
                    !additiveClick
                ) {
                    // A normal Local family click starts a clean focus view.
                    // Preserve only sorting; every potentially incompatible
                    // selection/search filter is intentionally discarded.
                    targetUrl = new URL("/", window.location.origin);
                    const sortBy = url.searchParams.get("sort_by") || "";
                    const sortDir = url.searchParams.get("sort_dir") || "";
                    if (sortBy) { targetUrl.searchParams.set("sort_by", sortBy); }
                    if (sortDir) { targetUrl.searchParams.set("sort_dir", sortDir); }
                }

                targetUrl.searchParams.delete(param);
                next.forEach(
                    (item) => targetUrl.searchParams.append(param, item)
                );
                const relatedModeParam = {
                    workspace: "workspace_mode",
                    category_filter: "category_mode",
                }[param] || "";
                if (relatedModeParam && (!additiveClick || next.length < 2)) {
                    targetUrl.searchParams.delete(relatedModeParam);
                }
                targetUrl.searchParams.delete("rows");
                saveViewState();
                stopAllPlaybackForNavigation();
                showBusy("Applying filters...", "Loading results...");
                window.location.href = targetUrl.toString();
            });
        });

        document.querySelectorAll(".library-group-mode-option").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                if (button.disabled) { return; }

                const param = String(button.dataset.groupModeParam || "");
                const value = String(button.dataset.groupModeValue || "or");
                if (!param) { return; }
                const url = new URL(window.location.href);
                if (value === "family_and") {
                    url.searchParams.set(param, "family_and");
                } else {
                    url.searchParams.delete(param);
                }
                url.searchParams.delete("rows");
                saveViewState();
                stopAllPlaybackForNavigation();
                showBusy("Applying Local family logic...", "Loading results...");
                window.location.href = url.toString();
            });
        });

        document.querySelectorAll("#main-filter-form select[data-auto-submit='1']").forEach((select) => {
            select.addEventListener("change", () => {
                if (mainFilterForm) {
                    mainFilterForm.requestSubmit();
                }
            });
        });

        // DB refresh result dismissal is stateful: remove both the banner and
        // the transient db_refresh URL marker so it cannot reappear on reload.
        document.querySelectorAll(".refresh-message-close[data-db-refresh-close='1']").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const message = button.closest(".refresh-message");
                if (message) {
                    message.remove();
                }

                const url = new URL(window.location.href);
                if (!url.searchParams.has("db_refresh")) {
                    return;
                }
                url.searchParams.delete("db_refresh");
                window.history.replaceState(
                    window.history.state,
                    "",
                    url.toString()
                );
            });
        });