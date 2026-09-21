        function closeCompareThisInline() {
            document.querySelectorAll(".compare-this-review-editor").forEach((editor) => {
                editor.remove();
            });

            const existing = document.getElementById("compare-this-inline-row");
            if (existing) {
                existing.querySelectorAll("audio").forEach((audio) => {
                    try {
                        audio.pause();
                        audio.removeAttribute("src");
                        audio.load();
                    } catch (error) {}
                });
                existing.remove();
            }
            compareThisState = null;
        }

        function getCompareThisTrackData(trackRow) {
            const menuButton = trackRow.querySelector(".row-menu-btn");
            const menuWrap = trackRow.querySelector(".row-menu-wrap");
            const playButton = trackRow.querySelector(".play-btn");
            const titleLink = trackRow.querySelector(".title-link");
            const durationBadge = trackRow.querySelector(".thumb-duration-badge");
            const thumbSource = trackRow.querySelector(".thumb-link, .thumb-placeholder");
            const titleMeta = trackRow.querySelector(".title-meta");
            const textTrigger = trackRow.querySelector(".text-field-trigger");

            const trackId = String(trackRow.dataset.trackId || "");
            const originalReviewBlock = findOriginalReviewBlockByTrackId(trackId);
            const originalStars = originalReviewBlock
                ? originalReviewBlock.querySelector(".review-stars")
                : null;
            const marks = originalStars
                ? (parseInt(originalStars.dataset.marks || "0", 10) || 0)
                : 0;
            const title = titleLink
                ? String(titleLink.textContent || "").trim()
                : (
                    menuButton
                        ? String(menuButton.dataset.title || menuButton.dataset.rawTitle || trackId)
                        : trackId
                );
            const localAudioUrl = playButton
                ? String(playButton.dataset.localAudio || "")
                : "";
            const localPath = playButton
                ? String(playButton.dataset.localPath || "")
                : "";

            return {
                trackId: trackId,
                title: title,
                audioUrl: localAudioUrl,
                waveformUrl: localPath || localAudioUrl,
                localPath: localPath,
                durationText: durationBadge
                    ? String(durationBadge.textContent || "").trim()
                    : "0:00",
                thumbSource: thumbSource,
                titleMeta: titleMeta,
                textField: textTrigger
                    ? String(textTrigger.dataset.textField || "")
                    : "",
                textLabel: textTrigger
                    ? String(textTrigger.dataset.textLabel || "")
                    : "",
                textPreview: textTrigger
                    ? String(
                        (
                            textTrigger.querySelector(".title-text-field-preview") ||
                            textTrigger
                        ).textContent || ""
                    ).trim()
                    : "",
                marks: marks,
                menuWrap: menuWrap
            };
        }

        function updateCompareThisCompactProgress(entry) {
            const audio = entry.audio;
            const duration = Number(audio.duration || 0);
            const current = Number(audio.currentTime || 0);
            const pct = duration > 0
                ? Math.max(0, Math.min(100, current / duration * 100))
                : 0;

            entry.fill.style.width = pct + "%";
            entry.knob.style.left = pct + "%";
            entry.time.textContent =
                formatTime(current) + " / " +
                (duration > 0 ? formatTime(duration) : entry.data.durationText || "0:00");
        }

        function pauseOtherCompareThisAudio(activeEntry) {
            if (!compareThisState) {
                return;
            }

            compareThisState.entries.forEach((entry) => {
                if (entry !== activeEntry && !entry.audio.paused) {
                    entry.audio.pause();
                }
            });

            if (
                lastActiveAudio &&
                lastActiveAudio !== activeEntry.audio &&
                !lastActiveAudio.paused
            ) {
                lastActiveAudio.pause();
            }
        }

        function playCompareThisEntry(index, requestedTime=null) {
            if (!compareThisState || !compareThisState.entries.length) {
                return;
            }

            const count = compareThisState.entries.length;
            const safeIndex = ((index % count) + count) % count;
            const entry = compareThisState.entries[safeIndex];
            const audio = entry.audio;

            const begin = () => {
                pauseOtherCompareThisAudio(entry);

                if (requestedTime !== null && isFinite(requestedTime)) {
                    const duration = Number(audio.duration || 0);
                    const maxTime = duration > 0 ? Math.max(0, duration - 0.03) : requestedTime;
                    audio.currentTime = Math.max(0, Math.min(maxTime, requestedTime));
                } else if (audio.ended) {
                    audio.currentTime = 0;
                }

                compareThisState.activeIndex = safeIndex;
                lastActiveAudio = audio;
                audio.play().catch(() => {});
            };

            if (audio.readyState >= 1) {
                begin();
            } else {
                audio.addEventListener("loadedmetadata", begin, { once: true });
                audio.load();
            }
        }

        async function editCompareThisTrack(button, data) {
            const audioUrl = data.audioUrl || "";
            const trackId = data.trackId || "";
            const title = data.title || "";

            if (!audioUrl && !trackId) {
                return;
            }

            button.disabled = true;
            const originalText = button.textContent;
            button.textContent = "Wait";

            try {
                let localPath = "";

                if (trackId) {
                    const localParams = new URLSearchParams();
                    localParams.set("track_id", trackId);
                    const localPathResponse = await fetch(
                        "/local-audio-path?" + localParams.toString()
                    );
                    if (localPathResponse.ok) {
                        localPath = (await localPathResponse.text()).trim();
                    }
                }

                let response;
                if (localPath) {
                    const params = new URLSearchParams();
                    params.set("path", localPath);
                    response = await fetch("/edit-local?" + params.toString());
                } else {
                    const params = new URLSearchParams();
                    params.set("audio_url", audioUrl);
                    params.set("track_id", trackId);
                    params.set("title", title);
                    response = await fetch("/edit-suno?" + params.toString());
                }

                if (!response.ok && response.status !== 204) {
                    alert("Could not open audio in editor.");
                }
            } catch (error) {
                alert("Could not open audio in editor.");
            } finally {
                button.disabled = false;
                button.textContent = originalText;
            }
        }

