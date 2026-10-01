(() => {
    if (window.LSMyLibrarySelectionView) return;

    function shellNavigate(url) {
        if (typeof window.LSShellNavigate === "function") {
            const handled = window.LSShellNavigate(url);
            if (handled !== false) return;
        }
        window.location.href = url;
    }

    let panelSnapshot = null;

    function snapshotPanel() {
        if (panelSnapshot) return;
        const panel = document.getElementById("selected-track-panel");
        if (!panel) return;
        panelSnapshot = {
            title: document.getElementById("selected-track-panel-title")?.textContent || "",
            meta: document.getElementById("selected-track-panel-meta")?.textContent || "",
            coverSrc: document.getElementById("selected-track-panel-cover")?.getAttribute("src") || "",
            coverDisplay: document.getElementById("selected-track-panel-cover")?.style.display || "",
            placeholderDisplay: document.getElementById("selected-track-panel-cover-placeholder")?.style.display || "",
            localStatus: document.getElementById("selected-track-local-status")?.textContent || "",
            stemsStatus: document.getElementById("selected-track-stems-status")?.textContent || "",
        };
    }

    function ensureLocalActions() {
        const panel = document.getElementById("selected-track-panel");
        if (!panel) return null;
        let actions = panel.querySelector(".ls-my-library-panel-actions");
        if (actions) return actions;
        const status = panel.querySelector(".selected-track-status-row");
        actions = document.createElement("div");
        actions.className = "selected-track-panel-actions ls-my-library-panel-actions";
        actions.innerHTML =
            '<a data-role="track" href="https://www.google.com/" target="_blank" rel="noopener noreferrer">Google: dziesma</a>' +
            '<a data-role="album" href="https://www.google.com/" target="_blank" rel="noopener noreferrer">Google: albums</a>';
        status?.insertAdjacentElement("afterend", actions);
        return actions;
    }

    function selectLocalTrack(row) {
        if (!row) return;
        snapshotPanel();
        const panel = document.getElementById("selected-track-panel");
        const title = String(row.dataset.title || "").trim() || "Selected track";
        const artist = String(row.dataset.artist || "").trim();
        const album = String(row.dataset.album || "").trim();
        const year = String(row.dataset.year || "").trim();
        const genre = String(row.dataset.genre || "").trim();
        const format = String(row.dataset.format || "").trim();
        const duration = String(row.dataset.duration || "").trim();
        const cover = String(row.dataset.playerCover || "").trim();

        document.querySelectorAll(".music-track-row.selected-track-current")
            .forEach((item) => item.classList.remove("selected-track-current"));
        row.classList.add("selected-track-current");

        if (panel) panel.classList.add("ls-my-library-track-context");
        const titleNode = document.getElementById("selected-track-panel-title");
        const metaNode = document.getElementById("selected-track-panel-meta");
        const coverNode = document.getElementById("selected-track-panel-cover");
        const placeholder = document.getElementById("selected-track-panel-cover-placeholder");
        const localStatus = document.getElementById("selected-track-local-status");
        const stemsStatus = document.getElementById("selected-track-stems-status");
        if (titleNode) titleNode.textContent = title;
        if (metaNode) metaNode.textContent = [artist, album, year, genre].filter(Boolean).join(" · ");
        if (localStatus) localStatus.textContent = [format, duration].filter(Boolean).join(" · ") || "Local";
        if (stemsStatus) stemsStatus.textContent = "Stems: none";
        if (coverNode && placeholder) {
            if (cover) {
                coverNode.src = cover;
                coverNode.style.display = "block";
                placeholder.style.display = "none";
            } else {
                coverNode.removeAttribute("src");
                coverNode.style.display = "none";
                placeholder.style.display = "flex";
            }
        }

        const actions = ensureLocalActions();
        if (actions) {
            const trackLink = actions.querySelector('[data-role="track"]');
            const albumLink = actions.querySelector('[data-role="album"]');
            const trackQuery = [artist, title, "song"].filter(Boolean).join(" ");
            const albumQuery = [artist, album, "album"].filter(Boolean).join(" ");
            if (trackLink) trackLink.href = "https://www.google.com/search?q=" + encodeURIComponent(trackQuery || title);
            if (albumLink) albumLink.href = "https://www.google.com/search?q=" + encodeURIComponent(albumQuery || album || artist);
        }

        document.dispatchEvent(new CustomEvent("ls-selected-track-changed", {
            detail: { trackId: String(row.dataset.trackId || ""), source: "my-library" }
        }));
    }

    function leave() {
        const panel = document.getElementById("selected-track-panel");
        panel?.classList.remove("ls-my-library-track-context");
        document.querySelector(".ls-my-library-panel-actions")?.remove();
        document.querySelectorAll(".music-track-row.selected-track-current")
            .forEach((row) => row.classList.remove("selected-track-current"));
        if (!panelSnapshot) return;
        const titleNode = document.getElementById("selected-track-panel-title");
        const metaNode = document.getElementById("selected-track-panel-meta");
        const coverNode = document.getElementById("selected-track-panel-cover");
        const placeholder = document.getElementById("selected-track-panel-cover-placeholder");
        const localStatus = document.getElementById("selected-track-local-status");
        const stemsStatus = document.getElementById("selected-track-stems-status");
        if (titleNode) titleNode.textContent = panelSnapshot.title;
        if (metaNode) metaNode.textContent = panelSnapshot.meta;
        if (localStatus) localStatus.textContent = panelSnapshot.localStatus;
        if (stemsStatus) stemsStatus.textContent = panelSnapshot.stemsStatus;
        if (coverNode && placeholder) {
            if (panelSnapshot.coverSrc) coverNode.setAttribute("src", panelSnapshot.coverSrc);
            else coverNode.removeAttribute("src");
            coverNode.style.display = panelSnapshot.coverDisplay;
            placeholder.style.display = panelSnapshot.placeholderDisplay;
        }
        panelSnapshot = null;
    }

    function init(root = document) {
        const view = root.querySelector?.("#ls-my-library-view");
        if (!view || view.dataset.lsMounted === "1") return false;
        view.dataset.lsMounted = "1";

        const query = String(view.dataset.query || "");
        const selectedDb = String(view.dataset.selectedDb || "");
        const searchForm = root.querySelector("#my-library-search-form");
        const dbSelect = root.querySelector("#db-select");
        const modal = root.querySelector("#new-db-modal");

        const openModal = () => {
            if (!modal) return;
            modal.classList.add("open");
            modal.setAttribute("aria-hidden", "false");
        };
        const closeModal = () => {
            if (!modal) return;
            modal.classList.remove("open");
            modal.setAttribute("aria-hidden", "true");
        };

        searchForm?.addEventListener("submit", (event) => {
            event.preventDefault();
            const data = new FormData(searchForm);
            const params = new URLSearchParams();
            for (const [key, value] of data.entries()) {
                if (typeof value === "string" && value.trim() !== "") {
                    params.set(key, value);
                }
            }
            shellNavigate("/my-library" + (params.toString() ? "?" + params.toString() : ""));
        });

        dbSelect?.addEventListener("change", () => {
            const value = String(dbSelect.value || "").trim();
            const params = new URLSearchParams();
            if (value) params.set("db", value);
            if (query) params.set("q", query);
            shellNavigate("/my-library" + (params.toString() ? "?" + params.toString() : ""));
        });

        root.querySelector("#grid-view")?.addEventListener("click", () => {
            const params = new URLSearchParams();
            if (selectedDb) params.set("db", selectedDb);
            if (query) params.set("q", query);
            shellNavigate("/my-library" + (params.toString() ? "?" + params.toString() : ""));
        });

        root.querySelector("#list-view")?.addEventListener("click", () => {
            const params = new URLSearchParams();
            if (selectedDb) params.set("db", selectedDb);
            if (query) params.set("q", query);
            params.set("view", "list");
            shellNavigate("/my-library?" + params.toString());
        });

        root.querySelector("#new-db")?.addEventListener("click", openModal);
        root.querySelector("#empty-new-db")?.addEventListener("click", openModal);
        root.querySelector("#modal-close")?.addEventListener("click", closeModal);
        root.querySelector("#modal-cancel")?.addEventListener("click", closeModal);
        modal?.addEventListener("click", (event) => {
            if (event.target === modal) closeModal();
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && modal?.classList.contains("open")) {
                closeModal();
            }
        }, { once: true });

        root.querySelector("#choose-root")?.addEventListener("click", async () => {
            const input = root.querySelector("#music-db-root");
            const current = String(input?.value || "");
            const response = await fetch(
                "/choose-music-db-root?initial=" + encodeURIComponent(current),
                { cache: "no-store" }
            );
            const data = await response.json();
            if (data.ok && data.path && input) input.value = data.path;
        });

        const albumTable = root.querySelector("#my-library-track-table");
        const playAll = root.querySelector("#my-library-play-all");
        const albumSearch = root.querySelector("#my-library-album-search");

        if (albumTable) {
            albumTable.addEventListener("click", (event) => {
                const row = event.target.closest(".music-track-row");
                if (!row || !albumTable.contains(row)) return;
                selectLocalTrack(row);

                const playButton = event.target.closest(".music-row-play");
                if (!playButton) return;
                event.preventDefault();
                event.stopPropagation();
                const player = window.LS && window.LS.player ? window.LS.player : null;
                if (player && typeof player.loadFromButton === "function") {
                    player.loadFromButton(playButton, true);
                    player.focusMainPlay?.();
                }
            });

            playAll?.addEventListener("click", () => {
                const first = Array.from(albumTable.querySelectorAll(".music-track-row"))
                    .find((row) => !row.hidden && !row.classList.contains("row-hidden"));
                first?.querySelector(".music-row-play")?.click();
            });

            albumSearch?.addEventListener("input", () => {
                const needle = String(albumSearch.value || "").trim().toLocaleLowerCase();
                albumTable.querySelectorAll(".music-track-row").forEach((row) => {
                    const haystack = String(row.textContent || "").toLocaleLowerCase();
                    const visible = !needle || haystack.includes(needle);
                    row.hidden = !visible;
                    row.classList.toggle("row-hidden", !visible);
                });
            });
        }

        root.querySelector("#music-db-import")?.addEventListener("click", async () => {
            const status = root.querySelector("#music-db-status");
            const button = root.querySelector("#music-db-import");
            const body = new URLSearchParams({
                name: String(root.querySelector("#music-db-name")?.value || ""),
                root_folder: String(root.querySelector("#music-db-root")?.value || ""),
                default_genre: String(root.querySelector("#music-db-genre")?.value || ""),
            });
            if (status) {
                status.className = "status";
                status.textContent = "Skenēju mūzikas mapi…";
            }
            if (button) button.disabled = true;
            try {
                const response = await fetch("/music-db-import", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString(),
                });
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "DB izveide neizdevās.");
                }
                if (status) {
                    status.className = "status ok";
                    status.textContent =
                        "Gatavs: " + data.track_count +
                        " dziesmas · pievienotas " + data.added +
                        " · atjaunotas " + data.updated + ".";
                }
                window.setTimeout(() => {
                    shellNavigate("/my-library?db=" + encodeURIComponent(data.name));
                }, 350);
            } catch (error) {
                if (status) {
                    status.className = "status error";
                    status.textContent = String(error?.message || error);
                }
            } finally {
                if (button) button.disabled = false;
            }
        });

        return true;
    }

    window.LSMyLibrarySelectionView = { init, leave, selectLocalTrack };
})();
