"""Elza v2.49 composer and microphone-level UI.

The existing Local Suno STT recorder remains the source of audio/transcription.
This enhancer only restructures the composer and visualizes the real microphone
MediaStream through Web Audio AnalyserNode.
"""

MARKER = 'data-elza-v232'

_STYLE = r"""
<style data-elza-v232="style">
.ls-elza-compose { position: relative; }
.ls-elza-v232-shell {
    position: relative;
    overflow: visible;
    border: 1px solid rgba(136,145,158,.9);
    border-radius: 23px;
    background: #303033;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.035);
}
.ls-elza-v232-shell .ls-elza-input-row {
    display: block;
    padding: 13px 14px 4px;
}
.ls-elza-v232-shell .ls-elza-input {
    width: 100% !important;
    min-height: 54px !important;
    max-height: 160px !important;
    padding: 0 !important;
    border: 0 !important;
    outline: 0 !important;
    resize: vertical;
    background: transparent !important;
    color: #f1f3f4 !important;
    caret-color: #fff;
    box-shadow: none !important;
}
.ls-elza-v232-shell .ls-elza-input::placeholder { color: rgba(238,241,245,.58) !important; }
.ls-elza-v232-actions {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 47px;
    padding: 4px 8px 8px;
}
.ls-elza-v232-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 36px;
    width: 36px;
    height: 36px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: #f1f3f4;
    cursor: pointer;
}
.ls-elza-v232-icon:hover { background: rgba(255,255,255,.08); }
.ls-elza-v232-plus { font-size: 29px; font-weight: 300; line-height: 1; }
.ls-elza-v232-spacer { flex: 1 1 auto; min-width: 4px; }
.ls-elza-v232-chip {
    display: none;
    align-items: center;
    min-height: 28px;
    padding: 2px 9px;
    border: 1px solid rgba(124,155,201,.7);
    border-radius: 14px;
    background: rgba(60,86,121,.5);
    color: #eef5ff;
    font-size: 11px;
    font-weight: 700;
}
.ls-elza-v232-chip.active { display: inline-flex; }
.ls-elza-v232-shell #ls-elza-voice {
    position: relative;
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    flex: 0 0 38px;
    width: 38px !important;
    min-width: 38px !important;
    height: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 50% !important;
    background: transparent !important;
    color: #f1f3f4 !important;
    font-size: 0 !important;
    box-shadow: none !important;
}
.ls-elza-v232-shell #ls-elza-voice::before {
    content: "";
    display: block;
    width: 21px;
    height: 21px;
    background: currentColor;
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm-1 4.93V22h2v-3.07A8.001 8.001 0 0 0 20 11h-2a6 6 0 0 1-12 0H4a8.001 8.001 0 0 0 7 7.93Z'/%3E%3C/svg%3E") center / contain no-repeat;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 14a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3Zm-1 4.93V22h2v-3.07A8.001 8.001 0 0 0 20 11h-2a6 6 0 0 1-12 0H4a8.001 8.001 0 0 0 7 7.93Z'/%3E%3C/svg%3E") center / contain no-repeat;
}
.ls-elza-v232-shell #ls-elza-voice:hover:not(:disabled) { background: rgba(255,255,255,.08) !important; }
.ls-elza-v232-shell.recording #ls-elza-voice { display: none !important; }
.ls-elza-v232-voice-mode {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: 38px;
    padding: 0 14px;
    border: 0;
    border-radius: 19px;
    background: #3f82f7;
    color: #fff;
    cursor: pointer;
    font-size: 14px;
    font-weight: 800;
}
.ls-elza-v232-voice-mode::before { content: "▥"; font-size: 14px; }
.ls-elza-v232-voice-mode:hover { background: #3275e9; }
.ls-elza-v232-shell #ls-elza-send {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    flex: 0 0 38px;
    width: 38px !important;
    min-width: 38px !important;
    height: 38px !important;
    min-height: 38px !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 50% !important;
    background: #3f82f7 !important;
    color: transparent !important;
    font-size: 0 !important;
    box-shadow: none !important;
}
.ls-elza-v232-shell #ls-elza-send::before {
    content: "↑";
    color: #fff;
    font-size: 25px;
    font-weight: 700;
    line-height: 1;
}
.ls-elza-v232-shell #ls-elza-send:hover:not(:disabled) { background: #3275e9 !important; }
.ls-elza-v232-menu {
    position: absolute;
    left: 7px;
    bottom: 50px;
    z-index: 30;
    display: none;
    min-width: 210px;
    padding: 7px;
    border: 1px solid rgba(130,142,158,.78);
    border-radius: 14px;
    background: #303033;
    box-shadow: 0 14px 36px rgba(0,0,0,.38);
}
.ls-elza-v232-menu.open { display: grid; gap: 4px; }
.ls-elza-v232-menu .ls-elza-mode-btn {
    width: 100% !important;
    height: auto !important;
    min-height: 36px !important;
    justify-content: flex-start !important;
    padding: 7px 10px !important;
    border: 0 !important;
    border-radius: 9px !important;
    background: transparent !important;
    color: transparent !important;
    font-size: 0 !important;
    box-shadow: none !important;
}
.ls-elza-v232-menu .ls-elza-mode-btn:hover:not(:disabled) { background: rgba(255,255,255,.08) !important; }
.ls-elza-v232-menu .ls-elza-mode-btn[aria-pressed="true"] { background: rgba(63,130,247,.28) !important; }
.ls-elza-v232-menu .ls-elza-mode-btn::after { color: #fff; font-size: 13px; font-weight: 700; }
.ls-elza-v232-menu #ls-elza-ux-mode::after { content: "UX pārbaude"; }
.ls-elza-v232-menu #ls-elza-test-mode::after { content: "Testēt funkciju"; }
.ls-elza-v232-menu #ls-elza-track-mode::after { content: "Track analīze"; }
.ls-elza-v232-menu #ls-elza-code-mode::after { content: "Koda analīze"; }
.ls-elza-mode-row.ls-elza-v232-source-row { display: none !important; }
.ls-elza-v232-recording {
    display: none;
    align-items: center;
    gap: 8px;
    flex: 1 1 auto;
    min-width: 0;
}
.ls-elza-v232-shell.recording .ls-elza-v232-recording { display: flex; }
.ls-elza-v232-shell.recording .ls-elza-input-row,
.ls-elza-v232-shell.recording .ls-elza-v232-plus,
.ls-elza-v232-shell.recording .ls-elza-v232-chip,
.ls-elza-v232-shell.recording .ls-elza-v232-spacer,
.ls-elza-v232-shell.recording .ls-elza-v232-voice-mode { display: none !important; }
.ls-elza-v232-cancel,
.ls-elza-v232-stop {
    flex: 0 0 36px;
    width: 36px;
    height: 36px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    color: #f1f3f4;
    cursor: pointer;
}
.ls-elza-v232-cancel { background: transparent; font-size: 26px; }
.ls-elza-v232-stop { background: rgba(255,255,255,.09); font-size: 14px; }
.ls-elza-v232-cancel:hover,
.ls-elza-v232-stop:hover { background: rgba(255,255,255,.15); }
.ls-elza-v232-wave {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
    flex: 1 1 auto;
    min-width: 100px;
    height: 32px;
    overflow: hidden;
}
.ls-elza-v232-wave > span {
    display: block;
    width: 3px;
    height: 3px;
    border-radius: 2px;
    background: rgba(241,243,244,.9);
    opacity: .42;
    transform-origin: center;
}
.ls-elza-v232-shell.recording #ls-elza-send { margin-left: 2px; }
.ls-elza-hint.ls-elza-v232-hint { margin-top: 5px; opacity: .72; }
@media (max-width: 650px) {
    .ls-elza-v232-shell { border-radius: 20px; }
    .ls-elza-v232-voice-mode { padding: 0 11px; }
    .ls-elza-v232-wave { min-width: 78px; }
}
</style>
"""

_SCRIPT = r"""
<script data-elza-v232="script">
(() => {
    if (window.__elzaV232Installed) { return; }
    window.__elzaV232Installed = true;

    const title = document.getElementById("ls-elza-title");
    const compose = document.querySelector(".ls-elza-compose");
    const inputRow = compose && compose.querySelector(".ls-elza-input-row");
    const input = document.getElementById("ls-elza-input");
    const modeRow = compose && compose.querySelector(".ls-elza-mode-row");
    const voiceButton = document.getElementById("ls-elza-voice");
    const sendButton = document.getElementById("ls-elza-send");
    const statusLine = document.getElementById("ls-elza-status");
    if (!compose || !inputRow || !input || !modeRow || !voiceButton || !sendButton) { return; }

    if (title) { title.textContent = "Elza v2.49"; }
    input.placeholder = "Jautāt Elzai";

    const shell = document.createElement("div");
    shell.className = "ls-elza-v232-shell";
    shell.setAttribute("data-elza-v232", "composer");
    inputRow.parentNode.insertBefore(shell, inputRow);
    shell.appendChild(inputRow);

    const actions = document.createElement("div");
    actions.className = "ls-elza-v232-actions";
    shell.appendChild(actions);

    const plusButton = document.createElement("button");
    plusButton.type = "button";
    plusButton.className = "ls-elza-v232-icon ls-elza-v232-plus";
    plusButton.textContent = "+";
    plusButton.title = "Papildu rīki";
    plusButton.setAttribute("aria-label", "Papildu rīki");
    actions.appendChild(plusButton);

    const chip = document.createElement("span");
    chip.className = "ls-elza-v232-chip";
    actions.appendChild(chip);

    const spacer = document.createElement("span");
    spacer.className = "ls-elza-v232-spacer";
    actions.appendChild(spacer);

    const menu = document.createElement("div");
    menu.className = "ls-elza-v232-menu";
    menu.setAttribute("role", "menu");
    shell.appendChild(menu);

    const modeButtons = Array.from(modeRow.querySelectorAll("[data-ls-elza-mode]"));
    modeButtons.forEach((button) => menu.appendChild(button));
    modeRow.classList.add("ls-elza-v232-source-row");

    const recording = document.createElement("div");
    recording.className = "ls-elza-v232-recording";

    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "ls-elza-v232-cancel";
    cancel.textContent = "×";
    cancel.title = "Atcelt ierakstu";
    cancel.setAttribute("aria-label", "Atcelt ierakstu");
    recording.appendChild(cancel);

    const wave = document.createElement("div");
    wave.className = "ls-elza-v232-wave";
    wave.setAttribute("aria-label", "Mikrofona līmenis");
    const waveBars = [];
    for (let index = 0; index < 28; index += 1) {
        const bar = document.createElement("span");
        waveBars.push(bar);
        wave.appendChild(bar);
    }
    recording.appendChild(wave);

    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "ls-elza-v232-stop";
    stop.textContent = "■";
    stop.title = "Stop";
    stop.setAttribute("aria-label", "Stop");
    recording.appendChild(stop);
    actions.appendChild(recording);

    actions.appendChild(voiceButton);

    const voiceMode = document.createElement("button");
    voiceMode.type = "button";
    voiceMode.className = "ls-elza-v232-voice-mode";
    voiceMode.textContent = "Balss";
    voiceMode.title = "Pilnais Balss režīms";
    actions.appendChild(voiceMode);
    actions.appendChild(sendButton);

    const hint = compose.querySelector(".ls-elza-hint");
    if (hint) {
        hint.classList.add("ls-elza-v232-hint");
        hint.textContent = "Enter = nosūtīt · Shift+Enter = jauna rinda";
    }

    function setStatus(text, error=false) {
        if (!statusLine) { return; }
        statusLine.textContent = text || "";
        statusLine.classList.toggle("error", Boolean(error));
    }

    function updateChip() {
        const active = modeButtons.find((button) => button.getAttribute("aria-pressed") === "true");
        if (!active) {
            chip.textContent = "";
            chip.classList.remove("active");
            return;
        }
        const labels = {UX_REVIEW: "UX", TEST_REVIEW: "Test", TRACK_DB: "Track", LS_CODE: "Code"};
        const mode = String(active.dataset.lsElzaMode || "").toUpperCase();
        chip.textContent = labels[mode] || mode || "Režīms";
        chip.classList.add("active");
    }

    function isRecording() {
        return voiceButton.classList.contains("recording")
            || voiceButton.getAttribute("aria-pressed") === "true"
            || String(voiceButton.textContent || "").trim().toLowerCase() === "stop";
    }

    let audioContext = null;
    let analyser = null;
    let analyserSource = null;
    let analyserFrame = 0;
    let analyserData = null;
    let analyserStream = null;
    let smoothed = new Array(waveBars.length).fill(0);

    function resetBars() {
        waveBars.forEach((bar) => {
            bar.style.height = "3px";
            bar.style.opacity = ".42";
        });
        smoothed = new Array(waveBars.length).fill(0);
    }

    function stopMicrophoneMeter() {
        if (analyserFrame) {
            cancelAnimationFrame(analyserFrame);
            analyserFrame = 0;
        }
        try { if (analyserSource) { analyserSource.disconnect(); } } catch (error) {}
        analyserSource = null;
        analyser = null;
        analyserData = null;
        analyserStream = null;
        if (audioContext) {
            try { audioContext.close(); } catch (error) {}
        }
        audioContext = null;
        resetBars();
    }

    function drawMicrophoneMeter() {
        if (!analyser || !analyserData || !isRecording()) {
            if (!isRecording()) { stopMicrophoneMeter(); }
            return;
        }
        analyser.getByteFrequencyData(analyserData);
        const usable = Math.max(1, Math.min(analyserData.length, 36));
        const half = Math.ceil(waveBars.length / 2);
        for (let i = 0; i < waveBars.length; i += 1) {
            const mirrored = i < half ? i : waveBars.length - 1 - i;
            const start = Math.floor((mirrored / half) * usable);
            const end = Math.max(start + 1, Math.floor(((mirrored + 1) / half) * usable));
            let total = 0;
            let count = 0;
            for (let bin = start; bin < end && bin < usable; bin += 1) {
                total += analyserData[bin];
                count += 1;
            }
            const raw = count ? total / count : 0;
            const target = Math.max(0, Math.min(1, (raw - 4) / 92));
            smoothed[i] = smoothed[i] * .56 + target * .44;
            const level = smoothed[i];
            waveBars[i].style.height = (3 + level * 26).toFixed(1) + "px";
            waveBars[i].style.opacity = (.40 + level * .60).toFixed(2);
        }
        analyserFrame = requestAnimationFrame(drawMicrophoneMeter);
    }

    async function startMicrophoneMeter(stream) {
        stopMicrophoneMeter();
        if (!stream || !stream.getAudioTracks || !stream.getAudioTracks().length) { return; }
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) {
            setStatus("Web Audio nav pieejams; STT turpinās bez līmeņa indikācijas.", true);
            return;
        }
        try {
            audioContext = new AudioContextClass();
            if (audioContext.state === "suspended") {
                try { await audioContext.resume(); } catch (error) {}
            }
            analyserSource = audioContext.createMediaStreamSource(stream);
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = .68;
            analyser.minDecibels = -82;
            analyser.maxDecibels = -18;
            analyserData = new Uint8Array(analyser.frequencyBinCount);
            analyserStream = stream;
            analyserSource.connect(analyser);
            drawMicrophoneMeter();
        } catch (error) {
            stopMicrophoneMeter();
            setStatus("Mikrofons darbojas, bet līmeņa indikatoru neizdevās ieslēgt.", true);
        }
    }

    const mediaDevices = navigator.mediaDevices;
    if (mediaDevices && typeof mediaDevices.getUserMedia === "function" && !mediaDevices.__elzaV232Wrapped) {
        const originalGetUserMedia = mediaDevices.getUserMedia.bind(mediaDevices);
        mediaDevices.getUserMedia = async function(constraints) {
            const stream = await originalGetUserMedia(constraints);
            if (constraints && constraints.audio) {
                window.setTimeout(() => { startMicrophoneMeter(stream); }, 0);
            }
            return stream;
        };
        mediaDevices.__elzaV232Wrapped = true;
    }

    function syncRecordingState() {
        const active = isRecording();
        shell.classList.toggle("recording", active);
        if (!active) {
            cancel.disabled = false;
            stop.disabled = false;
            stopMicrophoneMeter();
        } else if (analyserStream && !analyserFrame) {
            drawMicrophoneMeter();
        }
    }

    plusButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        menu.classList.toggle("open");
    });
    menu.addEventListener("click", (event) => {
        const button = event.target.closest("[data-ls-elza-mode]");
        if (button) {
            window.setTimeout(() => { updateChip(); menu.classList.remove("open"); }, 0);
        }
    });
    document.addEventListener("click", (event) => {
        if (!menu.contains(event.target) && event.target !== plusButton) { menu.classList.remove("open"); }
    });

    voiceMode.addEventListener("click", () => {
        setStatus("Pilnais Balss režīms vēl nav pieslēgts; mikrofons ir diktēšanai.");
    });

    stop.addEventListener("click", () => {
        if (isRecording()) { voiceButton.click(); }
    });

    const originalFetch = window.fetch.bind(window);
    let cancelNextStt = false;
    window.fetch = async function(inputValue, init) {
        const url = typeof inputValue === "string" ? inputValue : String(inputValue && inputValue.url || "");
        if (cancelNextStt && url.includes("/ls-elza-stt")) {
            cancelNextStt = false;
            return new Response(JSON.stringify({ok: true, text: "."}), {
                status: 200, headers: {"Content-Type": "application/json"}
            });
        }
        return originalFetch(inputValue, init);
    };

    cancel.addEventListener("click", () => {
        if (!isRecording()) { return; }
        cancel.disabled = true;
        stop.disabled = true;
        const before = String(input.value || "");
        cancelNextStt = true;
        voiceButton.click();
        const started = Date.now();
        const timer = window.setInterval(() => {
            if (!isRecording() && !voiceButton.disabled) {
                window.clearInterval(timer);
                input.value = before;
                input.dispatchEvent(new Event("input", {bubbles: true}));
                setStatus("Ieraksts atcelts.");
                input.focus();
                return;
            }
            if (Date.now() - started > 12000) {
                window.clearInterval(timer);
                setStatus("Ieraksta atcelšana ieilga.", true);
            }
        }, 100);
    });

    const observer = new MutationObserver(() => {
        syncRecordingState();
        updateChip();
    });
    observer.observe(voiceButton, {
        attributes: true,
        attributeFilter: ["class", "aria-pressed", "disabled"],
        childList: true,
        characterData: true,
        subtree: true,
    });
    modeButtons.forEach((button) => observer.observe(button, {
        attributes: true,
        attributeFilter: ["class", "aria-pressed", "disabled"],
    }));

    window.addEventListener("beforeunload", stopMicrophoneMeter);
    updateChip();
    syncRecordingState();
})();
</script>
"""


def enhance_rendered_assets_v230(template):
    text = str(template or "")
    if MARKER in text:
        return text
    return text + _STYLE + _SCRIPT
