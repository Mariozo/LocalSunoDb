        table.addEventListener("click", (event) => {
            const playButton = event.target.closest(".ls-cover-play-btn");
            if (playButton && table.contains(playButton)) {
                event.preventDefault();
                event.stopPropagation();

                // Linked PC audio keeps the LocalSunoDb player. Suno-only rows
                // use the exact same Suno.com destination as the track title.
                const hasLocalAudio = String(playButton.dataset.hasLocalAudio || "false") === "true";
                if (!hasLocalAudio) {
                    const trackId = String(playButton.dataset.trackId || "").trim();
                    const sunoUrl = String(playButton.dataset.sunoUrl || "").trim();
                    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trackId);
                    const playUrl = isUuid
                        ? "https://suno.com/embed/" + encodeURIComponent(trackId) + "?auto_play=true&autoplay=1"
                        : sunoUrl;
                    if (playUrl) {
                        if (typeof openUrlInNewTab === "function") {
                            openUrlInNewTab(playUrl);
                        } else {
                            const link = document.createElement("a");
                            link.href = playUrl;
                            link.target = "_blank";
                            link.rel = "noopener";
                            document.body.appendChild(link);
                            link.click();
                            link.remove();
                        }
                    }
                    return;
                }

                autoplayStartedFromPlayButton = true;
                if (lsGlobalPlayer) {
                    lsGlobalPlayer.loadFromButton(playButton, true);
                    if (typeof lsGlobalPlayer.focusMainPlay === "function") {
                        lsGlobalPlayer.focusMainPlay();
                    }
                }
                return;
            }

            const statusMarker = event.target.closest(".ls-play-status-marker");
            if (statusMarker && table.contains(statusMarker)) {
                event.preventDefault();
                event.stopPropagation();
                const markerPlayButton = statusMarker
                    .closest(".ls-track-cover-control")
                    ?.querySelector(".ls-cover-play-btn");
                if (markerPlayButton) { markerPlayButton.click(); }
            }
        });

        table.querySelectorAll(".ls-track-select-control").forEach((control) => {
            control.addEventListener("click", (event) => {
                // Selection is independent from cover playback.
                event.stopPropagation();
            });
        });

        // MiniEdit: restore rare full-size Cover access without changing the
        // primary left-click Play/Pause behavior. Right-clicking a valid row
        // cover opens one small context menu that uses the current resolved
        // data-large-cover URL. Failed/placeholder covers keep the browser's
        // normal context menu and never offer a stale image URL.
        let lsCoverContextMenu = null;

        function closeLsCoverContextMenu() {
            if (!lsCoverContextMenu) { return; }
            lsCoverContextMenu.classList.add("hidden");
            lsCoverContextMenu.removeAttribute("data-cover-url");
            lsCoverContextMenu.style.visibility = "";
        }

        function ensureLsCoverContextMenu() {
            if (lsCoverContextMenu && document.body.contains(lsCoverContextMenu)) {
                return lsCoverContextMenu;
            }

            const menu = document.createElement("div");
            menu.className = "row-menu ls-cover-context-menu hidden";
            menu.setAttribute("role", "menu");
            menu.setAttribute("aria-label", "Cover image actions");

            const openItem = document.createElement("button");
            openItem.type = "button";
            openItem.className = "row-menu-item";
            openItem.textContent = "Atvērt vāciņa attēlu jaunā cilnē";
            openItem.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                const url = String(menu.dataset.coverUrl || "").trim();
                closeLsCoverContextMenu();
                if (!url) { return; }

                const link = document.createElement("a");
                link.href = url;
                link.target = "_blank";
                link.rel = "noopener";
                link.style.display = "none";
                document.body.appendChild(link);
                link.click();
                link.remove();
            });

            menu.appendChild(openItem);
            document.body.appendChild(menu);
            lsCoverContextMenu = menu;
            return menu;
        }

        function positionLsCoverContextMenu(menu, clientX, clientY) {
            const viewportMargin = 8;
            const gap = 2;
            menu.classList.remove("hidden");
            menu.style.visibility = "hidden";
            menu.style.left = "0px";
            menu.style.top = "0px";
            menu.style.right = "auto";
            menu.style.bottom = "auto";

            const rect = menu.getBoundingClientRect();
            const width = rect.width || menu.offsetWidth || 220;
            const height = rect.height || menu.offsetHeight || 0;
            const left = Math.max(
                viewportMargin,
                Math.min(Number(clientX || 0) + gap, window.innerWidth - width - viewportMargin)
            );
            const top = Math.max(
                viewportMargin,
                Math.min(Number(clientY || 0) + gap, window.innerHeight - height - viewportMargin)
            );

            menu.style.left = Math.round(left) + "px";
            menu.style.top = Math.round(top) + "px";
            menu.style.visibility = "visible";
        }

        table.addEventListener("contextmenu", (event) => {
            const coverControl = event.target.closest(".ls-track-cover-control");
            if (!coverControl || !table.contains(coverControl)) { return; }
            if (event.target.closest(".ls-track-select-control, .ls-play-status-marker")) {
                return;
            }

            const thumbLink = coverControl.querySelector(".thumb-link");
            const coverUrl = thumbLink && !thumbLink.classList.contains("thumb-error")
                ? String(thumbLink.dataset.largeCover || "").trim()
                : "";
            if (!coverUrl) {
                closeLsCoverContextMenu();
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            if (typeof closeRowMenus === "function") {
                closeRowMenus();
            } else {
                closeLsCoverContextMenu();
            }

            const menu = ensureLsCoverContextMenu();
            menu.dataset.coverUrl = coverUrl;
            positionLsCoverContextMenu(menu, event.clientX, event.clientY);
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeLsCoverContextMenu();
            }
        });

