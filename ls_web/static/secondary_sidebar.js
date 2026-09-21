(() => {
            const collapseKey = "ls_suno_sidebar_collapsed";
            const button = document.getElementById("ls-sidebar-collapse-btn");

            function applyCollapsed(collapsed, persist=false) {
                const isCollapsed = !!collapsed;
                document.documentElement.classList.toggle("ls-sidebar-collapsed", isCollapsed);
                document.body.classList.toggle("ls-sidebar-collapsed", isCollapsed);
                if (button) {
                    button.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
                    button.setAttribute("aria-label", isCollapsed ? "Open navigation panel" : "Close navigation panel");
                    button.title = isCollapsed ? "Open navigation panel" : "Close navigation panel";
                }
                if (persist) {
                    try {
                        localStorage.setItem(collapseKey, isCollapsed ? "1" : "0");
                    } catch (error) {}
                }
            }

            let startsCollapsed = false;
            try {
                startsCollapsed = localStorage.getItem(collapseKey) === "1";
            } catch (error) {}
            applyCollapsed(startsCollapsed, false);

            if (button) {
                button.addEventListener("click", () => {
                    const next = !document.documentElement.classList.contains("ls-sidebar-collapsed");
                    applyCollapsed(next, true);
                });
            }

            // Keep the Library DOM alive while Imports is open.  Imports is shown
            // in a same-origin full-window iframe, so returning to Library does not
            // issue a new GET / request and does not rebuild the 5 MB Library page.
            const importsLink = document.querySelector('.header-tabs a[title="Imports"]');
            const libraryLink = document.querySelector('.header-tabs a[title="Suno Library"]');
            const isEmbeddedImports = window.self !== window.top && window.location.pathname === "/downloader";
            let importsOverlay = null;
            let importsPreviousTitle = "";
            let importsPreviousOverflow = "";

            function isPlainPrimaryClick(event) {
                return event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey;
            }

            function withEmbeddedFlag(rawUrl) {
                try {
                    const url = new URL(rawUrl || "/downloader", window.location.href);
                    url.searchParams.set("ls_embedded", "1");
                    return url.pathname + url.search + url.hash;
                } catch (error) {
                    return "/downloader?ls_embedded=1";
                }
            }

            function closeImportsOverlay(fromHistory=false) {
                if (!importsOverlay) { return; }
                const overlay = importsOverlay;
                importsOverlay = null;
                overlay.remove();
                document.documentElement.classList.remove("ls-imports-overlay-open");
                document.body.classList.remove("ls-imports-overlay-open");
                document.body.style.overflow = importsPreviousOverflow;
                if (importsPreviousTitle) {
                    document.title = importsPreviousTitle;
                }
                if (!fromHistory && window.history.state && window.history.state.lsImportsOverlay) {
                    window.history.back();
                }
            }

            function openImportsOverlay(rawUrl) {
                if (importsOverlay) { return; }
                importsPreviousTitle = document.title;
                importsPreviousOverflow = document.body.style.overflow || "";

                const overlay = document.createElement("div");
                overlay.id = "ls-imports-overlay";
                overlay.setAttribute("role", "dialog");
                overlay.setAttribute("aria-label", "Imports");
                Object.assign(overlay.style, {
                    position: "fixed",
                    inset: "0",
                    zIndex: "2147483000",
                    background: "#001f16",
                    margin: "0",
                    padding: "0",
                    border: "0",
                });

                const frame = document.createElement("iframe");
                frame.id = "ls-imports-overlay-frame";
                frame.title = "Imports";
                frame.src = withEmbeddedFlag(rawUrl);
                Object.assign(frame.style, {
                    display: "block",
                    width: "100%",
                    height: "100%",
                    margin: "0",
                    padding: "0",
                    border: "0",
                    background: "#001f16",
                });
                frame.addEventListener("load", () => {
                    try {
                        const childTitle = frame.contentDocument && frame.contentDocument.title;
                        if (childTitle) { document.title = childTitle; }
                    } catch (error) {}
                });

                overlay.appendChild(frame);
                document.body.appendChild(overlay);
                importsOverlay = overlay;
                document.documentElement.classList.add("ls-imports-overlay-open");
                document.body.classList.add("ls-imports-overlay-open");
                document.body.style.overflow = "hidden";

                const currentState = Object.assign({}, window.history.state || {});
                currentState.lsImportsOverlay = true;
                currentState.lsLibraryUrl = window.location.href;
                window.history.pushState(currentState, "", "/downloader");
            }

            if (window.location.pathname === "/" && importsLink && window.self === window.top) {
                importsLink.addEventListener("click", (event) => {
                    if (!isPlainPrimaryClick(event)) { return; }
                    event.preventDefault();
                    openImportsOverlay(importsLink.getAttribute("href") || "/downloader");
                });
            }

            if (isEmbeddedImports && libraryLink) {
                libraryLink.addEventListener("click", (event) => {
                    if (!isPlainPrimaryClick(event)) { return; }
                    event.preventDefault();
                    try {
                        window.parent.postMessage({type: "LS_CLOSE_IMPORTS"}, window.location.origin);
                    } catch (error) {}
                });
            }

            if (window.self === window.top) {
                window.addEventListener("message", (event) => {
                    if (event.origin !== window.location.origin) { return; }
                    if (!event.data || event.data.type !== "LS_CLOSE_IMPORTS") { return; }
                    closeImportsOverlay(false);
                });
                window.addEventListener("popstate", () => {
                    if (importsOverlay && !(window.history.state && window.history.state.lsImportsOverlay)) {
                        closeImportsOverlay(true);
                    }
                });
            }

            const settingsButton = document.getElementById("secondary-settings-btn");
            if (settingsButton) {
                settingsButton.addEventListener("click", () => {
                    const downloaderSettings = document.getElementById("downloader-settings-modal");
                    if (downloaderSettings) {
                        downloaderSettings.classList.add("open");
                        downloaderSettings.setAttribute("aria-hidden", "false");
                    } else {
                        window.location.href = String(settingsButton.dataset.sunoViewUrl || "/");
                    }
                });
            }
        })();
