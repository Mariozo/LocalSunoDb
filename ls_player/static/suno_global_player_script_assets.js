        function createGlobalPlayerController() {
            const root = document.getElementById("ls-global-player");
            if (!root) { return null; }

            const audio = root.querySelector("audio.ls-global-player-audio");
            const playToggle = document.getElementById("ls-global-player-play");
            const restartButton = document.getElementById("ls-global-player-restart");
            const previousButton = document.getElementById("ls-global-player-previous");
            const nextButton = document.getElementById("ls-global-player-next");
            const progress = document.getElementById("ls-global-player-progress");
            const loopButton = document.getElementById("ls-global-player-loop");
            const drawerLoopButton = document.getElementById("ls-global-player-loop-drawer");
            const expandButton = document.getElementById("ls-global-player-expand");
            const closeButton = document.getElementById("ls-global-player-close");
            const compareButton = document.getElementById("ls-global-player-compare");
            const stemsButton = document.getElementById("ls-global-player-stems");
            const editButton = document.getElementById("ls-global-player-edit");
            const audioOutputButton = document.getElementById("ls-audio-output-toggle");
            const volumeControl = document.getElementById("ls-player-volume-control");
            const volumeSlider = document.getElementById("ls-global-player-volume");
            const volumeMuteButton = document.getElementById("ls-player-volume-mute");
            const titleNode = document.getElementById("ls-global-player-title");
            const stemsMainTitle = document.getElementById("ls-stems-main-title");
            const mainWaveformBox = root.querySelector(".ls-global-player-wave-panel .waveform-box");
            const sidebarStemsButton = document.getElementById("ls-sidebar-stems-btn");
            const sidebarSunoLibraryLink = document.getElementById("ls-sidebar-suno-library-btn");
            const sourceLabel = document.getElementById("ls-global-player-source-label");
            const coverButton = document.getElementById("ls-global-player-cover-open");
            const cover = document.getElementById("ls-global-player-cover");
            const coverPlaceholder = document.getElementById("ls-global-player-cover-placeholder");
            const drawer = document.getElementById("ls-global-player-drawer");
            const wavePanel = document.getElementById("ls-global-player-wave-panel");
            const stemPanel = document.getElementById("ls-global-player-stem-panel");
            const hostedRoot = document.getElementById("ls-suno-hosted-player");
            const hostedPlayer = typeof createSunoHostedPlayerController === "function"
                ? createSunoHostedPlayerController(root)
                : null;
            const transportButtons = Array.from(root.querySelectorAll(
                ".back-btn, .forward-btn, .ab-set-a-btn, .ab-set-b-btn, .ab-clear-btn"
            ));

            let current = null;
            let currentTrackRow = null;
            let currentFragmentRow = null;
            let currentPlayButton = null;
            let currentSource = "suno";
            let stemPlaybackActive = false;
            const trackTable = document.getElementById("tracks-table");
            const trackListViewport = trackTable
                ? (trackTable.closest(".table-wrap") || trackTable)
                : null;
            let playerAlignmentFrame = 0;

            function syncTrackListBoundary() {
                if (!trackListViewport) { return; }
                const listRect = trackListViewport.getBoundingClientRect();
                const playerRect = root.getBoundingClientRect();
                const availableHeight = Math.max(
                    120,
                    Math.floor(playerRect.top - listRect.top)
                );
                const nextHeight = availableHeight + "px";
                if (trackListViewport.style.height !== nextHeight) {
                    trackListViewport.style.height = nextHeight;
                    trackListViewport.style.maxHeight = nextHeight;
                }
                trackListViewport.style.overflowY = "auto";
            }

            function alignPlayerToTrackList() {
                playerAlignmentFrame = 0;
                if (!trackListViewport) { return; }
                const rect = trackListViewport.getBoundingClientRect();
                const viewportWidth = Math.max(
                    0,
                    window.innerWidth || document.documentElement.clientWidth || 0
                );
                if (!rect.width || !viewportWidth) { return; }
                const left = Math.max(0, Math.min(viewportWidth, Math.round(rect.left)));
                const rightEdge = Math.max(
                    left,
                    Math.min(viewportWidth, Math.round(rect.right))
                );
                root.style.left = left + "px";
                root.style.right = Math.max(0, viewportWidth - rightEdge) + "px";
                syncTrackListBoundary();
            }

            function schedulePlayerAlignment() {
                if (playerAlignmentFrame) { return; }
                playerAlignmentFrame = window.requestAnimationFrame(alignPlayerToTrackList);
            }

            function syncPlayerReservedHeight() {
                const height = Math.max(0, Math.ceil(root.getBoundingClientRect().height || 0));
                if (height) {
                    document.documentElement.style.setProperty(
                        "--ls-global-player-live-height",
                        height + "px"
                    );
                }
                syncTrackListBoundary();
            }

            if (typeof ResizeObserver === "function") {
                root.__lsPlayerLayoutObserver = new ResizeObserver(() => {
                    schedulePlayerAlignment();
                    syncPlayerReservedHeight();
                });
                if (trackListViewport) {
                    root.__lsPlayerLayoutObserver.observe(trackListViewport);
                }
                if (trackTable && trackTable !== trackListViewport) {
                    root.__lsPlayerLayoutObserver.observe(trackTable);
                }
                root.__lsPlayerLayoutObserver.observe(root);
            }
            if (typeof MutationObserver === "function") {
                root.__lsPlayerPanelObserver = new MutationObserver(() => {
                    schedulePlayerAlignment();
                    syncPlayerReservedHeight();
                });
                root.__lsPlayerPanelObserver.observe(document.documentElement, {
                    attributes: true,
                    attributeFilter: ["class", "style"],
                });
                if (document.body) {
                    root.__lsPlayerPanelObserver.observe(document.body, {
                        attributes: true,
                        attributeFilter: ["class", "style"],
                    });
                }
            }
            window.addEventListener("resize", () => {
                schedulePlayerAlignment();
                syncPlayerReservedHeight();
            });
            schedulePlayerAlignment();
            syncPlayerReservedHeight();

            function applyAudioOutputState(payload) {
                if (!audioOutputButton) { return; }
                const state = payload && typeof payload === "object" ? payload : {};
                const mode = String(state.mode || "unknown");
                const currentName = String(state.current_name || "Nav noteikts");
                const targetName = String(state.target_name || "");
                const canToggle = Boolean(state.ok && state.can_toggle);
                audioOutputButton.dataset.canToggle = canToggle ? "true" : "false";
                audioOutputButton.classList.toggle("is-speakers", mode === "speakers");
                audioOutputButton.classList.toggle("is-headphones", mode === "headphones");
                audioOutputButton.classList.toggle(
                    "is-unknown", mode !== "speakers" && mode !== "headphones"
                );
                audioOutputButton.disabled = false;
                audioOutputButton.setAttribute(
                    "aria-pressed", mode === "headphones" ? "true" : "false"
                );
                if (canToggle) {
                    audioOutputButton.title =
                        "Pašlaik: " + currentName + ". Klikšķis pārslēgs uz: " + targetName + ".";
                    audioOutputButton.setAttribute(
                        "aria-label",
                        "Audio izeja: " + currentName + ". Pārslēgt uz " + targetName
                    );
                } else {
                    const errorText = String(
                        state.error || "Audio izeju pārslēgšana nav pieejama."
                    );
                    audioOutputButton.title = errorText;
                    audioOutputButton.setAttribute("aria-label", errorText);
                }
            }

            async function refreshAudioOutputState(force = false) {
                if (!audioOutputButton) { return; }
                try {
                    const response = await fetch(
                        "/audio-output-state" + (force ? "?refresh=1" : ""),
                        { cache: "no-store" }
                    );
                    applyAudioOutputState(await response.json());
                } catch (error) {
                    applyAudioOutputState({
                        ok: false,
                        can_toggle: false,
                        mode: "unknown",
                        error: "Windows audio izejas stāvokli neizdevās nolasīt."
                    });
                }
            }

            async function toggleAudioOutput() {
                if (!audioOutputButton || audioOutputButton.classList.contains("is-switching")) {
                    return;
                }
                audioOutputButton.classList.add("is-switching");
                audioOutputButton.disabled = true;
                try {
                    const wasPlaying = Boolean(current && !audio.paused && !audio.ended);
                    const response = await fetch("/toggle-audio-output", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: ""
                    });
                    const payload = await response.json();
                    applyAudioOutputState(payload);
                    if (!payload.ok) {
                        window.alert(payload.error || "Audio izeju neizdevās pārslēgt.");
                        return;
                    }

                    // Chrome may keep an already-open audio stream on the old
                    // Windows endpoint. Recreate only the main LS audio stream,
                    // preserving source, time and Play/Pause state.
                    if (current && !stemPlaybackActive && currentSource === "local") {
                        loadSource(currentSource, {
                            autoplay: wasPlaying,
                            preserveTime: true,
                        });
                    }
                } catch (error) {
                    window.alert("Audio izeju neizdevās pārslēgt.");
                    await refreshAudioOutputState(true);
                } finally {
                    audioOutputButton.classList.remove("is-switching");
                    audioOutputButton.disabled = false;
                }
            }

            if (audioOutputButton) {
                audioOutputButton.addEventListener("click", () => {
                    toggleAudioOutput();
                });
                refreshAudioOutputState(false);
                window.addEventListener("focus", () => refreshAudioOutputState(false));
                document.addEventListener(
                    "ls-audio-output-settings-saved",
                    () => refreshAudioOutputState(true)
                );
            }

            function focusMainPlayControl() {
                if (!playToggle || playToggle.disabled) { return; }
                window.requestAnimationFrame(() => {
                    try {
                        playToggle.focus({ preventScroll: true });
                    } catch (error) {
                        playToggle.focus();
                    }
                });
            }

            root.addEventListener("click", (event) => {
                const clickedControl = event.target instanceof Element
                    ? event.target.closest("button, input[type='range'], [role='button']")
                    : null;
                if (clickedControl) {
                    focusMainPlayControl();
                }
            });

            function visibleTrackRows() {
                return Array.from(table.querySelectorAll("tr.track-row")).filter(
                    (row) => !row.classList.contains("row-hidden")
                );
            }

            function compactNavigationRows() {
                return visibleTrackRows();
            }

            function compactNavigationAnchorRow() {
                return table.querySelector("tr.track-row.selected-track-current") || currentTrackRow;
            }

            function syncCompactTransportState() {
                const enabled = Boolean(current && (current.localAudio || isValidSunoTrackId(current.trackId)));
                const rows = compactNavigationRows();
                const anchorRow = compactNavigationAnchorRow();
                const index = anchorRow ? rows.indexOf(anchorRow) : -1;
                if (restartButton) { restartButton.disabled = !enabled; }
                if (previousButton) {
                    previousButton.disabled = !enabled || index <= 0;
                    previousButton.title = "Iepriekšējā dziesma";
                }
                if (nextButton) {
                    nextButton.disabled = !enabled || index < 0 || index >= rows.length - 1;
                    nextButton.title = "Nākamā dziesma";
                }
            }

            function setControlsEnabled(enabled) {
                const hosted = root.classList.contains("suno-hosted-mode");
                playToggle.disabled = !enabled || hosted;
                progress.disabled = !enabled || hosted;
                loopButton.disabled = !enabled || hosted;
                if (drawerLoopButton) { drawerLoopButton.disabled = !enabled || hosted; }
                expandButton.disabled = !enabled || hosted;
                if (closeButton) { closeButton.disabled = !enabled; }
                editButton.disabled = !enabled;
                transportButtons.forEach((button) => { button.disabled = !enabled || hosted; });
                syncCompactTransportState();
            }

            function setExpanded(expanded) {
                const shouldExpand = Boolean(expanded && current);
                const stemsExpanded = Boolean(shouldExpand && root.classList.contains("stems-mode"));
                root.classList.toggle("expanded", shouldExpand);
                document.body.classList.toggle("ls-global-player-expanded", shouldExpand);
                document.body.classList.toggle("ls-global-player-stems-expanded", stemsExpanded);
                drawer.setAttribute("aria-hidden", shouldExpand ? "false" : "true");
                expandButton.setAttribute("aria-expanded", shouldExpand ? "true" : "false");
                expandButton.innerText = shouldExpand ? "▼" : "▲";
                expandButton.title = shouldExpand ? "Collapse player" : "Expand player";
            }

            function setStemMode(enabled) {
                const useStems = Boolean(enabled && current && current.hasStems && stemPanel);
                root.classList.toggle("stems-mode", useStems);
                if (stemPanel) { stemPanel.classList.toggle("hidden", !useStems); }
                if (wavePanel) { wavePanel.classList.remove("hidden"); }
                document.body.classList.toggle(
                    "ls-global-player-stems-expanded",
                    useStems && root.classList.contains("expanded")
                );
                stemsButton.classList.toggle("active", useStems);
                stemsButton.title = useStems ? "Hide Stems" : "Show Stems";
                if (sidebarStemsButton) {
                    sidebarStemsButton.classList.toggle("active", useStems);
                    sidebarStemsButton.setAttribute("aria-pressed", useStems ? "true" : "false");
                    sidebarStemsButton.title = useStems
                        ? "Aizvērt izvēlētās dziesmas Stems paneli"
                        : "Atvērt izvēlētās dziesmas Stems paneli";
                }
                if (currentTrackRow) {
                    const rowStemsButton = currentTrackRow.querySelector(".stems-btn");
                    if (rowStemsButton) {
                        rowStemsButton.classList.toggle("active", useStems);
                    }
                }
            }

            function setStemPlaybackActive(active) {
                stemPlaybackActive = Boolean(active && current);
                // Stems have their own controls and waveform progress. The bottom
                // player always remains the full-song Suno/Local transport.
                sourceLabel.innerText = current
                    ? (currentSource === "local" ? "Local WAV" : "Suno Web")
                    : "Player inactive";
                syncPlayState();
                syncCompactTransportState();
            }

            function pauseMainForStems() {
                if (!audio.paused) { audio.pause(); }
                syncPlayState();
            }

            function pauseStemsForMainSource() {
                if (stemPanel && typeof pauseStemBlock === "function") {
                    pauseStemBlock(stemPanel, { updateSource: false });
                }
                setStemPlaybackActive(false);
            }

            function resetGlobalStemPanel() {
                if (!stemPanel) { return; }
                if (typeof stopStemBlock === "function") {
                    stopStemBlock(stemPanel, { updateSource: false });
                } else if (typeof pauseStemBlock === "function") {
                    pauseStemBlock(stemPanel, { updateSource: false });
                }
                stemPanel.dataset.loaded = "false";
                stemPanel.dataset.trackId = "";
                stemPanel.dataset.seqActive = "false";
                stemPanel.style.setProperty("--stem-count", "1");
                const list = stemPanel.querySelector(".stem-list");
                const status = stemPanel.querySelector(".stem-status");
                if (list) { list.innerHTML = "Select a track with Stems."; }
                if (status) { status.innerText = ""; }
                setStemPlaybackActive(false);
                setStemMode(false);
                if (currentStemBlock === stemPanel) { currentStemBlock = null; }
            }

            function updateCover(url, fullUrl = "") {
                const cleanUrl = String(url || "").trim();
                const cleanFullUrl = String(fullUrl || cleanUrl || "").trim();
                if (coverButton) {
                    coverButton.dataset.fullCover = cleanFullUrl;
                    coverButton.disabled = !cleanFullUrl;
                    coverButton.title = cleanFullUrl
                        ? "Atvērt pilna izmēra vāciņu jaunā cilnē"
                        : "Vāciņa attēls nav pieejams";
                }
                if (!cleanUrl) {
                    cover.removeAttribute("src");
                    cover.style.display = "none";
                    coverPlaceholder.style.display = "inline";
                    return;
                }
                let fallbackTried = false;
                cover.onload = () => {
                    cover.style.display = "block";
                    coverPlaceholder.style.display = "none";
                };
                cover.onerror = () => {
                    if (!fallbackTried && cleanFullUrl && cleanFullUrl !== cleanUrl) {
                        fallbackTried = true;
                        cover.src = cleanFullUrl;
                        return;
                    }
                    cover.removeAttribute("src");
                    cover.style.display = "none";
                    coverPlaceholder.style.display = "inline";
                };
                cover.src = cleanUrl;
            }

            function openCurrentFullCover() {
                if (!coverButton || coverButton.disabled) { return; }
                const url = String(coverButton.dataset.fullCover || "").trim();
                if (!url) { return; }
                const link = document.createElement("a");
                link.href = url;
                link.target = "_blank";
                link.rel = "noopener";
                link.style.display = "none";
                document.body.appendChild(link);
                link.click();
                link.remove();
            }

            if (coverButton) {
                coverButton.addEventListener("click", openCurrentFullCover);
            }

            let lastAudibleVolume = 1;

            function syncPlayerVolumeIcon(value) {
                if (!volumeMuteButton) { return; }
                const muted = Number(value || 0) <= 0.0001;
                volumeMuteButton.classList.toggle("is-muted", muted);
                volumeMuteButton.title = muted
                    ? "Skaņa izslēgta — klikšķis atjauno iepriekšējo skaļumu"
                    : "Izslēgt LS atskaņotāja skaņu";
                volumeMuteButton.setAttribute(
                    "aria-label",
                    muted ? "Skaņa izslēgta" : "Izslēgt LS atskaņotāja skaņu"
                );
                volumeMuteButton.setAttribute("aria-pressed", muted ? "true" : "false");
            }

            function setPlayerVolume(value) {
                const next = Math.max(0, Math.min(1, Number(value)));
                if (!Number.isFinite(next)) { return; }
                if (next > 0.0001) { lastAudibleVolume = next; }
                audio.muted = false;
                audio.volume = next;
                if (volumeSlider) {
                    volumeSlider.value = String(next);
                    volumeSlider.title = "LS atskaņotāja skaļums: " + Math.round(next * 100) + "%";
                }
                syncPlayerVolumeIcon(next);
            }

            if (volumeSlider) {
                setPlayerVolume(volumeSlider.value || 1);
                volumeSlider.addEventListener("input", () => {
                    setPlayerVolume(volumeSlider.value);
                });
            }

            if (volumeMuteButton) {
                volumeMuteButton.addEventListener("click", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    setPlayerVolume(audio.volume > 0.0001 ? 0 : Math.max(0.05, lastAudibleVolume));
                });
            }

            if (volumeControl) {
                volumeControl.addEventListener("wheel", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const direction = event.deltaY < 0 ? 1 : -1;
                    setPlayerVolume(audio.volume + direction * 0.05);
                }, { passive: false });
            }

            function syncVisibleStemCursors(position) {
                if (
                    !stemPanel ||
                    !isStemsViewOpen() ||
                    typeof getStemRows !== "function" ||
                    typeof updateStemWaveProgressAt !== "function"
                ) {
                    return;
                }
                getStemRows(stemPanel).forEach((row) => {
                    updateStemWaveProgressAt(row, Number(position || 0));
                });
            }

            function syncCompactProgress() {
                const duration = Number(audio.duration || 0);
                const currentTime = Number(audio.currentTime || 0);
                progress.value = duration > 0 ? String((currentTime / duration) * 100) : "0";
                if (!stemPlaybackActive) {
                    syncVisibleStemCursors(currentTime);
                }
            }

            function syncStemTransport(position, duration) {
                if (!current || !stemPlaybackActive) { return; }
                const sharedPosition = Math.max(0, Number(position || 0));
                const mainDuration = Number(audio.duration || 0);
                if (mainDuration > 0) {
                    const clamped = Math.min(sharedPosition, Math.max(0, mainDuration - 0.01));
                    if (Math.abs(Number(audio.currentTime || 0) - clamped) > 0.025) {
                        try { audio.currentTime = clamped; } catch (error) {}
                    }
                }
                updateProgress(root);
                syncCompactProgress();
                syncPlayState();
            }

            function leaveHostedMode() {
                if (hostedPlayer) { hostedPlayer.unmount(); }
                if (hostedRoot) { hostedRoot.hidden = true; }
                root.classList.remove("suno-hosted-mode");
            }

            function enterHostedMode() {
                if (!current || !hostedPlayer || !hostedRoot) { return false; }
                if (!audio.paused) { audio.pause(); }
                audio.removeAttribute("src");
                audio.load();
                pauseStemsForMainSource();
                setStemMode(false);
                setExpanded(false);
                root.classList.add("suno-hosted-mode");
                hostedRoot.hidden = false;
                const mounted = hostedPlayer.mount(current.trackId);
                sourceLabel.innerText = mounted ? "Suno hosted" : "Suno nav pieejams";
                setControlsEnabled(true);
                syncPlayState();
                syncCompactTransportState();
                schedulePlayerAlignment();
                syncPlayerReservedHeight();
                return mounted;
            }

            function syncPlayState() {
                if (root.classList.contains("suno-hosted-mode")) {
                    playToggle.innerText = "▶";
                    playToggle.title = "Suno atskaņotājs";
                    playToggle.disabled = true;
                    if (currentPlayButton) {
                        currentPlayButton.classList.remove("active");
                        currentPlayButton.innerText = "▶";
                        currentPlayButton.title = "Suno hosted player";
                    }
                    return;
                }
                const playing = Boolean(current && !audio.paused && !audio.ended);
                playToggle.innerText = playing ? "❚❚" : "▶";
                playToggle.title = playing ? "Pause" : "Play";
                if (currentPlayButton) {
                    currentPlayButton.innerText = playing ? "❚❚" : "▶";
                    currentPlayButton.classList.toggle("active", playing);
                    currentPlayButton.setAttribute(
                        "aria-label",
                        playing ? "Pause " + (current ? current.title : "track") : "Play " + (current ? current.title : "track")
                    );
                    currentPlayButton.title = playing ? "Pause" : "Play";
                }
            }

            function syncSourceLabel() {
                if (!stemPlaybackActive) {
                    sourceLabel.innerText = current
                        ? (currentSource === "local" ? "Local WAV" : "Suno Web")
                        : "Player inactive";
                }
            }

            function resetRowState() {
                if (currentTrackRow) {
                    currentTrackRow.classList.remove("player-open");
                    const rowStemsButton = currentTrackRow.querySelector(".stems-btn");
                    if (rowStemsButton) { rowStemsButton.classList.remove("active"); }
                }
                if (currentPlayButton) {
                    currentPlayButton.classList.remove("active");
                    currentPlayButton.innerText = "▶";
                }
            }

            function syncCompareSelectionState() {
                if (!compareButton) { return; }
                const libraryApi = window.LS && window.LS.library ? window.LS.library : null;
                const ready = Boolean(
                    libraryApi &&
                    typeof libraryApi.isLocalWavCompareReady === "function" &&
                    libraryApi.isLocalWavCompareReady()
                );
                compareButton.disabled = !ready;
                compareButton.title = ready
                    ? "Compare selected Local WAV files"
                    : "Select at least 2 Local WAV files with Select WAV";
            }

            function syncLoopControls() {
                const isActive = Boolean(audio.loop);
                [loopButton, drawerLoopButton].forEach((button) => {
                    if (!button) { return; }
                    button.classList.toggle("active", isActive);
                    button.setAttribute("aria-pressed", isActive ? "true" : "false");
                    button.title = isActive
                        ? "Loop ON — whole track or A/B section"
                        : "Loop whole track or A/B section";
                });
            }

            function deactivate() {
                leaveHostedMode();
                audio.pause();
                audio.removeAttribute("src");
                audio.load();
                resetGlobalStemPanel();
                resetRowState();
                current = null;
                currentTrackRow = null;
                currentFragmentRow = null;
                currentPlayButton = null;
                currentSource = "suno";
                stemPlaybackActive = false;
                root.classList.add("is-inactive");
                setExpanded(false);
                setControlsEnabled(false);
                syncCompareSelectionState();
                stemsButton.disabled = true;
                stemsButton.classList.remove("active");
                if (sidebarStemsButton) {
                    sidebarStemsButton.disabled = true;
                    sidebarStemsButton.classList.remove("active");
                    sidebarStemsButton.setAttribute("aria-pressed", "false");
                }
                audio.loop = false;
                syncLoopControls();
                titleNode.innerText = "No track selected";
                if (stemsMainTitle) { stemsMainTitle.innerText = "Main track"; }
                if (mainWaveformBox) { mainWaveformBox.dataset.clipLabel = "MAIN TRACK"; }
                sourceLabel.innerText = "Player inactive";
                updateCover("", "");
                progress.value = "0";
                root.querySelector(".time-readout").innerText = "0:00 / 0:00";
                root.querySelector(".wave-status").innerText = "player inactive";
                root.querySelector(".wave-loading").innerText = "Select a track";
                root.querySelector(".wave-loading").style.display = "flex";
                root.querySelector(".waveform-image").style.display = "none";
                lastActiveAudio = null;
                syncPlayState();
                syncSourceLabel();
            }

            function loadSource(source, options = {}) {
                if (!current) { return; }
                const requestedSource = source === "local" ? "local" : "suno";
                if (requestedSource === "local" && !current.localAudio) { return; }
                if (requestedSource === "suno" && !current.webAudio) { return; }

                const preserveTime = options.preserveTime === true;
                const shouldPlay = options.autoplay !== false;
                const oldTime = preserveTime ? Number(audio.currentTime || 0) : 0;
                const oldLoop = loopButton.classList.contains("active");

                if (!audio.paused) { audio.pause(); }
                pauseStemsForMainSource();
                leaveHostedMode();
                currentSource = requestedSource;

                // v5.510 black-box Player boundary: the Player receives one
                // browser-playable URL. It does not care whether that URL points
                // to LS local audio or to Suno-hosted web audio.
                const audioSrc = requestedSource === "local" ? current.localAudio : current.webAudio;
                const waveformSource = requestedSource === "local"
                    ? current.localPath
                    : buildPlaybackWaveformUrl(current.trackId, "suno");
                const waveformTrackId = requestedSource === "local"
                    ? current.trackId + "_local"
                    : current.trackId;

                setupPlayerBlock(
                    root,
                    audioSrc,
                    waveformSource,
                    waveformTrackId,
                    () => {
                        syncPlayState();
                        if (currentFragmentRow) {
                            autoplayNextFromFragment(currentFragmentRow);
                        }
                    }
                );

                audio.loop = oldLoop;
                syncLoopControls();
                setControlsEnabled(true);
                const startRequestedSource = () => {
                    if (!shouldPlay || !audioSrc) { return; }
                    audio.play().catch(() => {
                        sourceLabel.innerText = "Atskaņošanu neizdevās sākt";
                        syncPlayState();
                    });
                    lastActiveAudio = audio;
                };
                if (preserveTime && oldTime > 0) {
                    const restorePosition = () => {
                        if (audio.duration) {
                            audio.currentTime = Math.min(oldTime, Math.max(0, audio.duration - 0.05));
                        }
                        startRequestedSource();
                    };
                    if (audio.readyState >= 1) {
                        restorePosition();
                    } else {
                        audio.addEventListener("loadedmetadata", restorePosition, { once: true });
                    }
                } else {
                    startRequestedSource();
                }
                syncSourceLabel();
                syncCompactTransportState();
            }

            function syncGlobalPlayerTrackContext() {
                if (!currentTrackRow || !current) { return; }
                if (
                    typeof selectTrackRow === "function" &&
                    (
                        typeof selectedTrackRow === "undefined" ||
                        selectedTrackRow !== currentTrackRow
                    )
                ) {
                    selectTrackRow(
                        currentTrackRow,
                        { scroll: false, source: "playback" }
                    );
                }
                document.dispatchEvent(new CustomEvent(
                    "ls-track-playback-started",
                    { detail: { trackId: current.trackId || "" } }
                ));
            }

            function getSharedStemPosition() {
                if (
                    !stemPanel ||
                    typeof getStemEngine !== "function" ||
                    typeof getStemPlaybackPosition !== "function"
                ) {
                    return null;
                }
                const engine = getStemEngine(stemPanel);
                if (!engine || (!stemPlaybackActive && !engine.playing)) { return null; }
                return Math.max(0, Number(getStemPlaybackPosition(engine) || 0));
            }

            function toggleMainPlayback() {
                if (!current) { return false; }
                const stemPosition = getSharedStemPosition();
                pauseStemsForMainSource();
                if (!audio.getAttribute("src")) {
                    loadSource(currentSource, { autoplay: true, preserveTime: false });
                    return true;
                }
                if (stemPosition !== null && Number(audio.duration || 0) > 0) {
                    try {
                        audio.currentTime = Math.min(
                            stemPosition,
                            Math.max(0, Number(audio.duration || 0) - 0.01)
                        );
                    } catch (error) {}
                    updateProgress(root);
                    syncCompactProgress();
                }
                if (audio.paused || audio.ended) {
                    if (audio.ended && stemPosition === null) {
                        try { audio.currentTime = 0; } catch (error) {}
                    }
                    audio.play().catch(() => {
                        sourceLabel.innerText = "Atskaņošanu neizdevās sākt";
                        syncPlayState();
                    });
                } else {
                    audio.pause();
                }
                return true;
            }

            async function toggleUnifiedPlayback() {
                return toggleMainPlayback();
            }

            function isStemsViewOpen() {
                return Boolean(
                    current &&
                    current.hasStems &&
                    stemPanel &&
                    root.classList.contains("stems-mode") &&
                    root.classList.contains("expanded") &&
                    !stemPanel.classList.contains("hidden")
                );
            }

            async function activateStemPlayback() {
                // Ctrl+Space never opens Stems. It controls selected Stems only
                // inside the already expanded Stems view and uses the shared
                // full-song timeline position for immediate A/B comparison.
                if (!isStemsViewOpen()) { return false; }
                leaveHostedMode();
                if (stemPanel.dataset.loaded !== "true") {
                    await loadStemsForBlock(stemPanel, current.trackId || "");
                }
                if (typeof toggleStemSpacePause !== "function") { return false; }
                const sharedPosition = Math.max(0, Number(audio.currentTime || 0));
                if (!audio.paused) { audio.pause(); }
                return await toggleStemSpacePause(stemPanel, sharedPosition);
            }

            function loadFromButton(button, autoplay = true) {
                if (!button) { return false; }
                const trackRow = button.closest("tr.track-row");
                const fragmentRow = trackRow ? getFragmentRow(trackRow) : null;
                const trackId = button.dataset.trackId || "";
                if (!trackRow || !trackId) {
                    return false;
                }

                if (
                    current &&
                    current.trackId === trackId &&
                    currentPlayButton === button &&
                    !root.classList.contains("is-inactive")
                ) {
                    syncGlobalPlayerTrackContext();
                    if (autoplay === false) { return; }
                    toggleMainPlayback();
                    return;
                }

                closeOtherPlayers(fragmentRow);
                if (fragmentRow) {
                    fragmentRow.querySelectorAll("audio").forEach((rowAudio) => {
                        rowAudio.pause();
                    });
                    fragmentRow.classList.add("hidden");
                    fragmentRow.classList.remove("player-open");
                }
                resetGlobalStemPanel();
                resetRowState();
                const defaultPlayback = selectDefaultPlaybackSource(
                    button.dataset.localAudio || ""
                );
                current = {
                    trackId: trackId,
                    title: button.dataset.title || "[No title]",
                    cover: button.dataset.cover || "",
                    coverFull: button.dataset.coverFull || button.dataset.cover || "",
                    localAudio: button.dataset.localAudio || "",
                    localPath: button.dataset.localPath || "",
                    webAudio: buildSunoCurrentPlaybackUrl(
                        trackId,
                        button.dataset.audio || ""
                    ),
                    hasStems: (button.dataset.hasStems || "false") === "true",
                };
                currentTrackRow = trackRow;
                currentFragmentRow = fragmentRow;
                currentPlayButton = button;
                currentSource = defaultPlayback.source;
                stemPlaybackActive = false;

                root.classList.remove("is-inactive");
                setControlsEnabled(Boolean(current.localAudio || isValidSunoTrackId(current.trackId)));
                expandButton.disabled = false;
                if (closeButton) { closeButton.disabled = false; }
                editButton.disabled = false;
                syncCompareSelectionState();
                stemsButton.disabled = !current.hasStems;
                if (sidebarStemsButton) {
                    sidebarStemsButton.disabled = !current.hasStems;
                    sidebarStemsButton.classList.remove("active");
                    sidebarStemsButton.setAttribute("aria-pressed", "false");
                    sidebarStemsButton.title = current.hasStems
                        ? "Atvērt izvēlētās dziesmas Stems paneli"
                        : "Izvēlētajai dziesmai nav piesaistītu Stems";
                }
                titleNode.innerText = current.title;
                if (stemsMainTitle) { stemsMainTitle.innerText = current.title; }
                if (mainWaveformBox) { mainWaveformBox.dataset.clipLabel = current.title || "MAIN TRACK"; }
                updateCover(current.cover, current.coverFull);
                currentTrackRow.classList.add("player-open");
                syncGlobalPlayerTrackContext();
                syncPlayState();
                loadSource(currentSource, { autoplay: autoplay, preserveTime: false });
                syncPlayState();
                syncCompactTransportState();
                return true;
            }

            function loadFromStemButton(button) {
                if (!button) { return false; }
                const trackRow = button.closest("tr.track-row");
                if (!trackRow) { return false; }
                const playButton = trackRow.querySelector(".play-btn");
                if (!playButton) { return false; }
                loadFromButton(playButton, false);
                return true;
            }

            async function openStems() {
                if (!current || !current.hasStems || !stemPanel) { return false; }
                leaveHostedMode();
                setStemMode(true);
                setExpanded(true);
                currentStemBlock = stemPanel;
                await loadStemsForBlock(stemPanel, current.trackId || "");
                return true;
            }

            function blurCompactTransportControl(control) {
                if (!control) { return; }
                window.requestAnimationFrame(() => {
                    if (document.activeElement === control) { control.blur(); }
                });
            }

            async function restartCurrentTrack() {
                if (!current || currentSource === "suno" || !audio.getAttribute("src")) { return false; }
                pauseStemsForMainSource();
                try { audio.currentTime = 0; } catch (error) {}
                updateProgress(root);
                syncCompactProgress();
                return true;
            }

            async function loadAdjacentTrack(direction) {
                const rows = compactNavigationRows();
                const anchorRow = compactNavigationAnchorRow();
                if (!anchorRow) { return false; }
                const index = rows.indexOf(anchorRow);
                const targetIndex = index + (direction < 0 ? -1 : 1);
                if (index < 0 || targetIndex < 0 || targetIndex >= rows.length) {
                    syncCompactTransportState();
                    return false;
                }
                const targetRow = rows[targetIndex];
                const targetButton = targetRow.querySelector(".ls-cover-play-btn");
                if (!targetButton) { return false; }

                autoplayStartedFromPlayButton = true;
                loadFromButton(targetButton, true);
                targetRow.scrollIntoView({ block: "nearest", inline: "nearest" });
                syncCompactTransportState();
                return true;
            }

            playToggle.addEventListener("click", async () => {
                await toggleUnifiedPlayback();
                blurCompactTransportControl(playToggle);
            });
            if (restartButton) {
                restartButton.addEventListener("click", async () => {
                    await restartCurrentTrack();
                    blurCompactTransportControl(restartButton);
                });
            }
            if (previousButton) {
                previousButton.addEventListener("click", async () => {
                    await loadAdjacentTrack(-1);
                    blurCompactTransportControl(previousButton);
                });
            }
            if (nextButton) {
                nextButton.addEventListener("click", async () => {
                    await loadAdjacentTrack(1);
                    blurCompactTransportControl(nextButton);
                });
            }

            progress.addEventListener("input", async () => {
                if (!current || currentSource === "suno" || !audio.duration) { return; }
                pauseStemsForMainSource();
                audio.currentTime = (Number(progress.value || 0) / 100) * audio.duration;
                updateProgress(root);
            });

            function toggleGlobalLoop() {
                if (!current || currentSource === "suno") { return; }
                audio.loop = !audio.loop;
                syncLoopControls();
                if (audio.loop) {
                    setAutoplayListEnabled(false, true);
                    lastActiveAudio = audio;
                }
            }

            loopButton.addEventListener("click", () => {
                toggleGlobalLoop();
                blurCompactTransportControl(loopButton);
            });
            if (drawerLoopButton) {
                drawerLoopButton.addEventListener("click", () => {
                    toggleGlobalLoop();
                    blurCompactTransportControl(drawerLoopButton);
                });
            }

            expandButton.addEventListener("click", () => {
                setExpanded(!root.classList.contains("expanded"));
            });
            if (closeButton) { closeButton.addEventListener("click", deactivate); }

            compareButton.addEventListener("click", () => {
                syncCompareSelectionState();
                if (compareButton.disabled) { return; }
                setExpanded(false);
                leaveHostedMode();
                audio.pause();
                pauseStemsForMainSource();
                document.dispatchEvent(new CustomEvent(
                    "ls-library-open-selected-wav-compare"
                ));
            });

            document.addEventListener(
                "ls-library-wav-selection-changed",
                syncCompareSelectionState
            );

            async function toggleStems() {
                if (root.classList.contains("stems-mode")) {
                    setStemMode(false);
                    return false;
                }
                return await openStems();
            }

            function returnToSunoLibraryWithoutReload() {
                if (!root.classList.contains("stems-mode")) { return false; }
                setStemMode(false);
                setExpanded(false);
                schedulePlayerAlignment();
                syncPlayerReservedHeight();
                focusMainPlayControl();
                return true;
            }

            stemsButton.addEventListener("click", async () => {
                await toggleStems();
                focusMainPlayControl();
            });

            if (sidebarStemsButton) {
                sidebarStemsButton.addEventListener("click", async () => {
                    if (sidebarStemsButton.disabled || !current || !current.hasStems) { return; }
                    await toggleStems();
                    focusMainPlayControl();
                });
            }

            if (sidebarSunoLibraryLink) {
                sidebarSunoLibraryLink.addEventListener("click", (event) => {
                    if (
                        event.defaultPrevented ||
                        event.button !== 0 ||
                        event.ctrlKey || event.metaKey || event.shiftKey || event.altKey
                    ) {
                        return;
                    }
                    if (!root.classList.contains("stems-mode")) { return; }
                    event.preventDefault();
                    returnToSunoLibraryWithoutReload();
                });
            }

            editButton.addEventListener("click", () => {
                if (!currentFragmentRow || !current) { return; }
                if (currentSource === "local") {
                    const localEditButton = currentFragmentRow.querySelector(".edit-local-btn");
                    if (localEditButton) {
                        localEditButton.dataset.localPath = current.localPath || "";
                        localEditButton.click();
                    }
                    return;
                }
                const sunoEditButton = currentFragmentRow.querySelector(".edit-suno-btn");
                if (sunoEditButton) { sunoEditButton.click(); }
            });

            function syncPlaybackSelection() {
                pauseStemsForMainSource();
                syncPlayState();
                syncGlobalPlayerTrackContext();
            }

            document.addEventListener("ls-selected-track-changed", (event) => {
                const detail = event && event.detail ? event.detail : {};
                if (detail.source !== "selection") { return; }
                const trackId = String(detail.trackId || "").trim();
                const selectedRow = Array.from(
                    table.querySelectorAll("tr.track-row")
                ).find((row) => String(row.dataset.trackId || "") === trackId);
                const selectedPlayButton = selectedRow
                    ? selectedRow.querySelector(".ls-cover-play-btn")
                    : null;
                if (selectedPlayButton) {
                    loadFromButton(selectedPlayButton, false);
                    return;
                }
                leaveHostedMode();
                if (current && !audio.paused) { audio.pause(); }
                if (
                    stemPanel &&
                    currentStemBlock === stemPanel &&
                    typeof pauseStemBlock === "function"
                ) {
                    pauseStemBlock(stemPanel);
                }
            });

            audio.addEventListener("play", syncPlaybackSelection);
            audio.addEventListener("pause", syncPlayState);
            audio.addEventListener("ended", syncPlayState);
            audio.addEventListener("timeupdate", syncCompactProgress);
            audio.addEventListener("loadedmetadata", syncCompactProgress);

            deactivate();
            return {
                loadFromButton: loadFromButton,
                loadFromStemButton: loadFromStemButton,
                openStems: openStems,
                toggleStems: toggleStems,
                returnToSunoLibrary: returnToSunoLibraryWithoutReload,
                deactivate: deactivate,
                pauseMainForStems: pauseMainForStems,
                setStemPlaybackActive: setStemPlaybackActive,
                getAudio: () => audio,
                getCurrentTrackId: () => current ? current.trackId : "",
                getCurrentSource: () => currentSource,
                hasCurrentTrack: () => Boolean(current),
                togglePlayback: toggleUnifiedPlayback,
                activateStemPlayback: activateStemPlayback,
                isStemsViewOpen: isStemsViewOpen,
                isStemPlaybackActive: () => stemPlaybackActive,
                syncStemTransport: syncStemTransport,
                restart: restartCurrentTrack,
                previous: () => loadAdjacentTrack(-1),
                next: () => loadAdjacentTrack(1),
                focusMainPlay: () => {
                    window.requestAnimationFrame(() => {
                        try { playToggle.focus({ preventScroll: true }); }
                        catch (error) { playToggle.focus(); }
                    });
                },
            };
        }

        // The Stems engine may publish an initial progress reset while the
        // global controller is still being constructed. Initialize the shared
        // reference first so those callbacks see null instead of the temporal
        // dead zone of a const initializer.
        let lsGlobalPlayer = null;
        lsGlobalPlayer = createGlobalPlayerController();
        window.LS = window.LS || {};
        window.LS.player = lsGlobalPlayer;

