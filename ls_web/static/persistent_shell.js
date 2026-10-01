(() => {
    if (window.LSPersistentShellInstalled) return;
    window.LSPersistentShellInstalled = true;

    const ORIGIN = window.location.origin;
    const SECONDARY_PATHS = new Set([
        "/my-library",
        "/music-db",
        "/playlists",
        "/downloader",
        "/help",
    ]);
    const ROOT_PATH = "/";
    const SHELL_OPEN_PARAM = "ls_open";
    const EMBEDDED_PARAM = "ls_embedded";

    function normalizeTarget(rawUrl) {
        let url;
        try {
            url = new URL(rawUrl || ROOT_PATH, ORIGIN);
        } catch (_) {
            return "";
        }
        if (url.origin !== ORIGIN) return "";
        if (url.pathname === "/music-db") url.pathname = "/my-library";
        url.searchParams.delete(EMBEDDED_PARAM);
        url.searchParams.delete(SHELL_OPEN_PARAM);
        return url.pathname + (url.search ? url.search : "") + (url.hash || "");
    }

    function routePath(rawUrl) {
        try {
            return new URL(rawUrl || ROOT_PATH, ORIGIN).pathname;
        } catch (_) {
            return "";
        }
    }

    function isShellRoute(rawUrl) {
        const path = routePath(rawUrl);
        return path === ROOT_PATH || SECONDARY_PATHS.has(path);
    }

    function isSecondaryRoute(rawUrl) {
        return SECONDARY_PATHS.has(routePath(rawUrl));
    }

    function sectionFor(rawUrl) {
        const path = routePath(rawUrl);
        if (path === "/my-library" || path === "/music-db") return "my-library";
        if (path === "/playlists") return "playlists";
        if (path === "/downloader") return "downloader";
        if (path === "/help") return "help";
        return "suno";
    }

    function embeddedUrl(rawUrl) {
        const url = new URL(rawUrl || ROOT_PATH, ORIGIN);
        url.searchParams.set(EMBEDDED_PARAM, "1");
        return url.pathname + url.search + (url.hash || "");
    }

    function isPlainPrimaryClick(event) {
        return event.button === 0 &&
            !event.ctrlKey &&
            !event.metaKey &&
            !event.shiftKey &&
            !event.altKey;
    }

    function isBackendRestartShortcut(event) {
        return Boolean(
            event &&
            !event.repeat &&
            event.ctrlKey &&
            event.shiftKey &&
            !event.altKey &&
            !event.metaKey &&
            (
                event.code === "Home" ||
                String(event.key || "").toLowerCase() === "home"
            )
        );
    }

    function triggerBackendRestartButton() {
        const button = document.querySelector("[data-ls-backend-restart='1']");
        if (!button || button.disabled) return false;
        button.click();
        return true;
    }

    function pauseLocalAudio() {
        document.querySelectorAll("audio").forEach((audio) => {
            if (!audio.paused) {
                try { audio.pause(); } catch (_) {}
            }
        });
    }

    function mediaPlaybackMetadata(media) {
        const dataset = media?.dataset || {};
        const title = String(
            dataset.lsTitle ||
            document.getElementById("ls-global-player-title")?.textContent ||
            ""
        ).trim();
        const artist = String(
            dataset.lsArtist ||
            document.getElementById("selected-track-panel-meta")?.textContent ||
            ""
        ).trim();
        const album = String(dataset.lsAlbum || "").trim();
        return { title, artist, album };
    }

    function installEmbeddedShell() {
        document.documentElement.classList.add("ls-shell-embedded");
        if (document.body) document.body.classList.add("ls-shell-embedded");

        window.LSShellNavigate = (rawUrl) => {
            const target = normalizeTarget(rawUrl);
            if (!target || !isShellRoute(target)) return false;
            try {
                if (
                    window.parent &&
                    window.parent !== window &&
                    typeof window.parent.LSShellNavigate === "function"
                ) {
                    return window.parent.LSShellNavigate(target) !== false;
                }
            } catch (_) {}
            try {
                window.parent.postMessage(
                    { type: "LS_SHELL_NAVIGATE", url: target },
                    ORIGIN
                );
                return true;
            } catch (_) {
                return false;
            }
        };

        document.addEventListener("click", (event) => {
            if (!isPlainPrimaryClick(event)) return;
            const anchor = event.target?.closest?.("a[href]");
            if (!anchor) return;
            if (anchor.hasAttribute("download")) return;
            const targetAttr = String(anchor.getAttribute("target") || "").trim();
            if (targetAttr && targetAttr !== "_self") return;
            const target = normalizeTarget(anchor.href);
            if (!target || !isShellRoute(target)) return;
            event.preventDefault();
            window.LSShellNavigate(target);
        }, true);

        document.addEventListener("submit", (event) => {
            const form = event.target;
            if (!(form instanceof HTMLFormElement)) return;
            const method = String(form.method || "get").toLowerCase();
            if (method !== "get") return;
            const action = normalizeTarget(form.action || window.location.href);
            if (!action || !isShellRoute(action)) return;
            const url = new URL(action, ORIGIN);
            const data = new FormData(form);
            for (const [key, value] of data.entries()) {
                if (typeof value === "string") {
                    url.searchParams.append(key, value);
                }
            }
            event.preventDefault();
            window.LSShellNavigate(
                url.pathname + url.search + (url.hash || "")
            );
        }, true);

        document.addEventListener("keydown", (event) => {
            if (!isBackendRestartShortcut(event)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            try {
                window.parent.postMessage(
                    { type: "LS_SHELL_RESTART_BACKEND" },
                    ORIGIN
                );
            } catch (_) {}
        }, true);

        document.addEventListener("play", (event) => {
            if (!(event.target instanceof HTMLMediaElement)) return;
            try {
                window.parent.postMessage({ type: "LS_SHELL_AUDIO_PLAY" }, ORIGIN);
            } catch (_) {}
        }, true);

        window.addEventListener("message", (event) => {
            if (event.origin !== ORIGIN) return;
            if (!event.data || event.data.type !== "LS_SHELL_PAUSE_AUDIO") return;
            pauseLocalAudio();
        });
    }

    function redirectStandaloneSecondary() {
        if (!isSecondaryRoute(window.location.href)) return false;
        const target = normalizeTarget(window.location.href);
        const shell = new URL(ROOT_PATH, ORIGIN);
        shell.searchParams.set(SHELL_OPEN_PARAM, target);
        window.location.replace(shell.pathname + shell.search);
        return true;
    }

    function installParentShell() {
        const body = document.body;
        if (!body || body.id !== "ls-library") return;

        document.documentElement.classList.add("ls-shell-parent");

        const originalUrl = new URL(window.location.href);
        const requestedOpen = originalUrl.searchParams.get(SHELL_OPEN_PARAM) || "";
        originalUrl.searchParams.delete(SHELL_OPEN_PARAM);
        const libraryUrl =
            originalUrl.pathname +
            (originalUrl.search ? originalUrl.search : "") +
            (originalUrl.hash || "");
        const libraryTitle = document.title;

        if (requestedOpen) {
            window.history.replaceState(
                { lsShell: true, section: "suno" },
                "",
                libraryUrl
            );
        }

        const host = document.createElement("div");
        host.id = "ls-shell-screen-host";
        host.setAttribute("aria-live", "off");
        document.body.appendChild(host);

        const frames = new Map();
        const selectedTrackByFrame = new WeakMap();
        let activeTarget = "";
        let viewTitle = libraryTitle;
        let currentPlayback = null;

        function updateSidebar(section) {
            document.querySelectorAll(
                "header .header-tabs a.header-tab[href]"
            ).forEach((link) => {
                const linkSection = sectionFor(link.href);
                const shouldBeActive =
                    (section === "suno" && linkSection === "suno") ||
                    (section === "my-library" && linkSection === "my-library") ||
                    (section === "playlists" && linkSection === "playlists") ||
                    (section === "downloader" && linkSection === "downloader");
                link.classList.toggle("active", shouldBeActive);
            });
        }

        function ensureSidebarAudioIndicators() {
            document.querySelectorAll("header .header-tabs a.header-tab[href]").forEach((link) => {
                const section = sectionFor(link.href);
                if (!["suno", "my-library", "playlists"].includes(section)) return;
                link.dataset.lsShellSection = section;
                if (link.querySelector(".ls-sidebar-audio-indicator")) return;
                const indicator = document.createElement("span");
                indicator.className = "ls-sidebar-audio-indicator";
                indicator.title = "Šeit pašlaik skan audio";
                indicator.setAttribute("aria-label", "Šeit pašlaik skan audio");
                indicator.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 10v4h4l5 4V6L9 10H5Z" fill="currentColor"/><path d="M17 9.3c1.2 1.5 1.2 4 0 5.4M19.3 7c2.5 2.7 2.5 7.3 0 10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
                link.appendChild(indicator);
            });
        }

        function playbackTitle(playback) {
            const title = String(playback?.metadata?.title || "").trim();
            const artist = String(playback?.metadata?.artist || "").trim();
            if (title && artist) return "▶ " + artist + " — " + title + " · LS";
            if (title) return "▶ " + title + " · LS";
            return "▶ Local Suno · LS";
        }

        function refreshDocumentTitle() {
            document.title = currentPlayback ? playbackTitle(currentPlayback) : viewTitle;
        }

        function setViewTitle(title) {
            const value = String(title || "").trim();
            if (value) viewTitle = value;
            refreshDocumentTitle();
        }

        function setPlaybackState(playing, section, metadata) {
            currentPlayback = playing ? {
                section: section || "suno",
                metadata: metadata || {},
            } : null;
            document.querySelectorAll(
                "header .header-tabs a.header-tab.is-audio-playing"
            ).forEach((link) => link.classList.remove("is-audio-playing"));
            if (currentPlayback) {
                document.querySelector(
                    'header .header-tabs a.header-tab[data-ls-shell-section="' +
                    currentPlayback.section + '"]'
                )?.classList.add("is-audio-playing");
            }
            refreshDocumentTitle();
        }

        function setSharedPanelMode(section) {
            const panel = document.getElementById("selected-track-panel");
            if (!panel) return;
            panel.classList.toggle(
                "is-external-context",
                section === "my-library" || section === "playlists"
            );
            panel.classList.toggle("is-imports-context", section === "downloader");
            if (section === "suno") {
                document.getElementById("selected-track-external-actions")?.setAttribute("hidden", "");
            }
        }

        function setSharedPanelSelection(data) {
            const panel = document.getElementById("selected-track-panel");
            if (!panel) return;
            const item = data && typeof data === "object" ? data : {};
            const title = String(item.title || "Izvēlies dziesmu").trim();
            const artist = String(item.artist || "").trim();
            const album = String(item.album || "").trim();
            const year = String(item.year || "").trim();
            const genre = String(item.genre || "").trim();
            const format = String(item.format || "").trim();
            const duration = String(item.duration || "").trim();
            const coverUrl = String(item.cover || "").trim();

            panel.classList.add("is-external-context");
            panel.classList.remove("is-imports-context");

            const titleNode = document.getElementById("selected-track-panel-title");
            const metaNode = document.getElementById("selected-track-panel-meta");
            const cover = document.getElementById("selected-track-panel-cover");
            const placeholder = document.getElementById("selected-track-panel-cover-placeholder");
            const localStatus = document.getElementById("selected-track-local-status");
            const stemsStatus = document.getElementById("selected-track-stems-status");
            const actions = document.getElementById("selected-track-external-actions");
            const googleSong = document.getElementById("selected-track-google-song");
            const googleAlbum = document.getElementById("selected-track-google-album");

            if (titleNode) titleNode.textContent = title;
            if (metaNode) metaNode.textContent = [artist, album, year, genre].filter(Boolean).join(" · ");
            if (localStatus) localStatus.textContent = [format, duration].filter(Boolean).join(" · ") || "Local";
            if (stemsStatus) stemsStatus.style.display = "none";
            if (actions) actions.hidden = false;

            if (cover && placeholder) {
                if (coverUrl) {
                    cover.src = coverUrl;
                    cover.style.display = "block";
                    placeholder.style.display = "none";
                } else {
                    cover.removeAttribute("src");
                    cover.style.display = "none";
                    placeholder.style.display = "flex";
                }
            }

            if (googleSong) {
                googleSong.href = "https://www.google.com/search?q=" + encodeURIComponent(
                    [artist, title, "song"].filter(Boolean).join(" ")
                );
            }
            if (googleAlbum) {
                googleAlbum.href = "https://www.google.com/search?q=" + encodeURIComponent(
                    [artist, album || title, "album"].filter(Boolean).join(" ")
                );
            }
        }

        function restoreSunoPanel() {
            const panel = document.getElementById("selected-track-panel");
            if (!panel) return;
            panel.classList.remove("is-external-context", "is-imports-context");
            const stemsStatus = document.getElementById("selected-track-stems-status");
            const actions = document.getElementById("selected-track-external-actions");
            if (stemsStatus) stemsStatus.style.display = "";
            if (actions) actions.hidden = true;
        }

        function frameForWindow(sourceWindow) {
            for (const frame of frames.values()) {
                if (frame.contentWindow === sourceWindow) return frame;
            }
            return null;
        }

        ensureSidebarAudioIndicators();

        function pauseFramesExcept(sourceWindow) {
            frames.forEach((frame) => {
                if (!frame.contentWindow || frame.contentWindow === sourceWindow) return;
                try {
                    frame.contentWindow.postMessage(
                        { type: "LS_SHELL_PAUSE_AUDIO" },
                        ORIGIN
                    );
                } catch (_) {}
            });
        }

        function pauseParentAudio() {
            document.querySelectorAll("audio").forEach((audio) => {
                if (!audio.paused) {
                    try { audio.pause(); } catch (_) {}
                }
            });
        }

        function ensureFrame(target) {
            let frame = frames.get(target);
            if (frame) return frame;

            frame = document.createElement("iframe");
            frame.className = "ls-shell-screen-frame";
            frame.dataset.shellUrl = target;
            frame.title = sectionFor(target);
            frame.allow = "autoplay";
            frame.src = embeddedUrl(target);
            frame.addEventListener("load", () => {
                if (frame.classList.contains("is-active")) {
                    try {
                        const title = frame.contentDocument?.title;
                        if (title) setViewTitle(title);
                    } catch (_) {}
                }
            });
            host.appendChild(frame);
            frames.set(target, frame);
            return frame;
        }

        function setFrameActive(frame) {
            frames.forEach((item) => {
                item.classList.toggle("is-active", item === frame);
                item.setAttribute(
                    "aria-hidden",
                    item === frame ? "false" : "true"
                );
            });
        }

        function setHistory(target, mode) {
            if (mode === "none") return;
            const current =
                window.location.pathname +
                window.location.search +
                window.location.hash;
            if (current === target) return;
            const method = mode === "replace" ? "replaceState" : "pushState";
            window.history[method](
                { lsShell: true, section: sectionFor(target) },
                "",
                target
            );
        }

        function showLibrary(mode = "push") {
            activeTarget = "";
            document.documentElement.classList.remove("ls-shell-secondary-active");
            document.body.classList.remove("ls-shell-secondary-active");
            setFrameActive(null);
            updateSidebar("suno");
            restoreSunoPanel();
            setViewTitle(libraryTitle);
            setHistory(libraryUrl, mode);
        }

        function showScreen(rawTarget, mode = "push") {
            const target = normalizeTarget(rawTarget);
            if (!target || !isShellRoute(target)) {
                window.location.href = rawTarget;
                return false;
            }
            if (routePath(target) === ROOT_PATH) {
                showLibrary(mode);
                return true;
            }

            const frame = ensureFrame(target);
            activeTarget = target;
            setFrameActive(frame);
            document.documentElement.classList.add("ls-shell-secondary-active");
            document.body.classList.add("ls-shell-secondary-active");
            const section = sectionFor(target);
            updateSidebar(section);
            setSharedPanelMode(section);
            const rememberedSelection = selectedTrackByFrame.get(frame);
            if (rememberedSelection) {
                setSharedPanelSelection(rememberedSelection);
            } else if (section === "my-library" || section === "playlists") {
                setSharedPanelSelection({
                    title: "Izvēlies dziesmu",
                    artist: section === "my-library" ? "My Library" : "Playlists",
                });
            }
            setHistory(target, mode);
            try {
                const title = frame.contentDocument?.title;
                if (title) setViewTitle(title);
            } catch (_) {}
            return true;
        }

        window.LSShellNavigate = (rawUrl) => showScreen(rawUrl, "push");
        window.LSRestartBackendFromShortcut = () => triggerBackendRestartButton();

        document.addEventListener("keydown", (event) => {
            if (!isBackendRestartShortcut(event)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            triggerBackendRestartButton();
        }, true);

        document.addEventListener("click", (event) => {
            if (!isPlainPrimaryClick(event)) return;
            const anchor = event.target?.closest?.("a[href]");
            if (!anchor) return;
            if (anchor.hasAttribute("download")) return;
            const targetAttr = String(anchor.getAttribute("target") || "").trim();
            if (targetAttr && targetAttr !== "_self") return;
            const target = normalizeTarget(anchor.href);
            if (!target || !isShellRoute(target)) return;

            if (
                routePath(target) === ROOT_PATH &&
                !document.documentElement.classList.contains(
                    "ls-shell-secondary-active"
                )
            ) {
                return;
            }

            event.preventDefault();
            showScreen(target, "push");
        }, true);

        document.addEventListener("play", (event) => {
            if (!(event.target instanceof HTMLMediaElement)) return;
            pauseFramesExcept(null);
            setPlaybackState(
                true,
                String(event.target.dataset.lsSection || "suno"),
                mediaPlaybackMetadata(event.target)
            );
        }, true);

        document.addEventListener("pause", (event) => {
            if (!(event.target instanceof HTMLMediaElement)) return;
            setPlaybackState(false, "", {});
        }, true);

        document.addEventListener("ended", (event) => {
            if (!(event.target instanceof HTMLMediaElement)) return;
            setPlaybackState(false, "", {});
        }, true);

        window.addEventListener("message", (event) => {
            if (event.origin !== ORIGIN || !event.data) return;
            if (event.data.type === "LS_SHELL_NAVIGATE") {
                showScreen(event.data.url || ROOT_PATH, "push");
                return;
            }
            if (event.data.type === "LS_SHELL_AUDIO_PLAY") {
                pauseParentAudio();
                pauseFramesExcept(event.source || null);
                return;
            }
            if (event.data.type === "LS_SHELL_SELECTED_TRACK") {
                const frame = frameForWindow(event.source || null);
                const item = event.data.track && typeof event.data.track === "object"
                    ? event.data.track : {};
                if (frame) selectedTrackByFrame.set(frame, item);
                if (frame?.classList.contains("is-active")) setSharedPanelSelection(item);
                return;
            }
            if (event.data.type === "LS_SHELL_EXTERNAL_PLAY") {
                const player = window.LS?.player;
                const items = Array.isArray(event.data.items) ? event.data.items : [];
                const index = Number(event.data.index || 0);
                if (player && typeof player.loadExternalQueue === "function" && items.length) {
                    const frame = frameForWindow(event.source || null);
                    const item = items[Math.max(0, Math.min(items.length - 1, index))] || {};
                    if (frame) selectedTrackByFrame.set(frame, item);
                    if (frame?.classList.contains("is-active")) setSharedPanelSelection(item);
                    player.loadExternalQueue(items, index, true);
                }
                return;
            }
            if (event.data.type === "LS_SHELL_RESTART_BACKEND") {
                triggerBackendRestartButton();
            }
        });

        window.addEventListener("popstate", () => {
            const target = normalizeTarget(window.location.href);
            if (!target || routePath(target) === ROOT_PATH) {
                showLibrary("none");
            } else if (isSecondaryRoute(target)) {
                showScreen(target, "none");
            }
        });

        if (requestedOpen) {
            const target = normalizeTarget(requestedOpen);
            if (target && isSecondaryRoute(target)) {
                showScreen(target, "replace");
            }
        }
    }

    function boot() {
        if (window.self !== window.top) {
            installEmbeddedShell();
            return;
        }
        if (document.body?.id === "ls-library") {
            installParentShell();
            return;
        }
        redirectStandaloneSecondary();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
        boot();
    }
})();
