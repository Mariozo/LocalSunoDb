        function buildCompareThisCompactItem(data, index) {
            const item = document.createElement("div");
            item.className = "compare-this-compact-item";
            item.dataset.trackId = data.trackId || "";

            const thumb = document.createElement("div");
            thumb.className = "compare-this-compact-thumb";
            if (data.thumbSource) {
                thumb.appendChild(data.thumbSource.cloneNode(true));
            }

            const head = document.createElement("div");
            head.className = "compare-this-compact-head";

            const playButton = document.createElement("button");
            playButton.type = "button";
            playButton.className = "compare-this-compact-play";
            playButton.textContent = "▶";
            playButton.title = "Play / pause";

            const time = document.createElement("span");
            time.className = "compare-this-compact-time";
            time.textContent = "0:00 / " + (data.durationText || "0:00");

            const itemIndex = document.createElement("span");
            itemIndex.className = "compare-this-compact-index";
            itemIndex.textContent = String(index + 1) + ".";

            const name = document.createElement("span");
            name.className = "compare-this-compact-name";
            name.textContent = data.title;
            name.title = data.title;

            const textButton = document.createElement("button");
            textButton.type = "button";
            textButton.className = "compare-this-compact-text";
            textButton.style.display =
                data.textField && data.textPreview ? "" : "none";
            textButton.textContent = data.textField && data.textPreview
                ? "[" + (data.textLabel || data.textField) + "] " + data.textPreview
                : "";
            textButton.addEventListener("click", () => {
                openTrackTextForTrack(
                    data.trackId || "",
                    data.title || "",
                    data.textField || "lyrics"
                );
            });

            const badges = document.createElement("span");
            badges.className = "compare-this-compact-badges";
            if (data.titleMeta) {
                Array.from(data.titleMeta.children).forEach((child) => {
                    const clone = child.cloneNode(true);
                    clone.style.pointerEvents = "";

                    if (clone.classList.contains("user-tag-badge")) {
                        clone.tabIndex = 0;
                        clone.setAttribute("role", "button");
                        clone.title =
                            (clone.dataset.userTag || clone.textContent || "#Tag") +
                            " — click to edit Flags and Tags";
                    } else if (clone.classList.contains("user-rating-badge")) {
                        clone.tabIndex = 0;
                        clone.setAttribute("role", "button");
                        clone.title =
                            (clone.title ? clone.title + ". " : "") +
                            "Click to edit LS markers.";
                    }

                    badges.appendChild(clone);
                });
            }

            head.appendChild(playButton);
            head.appendChild(time);
            head.appendChild(itemIndex);
            head.appendChild(name);
            head.appendChild(textButton);
            head.appendChild(badges);

            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "download-wav-btn compare-this-compact-edit";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => {
                editCompareThisTrack(editButton, data);
            });

            const compactMenuButton = document.createElement("button");
            compactMenuButton.type = "button";
            compactMenuButton.className = "compare-this-compact-menu";
            compactMenuButton.textContent = "⋮";
            compactMenuButton.title = "More actions";
            compactMenuButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const originalWrap = data.menuWrap;
                const originalMenu = originalWrap
                    ? originalWrap.querySelector(".row-menu")
                    : null;

                if (!originalMenu) {
                    return;
                }

                const wasHidden = originalMenu.classList.contains("hidden");
                closeRowMenus();

                if (wasHidden) {
                    originalMenu.classList.remove("hidden");
                    positionRowMenu(compactMenuButton, originalMenu);
                }
            });

            const reviewEditor = document.createElement("div");
            reviewEditor.className =
                "user-review-block compare-this-review-editor";
            reviewEditor.dataset.trackId = data.trackId || "";

            const reviewStars = document.createElement("div");
            reviewStars.className = "review-stars";
            reviewStars.dataset.marks = String(data.marks || 0);
            reviewStars.title = "LS marķieri";

            [
                [1, "Labs ritms"],
                [2, "Labs pavadījums"],
                [4, "Labs solo"],
                [8, "Interesants"],
                [16, "Pievērst uzmanību / izcils moments"]
            ].forEach(([mask, titleText]) => {
                const star = document.createElement("button");
                star.type = "button";
                star.className = "review-star";
                star.dataset.mask = String(mask);
                star.title = titleText;
                star.textContent = "✶";
                reviewStars.appendChild(star);
            });

            const reviewStatus = document.createElement("span");
            reviewStatus.className = "review-save-status";

            reviewEditor.appendChild(reviewStars);
            reviewEditor.appendChild(reviewStatus);

            badges.addEventListener("click", (event) => {
                const tagBadge = event.target.closest(".user-tag-badge");
                if (tagBadge) {
                    event.preventDefault();
                    event.stopPropagation();
                    const originalBlock = findOriginalReviewBlockByTrackId(data.trackId);
                    if (originalBlock) {
                        openUserTagPanel(originalBlock);
                    }
                    return;
                }

                const ratingBadge = event.target.closest(".user-rating-badge");
                if (ratingBadge) {
                    event.preventDefault();
                    event.stopPropagation();

                    if (reviewEditor.classList.contains("open")) {
                        reviewEditor.classList.remove("open");
                    } else {
                        openCompareThisReviewEditor(reviewEditor, ratingBadge);
                    }
                }
            });

            badges.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") {
                    return;
                }
                const targetBadge = event.target.closest(
                    ".user-tag-badge, .user-rating-badge"
                );
                if (targetBadge) {
                    event.preventDefault();
                    targetBadge.click();
                }
            });

            reviewStars.addEventListener("click", () => {
                setTimeout(() => {
                    const marks = parseInt(reviewStars.dataset.marks || "0", 10) || 0;
                    refreshTrackRatingBadge(data.trackId, marks);
                }, 0);
            });

            const audio = document.createElement("audio");
            audio.className = "compare-this-compact-audio";
            audio.preload = "metadata";
            audio.src = data.audioUrl;

            const waveform = document.createElement("div");
            waveform.className = "waveform-box compare-this-compact-wave";
            waveform.title = "Click = seek and play. Tab = next selected track from the last clicked position.";

            const loading = document.createElement("div");
            loading.className = "wave-loading";
            loading.textContent = "Loading waveform...";

            const image = document.createElement("img");
            image.className = "waveform-image";
            image.alt = "waveform";

            const fill = document.createElement("div");
            fill.className = "big-progress-fill";

            const knob = document.createElement("div");
            knob.className = "big-progress-knob";

            const status = document.createElement("span");
            status.className = "wave-status";
            status.style.display = "none";

            waveform.appendChild(loading);
            waveform.appendChild(image);
            waveform.appendChild(fill);
            waveform.appendChild(knob);

            item.appendChild(thumb);
            item.appendChild(head);
            item.appendChild(editButton);
            item.appendChild(compactMenuButton);
            document.body.appendChild(reviewEditor);
            item.appendChild(audio);
            item.appendChild(status);
            item.appendChild(waveform);

            updateReviewStars(reviewStars, data.marks || 0);
            ensureCompareThisRatingBadge(item, data.marks || 0);

            const entry = {
                item: item,
                audio: audio,
                playButton: playButton,
                time: time,
                waveform: waveform,
                fill: fill,
                knob: knob,
                data: data,
                index: index
            };

            audio.addEventListener("play", () => {
                pauseOtherCompareThisAudio(entry);
                if (compareThisState) {
                    compareThisState.activeIndex = index;
                }
                lastActiveAudio = audio;
                playButton.textContent = "❚❚";
                waveform.classList.add("is-playing");
            });

            audio.addEventListener("pause", () => {
                playButton.textContent = "▶";
                waveform.classList.remove("is-playing");
                updateCompareThisCompactProgress(entry);
            });

            audio.addEventListener("ended", () => {
                playButton.textContent = "▶";
                waveform.classList.remove("is-playing");
                updateCompareThisCompactProgress(entry);
            });

            audio.addEventListener("loadedmetadata", () => {
                updateCompareThisCompactProgress(entry);
            });

            audio.addEventListener("timeupdate", () => {
                updateCompareThisCompactProgress(entry);
            });

            playButton.addEventListener("click", () => {
                if (audio.paused) {
                    playCompareThisEntry(index, null);
                } else {
                    audio.pause();
                }
            });

            waveform.addEventListener("click", (event) => {
                if (!audio.duration) {
                    return;
                }

                const rect = waveform.getBoundingClientRect();
                const ratio = Math.max(
                    0,
                    Math.min(1, (event.clientX - rect.left) / rect.width)
                );
                const clickedTime = ratio * audio.duration;

                if (compareThisState) {
                    compareThisState.anchorTime = clickedTime;
                    compareThisState.activeIndex = index;
                }

                playCompareThisEntry(index, clickedTime);
            });

            loadWaveform(item, data.trackId, data.waveformUrl || data.audioUrl);
            audio.load();

            return entry;
        }

