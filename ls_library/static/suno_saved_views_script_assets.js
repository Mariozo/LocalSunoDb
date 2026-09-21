        function buildReusableSavedViewQuery(value) {
            const allowed = new Set([
                "q", "style_q", "workspace", "workspace_mode",
                "category_filter", "category_mode", "local_family_filter",
                "kind_filter", "local_audio_filter", "search_name",
                "search_lyrics", "search_prompt", "search_marks", "search_tags",
                "flag_filter", "tag_filter", "sort_by", "sort_dir"
            ]);
            const text = String(value || "").trim();
            let queryText = text;
            if (text.includes("://")) {
                try {
                    queryText = new URL(text).search;
                } catch (_) {
                    return "";
                }
            }
            const source = new URLSearchParams(queryText.replace(/^\?/, ""));
            const clean = new URLSearchParams();
            source.forEach((rawValue, key) => {
                if (!allowed.has(key)) { return; }
                const cleanValue = String(rawValue || "").trim();
                if (!cleanValue) { return; }
                clean.append(key, cleanValue);
            });
            return clean.toString();
        }

        function getSavedViewSuggestedName() {
            const labels = Array.from(document.querySelectorAll(".ls-filter-chip-label"))
                .map((item) => String(item.textContent || "").trim())
                .filter(Boolean);
            return labels.length ? labels.join(" + ").slice(0, 80) : "All tracks";
        }

        function setSavedViewModalStatus(message, ok=false) {
            if (!savedViewModalStatus) { return; }
            savedViewModalStatus.textContent = String(message || "");
            savedViewModalStatus.style.color = ok ? "#83D3AB" : "#FF9C9C";
        }

        function openSavedViewModal(viewId="", viewName="", queryOverride="") {
            if (!savedViewModal || !savedViewNameInput) { return; }
            savedViewEditingId = String(viewId || "").trim();
            const isRename = !!savedViewEditingId;
            savedViewPendingQuery = isRename ? "" : String(queryOverride || "").trim();
            if (savedViewModalTitle) {
                savedViewModalTitle.textContent = isRename ? "Rename saved view" : "Save current view";
            }
            if (savedViewModalHelp) {
                savedViewModalHelp.textContent = isRename
                    ? "Only the name will change. The saved filters stay the same."
                    : "The current filters and sorting will be saved. The database is not changed.";
            }
            if (savedViewModalSave) {
                savedViewModalSave.textContent = isRename ? "Rename" : "Save view";
                savedViewModalSave.disabled = false;
            }
            savedViewNameInput.value = isRename
                ? String(viewName || "")
                : (String(viewName || "").trim() || getSavedViewSuggestedName());
            setSavedViewModalStatus("");
            if (savedViewsDetails) { savedViewsDetails.open = false; }
            savedViewModal.style.display = "flex";
            setTimeout(() => {
                savedViewNameInput.focus();
                const caretPosition = savedViewNameInput.value.length;
                savedViewNameInput.setSelectionRange(caretPosition, caretPosition);
            }, 30);
        }

        function closeSavedViewModal() {
            if (!savedViewModal) { return; }
            savedViewModal.style.display = "none";
            savedViewEditingId = "";
            savedViewPendingQuery = "";
            setSavedViewModalStatus("");
        }

        async function postSavedViewAction(path, values) {
            const body = new URLSearchParams();
            Object.entries(values || {}).forEach(([key, value]) => body.set(key, String(value ?? "")));
            const response = await fetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body.toString(),
            });
            const data = await response.json().catch(() => ({
                ok: false,
                error: "Invalid Saved views response.",
            }));
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "Saved views action failed.");
            }
            return data;
        }

        function refreshSavedViewsMenu(views) {
            if (!savedViewsDetails) { return; }
            const items = Array.isArray(views) ? views : [];
            const summary = savedViewsDetails.querySelector("summary");
            const menu = savedViewsDetails.querySelector(".ls-saved-views-menu");
            if (summary) {
                summary.textContent = items.length ? "Views (" + items.length + ")" : "Views";
            }
            if (!menu) { return; }
            menu.replaceChildren();

            if (!items.length) {
                const empty = document.createElement("div");
                empty.className = "ls-saved-view-empty";
                empty.textContent = "No saved views yet";
                menu.appendChild(empty);
                return;
            }

            items.forEach((item) => {
                const viewId = String(item && item.id || "");
                const viewName = String(item && item.name || "Saved view");
                const viewQuery = String(item && item.query || "");

                const row = document.createElement("div");
                row.className = "ls-saved-view-row";
                row.dataset.savedViewId = viewId;

                const link = document.createElement("a");
                link.className = "ls-saved-view-link";
                link.href = viewQuery ? "/?" + viewQuery : "/";
                link.title = "Open " + viewName;
                link.textContent = viewName;

                const rename = document.createElement("button");
                rename.type = "button";
                rename.className = "ls-saved-view-rename";
                rename.dataset.savedViewId = viewId;
                rename.dataset.savedViewName = viewName;
                rename.title = "Rename saved view";
                rename.textContent = "Rename";

                const remove = document.createElement("button");
                remove.type = "button";
                remove.className = "ls-saved-view-delete";
                remove.dataset.savedViewId = viewId;
                remove.dataset.savedViewName = viewName;
                remove.title = "Delete saved view";
                remove.setAttribute("aria-label", "Delete " + viewName);
                remove.textContent = "×";

                row.append(link, rename, remove);
                menu.appendChild(row);
            });
        }

        async function commitSavedViewModal() {
            if (!savedViewNameInput || !savedViewModalSave) { return; }
            const name = String(savedViewNameInput.value || "").trim();
            if (!name) {
                setSavedViewModalStatus("Enter a view name.");
                savedViewNameInput.focus();
                return;
            }
            savedViewModalSave.disabled = true;
            setSavedViewModalStatus(savedViewEditingId ? "Renaming..." : "Saving...", true);
            const isElzaSave = !savedViewEditingId && !!savedViewPendingQuery;
            const elzaSavedQuery = savedViewPendingQuery;
            try {
                let result = null;
                if (savedViewEditingId) {
                    result = await postSavedViewAction("/rename-saved-view", {
                        view_id: savedViewEditingId,
                        name: name,
                    });
                } else {
                    result = await postSavedViewAction("/save-current-view", {
                        name: name,
                        query: buildReusableSavedViewQuery(savedViewPendingQuery || window.location.search),
                    });
                }
                saveViewState();
                if (isElzaSave) {
                    refreshSavedViewsMenu(result && result.views);
                    closeSavedViewModal();
                    window.dispatchEvent(new CustomEvent("ls-elza-view-saved", {
                        detail: { query: elzaSavedQuery, name: name },
                    }));
                    return;
                }
                window.location.reload();
            } catch (error) {
                setSavedViewModalStatus(String(error && error.message || error));
                savedViewModalSave.disabled = false;
            }
        }

        if (saveViewButton) { saveViewButton.addEventListener("click", () => openSavedViewModal()); }
        if (savedViewModalClose) { savedViewModalClose.addEventListener("click", closeSavedViewModal); }
        if (savedViewModalCancel) { savedViewModalCancel.addEventListener("click", closeSavedViewModal); }
        if (savedViewModalSave) { savedViewModalSave.addEventListener("click", commitSavedViewModal); }
        if (savedViewNameInput) {
            savedViewNameInput.addEventListener("keydown", (event) => {
                if (event.key === "Enter") { event.preventDefault(); commitSavedViewModal(); }
            });
        }
        if (savedViewModal) {
            savedViewModal.addEventListener("click", (event) => {
                if (event.target === savedViewModal) { closeSavedViewModal(); }
            });
        }
        window.addEventListener("ls-elza-save-view-request", (event) => {
            const detail = event && event.detail && typeof event.detail === "object"
                ? event.detail
                : {};
            let targetUrl = null;
            try {
                targetUrl = new URL(String(detail.url || ""), window.location.origin);
            } catch (error) {
                return;
            }
            if (targetUrl.origin !== window.location.origin) { return; }
            openSavedViewModal(
                "",
                String(detail.name || "LS Elza selection").slice(0, 80),
                targetUrl.search
            );
        });

        if (savedViewsDetails) {
            savedViewsDetails.addEventListener("click", async (event) => {
                const renameButton = event.target.closest(".ls-saved-view-rename");
                if (renameButton && savedViewsDetails.contains(renameButton)) {
                    event.preventDefault();
                    event.stopPropagation();
                    openSavedViewModal(
                        renameButton.dataset.savedViewId || "",
                        renameButton.dataset.savedViewName || ""
                    );
                    return;
                }

                const deleteButton = event.target.closest(".ls-saved-view-delete");
                if (!deleteButton || !savedViewsDetails.contains(deleteButton)) { return; }
                event.preventDefault();
                event.stopPropagation();
                const viewId = String(deleteButton.dataset.savedViewId || "");
                const viewName = String(deleteButton.dataset.savedViewName || "Saved view");
                if (!viewId || !window.confirm('Delete saved view "' + viewName + '"?')) { return; }
                deleteButton.disabled = true;
                try {
                    await postSavedViewAction("/delete-saved-view", { view_id: viewId });
                    saveViewState();
                    window.location.reload();
                } catch (error) {
                    deleteButton.disabled = false;
                    window.alert(String(error && error.message || error));
                }
            });
        }
        document.addEventListener("click", (event) => {
            if (savedViewsDetails && savedViewsDetails.open && !savedViewsDetails.contains(event.target)) {
                savedViewsDetails.open = false;
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && savedViewModal && savedViewModal.style.display === "flex") {
                event.preventDefault();
                event.stopImmediatePropagation();
                closeSavedViewModal();
            }
        }, true);
