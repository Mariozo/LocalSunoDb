        document.addEventListener("click", async (event) => {
            const playAll = event.target.closest(".stem-play-all");
            const pauseAll = event.target.closest(".stem-pause-all");
            const stopAll = event.target.closest(".stem-stop-all");
            const rewindAll = event.target.closest(".stem-rewind-all");
            const selectToggle = event.target.closest(".stem-select-toggle");
            const playSeq = event.target.closest(".stem-play-seq");
            const openAudacity = event.target.closest(".stem-open-audacity");

            if (!playAll && !pauseAll && !stopAll && !rewindAll && !selectToggle && !playSeq && !openAudacity) {
                return;
            }

            const stemBlock = event.target.closest(".stem-block");
            if (!stemBlock) { return; }
            const audios = getStemAudios(stemBlock);
            const checkedAudios = getCheckedStemAudios(stemBlock);

            if (playAll) {
                try {
                    if (
                        lsGlobalPlayer &&
                        stemBlock.id === "ls-global-player-stem-panel" &&
                        typeof lsGlobalPlayer.activateStemPlayback === "function"
                    ) {
                        await lsGlobalPlayer.activateStemPlayback();
                    } else {
                        await toggleStemSpacePause(stemBlock);
                    }
                } catch (error) {
                    alert(String(error && error.message || error || "Could not control selected Stems."));
                }
                return;
            }

            if (pauseAll) {
                pauseStemBlock(stemBlock);
                setStemControlActive(stemBlock, ".stem-pause-all", true);
                return;
            }

            if (stopAll) {
                stopStemBlock(stemBlock);
                setStemControlActive(stemBlock, ".stem-stop-all", true);
                return;
            }

            if (rewindAll) {
                cancelSequential(stemBlock);
                audios.forEach((audio) => {
                    audio.pause();
                    try { audio.currentTime = 0; } catch (error) {}
                });
                try {
                    await rewindStemMix(stemBlock);
                } catch (error) {
                    alert(String(error && error.message || error || "Could not rewind Stems."));
                }
                return;
            }

            if (selectToggle) {
                const checks = Array.from(stemBlock.querySelectorAll(".stem-check"));
                const allChecked = checks.length > 0 && checks.every((check) => check.checked);
                setAllStemChecks(stemBlock, !allChecked);
                return;
            }

            if (playSeq) {
                stopStemMix(stemBlock, { updateSource: false });
                if (stemBlock.dataset.seqActive === "true") {
                    const currentAudio = checkedAudios.find((item) => !item.paused && !item.ended) || audios.find((item) => !item.paused && !item.ended);
                    if (currentAudio) {
                        currentAudio.pause();
                        try { currentAudio.currentTime = 0; } catch (error) {}
                        if (typeof currentAudio.onended === "function") {
                            currentAudio.onended(new Event("ended"));
                        }
                    }
                    return;
                }
                if (!checkedAudios.length) {
                    alert("Select at least one Stem first.");
                    return;
                }

                pauseMainAudioForStems();
                const seqToken = String(Date.now());
                stemBlock.dataset.seqToken = seqToken;
                currentStemBlock = stemBlock;
                clearStemControlActive(stemBlock);
                setSequentialRunning(stemBlock, true);
                audios.forEach((item) => {
                    item.pause();
                    try { item.currentTime = 0; } catch (error) {}
                });
                resetStemPlayButtons(stemBlock);
                applyStemMixState(stemBlock);
                markStemPlaybackSource(true);

                let index = 0;
                const finishSequential = () => {
                    if (stemBlock.dataset.seqToken === seqToken) {
                        setSequentialRunning(stemBlock, false);
                    }
                    resetStemPlayButtons(stemBlock);
                    markStemPlaybackSource(false);
                };

                const playNext = async () => {
                    if (stemBlock.dataset.seqToken !== seqToken) { return; }
                    if (index >= checkedAudios.length) {
                        finishSequential();
                        return;
                    }
                    const item = checkedAudios[index];
                    ensureStemSrc(item);
                    try { item.currentTime = 0; } catch (error) {}
                    applyStemMixState(stemBlock);
                    lastActiveAudio = item;
                    index += 1;
                    item.onended = () => {
                        const row = item.closest(".stem-row");
                        if (row) { row.classList.remove("active-stem"); }
                        playNext();
                    };
                    await item.play().catch(() => { playNext(); });
                };

                await playNext();
                return;
            }

            if (openAudacity) {
                const paths = Array.from(stemBlock.querySelectorAll(".stem-check:checked"))
                    .map((check) => check.dataset.path || "")
                    .filter(Boolean);
                if (!paths.length) {
                    alert("Select at least one Stem first.");
                    return;
                }
                const body = new URLSearchParams();
                paths.forEach((path) => body.append("path", path));
                try {
                    const response = await fetch("/open-stems-audacity", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });
                    const text = await response.text();
                    if (!response.ok) { alert(text || "Could not open Stems in Audacity."); }
                } catch (error) {
                    alert("Could not open Stems in Audacity.");
                }
            }
        });



        // Public STEMS API.  The legacy inline transport stays private to this block.
        window.LS = window.LS || {};
        window.LS.stems = Object.assign(window.LS.stems || {}, {
            playSelected(stemBlock, sharedPosition = null) {
                return toggleStemSpacePause(stemBlock, sharedPosition);
            },
            pause(stemBlock) {
                if (stemBlock) { pauseStemBlock(stemBlock); }
            },
            load(stemBlock, trackId) {
                return loadStemsForBlock(stemBlock, trackId);
            }
        });
