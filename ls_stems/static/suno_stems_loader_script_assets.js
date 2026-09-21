        async function loadStemsForBlock(stemBlock, trackId) {
            if (!stemBlock) { return; }
            const cleanTrackId = String(trackId || "").trim();
            if (
                stemBlock.dataset.loaded === "true" &&
                stemBlock.dataset.trackId === cleanTrackId
            ) {
                updateStemMasterCheck(stemBlock);
                applyStemMixState(stemBlock);
                return;
            }

            stopStemBlock(stemBlock, { updateSource: false });
            stemBlock.dataset.loaded = "false";
            stemBlock.dataset.trackId = cleanTrackId;
            const list = stemBlock.querySelector(".stem-list");
            const status = stemBlock.querySelector(".stem-status");
            list.innerHTML = "Loading stems...";
            status.innerText = "";

            const response = await fetch("/stems-json?track_id=" + encodeURIComponent(cleanTrackId));
            if (!response.ok) {
                list.innerHTML = "Could not load stems.";
                return;
            }

            const data = await response.json();
            const stems = data.stems || [];
            if (!stems.length) {
                list.innerHTML = "No local stems found. Ja šim ierakstam Stems agrāk bija, jāpārlasa/piesaista local_audio_files.";
                status.innerText = "0 stems";
                return;
            }

            list.innerHTML = "";
            list.style.setProperty("--stem-count", String(Math.max(1, stems.length)));
            stemBlock.style.setProperty("--stem-count", String(Math.max(1, stems.length)));
            const stemPalette = [
                ["#6957F5", "#F27C00"], ["#E5CC00", "#E8C800"],
                ["#E5CC00", "#E8C800"], ["#FF6A00", "#E8C800"],
                ["#EC0A78", "#00B95F"], ["#6957F5", "#E8C800"],
                ["#00B95F", "#FF6A00"], ["#EC0A78", "#E8C800"],
                ["#00B95F", "#E8C800"], ["#E5CC00", "#EC0A78"],
                ["#2588F5", "#FF6A00"], ["#2588F5", "#00B95F"],
                ["#6957F5", "#FF6A00"]
            ];
            stems.forEach((stem, stemIndex) => {
                const row = document.createElement("div");
                const palette = stemPalette[stemIndex % stemPalette.length];
                row.className = "stem-row stem-included";
                row.dataset.muted = "false";
                row.dataset.solo = "false";
                row.dataset.stemUrl = String(stem.url || "");
                row.style.setProperty("--stem-accent", palette[0]);
                row.style.setProperty("--stem-clip", palette[1]);
                row.innerHTML = `
                    <div class="stem-row-controls">
                        <span class="stem-index">${stemIndex + 2}</span>
                        <button type="button" class="stem-mute" aria-pressed="false" title="Mute / unmute this Stem">
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 10h4l5-4v12l-5-4H4z"></path><path d="M16 9c2 2 2 4 0 6"></path></svg>
                        </button>
                        <button type="button" class="stem-solo" aria-pressed="false" title="Solo this Stem">S</button>
                        <button type="button" class="stem-include-toggle active" aria-pressed="true" title="Included in Play selected and To Audacity">
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 14.5 14.5 9.5"></path><path d="M7.2 17.1 5.9 18.4a3.5 3.5 0 0 1-5-5l3-3a3.5 3.5 0 0 1 5 0"></path><path d="m16.8 6.9 1.3-1.3a3.5 3.5 0 0 1 5 5l-3 3a3.5 3.5 0 0 1-5 0"></path></svg>
                        </button>
                        <div class="stem-label"></div>
                        <button type="button" class="stem-menu-button" aria-expanded="false" title="Stem level and row options">⋮</button>
                        <label class="stem-include" title="Include this Stem">
                            <input type="checkbox" class="stem-check" checked>
                            <span>Include</span>
                        </label>
                        <div class="stem-row-menu" hidden>
                            <label class="stem-level" title="Stem playback level — default 80%">
                                <span>Level</span>
                                <input type="range" class="stem-level-range" min="0" max="100" step="1" value="80">
                                <output class="stem-level-value">80%</output>
                            </label>
                        </div>
                    </div>
                    <div class="stem-wave" data-clip-label="" title="Stem waveform preview. Silent gaps show why a Stem may not be heard.">
                        <div class="stem-wave-loading">waveform...</div>
                        <img alt="stem waveform">
                        <div class="stem-wave-progress"></div>
                    </div>
                    <audio class="stem-audio" preload="metadata"></audio>
                `;
                const label = row.querySelector(".stem-label");
                label.innerText = stem.label || "Stem";
                label.title = stem.label || "Stem";
                const stemWave = row.querySelector(".stem-wave");
                if (stemWave) { stemWave.dataset.clipLabel = stem.label || "Stem"; }

                const check = row.querySelector(".stem-check");
                const includeToggle = row.querySelector(".stem-include-toggle");
                const menuButton = row.querySelector(".stem-menu-button");
                const rowMenu = row.querySelector(".stem-row-menu");
                if (includeToggle) {
                    includeToggle.addEventListener("click", () => {
                        check.checked = !check.checked;
                        check.dispatchEvent(new Event("change", { bubbles: true }));
                    });
                }
                if (menuButton && rowMenu) {
                    menuButton.addEventListener("click", (event) => {
                        event.stopPropagation();
                        const willOpen = rowMenu.hidden;
                        list.querySelectorAll(".stem-row-menu").forEach((item) => { item.hidden = true; });
                        list.querySelectorAll(".stem-menu-button").forEach((item) => item.setAttribute("aria-expanded", "false"));
                        rowMenu.hidden = !willOpen;
                        menuButton.setAttribute("aria-expanded", willOpen ? "true" : "false");
                    });
                }
                check.dataset.path = String(stem.path || "");
                const audio = row.querySelector("audio.stem-audio");
                audio.dataset.src = stem.url;

                const waveBox = row.querySelector(".stem-wave");
                const waveImg = waveBox ? waveBox.querySelector("img") : null;
                const waveLoading = waveBox ? waveBox.querySelector(".stem-wave-loading") : null;
                if (waveImg && stem.waveform_url) {
                    waveImg.onload = () => {
                        if (waveLoading) { waveLoading.style.display = "none"; }
                        waveImg.style.display = "block";
                    };
                    waveImg.onerror = () => {
                        if (waveLoading) { waveLoading.innerText = "no graph"; }
                        waveImg.style.display = "none";
                    };
                    waveImg.src = stem.waveform_url;
                }

                check.addEventListener("change", async () => {
                    if (includeToggle) {
                        includeToggle.classList.toggle("active", check.checked);
                        includeToggle.setAttribute("aria-pressed", check.checked ? "true" : "false");
                        includeToggle.title = check.checked
                            ? "Included in Play selected and To Audacity"
                            : "Excluded from Play selected and To Audacity";
                    }
                    syncStemSelectionVisual(row, check.checked);
                    if (!check.checked) {
                        audio.pause();
                        try { audio.currentTime = 0; } catch (error) {}
                        row.classList.remove("active-stem");
                    }
                    updateStemMasterCheck(stemBlock);
                    applyStemMixState(stemBlock);
                    try { await restartPlayingStemSelection(stemBlock); } catch (error) {}
                });

                row.querySelector(".stem-mute").addEventListener("click", () => {
                    row.dataset.muted = row.dataset.muted === "true" ? "false" : "true";
                    applyStemMixState(stemBlock);
                });

                row.querySelector(".stem-solo").addEventListener("click", () => {
                    row.dataset.solo = row.dataset.solo === "true" ? "false" : "true";
                    applyStemMixState(stemBlock);
                });

                const levelRange = row.querySelector(".stem-level-range");
                const levelValue = row.querySelector(".stem-level-value");
                levelRange.addEventListener("input", () => {
                    levelValue.value = levelRange.value + "%";
                    levelValue.innerText = levelRange.value + "%";
                    applyStemMixState(stemBlock);
                });

                audio.addEventListener("play", () => {
                    ensureStemSrc(audio);
                    applyStemMixState(stemBlock);
                    lastActiveAudio = audio;
                    currentStemBlock = stemBlock;
                    row.classList.add("active-stem");
                    updateStemWaveProgress(audio);
                });
                audio.addEventListener("loadedmetadata", () => updateStemWaveProgress(audio));
                audio.addEventListener("timeupdate", () => updateStemWaveProgress(audio));
                audio.addEventListener("seeking", () => updateStemWaveProgress(audio));
                audio.addEventListener("pause", () => {
                    updateStemWaveProgress(audio);
                    row.classList.remove("active-stem");
                });
                audio.addEventListener("ended", () => {
                    row.classList.remove("active-stem");
                    updateStemWaveProgress(audio);
                });
                list.appendChild(row);
            });
            if (!stemBlock.dataset.rowMenuBound) {
                stemBlock.dataset.rowMenuBound = "true";
                document.addEventListener("click", (event) => {
                    if (stemBlock.contains(event.target) && event.target.closest(".stem-row-menu")) { return; }
                    stemBlock.querySelectorAll(".stem-row-menu").forEach((item) => { item.hidden = true; });
                    stemBlock.querySelectorAll(".stem-menu-button").forEach((item) => item.setAttribute("aria-expanded", "false"));
                });
            }
            stemBlock.dataset.loaded = "true";
            updateStemMasterCheck(stemBlock);
            applyStemMixState(stemBlock);

            // Prepare decoded buffers in the background. Playback waits for every
            // selected Stem, so missing/late tracks are never silently omitted.
            ensureStemBuffers(stemBlock, getCheckedStemRows(stemBlock)).catch(() => {
                updateStemMasterCheck(stemBlock);
            });
        }

