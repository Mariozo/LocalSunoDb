        document.addEventListener("click", async (event) => {
            const auditAcceptButton = event.target.closest(".intent-audit-accept-btn");
            const clickedCategoryButton = event.target.closest(".main-category-toggle-btn");
            const auditTrackRow = auditAcceptButton
                ? auditAcceptButton.closest(".track-row")
                : null;
            const mainCategoryButton = clickedCategoryButton || (
                auditTrackRow
                    ? auditTrackRow.querySelector(".main-category-toggle-btn")
                    : null
            );
            const likeButton = event.target.closest(".like-toggle-btn");

            if (mainCategoryButton) {
                event.preventDefault();
                event.stopPropagation();

                if (mainCategoryButton.classList.contains("saving")) {
                    return;
                }

                const trackId = mainCategoryButton.dataset.trackId || "";
                const oldCategory = mainCategoryButton.dataset.category || mainCategoryButton.innerText.trim();
                const isConfirmed = mainCategoryButton.dataset.confirmed === "true";
                const trackRow = mainCategoryButton.closest(".track-row");
                const activeKind = new URLSearchParams(window.location.search)
                    .get("kind_filter") || "";
                const auditFilterActive = activeKind === "__intent_s_to_i__"
                    || activeKind === "__intent_i_to_s__";
                const proposedCategory = auditAcceptButton
                    ? (auditAcceptButton.dataset.intentCategory || "")
                    : "";
                const keepAuditCurrent = !auditAcceptButton
                    && auditFilterActive
                    && Boolean(trackRow?.querySelector(".intent-audit-badge"));
                const newCategory = resolveMainCategoryClick(
                    oldCategory,
                    isConfirmed,
                    proposedCategory,
                    keepAuditCurrent
                );

                if (!trackId) {
                    return;
                }

                mainCategoryButton.classList.add("saving");
                const body = new URLSearchParams();
                body.set("track_id", trackId);
                body.set("category", newCategory);

                try {
                    const response = await fetch("/toggle-main-category", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });
                    const text = await response.text();
                    if (!response.ok) {
                        alert(text || "Could not update category.");
                        return;
                    }

                    const savedCategory = (text || newCategory).trim();
                    syncMainCategoryButtons(trackId, savedCategory);
                    const auditBadge = trackRow
                        ? trackRow.querySelector(".intent-audit-badge")
                        : null;
                    if (auditBadge) {
                        stopAndRemoveResolvedAuditCandidate(trackRow, auditFilterActive);
                        showIntentAuditDecisionStatus(
                            keepAuditCurrent || savedCategory === oldCategory
                                ? `Kept ${savedCategory} · marked reviewed`
                                : `Changed to ${savedCategory} · marked reviewed`
                        );
                    }
                    const activeCategories = new URLSearchParams(
                        window.location.search
                    ).getAll("category_filter").flatMap(
                        (value) => value.split(",")
                    );
                    if (
                        trackRow
                        && shouldRemoveConfirmedCategoryRow(
                            activeCategories,
                            savedCategory
                        )
                    ) {
                        stopAndRemoveResolvedAuditCandidate(trackRow, true);
                    }
                } catch (error) {
                    alert("Could not update category.");
                } finally {
                    mainCategoryButton.classList.remove("saving");
                }

                return;
            }

            if (likeButton) {
                event.preventDefault();
                event.stopPropagation();

                const trackId = likeButton.dataset.trackId || "";
                const currentLiked = (likeButton.dataset.liked || "false") === "true";
                const newLiked = !currentLiked;

                if (!trackId) {
                    return;
                }

                const body = new URLSearchParams();
                body.set("track_id", trackId);
                body.set("liked", newLiked ? "true" : "false");

                likeButton.disabled = true;

                try {
                    const response = await fetch("/toggle-like", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });

                    if (!response.ok) {
                        const text = await response.text();
                        alert(text || "Could not update Like.");
                        return;
                    }

                    syncLikeButtons(trackId, newLiked);
                } catch (error) {
                    alert("Could not update Like.");
                } finally {
                    likeButton.disabled = false;
                }

                return;
            }

            const editLyricsItem = event.target.closest(".menu-edit-lyrics");

            if (editLyricsItem) {
                event.preventDefault();
                event.stopPropagation();

                const wrap = editLyricsItem.closest(".row-menu-wrap");
                const menuButton = wrap
                    ? wrap.querySelector(".row-menu-btn")
                    : null;

                const trackId = menuButton
                    ? (menuButton.dataset.trackId || "")
                    : "";
                const trackTitle = menuButton
                    ? (
                        menuButton.dataset.rawTitle ||
                        menuButton.dataset.title ||
                        trackId
                    )
                    : trackId;
                closeRowMenus();

                if (trackId) {
                    openLyricsEditorForTrack(trackId, trackTitle);
                }

                return;
            }

            const editTitleItem = event.target.closest(".menu-edit-title");

            if (editTitleItem) {
                event.preventDefault();
                event.stopPropagation();

                const wrap = editTitleItem.closest(".row-menu-wrap");
                const menuButton = wrap ? wrap.querySelector(".row-menu-btn") : null;
                const trackId = menuButton ? menuButton.dataset.trackId : "";
                const currentTitle = menuButton ? (menuButton.dataset.rawTitle || menuButton.dataset.title || "") : "";

                closeRowMenus();

                if (!trackId) {
                    return;
                }

                const cleanCurrentTitle = (currentTitle === "[No title]") ? "" : currentTitle;
                const newTitle = prompt("Jaunais LS nosaukums:", cleanCurrentTitle);

                if (newTitle === null) {
                    return;
                }

                const trimmedTitle = newTitle.trim();
                if (!trimmedTitle) {
                    alert("Nosaukums nedrīkst būt tukšs.");
                    return;
                }

                const body = new URLSearchParams();
                body.set("track_id", trackId);
                body.set("title", trimmedTitle);

                try {
                    const response = await fetch("/save-title", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });

                    const text = await response.text();

                    if (!response.ok) {
                        alert(text || "Could not save title.");
                        return;
                    }

                    saveViewState();
                    window.location.reload();
                } catch (error) {
                    alert("Could not save title.");
                }

                return;
            }

            const addLocalItem = event.target.closest(".menu-add-local");

            if (addLocalItem) {
                event.preventDefault();
                event.stopPropagation();

                const wrap = addLocalItem.closest(".row-menu-wrap");
                const menuButton = wrap ? wrap.querySelector(".row-menu-btn") : null;
                const trackId = menuButton ? menuButton.dataset.trackId : "";
                const title = menuButton ? menuButton.dataset.title : "";

                closeRowMenus();

                if (!trackId) {
                    return;
                }

                const localPath = prompt("Paste full local audio path for:\n" + (title || trackId));

                if (!localPath) {
                    return;
                }

                const body = new URLSearchParams();
                body.set("track_id", trackId);
                body.set("path", localPath);

                try {
                    const response = await fetch("/add-local-audio", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });

                    const text = await response.text();

                    if (!response.ok) {
                        alert(text || "Could not add local audio.");
                        return;
                    }

                    alert(text || "Local audio added.");
                    saveViewState();
                    window.location.reload();
                } catch (error) {
                    alert("Could not add local audio.");
                }

                return;
            }

            const addStemFolderItem = event.target.closest(".menu-add-stem-folder");

            if (addStemFolderItem) {
                event.preventDefault();
                event.stopPropagation();

                const wrap = addStemFolderItem.closest(".row-menu-wrap");
                const menuButton = wrap ? wrap.querySelector(".row-menu-btn") : null;
                const trackId = menuButton ? menuButton.dataset.trackId : "";

                closeRowMenus();
                if (!trackId) { return; }

                saveViewState();
                try {
                    const response = await fetch("/choose-stem-folder?track_id=" + encodeURIComponent(trackId));
                    const text = await response.text();
                    if (!response.ok) {
                        alert(text || "Could not add stem folder.");
                        return;
                    }
                    if (text) { alert(text); }
                    window.location.reload();
                } catch (error) {
                    alert("Could not add stem folder.");
                }
                return;
            }

            const deleteLocalVariantItem = event.target.closest(".menu-delete-local-variant");

            if (deleteLocalVariantItem) {
                event.preventDefault();
                event.stopPropagation();

                const wrap = deleteLocalVariantItem.closest(".row-menu-wrap");
                const menuButton = wrap ? wrap.querySelector(".row-menu-btn") : null;
                const trackId = menuButton ? menuButton.dataset.trackId : "";
                const title = menuButton ? menuButton.dataset.title : "";
                const localWav = menuButton ? (menuButton.dataset.localWav || "") : "";
                const localMp3 = menuButton ? (menuButton.dataset.localMp3 || "") : "";
                const localPath = localWav || localMp3;

                closeRowMenus();

                if (!trackId || !localPath) {
                    alert("This row has no linked local WAV/MP3 file in LS DB.");
                    return;
                }

                const ok = confirm(
                    "Delete the COMPLETE local variant?\n\n" +
                    (title || trackId) + "\n\n" +
                    localPath + "\n\n" +
                    "The whole numbered variant folder, including Stems, will be moved to LS Backup.\n" +
                    "LS will create a DB backup and remove DB links for files inside this variant.\n" +
                    "The song-title folder is removed only if no local material remains.\n" +
                    "Variant numbers are never renumbered or reused.\n\n" +
                    "Nothing is deleted from Suno."
                );

                if (!ok) {
                    return;
                }

                const body = new URLSearchParams();
                body.set("track_id", trackId);
                body.set("path", localPath);

                try {
                    const response = await fetch("/delete-local-variant", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });

                    const responseText = await response.text();

                    if (!response.ok) {
                        alert(responseText || "Could not delete local variant.");
                        return;
                    }

                    alert(responseText || "Local variant moved to Backup.");
                    saveViewState();
                    window.location.reload();
                } catch (error) {
                    alert("Could not delete local variant.");
                }

                return;
            }

            const deleteLocalItem = event.target.closest(".menu-delete-local");

            if (deleteLocalItem) {
                event.preventDefault();
                event.stopPropagation();

                const wrap = deleteLocalItem.closest(".row-menu-wrap");
                const menuButton = wrap ? wrap.querySelector(".row-menu-btn") : null;
                const trackId = menuButton ? menuButton.dataset.trackId : "";
                const title = menuButton ? menuButton.dataset.title : "";
                const localWav = menuButton ? (menuButton.dataset.localWav || "") : "";
                const localMp3 = menuButton ? (menuButton.dataset.localMp3 || "") : "";
                const localPath = localWav || localMp3;

                closeRowMenus();

                if (!trackId || !localPath) {
                    alert("This row has no linked local audio file in LS DB.");
                    return;
                }

                const ok = confirm(
                    "Move linked local audio to LS Backup and remove it from this row?\n\n" +
                    (title || trackId) + "\n\n" +
                    localPath + "\n\n" +
                    "This does not delete anything from Suno."
                );

                if (!ok) {
                    return;
                }

                const body = new URLSearchParams();
                body.set("track_id", trackId);
                body.set("path", localPath);

                try {
                    const response = await fetch("/delete-local-audio", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });

                    const text = await response.text();

                    if (!response.ok) {
                        alert(text || "Could not delete local audio.");
                        return;
                    }

                    alert(text || "Local audio moved to Backup.");
                    saveViewState();
                    window.location.reload();
                } catch (error) {
                    alert("Could not delete local audio.");
                }

                return;
            }
        });


