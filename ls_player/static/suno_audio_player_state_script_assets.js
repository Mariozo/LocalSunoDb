        function buildPlaybackMediaUrl(trackId, source) {
            const value = String(trackId || "").trim();
            if (!value) { return ""; }
            const mode = source === "local" ? "local" : "suno";
            return "/playback-media?track_id=" + encodeURIComponent(value) + "&source=" + mode;
        }

        function buildPlaybackWaveformUrl(trackId, source) {
            const value = String(trackId || "").trim();
            if (!value) { return ""; }
            const mode = source === "local" ? "local" : "suno";
            return "/playback-waveform?track_id=" + encodeURIComponent(value) + "&source=" + mode;
        }

        function buildSunoCurrentPlaybackUrl(trackId, fallbackAudioUrl = "") {
            const value = String(trackId || "").trim();
            if (value) {
                return buildPlaybackMediaUrl(value, "suno");
            }
            return String(fallbackAudioUrl || "").trim();
        }

        function selectDefaultPlaybackSource(localAudio) {
            const local = String(localAudio || "").trim();
            if (local) {
                return { source: "local", audioSrc: local };
            }
            return { source: "suno", audioSrc: "" };
        }

        function clearPlayerHighlight(exceptFragmentRow = null) {
            table.querySelectorAll("tr.track-row, tr.fragment-row").forEach((row) => {
                if (exceptFragmentRow && (row === exceptFragmentRow || row === exceptFragmentRow.previousElementSibling)) {
                    return;
                }

                row.classList.remove("player-open");
            });
        }

        function setPlayerHighlight(trackRow, fragmentRow) {
            clearPlayerHighlight(fragmentRow);
            trackRow.classList.add("player-open");
            fragmentRow.classList.add("player-open");
        }

        function pausePlaybackForTrackSelection() {
            table.querySelectorAll("tr.fragment-row:not(.hidden) audio").forEach((audio) => {
                if (!audio.paused) {
                    audio.pause();
                }
            });
            table.querySelectorAll(
                ".play-btn.active, .compare-btn.active, .stems-btn.active"
            ).forEach((button) => {
                button.classList.remove("active");
                if (button.classList.contains("play-btn")) {
                    button.innerText = "▶";
                }
            });
            table.querySelectorAll(
                "tr.fragment-row:not(.hidden) .stem-block"
            ).forEach((stemBlock) => {
                cancelSequential(stemBlock);
                resetStemPlayButtons(stemBlock);
                clearStemControlActive(stemBlock);
                if (currentStemBlock === stemBlock) {
                    currentStemBlock = null;
                }
            });
            if (currentStemBlock) {
                pauseStemBlock(currentStemBlock);
            }
            table.querySelectorAll("tr.track-row, tr.fragment-row").forEach((row) => {
                row.classList.remove("player-open");
            });
        }

        function closeOtherPlayers(currentRow) {
            const fragmentRows = table.querySelectorAll("tr.fragment-row");
            const buttons = table.querySelectorAll(".play-btn, .compare-btn, .stems-btn");

            clearPlayerHighlight(currentRow);

            fragmentRows.forEach((row) => {
                if (row !== currentRow) {
                    row.classList.add("hidden");

                    const otherStemBlock = row.querySelector(".stem-block");
                    if (otherStemBlock) {
                        cancelSequential(otherStemBlock);
                        clearStemControlActive(otherStemBlock);
                        if (currentStemBlock === otherStemBlock) { currentStemBlock = null; }
                    }
                    row.querySelectorAll("audio").forEach((audio) => {
                        audio.pause();
                        audio.removeAttribute("src");
                        audio.load();
                    });
                    const stemBlock = row.querySelector(".stem-block");
                    if (stemBlock) {
                        resetStemPlayButtons(stemBlock);
                    }
                }
            });

            buttons.forEach((button) => {
                button.classList.remove("active");

                if (button.classList.contains("play-btn")) {
                    button.innerText = "▶";
                }
            });
        }

        function getPlayerBlockAudio(playerBlock) {
            if (!playerBlock) { return null; }
            if (playerBlock.classList.contains("ls-global-player")) {
                return playerBlock.querySelector("audio.ls-global-player-audio");
            }
            return playerBlock.querySelector("audio");
        }

        function getZoomWindow(playerBlock, duration) {
            const box = playerBlock.querySelector(".waveform-box");
            if (!box || !duration) {
                return { start: 0, end: duration || 0, span: duration || 0 };
            }
            const start = Math.max(0, Math.min(duration, parseFloat(box.dataset.zoomStart || "0") || 0));
            const endRaw = parseFloat(box.dataset.zoomEnd || String(duration)) || duration;
            const end = Math.max(start + 0.1, Math.min(duration, endRaw));
            return { start: start, end: end, span: Math.max(0.1, end - start) };
        }

        function timeToZoomPercent(playerBlock, timeValue) {
            const audio = getPlayerBlockAudio(playerBlock);
            const duration = audio.duration || 0;
            if (!duration) { return 0; }
            const zoom = getZoomWindow(playerBlock, duration);
            return Math.max(0, Math.min(100, ((timeValue - zoom.start) / zoom.span) * 100));
        }

        function zoomPercentToTime(playerBlock, percent) {
            const audio = getPlayerBlockAudio(playerBlock);
            const duration = audio.duration || 0;
            if (!duration) { return 0; }
            const zoom = getZoomWindow(playerBlock, duration);
            return Math.max(0, Math.min(duration, zoom.start + (percent * zoom.span)));
        }

        function updateProgress(playerBlock) {
            const audio = getPlayerBlockAudio(playerBlock);
            const fill = playerBlock.querySelector(".big-progress-fill");
            const knob = playerBlock.querySelector(".big-progress-knob");
            const readout = playerBlock.querySelector(".time-readout");

            const duration = audio.duration || 0;
            const current = audio.currentTime || 0;
            const percent = duration > 0 ? timeToZoomPercent(playerBlock, current) : 0;

            fill.style.width = percent + "%";
            knob.style.left = percent + "%";
            readout.innerText = formatTime(current) + " / " + formatTime(duration);
        }

