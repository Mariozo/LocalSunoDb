        function alignCompareThisInline() {
            if (
                !compareThisState ||
                !compareThisState.row ||
                !compareThisState.sourceTrackRow
            ) {
                return;
            }

            const inlineRow = compareThisState.row;
            const sourceTrackRow = compareThisState.sourceTrackRow;
            const cell = inlineRow.querySelector("td");
            const player = inlineRow.querySelector(".compare-this-inline-player");

            if (!cell || !player) {
                return;
            }

            const sourceThumb = sourceTrackRow.querySelector(
                ".thumb-link, .thumb-placeholder"
            );
            const sourceMenu = sourceTrackRow.querySelector(".row-menu-btn");

            if (!sourceThumb || !sourceMenu) {
                return;
            }

            const cellRect = cell.getBoundingClientRect();
            const thumbRect = sourceThumb.getBoundingClientRect();
            const menuRect = sourceMenu.getBoundingClientRect();

            const leftMargin = Math.max(
                8,
                Math.round(thumbRect.left - cellRect.left)
            );
            const rightMargin = Math.max(
                8,
                Math.round(cellRect.right - menuRect.right)
            );

            const availableWidth = Math.max(
                260,
                Math.round(cellRect.width - leftMargin - rightMargin)
            );

            player.style.marginLeft = leftMargin + "px";
            player.style.marginRight = "0px";
            player.style.width = availableWidth + "px";
            player.style.maxWidth = availableWidth + "px";
        }

        function openCompareThisInline() {
            const compareSelection = getLocalWavCompareSelectionState();
            if (!compareSelection.compareReady) {
                return;
            }

            closeCompareThisInline();

            const selectedTrackRows = getSelectedLocalWavTrackRows();
            if (selectedTrackRows.length < 2) {
                return;
            }

            closeOtherPlayers(null);

            const firstTrackRow = selectedTrackRows[0];
            const firstFragmentRow = getFragmentRow(firstTrackRow);

            const inlineRow = document.createElement("tr");
            inlineRow.id = "compare-this-inline-row";
            inlineRow.className = "compare-this-inline-row";

            const cell = document.createElement("td");
            cell.colSpan = 9;

            const player = document.createElement("div");
            player.className = "compare-this-inline-player";

            const head = document.createElement("div");
            head.className = "compare-this-inline-head";

            const title = document.createElement("div");
            title.className = "compare-this-inline-title";
            title.textContent =
                "Compare This — " + selectedTrackRows.length + " selected";

            const closeButton = document.createElement("button");
            closeButton.type = "button";
            closeButton.className = "secondary compare-this-inline-close";
            closeButton.textContent = "Close";
            closeButton.addEventListener("click", closeCompareThisInline);

            head.appendChild(title);
            head.appendChild(closeButton);

            const list = document.createElement("div");
            list.className = "compare-this-compact-list";

            player.appendChild(head);
            player.appendChild(list);
            cell.appendChild(player);
            inlineRow.appendChild(cell);

            const insertionAnchor = firstFragmentRow || firstTrackRow;
            insertionAnchor.insertAdjacentElement("afterend", inlineRow);

            compareThisState = {
                row: inlineRow,
                cell: cell,
                sourceTrackRow: firstTrackRow,
                entries: [],
                activeIndex: -1,
                anchorTime: null
            };

            selectedTrackRows.forEach((trackRow, index) => {
                const data = getCompareThisTrackData(trackRow);
                if (!data.audioUrl) {
                    return;
                }

                const entry = buildCompareThisCompactItem(data, index);
                compareThisState.entries.push(entry);
                list.appendChild(entry.item);
            });

            if (!compareThisState.entries.length) {
                closeCompareThisInline();
                alert("Selected rows do not have playable Local WAV audio.");
                return;
            }

            requestAnimationFrame(() => {
                alignCompareThisInline();
                requestAnimationFrame(alignCompareThisInline);
            });

            inlineRow.scrollIntoView({
                behavior: "smooth",
                block: "nearest"
            });
        }

        if (compareThisButton) {
            compareThisButton.addEventListener("click", openCompareThisInline);
        }

        document.addEventListener(
            "ls-library-open-selected-wav-compare",
            openCompareThisInline
        );

        document.addEventListener("click", (event) => {
            if (
                !event.target.closest(".compare-this-review-editor") &&
                !event.target.closest(".compare-this-compact-badges .user-rating-badge")
            ) {
                closeAllCompareThisReviewEditors();
            }
        });

        window.addEventListener("scroll", () => {
            closeAllCompareThisReviewEditors();
        }, true);

        window.addEventListener("resize", () => {
            closeAllCompareThisReviewEditors();
            requestAnimationFrame(alignCompareThisInline);
        });

        document.addEventListener("keydown", (event) => {
            if (
                event.key === "Escape" &&
                document.getElementById("compare-this-inline-row")
            ) {
                closeCompareThisInline();
                return;
            }

            if (
                event.key === "Tab" &&
                compareThisState &&
                compareThisState.entries.length &&
                !event.ctrlKey &&
                !event.altKey &&
                !event.metaKey
            ) {
                const target = event.target;
                const tagName = target && target.tagName
                    ? target.tagName.toLowerCase()
                    : "";

                if (
                    tagName === "input" ||
                    tagName === "textarea" ||
                    tagName === "select" ||
                    (target && target.isContentEditable)
                ) {
                    return;
                }

                event.preventDefault();

                const currentIndex = compareThisState.activeIndex;
                const nextIndex = currentIndex < 0
                    ? 0
                    : (currentIndex + 1) % compareThisState.entries.length;

                let startTime = compareThisState.anchorTime;
                if (startTime === null && currentIndex >= 0) {
                    const currentEntry = compareThisState.entries[currentIndex];
                    startTime = Number(currentEntry.audio.currentTime || 0);
                }
                if (startTime === null) {
                    startTime = 0;
                }

                playCompareThisEntry(nextIndex, startTime);
            }
        });
