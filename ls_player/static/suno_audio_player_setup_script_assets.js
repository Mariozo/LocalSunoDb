        function setupPlayerBlock(playerBlock, audioSrc, waveformSource, trackId, endCallback) {
            const audio = getPlayerBlockAudio(playerBlock);
            const backButton = playerBlock.querySelector(".back-btn");

            audio.addEventListener("play", () => {
                const fragment = playerBlock.closest(".fragment-row");
                if (fragment) {
                    fragment.querySelectorAll("audio").forEach((otherAudio) => {
                        if (otherAudio !== audio && !otherAudio.paused) {
                            otherAudio.pause();
                        }
                    });
                }
                if (lastActiveAudio && lastActiveAudio !== audio && !lastActiveAudio.paused) {
                    lastActiveAudio.pause();
                }
                lastActiveAudio = audio;
                const fragmentRow = playerBlock.closest(".fragment-row");
                const trackRow = fragmentRow
                    ? fragmentRow.previousElementSibling
                    : null;
                if (
                    trackRow &&
                    trackRow.classList.contains("track-row")
                ) {
                    setPlayerHighlight(trackRow, fragmentRow);
                    const playButton = trackRow.querySelector(".play-btn");
                    if (playButton && playerBlock.classList.contains("suno-block")) {
                        playButton.innerText = "❚❚";
                        playButton.classList.add("active");
                    }
                }
            });

            audio.addEventListener("focus", () => {
                lastActiveAudio = audio;
            });

            audio.addEventListener("click", () => {
                lastActiveAudio = audio;
            });
            const forwardButton = playerBlock.querySelector(".forward-btn");
            const setAButton = playerBlock.querySelector(".ab-set-a-btn");
            const setBButton = playerBlock.querySelector(".ab-set-b-btn");
            const clearABButton = playerBlock.querySelector(".ab-clear-btn");
            const abReadout = playerBlock.querySelector(".ab-readout");
            const waveformBox = playerBlock.querySelector(".waveform-box");
            const waveformImage = playerBlock.querySelector(".waveform-image");
            const abRegion = playerBlock.querySelector(".ab-region");
            const abMarkerA = playerBlock.querySelector(".ab-marker-a");
            const abMarkerB = playerBlock.querySelector(".ab-marker-b");
            const zoomReadout = playerBlock.querySelector(".zoom-readout");
            let abStart = null;
            let abEnd = null;
            let zoomStart = 0;
            let zoomEnd = null;

            function resetZoomWindow() {
                const duration = audio.duration || 0;
                zoomStart = 0;
                zoomEnd = duration || null;
                if (waveformBox) {
                    waveformBox.dataset.zoomStart = "0";
                    waveformBox.dataset.zoomEnd = String(duration || 0);
                    waveformBox.classList.remove("zoomed");
                }
                updateZoomReadout();
            }

            function updateWaveformVisualZoom() {
                const duration = audio.duration || 0;
                if (!waveformImage || !duration) {
                    return;
                }
                const endValue = zoomEnd || duration;
                const span = Math.max(0.1, endValue - zoomStart);
                const zoomFactor = Math.max(1, duration / span);

                if (zoomFactor <= 1.01) {
                    waveformImage.style.width = "100%";
                    waveformImage.style.left = "0%";
                    return;
                }

                // Full waveform image is widened; left offset shows the chosen time window.
                // left percent is relative to the container width.
                const leftPct = -((zoomStart / span) * 100);
                waveformImage.style.width = (zoomFactor * 100) + "%";
                waveformImage.style.left = leftPct + "%";
            }

            function updateZoomReadout() {
                const duration = audio.duration || 0;
                if (!zoomReadout) { return; }
                updateWaveformVisualZoom();
                if (!duration || zoomStart <= 0.01 && (zoomEnd === null || Math.abs(zoomEnd - duration) < 0.05)) {
                    zoomReadout.innerText = "";
                    if (waveformBox) { waveformBox.classList.remove("zoomed"); }
                    return;
                }
                const span = Math.max(0.1, (zoomEnd || duration) - zoomStart);
                const zoomFactor = duration / span;
                zoomReadout.innerText = "Zoom ×" + zoomFactor.toFixed(1);
                if (waveformBox) { waveformBox.classList.add("zoomed"); }
            }

            function setZoomWindow(start, end) {
                const duration = audio.duration || 0;
                if (!duration) { return; }
                const minSpan = Math.min(duration, 1.0);
                zoomStart = Math.max(0, Math.min(duration - minSpan, start));
                zoomEnd = Math.max(zoomStart + minSpan, Math.min(duration, end));
                if (waveformBox) {
                    waveformBox.dataset.zoomStart = String(zoomStart);
                    waveformBox.dataset.zoomEnd = String(zoomEnd);
                }
                updateZoomReadout();
                updateProgress(playerBlock);
                updateABDisplay();
            }

            function fmtShortTime(value) {
                if (!isFinite(value) || value < 0) { return "--:--"; }
                const m = Math.floor(value / 60);
                const s = Math.floor(value % 60);
                return String(m) + ":" + String(s).padStart(2, "0");
            }

            function updateABDisplay() {
                const duration = audio.duration || 0;
                const hasA = abStart !== null && isFinite(abStart);
                const hasB = abEnd !== null && isFinite(abEnd);

                if (setAButton) { setAButton.classList.toggle("active", hasA); }
                if (setBButton) { setBButton.classList.toggle("active", hasB); }
                if (clearABButton) { clearABButton.disabled = !(hasA || hasB); }

                if (abMarkerA) {
                    if (hasA && duration > 0) {
                        abMarkerA.style.left = timeToZoomPercent(playerBlock, abStart) + "%";
                        abMarkerA.style.display = "block";
                    } else {
                        abMarkerA.style.display = "none";
                    }
                }

                if (abMarkerB) {
                    if (hasB && duration > 0) {
                        abMarkerB.style.left = timeToZoomPercent(playerBlock, abEnd) + "%";
                        abMarkerB.style.display = "block";
                    } else {
                        abMarkerB.style.display = "none";
                    }
                }

                if (abRegion) {
                    if (hasA && hasB && duration > 0 && abEnd > abStart) {
                        const left = timeToZoomPercent(playerBlock, abStart);
                        const right = timeToZoomPercent(playerBlock, abEnd);
                        abRegion.style.left = left + "%";
                        abRegion.style.width = Math.max(0, right - left) + "%";
                        abRegion.style.display = "block";
                    } else {
                        abRegion.style.display = "none";
                    }
                }

                if (abReadout) {
                    if (hasA && hasB && abEnd > abStart) {
                        abReadout.innerText = "A/B " + fmtShortTime(abStart) + "–" + fmtShortTime(abEnd);
                    } else if (hasA) {
                        abReadout.innerText = "A " + fmtShortTime(abStart);
                    } else if (hasB) {
                        abReadout.innerText = "B " + fmtShortTime(abEnd);
                    } else {
                        abReadout.innerText = "";
                    }
                }
            }

            function setABPoint(which) {
                if (!audio || !isFinite(audio.currentTime)) { return; }
                const t = Math.max(0, audio.currentTime || 0);
                if (which === "a") {
                    abStart = t;
                    if (abEnd !== null && abEnd <= abStart) { abEnd = null; }
                } else {
                    abEnd = t;
                    if (abStart !== null && abEnd <= abStart) {
                        const oldA = abStart;
                        abStart = abEnd;
                        abEnd = oldA;
                    }
                }
                updateABDisplay();
            }

            playerBlock.classList.remove("hidden");
            audio.src = audioSrc;
            audio.loop = false;
            abStart = null;
            abEnd = null;
            resetZoomWindow();
            updateABDisplay();
            const loopButton = playerBlock.querySelector(".loop-audio-btn");
            if (loopButton) {
                loopButton.classList.remove("active");
                loopButton.innerText = "Loop";
                loopButton.title = "Loop: atskaņot šo audio bezgalīgi";
            }
            audio.load();

            loadWaveform(playerBlock, trackId, waveformSource);

            audio.onloadedmetadata = () => {
                resetZoomWindow();
                updateProgress(playerBlock);
                updateABDisplay();
            };

            audio.ontimeupdate = () => {
                updateProgress(playerBlock);
                if (audio.loop && abStart !== null && abEnd !== null && abEnd > abStart) {
                    if (audio.currentTime >= abEnd || audio.currentTime < abStart) {
                        audio.currentTime = abStart;
                        audio.play().catch(() => {});
                    }
                }
            };

            audio.onended = () => {
                if (audio.loop && abStart !== null && abEnd !== null && abEnd > abStart) {
                    audio.currentTime = abStart;
                    audio.play().catch(() => {});
                    return;
                }
                if (endCallback) {
                    endCallback();
                }
                updateProgress(playerBlock);
            };

            if (setAButton) {
                setAButton.onclick = () => setABPoint("a");
            }

            if (setBButton) {
                setBButton.onclick = () => setABPoint("b");
            }

            if (clearABButton) {
                clearABButton.onclick = () => {
                    abStart = null;
                    abEnd = null;
                    updateABDisplay();
                };
            }

            if (backButton) {
                backButton.onclick = () => {
                    audio.currentTime = Math.max(0, audio.currentTime - 10);
                    updateProgress(playerBlock);
                };
            }

            if (forwardButton) {
                forwardButton.onclick = () => {
                    if (audio.duration) {
                        audio.currentTime = Math.min(audio.duration, audio.currentTime + 10);
                        updateProgress(playerBlock);
                    }
                };
            }

            waveformBox.onclick = (event) => {
                const rect = waveformBox.getBoundingClientRect();
                const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));

                if (audio.duration) {
                    audio.currentTime = zoomPercentToTime(playerBlock, ratio);
                    if (event.ctrlKey || event.shiftKey) {
                        setABPoint("a");
                    } else if (event.altKey) {
                        setABPoint("b");
                    }
                    updateProgress(playerBlock);
                }
            };

            waveformBox.addEventListener("wheel", (event) => {
                if (!audio.duration) { return; }

                // Normal mouse wheel must not zoom or move anything.
                // Zoom is only Ctrl + mouse wheel over waveform.
                if (!event.ctrlKey) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const rect = waveformBox.getBoundingClientRect();
                const pct = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
                const zoom = getZoomWindow(playerBlock, audio.duration);
                const center = zoom.start + pct * zoom.span;
                const factor = event.deltaY < 0 ? 0.72 : 1.38;
                let newSpan = Math.max(0.5, Math.min(audio.duration, zoom.span * factor));
                let start = center - pct * newSpan;
                let end = start + newSpan;
                if (start < 0) {
                    end -= start;
                    start = 0;
                }
                if (end > audio.duration) {
                    start -= (end - audio.duration);
                    end = audio.duration;
                }
                setZoomWindow(start, end);
            }, { passive: false });

            waveformBox.ondblclick = (event) => {
                event.preventDefault();
                resetZoomWindow();
                updateProgress(playerBlock);
                updateABDisplay();
            };

            return audio;
        }

