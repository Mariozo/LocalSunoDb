        const lsStemEngines = new WeakMap();

        function getStemEngine(stemBlock) {
            if (!stemBlock) { return null; }
            let engine = lsStemEngines.get(stemBlock);
            if (!engine) {
                engine = {
                    context: null,
                    activeNodes: new Map(),
                    generation: 0,
                    offset: 0,
                    startedAt: 0,
                    duration: 0,
                    playing: false,
                    mode: "mix",
                    raf: 0,
                    loading: false,
                    readyCount: 0,
                    loadError: "",
                };
                lsStemEngines.set(stemBlock, engine);
            }
            return engine;
        }

        function getStemRows(stemBlock) {
            if (!stemBlock) { return []; }
            return Array.from(stemBlock.querySelectorAll(".stem-row"));
        }

        function getCheckedStemRows(stemBlock) {
            return getStemRows(stemBlock).filter((row) => {
                const check = row.querySelector(".stem-check");
                return !check || check.checked;
            });
        }

        function syncStemSelectionVisual(row, included) {
            if (!row) { return; }
            const isIncluded = Boolean(included);
            row.classList.toggle("stem-included", isIncluded);
            row.classList.toggle("stem-excluded", !isIncluded);
            const wave = row.querySelector(".stem-wave");
            if (wave) {
                wave.title = isIncluded
                    ? "Selected for the Stems mix — dark waveform"
                    : "Not selected for the Stems mix — grey waveform";
            }
        }

        function getSelectedStemLabels(stemBlock) {
            return getCheckedStemRows(stemBlock)
                .map((row) => String(row.querySelector(".stem-label")?.textContent || "").trim().toLowerCase())
                .filter(Boolean);
        }

        function setStemChecksByLabels(stemBlock, labels) {
            if (!stemBlock) { return; }
            const wanted = new Set((labels || []).map((value) => String(value || "").trim().toLowerCase()).filter(Boolean));
            const rows = getStemRows(stemBlock);
            rows.forEach((row) => {
                const check = row.querySelector(".stem-check");
                const label = String(row.querySelector(".stem-label")?.textContent || "").trim().toLowerCase();
                if (!check) { return; }
                check.checked = wanted.size ? wanted.has(label) : true;
                const toggle = row.querySelector(".stem-include-toggle");
                if (toggle) {
                    toggle.classList.toggle("active", check.checked);
                    toggle.setAttribute("aria-pressed", check.checked ? "true" : "false");
                    toggle.title = check.checked
                        ? "Included in Play selected and To Audacity"
                        : "Excluded from Play selected and To Audacity";
                }
                syncStemSelectionVisual(row, check.checked);
            });
            if (!getCheckedStemRows(stemBlock).length && rows.length) {
                const firstCheck = rows[0].querySelector(".stem-check");
                if (firstCheck) {
                    firstCheck.checked = true;
                    syncStemSelectionVisual(rows[0], true);
                    const firstToggle = rows[0].querySelector(".stem-include-toggle");
                    if (firstToggle) {
                        firstToggle.classList.add("active");
                        firstToggle.setAttribute("aria-pressed", "true");
                    }
                }
            }
            updateStemMasterCheck(stemBlock);
            applyStemMixState(stemBlock);
        }

        function isStemPlaybackRunning(stemBlock) {
            const engine = getStemEngine(stemBlock);
            if (engine && engine.playing) { return true; }
            return getStemAudios(stemBlock).some((audio) => !audio.paused && !audio.ended);
        }

        function getStemAudios(stemBlock) {
            return getStemRows(stemBlock)
                .map((row) => row.querySelector("audio.stem-audio"))
                .filter(Boolean);
        }

        function getCheckedStemAudios(stemBlock) {
            return getCheckedStemRows(stemBlock)
                .map((row) => row.querySelector("audio.stem-audio"))
                .filter(Boolean);
        }

        function ensureStemSrc(audio) {
            if (!audio || audio.getAttribute("src")) { return; }
            const source = audio.dataset.src || "";
            if (source) {
                audio.src = source;
                audio.load();
            }
        }

        function getStemContext(engine) {
            if (!engine) { return null; }
            if (!engine.context) {
                const AudioContextClass = window.AudioContext || window.webkitAudioContext;
                if (!AudioContextClass) { throw new Error("Web Audio API is not available."); }
                engine.context = new AudioContextClass({ latencyHint: "playback" });
            }
            return engine.context;
        }

        function getStemRowLevel(row) {
            const range = row ? row.querySelector(".stem-level-range") : null;
            return Math.max(0, Math.min(100, Number(range ? range.value : 80) || 0));
        }

        function getStemPlaybackPosition(engine) {
            if (!engine) { return 0; }
            if (!engine.playing || !engine.context) { return Math.max(0, engine.offset || 0); }
            return Math.max(0, (engine.offset || 0) + Math.max(0, engine.context.currentTime - engine.startedAt));
        }

        function updateStemWaveProgressAt(row, currentTime) {
            if (!row) { return; }
            const marker = row.querySelector(".stem-wave-progress");
            if (!marker) { return; }
            const audio = row.querySelector("audio.stem-audio");
            const duration = Number((row._lsStemBuffer && row._lsStemBuffer.duration) || (audio && audio.duration) || 0);
            const percent = duration > 0
                ? Math.max(0, Math.min(100, (Number(currentTime || 0) / duration) * 100))
                : 0;
            marker.style.left = percent + "%";
        }

        function updateStemWaveProgress(audio) {
            if (!audio) { return; }
            updateStemWaveProgressAt(audio.closest(".stem-row"), Number(audio.currentTime || 0));
        }

        function updateStemEngineProgress(stemBlock, position) {
            getStemRows(stemBlock).forEach((row) => updateStemWaveProgressAt(row, position));
            const engine = getStemEngine(stemBlock);
            if (
                typeof lsGlobalPlayer !== "undefined" &&
                lsGlobalPlayer &&
                typeof lsGlobalPlayer.syncStemTransport === "function"
            ) {
                lsGlobalPlayer.syncStemTransport(
                    Number(position || 0),
                    Number(engine && engine.duration || 0)
                );
            }
        }

        function stopStemAnimation(engine) {
            if (engine && engine.raf) {
                cancelAnimationFrame(engine.raf);
                engine.raf = 0;
            }
        }

        function startStemAnimation(stemBlock) {
            const engine = getStemEngine(stemBlock);
            if (!engine) { return; }
            stopStemAnimation(engine);
            const tick = () => {
                if (!engine.playing) {
                    engine.raf = 0;
                    return;
                }
                const position = getStemPlaybackPosition(engine);
                updateStemEngineProgress(stemBlock, position);
                engine.raf = requestAnimationFrame(tick);
            };
            engine.raf = requestAnimationFrame(tick);
        }

        function disconnectStemNodes(engine) {
            if (!engine) { return; }
            engine.activeNodes.forEach((nodes) => {
                try { nodes.source.onended = null; } catch (error) {}
                try { nodes.source.stop(); } catch (error) {}
                try { nodes.source.disconnect(); } catch (error) {}
                try { nodes.gain.disconnect(); } catch (error) {}
            });
            engine.activeNodes.clear();
        }

        function updateStemMasterCheck(stemBlock) {
            if (!stemBlock) { return; }
            const checks = Array.from(stemBlock.querySelectorAll(".stem-check"));
            const toggle = stemBlock.querySelector(".stem-select-toggle");
            const status = stemBlock.querySelector(".stem-status");
            if (!checks.length) {
                if (toggle) { toggle.disabled = true; }
                return;
            }
            const checkedCount = checks.filter((check) => check.checked).length;
            if (toggle) {
                toggle.disabled = false;
                toggle.dataset.allChecked = checkedCount === checks.length ? "true" : "false";
                toggle.title = checkedCount === checks.length
                    ? "Clear all Include selections"
                    : "Select all Stems for playback and Audacity";
            }
            if (status) {
                const engine = getStemEngine(stemBlock);
                const ready = engine ? engine.readyCount : 0;
                const preparation = engine && engine.loading
                    ? " · preparing…"
                    : (ready > 0 ? " · " + ready + " ready" : "");
                status.innerText = checks.length + " stems · " + checkedCount + " included" + preparation;
            }
        }

        async function decodeStemRow(stemBlock, row) {
            if (!row) { throw new Error("Missing Stem row."); }
            if (row._lsStemBuffer) { return row._lsStemBuffer; }
            if (row._lsStemBufferPromise) { return await row._lsStemBufferPromise; }
            const engine = getStemEngine(stemBlock);
            const context = getStemContext(engine);
            const url = String(row.dataset.stemUrl || "").trim();
            if (!url) { throw new Error("Missing Stem audio URL."); }

            row._lsStemBufferPromise = (async () => {
                const response = await fetch(url, { cache: "default" });
                if (!response.ok) {
                    throw new Error("Stem audio HTTP " + response.status);
                }
                const bytes = await response.arrayBuffer();
                const buffer = await context.decodeAudioData(bytes.slice(0));
                row._lsStemBuffer = buffer;
                row._lsStemBufferPromise = null;
                return buffer;
            })().catch((error) => {
                row._lsStemBufferPromise = null;
                row.dataset.loadError = String(error && error.message || error || "Stem decode failed");
                throw error;
            });
            return await row._lsStemBufferPromise;
        }

        async function ensureStemBuffers(stemBlock, rows) {
            const engine = getStemEngine(stemBlock);
            const targets = (rows || getCheckedStemRows(stemBlock)).filter(Boolean);
            if (!engine || !targets.length) { return []; }
            engine.loading = true;
            engine.loadError = "";
            updateStemMasterCheck(stemBlock);

            const results = [];
            for (const row of targets) {
                try {
                    await decodeStemRow(stemBlock, row);
                    results.push(row);
                } catch (error) {
                    engine.loadError = String(error && error.message || error || "Stem decode failed");
                    break;
                }
            }
            engine.readyCount = getStemRows(stemBlock).filter((row) => Boolean(row._lsStemBuffer)).length;
            engine.loading = false;
            updateStemMasterCheck(stemBlock);
            if (results.length !== targets.length) {
                throw new Error(engine.loadError || "Not every selected Stem could be prepared.");
            }
            return results;
        }

        function applyStemMixState(stemBlock) {
            const rows = getStemRows(stemBlock);
            const engine = getStemEngine(stemBlock);
            const anySolo = rows.some((row) => row.dataset.solo === "true");
            rows.forEach((row) => {
                const audio = row.querySelector("audio.stem-audio");
                const muteButton = row.querySelector(".stem-mute");
                const soloButton = row.querySelector(".stem-solo");
                const isMuted = row.dataset.muted === "true";
                const isSolo = row.dataset.solo === "true";
                const levelValue = getStemRowLevel(row);
                const effectiveGain = isMuted || (anySolo && !isSolo) ? 0 : levelValue / 100;
                if (audio) {
                    audio.volume = levelValue / 100;
                    audio.muted = effectiveGain === 0;
                }
                const nodes = engine ? engine.activeNodes.get(row) : null;
                if (nodes && nodes.gain && engine.context) {
                    nodes.gain.gain.setTargetAtTime(effectiveGain, engine.context.currentTime, 0.012);
                }
                if (muteButton) {
                    muteButton.classList.toggle("active", isMuted);
                    muteButton.setAttribute("aria-pressed", isMuted ? "true" : "false");
                }
                if (soloButton) {
                    soloButton.classList.toggle("active", isSolo);
                    soloButton.setAttribute("aria-pressed", isSolo ? "true" : "false");
                }
                row.classList.toggle("stem-muted", effectiveGain === 0);
                row.classList.toggle("stem-soloed", isSolo);
            });
        }

        function setSequentialRunning(stemBlock, running) {
            if (!stemBlock) { return; }
            stemBlock.dataset.seqActive = running ? "true" : "false";
            const seqButton = stemBlock.querySelector(".stem-play-seq");
            if (seqButton) {
                seqButton.disabled = false;
                seqButton.innerText = running ? "▶▶ Next" : "▶▶ Sequential";
                seqButton.classList.toggle("active-control", running);
            }
        }

        function cancelSequential(stemBlock) {
            if (!stemBlock) { return; }
            stemBlock.dataset.seqToken = String(Date.now());
            setSequentialRunning(stemBlock, false);
            getStemAudios(stemBlock).forEach((audio) => {
                audio.onended = null;
                audio.pause();
            });
        }

        function resetStemPlayButtons(stemBlock) {
            if (!stemBlock) { return; }
            stemBlock.querySelectorAll(".stem-row").forEach((row) => row.classList.remove("active-stem"));
        }

        function clearStemControlActive(stemBlock) {
            if (!stemBlock) { return; }
            stemBlock.querySelectorAll(".stem-play-all, .stem-play-seq, .stem-rewind-all, .stem-pause-all, .stem-stop-all").forEach((button) => {
                button.classList.remove("active-control");
            });
        }

        function setStemControlActive(stemBlock, selector, momentary=false) {
            if (!stemBlock) { return; }
            clearStemControlActive(stemBlock);
            const button = stemBlock.querySelector(selector);
            if (!button) { return; }
            button.classList.add("active-control");
            if (momentary) {
                setTimeout(() => button.classList.remove("active-control"), 650);
            }
        }

        function markStemPlaybackSource(active) {
            if (typeof lsGlobalPlayer !== "undefined" && lsGlobalPlayer && lsGlobalPlayer.setStemPlaybackActive) {
                lsGlobalPlayer.setStemPlaybackActive(active);
            }
        }

        function pauseMainAudioForStems() {
            if (typeof lsGlobalPlayer !== "undefined" && lsGlobalPlayer && lsGlobalPlayer.pauseMainForStems) {
                lsGlobalPlayer.pauseMainForStems();
            }
        }

        function finishStemMix(stemBlock, generation) {
            const engine = getStemEngine(stemBlock);
            if (!engine || generation !== engine.generation) { return; }
            disconnectStemNodes(engine);
            engine.playing = false;
            engine.offset = engine.duration;
            stopStemAnimation(engine);
            updateStemEngineProgress(stemBlock, engine.offset);
            resetStemPlayButtons(stemBlock);
            clearStemControlActive(stemBlock);
            markStemPlaybackSource(true);
        }

        async function startStemMixAt(stemBlock, rows, offset=0) {
            const selectedRows = (rows || getCheckedStemRows(stemBlock)).filter(Boolean);
            if (!selectedRows.length) { throw new Error("Select at least one Stem first."); }
            cancelSequential(stemBlock);
            const readyRows = await ensureStemBuffers(stemBlock, selectedRows);
            const engine = getStemEngine(stemBlock);
            const context = getStemContext(engine);
            await context.resume();
            pauseMainAudioForStems();

            disconnectStemNodes(engine);
            engine.generation += 1;
            const generation = engine.generation;
            engine.mode = "mix";
            engine.offset = Math.max(0, Number(offset || 0));
            engine.duration = Math.max(...readyRows.map((row) => Number(row._lsStemBuffer.duration || 0)), 0);
            engine.startedAt = context.currentTime + 0.08;
            engine.playing = true;

            readyRows.forEach((row) => {
                const buffer = row._lsStemBuffer;
                if (!buffer || engine.offset >= buffer.duration) { return; }
                const source = context.createBufferSource();
                const gain = context.createGain();
                source.buffer = buffer;
                source.connect(gain).connect(context.destination);
                engine.activeNodes.set(row, { source, gain });
                source.onended = () => {
                    if (generation !== engine.generation) { return; }
                    engine.activeNodes.delete(row);
                    row.classList.remove("active-stem");
                    if (engine.playing && engine.activeNodes.size === 0) {
                        finishStemMix(stemBlock, generation);
                    }
                };
                row.classList.add("active-stem");
                source.start(engine.startedAt, Math.max(0, Math.min(engine.offset, buffer.duration - 0.01)));
            });

            if (!engine.activeNodes.size) {
                engine.playing = false;
                throw new Error("Selected Stems have no playable material at this position.");
            }
            applyStemMixState(stemBlock);
            currentStemBlock = stemBlock;
            lastActiveAudio = null;
            markStemPlaybackSource(true);
            setStemControlActive(stemBlock, ".stem-play-all");
            startStemAnimation(stemBlock);
            return true;
        }

        async function playStemMix(stemBlock, restart=true) {
            const engine = getStemEngine(stemBlock);
            const offset = restart ? 0 : Math.max(0, Number(engine && engine.offset || 0));
            return await startStemMixAt(stemBlock, getCheckedStemRows(stemBlock), offset);
        }

        function pauseStemMix(stemBlock, options={}) {
            const engine = getStemEngine(stemBlock);
            if (!engine || !engine.playing) { return false; }
            const position = getStemPlaybackPosition(engine);
            engine.generation += 1;
            disconnectStemNodes(engine);
            engine.playing = false;
            engine.offset = Math.min(position, engine.duration || position);
            stopStemAnimation(engine);
            updateStemEngineProgress(stemBlock, engine.offset);
            resetStemPlayButtons(stemBlock);
            setStemControlActive(stemBlock, ".stem-pause-all", true);
            if (options.updateSource !== false) { markStemPlaybackSource(true); }
            return true;
        }

        function stopStemMix(stemBlock, options={}) {
            const engine = getStemEngine(stemBlock);
            if (!engine) { return; }
            engine.generation += 1;
            disconnectStemNodes(engine);
            engine.playing = false;
            engine.offset = 0;
            engine.duration = 0;
            stopStemAnimation(engine);
            updateStemEngineProgress(stemBlock, 0);
            resetStemPlayButtons(stemBlock);
            if (options.updateSource !== false) { markStemPlaybackSource(true); }
        }

        async function rewindStemMix(stemBlock) {
            const engine = getStemEngine(stemBlock);
            const wasPlaying = Boolean(engine && engine.playing);
            if (wasPlaying) {
                await startStemMixAt(stemBlock, getCheckedStemRows(stemBlock), 0);
            } else {
                if (engine) { engine.offset = 0; }
                updateStemEngineProgress(stemBlock, 0);
            }
            setStemControlActive(stemBlock, ".stem-rewind-all", true);
        }

        async function seekStemMix(stemBlock, position) {
            const engine = getStemEngine(stemBlock);
            if (!engine) { return false; }
            const target = Math.max(0, Math.min(Number(position || 0), Number(engine.duration || position || 0)));
            if (engine.playing) {
                await startStemMixAt(stemBlock, getCheckedStemRows(stemBlock), target);
            } else {
                engine.offset = target;
                updateStemEngineProgress(stemBlock, target);
                markStemPlaybackSource(true);
            }
            return true;
        }

        async function restartPlayingStemSelection(stemBlock) {
            const engine = getStemEngine(stemBlock);
            if (!engine || !engine.playing || engine.mode !== "mix") { return; }
            const position = getStemPlaybackPosition(engine);
            const rows = getCheckedStemRows(stemBlock);
            if (!rows.length) {
                stopStemMix(stemBlock);
                return;
            }
            await startStemMixAt(stemBlock, rows, position);
        }

        function setAllStemChecks(stemBlock, checked) {
            if (!stemBlock) { return; }
            stemBlock.querySelectorAll(".stem-check").forEach((check) => {
                check.checked = checked;
                const row = check.closest(".stem-row");
                const toggle = row ? row.querySelector(".stem-include-toggle") : null;
                if (toggle) {
                    toggle.classList.toggle("active", checked);
                    toggle.setAttribute("aria-pressed", checked ? "true" : "false");
                    toggle.title = checked
                        ? "Included in Play selected and To Audacity"
                        : "Excluded from Play selected and To Audacity";
                }
                syncStemSelectionVisual(row, checked);
            });
            updateStemMasterCheck(stemBlock);
            applyStemMixState(stemBlock);
            restartPlayingStemSelection(stemBlock).catch(() => {});
        }

        async function toggleStemSpacePause(stemBlock, sharedPosition=null) {
            if (!stemBlock) { return false; }
            const engine = getStemEngine(stemBlock);
            if (engine && engine.playing) {
                pauseStemMix(stemBlock);
                return true;
            }

            const sequentialPlaying = getStemAudios(stemBlock).filter((audio) => !audio.paused && !audio.ended);
            if (sequentialPlaying.length) {
                sequentialPlaying.forEach((audio) => audio.pause());
                markStemPlaybackSource(false);
                setStemControlActive(stemBlock, ".stem-pause-all", true);
                return true;
            }

            try {
                const requestedPosition = Number(sharedPosition);
                const hasSharedPosition = Number.isFinite(requestedPosition) && requestedPosition >= 0;
                if (hasSharedPosition) {
                    await startStemMixAt(
                        stemBlock,
                        getCheckedStemRows(stemBlock),
                        requestedPosition
                    );
                    return true;
                }
                const canResume = Boolean(
                    engine &&
                    engine.offset > 0 &&
                    engine.duration > 0 &&
                    engine.offset < engine.duration - 0.05
                );
                await playStemMix(stemBlock, !canResume);
                return true;
            } catch (error) {
                alert(String(error && error.message || error || "Could not play selected Stems."));
                return false;
            }
        }

        function pauseStemBlock(stemBlock, options={}) {
            if (!stemBlock) { return; }
            cancelSequential(stemBlock);
            pauseStemMix(stemBlock, options);
            getStemAudios(stemBlock).forEach((audio) => audio.pause());
            resetStemPlayButtons(stemBlock);
        }

        function stopStemBlock(stemBlock, options={}) {
            if (!stemBlock) { return; }
            cancelSequential(stemBlock);
            stopStemMix(stemBlock, options);
            getStemAudios(stemBlock).forEach((audio) => {
                audio.pause();
                try { audio.currentTime = 0; } catch (error) {}
                updateStemWaveProgress(audio);
            });
            resetStemPlayButtons(stemBlock);
        }

