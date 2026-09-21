        let compareThisState = null;

        function findOriginalReviewBlockByTrackId(trackId) {
            const idKey = String(trackId || "").trim().toLowerCase();
            return Array.from(document.querySelectorAll(".user-review-block")).find((block) =>
                !block.classList.contains("compare-this-review-editor") &&
                String(block.dataset.trackId || "").trim().toLowerCase() === idKey
            ) || null;
        }

        function compareThisMarkLabels(marks) {
            const value = parseInt(marks || "0", 10) || 0;
            const labels = [];
            if (value & 1) { labels.push("Labs ritms"); }
            if (value & 2) { labels.push("Labs pavadījums"); }
            if (value & 4) { labels.push("Labs solo"); }
            if (value & 8) { labels.push("Interesants"); }
            if (value & 16) { labels.push("Pievērst uzmanību / izcils moments"); }
            return labels;
        }

        function ensureCompareThisRatingBadge(item, marks) {
            if (!item) { return; }
            const badgeBox = item.querySelector(".compare-this-compact-badges");
            if (!badgeBox) { return; }

            const value = parseInt(marks || "0", 10) || 0;
            const labels = compareThisMarkLabels(value);
            let badge = badgeBox.querySelector(".user-rating-badge");

            if (!badge) {
                badge = document.createElement("span");
                badge.className = "title-badge user-rating-badge compare-this-empty-rating";
                badge.tabIndex = 0;
                badge.setAttribute("role", "button");

                const beforeNode = badgeBox.querySelector(".model-badge") || null;
                badgeBox.insertBefore(badge, beforeNode);
            }

            badge.classList.toggle("compare-this-empty-rating", labels.length === 0);
            badge.textContent = labels.length ? labels.map(() => "✶").join(" ") : "✶";
            badge.title = labels.length
                ? labels.join(", ") + ". Click to edit LS markers."
                : "Add LS markers";
        }

        function refreshTrackRatingBadge(trackId, marks) {
            const idKey = String(trackId || "").trim().toLowerCase();
            const value = parseInt(marks || "0", 10) || 0;
            const labels = compareThisMarkLabels(value);

            const row = Array.from(document.querySelectorAll("tr.track-row")).find((candidate) =>
                String(candidate.dataset.trackId || "").trim().toLowerCase() === idKey
            ) || null;

            if (row) {
                let metaLine = row.querySelector(".title-meta-line");
                let meta = row.querySelector(".title-meta");
                let badge = row.querySelector(".user-rating-badge");

                if (labels.length) {
                    if (!meta) {
                        const titleStack = row.querySelector(".title-stack");
                        if (titleStack) {
                            metaLine = document.createElement("div");
                            metaLine.className = "title-meta-line";
                            meta = document.createElement("span");
                            meta.className = "title-meta";
                            metaLine.appendChild(meta);
                            titleStack.appendChild(metaLine);
                        }
                    }

                    if (meta && !badge) {
                        badge = document.createElement("span");
                        badge.className = "title-badge user-rating-badge";
                        const beforeNode =
                            meta.querySelector(".user-tag-badge") ||
                            meta.querySelector(".model-badge") ||
                            null;
                        meta.insertBefore(badge, beforeNode);
                    }

                    if (badge) {
                        badge.textContent = labels.map(() => "✶").join(" ");
                        badge.title = labels.join(", ");
                    }
                } else if (badge) {
                    badge.remove();
                }
            }

            document.querySelectorAll(".compare-this-compact-item").forEach((item) => {
                if (String(item.dataset.trackId || "").trim().toLowerCase() !== idKey) {
                    return;
                }
                ensureCompareThisRatingBadge(item, value);
                const starsBox = item.querySelector(".compare-this-review-editor .review-stars");
                if (starsBox) {
                    updateReviewStars(starsBox, value);
                }
            });
        }

        function refreshCompareThisTagBadges(trackId, tags) {
            const idKey = String(trackId || "").trim().toLowerCase();
            const finalTags = Array.isArray(tags) ? tags.filter(Boolean).slice(0, 4) : [];

            document.querySelectorAll(".compare-this-compact-item").forEach((item) => {
                if (String(item.dataset.trackId || "").trim().toLowerCase() !== idKey) {
                    return;
                }

                const badgeBox = item.querySelector(".compare-this-compact-badges");
                if (!badgeBox) { return; }

                badgeBox.querySelectorAll(".user-tag-badge").forEach((badge) => badge.remove());
                const beforeNode = badgeBox.querySelector(".model-badge") || null;

                finalTags.forEach((tag) => {
                    const badge = document.createElement("span");
                    badge.className = "title-badge user-tag-badge";
                    badge.dataset.userTag = tag;
                    badge.textContent = tag;
                    badge.tabIndex = 0;
                    badge.setAttribute("role", "button");
                    badge.title = tag + " — click to edit Flags and Tags";
                    badgeBox.insertBefore(badge, beforeNode);
                });
            });
        }

        function closeAllCompareThisReviewEditors(exceptEditor=null) {
            document.querySelectorAll(".compare-this-review-editor.open").forEach((editor) => {
                if (editor !== exceptEditor) {
                    editor.classList.remove("open");
                }
            });
        }

        function openCompareThisReviewEditor(editor, anchorBadge) {
            if (!editor || !anchorBadge) {
                return;
            }

            closeAllCompareThisReviewEditors(editor);

            editor.classList.add("open");
            editor.style.visibility = "hidden";
            editor.style.left = "0px";
            editor.style.top = "0px";

            const anchorRect = anchorBadge.getBoundingClientRect();
            const editorRect = editor.getBoundingClientRect();
            const margin = 8;
            const gap = 6;

            let left =
                anchorRect.left +
                (anchorRect.width / 2) -
                (editorRect.width / 2);

            left = Math.max(
                margin,
                Math.min(left, window.innerWidth - editorRect.width - margin)
            );

            let top = anchorRect.bottom + gap;
            if (top + editorRect.height > window.innerHeight - margin) {
                top = anchorRect.top - editorRect.height - gap;
            }

            top = Math.max(
                margin,
                Math.min(top, window.innerHeight - editorRect.height - margin)
            );

            editor.style.left = Math.round(left) + "px";
            editor.style.top = Math.round(top) + "px";
            editor.style.visibility = "visible";
        }

