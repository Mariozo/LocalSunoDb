(function () {
    "use strict";

    function initializeLibraryPlaybackIndicator() {
        const root = document.body;
        if (!root || root.id !== "ls-library") { return; }

        const LS = window.LS || {};
        const player = LS.player;
        if (!player || typeof player.getAudio !== "function") { return; }

        const audio = player.getAudio();
        if (!audio || audio.dataset.lsCoverIndicatorBound === "1") { return; }
        audio.dataset.lsCoverIndicatorBound = "1";

        let activeTrackId = "";

        function normalizeTrackId(value) {
            return String(value || "").trim();
        }

        function getCurrentTrackId() {
            if (typeof player.getCurrentTrackId !== "function") { return ""; }
            return normalizeTrackId(player.getCurrentTrackId());
        }

        function findTrackRow(trackId) {
            const wanted = normalizeTrackId(trackId);
            if (!wanted) { return null; }
            return Array.from(root.querySelectorAll("tr.track-row")).find(
                (row) => normalizeTrackId(row.dataset.trackId) === wanted
            ) || null;
        }

        function ensureIndicator(row) {
            if (!row) { return null; }
            const coverControl = row.querySelector(".ls-track-cover-control");
            if (!coverControl) { return null; }

            let indicator = coverControl.querySelector(".ls-cover-playback-indicator");
            if (indicator) { return indicator; }

            indicator = document.createElement("span");
            indicator.className = "ls-cover-playback-indicator";
            indicator.setAttribute("aria-hidden", "true");
            for (let index = 0; index < 5; index += 1) {
                const bar = document.createElement("span");
                bar.className = "ls-cover-playback-bar";
                indicator.appendChild(bar);
            }
            coverControl.appendChild(indicator);
            return indicator;
        }

        function clearPlaybackClasses(exceptRow) {
            root.querySelectorAll(
                "tr.track-row.ls-cover-audio-playing, tr.track-row.ls-cover-audio-paused"
            ).forEach((row) => {
                if (row === exceptRow) { return; }
                row.classList.remove("ls-cover-audio-playing", "ls-cover-audio-paused");
            });
        }

        function showTrackState(trackId, state) {
            const normalizedId = normalizeTrackId(trackId);
            if (!normalizedId || state === "stopped") {
                clearPlaybackClasses(null);
                activeTrackId = "";
                return;
            }

            const row = findTrackRow(normalizedId);
            if (!row) {
                clearPlaybackClasses(null);
                activeTrackId = normalizedId;
                return;
            }

            ensureIndicator(row);
            clearPlaybackClasses(row);
            row.classList.toggle("ls-cover-audio-playing", state === "playing");
            row.classList.toggle("ls-cover-audio-paused", state === "paused");
            activeTrackId = normalizedId;
        }

        function clearIfTrackChanged(nextTrackId) {
            const nextId = normalizeTrackId(nextTrackId);
            if (activeTrackId && nextId && activeTrackId !== nextId) {
                clearPlaybackClasses(null);
                activeTrackId = "";
            }
        }

        audio.addEventListener("play", () => {
            showTrackState(getCurrentTrackId(), "playing");
        });

        audio.addEventListener("pause", () => {
            const trackId = getCurrentTrackId() || activeTrackId;
            if (!activeTrackId || trackId !== activeTrackId) { return; }
            showTrackState(trackId, audio.ended ? "stopped" : "paused");
        });

        audio.addEventListener("ended", () => {
            showTrackState(getCurrentTrackId() || activeTrackId, "stopped");
        });

        audio.addEventListener("emptied", () => {
            if (activeTrackId) { showTrackState(activeTrackId, "stopped"); }
        });

        document.addEventListener("ls-track-playback-started", (event) => {
            const detail = event && event.detail ? event.detail : {};
            clearIfTrackChanged(detail.trackId);
        });
    }

    if (document.readyState === "loading") {
        window.addEventListener("DOMContentLoaded", initializeLibraryPlaybackIndicator, { once: true });
    } else {
        initializeLibraryPlaybackIndicator();
    }
})();
