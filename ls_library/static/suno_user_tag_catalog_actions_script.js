        async function postUserTagAction(url, values) {
            const body = new URLSearchParams();
            Object.entries(values || {}).forEach(([key, value]) => body.set(key, String(value ?? "")));
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body.toString()
            });
            const data = await response.json().catch(() => ({ ok: false, error: "Invalid server response" }));
            if (!response.ok || !data.ok) {
                throw new Error(data.error || "Tag action failed");
            }
            return data;
        }

        async function toggleTagOnActiveTrack(tag) {
            const target = getActiveUserTagTarget();

            if (!target.trackId || !target.block) {
                setTagPanelStatus("Choose a track first.", false);
                return;
            }

            const oldTags = getBlockTags(target.block);
            const key = userTagKey(tag);
            const hasTag = oldTags.some(
                (item) => userTagKey(item) === key
            );
            const newTags = hasTag
                ? oldTags.filter((item) => userTagKey(item) !== key)
                : oldTags.concat([tag]);

            setBlockTags(target.block, newTags);
            if (isCurrentUserTagTarget(target)) {
                renderUserTagPanel();
            }

            const status = target.block.querySelector(
                ".review-save-status"
            );
            const ok = await saveUserReview(
                target.trackId,
                null,
                normalizeTagsClient(newTags.join(", ")),
                status
            );

            if (!ok) {
                setBlockTags(target.block, oldTags);
                if (isCurrentUserTagTarget(target)) {
                    renderUserTagPanel();
                    setTagPanelStatus(
                        "Could not save tag change.",
                        false
                    );
                }
            } else if (isCurrentUserTagTarget(target)) {
                setTagPanelStatus(
                    hasTag
                        ? "Tag removed from this track."
                        : "Tag added to this track."
                );
            }
        }

        async function addNewUserTagAndAssign() {
            const filterMode = userTagPanelMode === "filter";
            const actionSession = activeTagSession;
            const target = filterMode ? null : getActiveUserTagTarget();

            if (!filterMode && (!target.trackId || !target.block)) {
                setTagPanelStatus("Choose a track first.", false);
                return;
            }

            const requested = normalizeOneTagClient(
                userTagNewInput ? userTagNewInput.value : ""
            );
            if (!requested) {
                setTagPanelStatus("Enter a tag name.", false);
                return;
            }

            try {
                const data = await postUserTagAction(
                    "/add-user-tag",
                    { tag: requested }
                );
                userTagCatalog = Array.isArray(data.tags)
                    ? data.tags
                    : userTagCatalog;
                pinnedUserTags = new Set(
                    (data.pinned || []).map(userTagKey)
                );
                const canonical = data.tag || requested;

                if (!filterMode) {
                    const oldTags = getBlockTags(target.block);
                    if (
                        !oldTags.some(
                            (item) =>
                                userTagKey(item) === userTagKey(canonical)
                        )
                    ) {
                        const newTags = oldTags.concat([canonical]);
                        setBlockTags(target.block, newTags);

                        const status = target.block.querySelector(
                            ".review-save-status"
                        );
                        const ok = await saveUserReview(
                            target.trackId,
                            null,
                            normalizeTagsClient(newTags.join(", ")),
                            status
                        );

                        if (!ok) {
                            setBlockTags(target.block, oldTags);
                            throw new Error(
                                "Tag was created, but could not be assigned " +
                                "to this exact Track ID."
                            );
                        }
                    }
                }

                const panelContextIsCurrent = filterMode
                    ? (
                        userTagPanelMode === "filter" &&
                        actionSession === activeTagSession
                    )
                    : isCurrentUserTagTarget(target);

                if (panelContextIsCurrent) {
                    if (userTagNewInput) {
                        userTagNewInput.value = "";
                    }
                    updateUserTagClearButtons();
                    renderUserTagPanel();
                    setTagPanelStatus(
                        filterMode
                            ? canonical + " created in tag catalog."
                            : canonical + " added."
                    );
                    if (userTagNewInput) {
                        userTagNewInput.focus();
                    }
                }
            } catch (error) {
                const panelContextIsCurrent = filterMode
                    ? (
                        userTagPanelMode === "filter" &&
                        actionSession === activeTagSession
                    )
                    : isCurrentUserTagTarget(target);
                if (panelContextIsCurrent) {
                    setTagPanelStatus(
                        error.message || "Could not add tag.",
                        false
                    );
                }
            }
        }

        async function togglePinnedUserTag(tag) {
            const key = userTagKey(tag);
            const nextPinned = !pinnedUserTags.has(key);
            try {
                const data = await postUserTagAction("/pin-user-tag", {
                    tag: tag,
                    pinned: nextPinned ? "1" : "0"
                });
                userTagCatalog = Array.isArray(data.tags) ? data.tags : userTagCatalog;
                pinnedUserTags = new Set((data.pinned || []).map(userTagKey));
                renderUserTagPanel();
                setTagPanelStatus(nextPinned ? "Tag pinned." : "Tag unpinned.");
            } catch (error) {
                setTagPanelStatus(error.message || "Could not change pin.", false);
            }
        }

        async function deleteUserTagGlobally(tag) {
            const confirmed = confirm(
                "Delete " + tag + " from the tag catalog?\n\n" +
                "This also removes this tag marker from ALL tracks.\n" +
                "LS will create DB and tag-list backups first."
            );
            if (!confirmed) { return; }

            try {
                const data = await postUserTagAction("/delete-user-tag", { tag: tag });
                userTagCatalog = Array.isArray(data.tags) ? data.tags : userTagCatalog.filter((item) => userTagKey(item) !== userTagKey(tag));
                pinnedUserTags = new Set((data.pinned || []).map(userTagKey));

                document.querySelectorAll("tr.track-row, .user-review-block").forEach((block) => {
                    const oldTags = getBlockTags(block);
                    const newTags = oldTags.filter((item) => userTagKey(item) !== userTagKey(tag));
                    if (newTags.length !== oldTags.length) {
                        setBlockTags(block, newTags);
                    }
                });

                document.querySelectorAll(".user-tag-badge").forEach((badge) => {
                    const badgeTag = badge.dataset.userTag || badge.innerText || "";
                    if (userTagKey(badgeTag) === userTagKey(tag)) {
                        badge.remove();
                    }
                });

                renderUserTagPanel();
                setTagPanelStatus(
                    tag + " deleted. Removed from " +
                    String(data.removed_from_tracks || 0) + " track(s)."
                );
            } catch (error) {
                setTagPanelStatus(error.message || "Could not delete tag.", false);
            }
        }