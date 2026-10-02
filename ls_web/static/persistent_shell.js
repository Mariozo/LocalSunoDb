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
    const FRAGMENT_PARAM = "ls_fragment";
    const SAME_DOM_PATHS = new Set(["/my-library", "/music-db", "/playlists"]);

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
        url.searchParams.delete(FRAGMENT_PARAM);
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

    function isSameDomRoute(rawUrl) {
        return SAME_DOM_PATHS.has(routePath(rawUrl));
    }

    function fragmentUrl(rawUrl) {
        const url = new URL(rawUrl || ROOT_PATH, ORIGIN);
        if (url.pathname === "/music-db") url.pathname = "/my-library";
        url.searchParams.delete(EMBEDDED_PARAM);
        url.searchParams.delete(SHELL_OPEN_PARAM);
        url.searchParams.set(FRAGMENT_PARAM, "1");
        return url.pathname + url.search;
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

        const libraryMain = document.querySelector("body > main");
        const contentMain = document.createElement("main");
        contentMain.id = "ls-shell-content-main";
        contentMain.hidden = true;
        contentMain.setAttribute("aria-live", "polite");
        if (libraryMain) libraryMain.insertAdjacentElement("afterend", contentMain);

        const frames = new Map();
        let activeTarget = "";
        let sharedAssetsPromise = null;

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

        function ensureSharedAssets() {
            if (sharedAssetsPromise) return sharedAssetsPromise;
            sharedAssetsPromise = new Promise((resolve, reject) => {
                if (!document.getElementById("ls-shared-view-style")) {
                    const link = document.createElement("link");
                    link.id = "ls-shared-view-style";
                    link.rel = "stylesheet";
                    link.href = "/ls-static/ls_web/static/shared_views.css?v=same-dom-1";
                    document.head.appendChild(link);
                }
                if (window.LSSharedViews) {
                    resolve();
                    return;
                }
                const script = document.createElement("script");
                script.id = "ls-shared-view-script";
                script.src = "/ls-static/ls_web/static/shared_views.js?v=same-dom-1";
                script.onload = () => resolve();
                script.onerror = () => reject(new Error("Shared view controller failed to load."));
                document.head.appendChild(script);
            });
            return sharedAssetsPromise;
        }

        function setContentMode(active) {
            if (libraryMain) libraryMain.hidden = Boolean(active);
            contentMain.hidden = !active;
            document.documentElement.classList.toggle("ls-shell-content-active", Boolean(active));
            document.body.classList.toggle("ls-shell-content-active", Boolean(active));
        }

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
                        if (title) document.title = title;
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
            setFrameActive(null);
            setContentMode(false);
            document.documentElement.classList.remove("ls-shell-secondary-active");
            document.body.classList.remove("ls-shell-secondary-active");
            updateSidebar("suno");
            document.title = libraryTitle;
            setHistory(libraryUrl, mode);
        }

        function showFrameScreen(target, mode = "push") {
            setContentMode(false);
            const frame = ensureFrame(target);
            activeTarget = target;
            setFrameActive(frame);
            document.documentElement.classList.add("ls-shell-secondary-active");
            document.body.classList.add("ls-shell-secondary-active");
            updateSidebar(sectionFor(target));
            setHistory(target, mode);
            try {
                const title = frame.contentDocument?.title;
                if (title) document.title = title;
            } catch (_) {}
            return true;
        }

        async function showSameDomScreen(target, mode = "push") {
            activeTarget = target;
            setFrameActive(null);
            setContentMode(true);
            document.documentElement.classList.remove("ls-shell-secondary-active");
            document.body.classList.remove("ls-shell-secondary-active");
            updateSidebar(sectionFor(target));
            setHistory(target, mode);
            contentMain.innerHTML = '<div style="padding:24px;color:var(--ls-suno-muted)">Loading…</div>';

            try {
                await ensureSharedAssets();
                const response = await fetch(fragmentUrl(target), {
                    cache: "no-store",
                    headers: { "X-LS-View": "fragment" },
                });
                if (!response.ok) throw new Error("HTTP " + response.status);
                const html = await response.text();
                if (activeTarget !== target) return true;
                contentMain.innerHTML = html;
                window.LSSharedViews?.init(contentMain);
            } catch (error) {
                if (activeTarget === target) {
                    contentMain.innerHTML =
                        '<div style="padding:24px;color:#ff9b9b">View load failed: ' +
                        String(error?.message || error) + '</div>';
                }
            }
            return true;
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
            if (isSameDomRoute(target)) {
                showSameDomScreen(target, mode);
                return true;
            }
            return showFrameScreen(target, mode);
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
                !document.documentElement.classList.contains("ls-shell-secondary-active") &&
                !document.documentElement.classList.contains("ls-shell-content-active")
            ) {
                return;
            }

            event.preventDefault();
            showScreen(target, "push");
        }, true);

        document.addEventListener("play", (event) => {
            if (!(event.target instanceof HTMLMediaElement)) return;
            pauseFramesExcept(null);
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
