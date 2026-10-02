(() => {
    if (window.LSSharedViews) return;

    const qs = (root, selector) => root?.querySelector?.(selector) || null;
    const qsa = (root, selector) => Array.from(root?.querySelectorAll?.(selector) || []);

    function navigate(url) {
        if (typeof window.LSShellNavigate === "function") {
            const handled = window.LSShellNavigate(url);
            if (handled !== false) return;
        }
        window.location.href = url;
    }

    async function post(path, values = {}) {
        const body = new URLSearchParams();
        Object.entries(values).forEach(([key, value]) => body.set(key, String(value ?? "")));
        const response = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: body.toString(),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || "Operation failed.");
        return data;
    }

    function updatePanelFromRow(row) {
        if (!row) return;
        qsa(document, "[data-ls-player-row].selected-track-current")
            .forEach((item) => item.classList.toggle("selected-track-current", item === row));

        const panel = document.getElementById("selected-track-panel");
        if (!panel) return;

        panel.classList.add("is-shared-track");
        const title = String(row.dataset.title || "Selected track").trim();
        const artist = String(row.dataset.artist || "").trim();
        const album = String(row.dataset.album || "").trim();
        const year = String(row.dataset.year || "").trim();
        const genre = String(row.dataset.genre || "").trim();
        const format = String(row.dataset.format || "").trim();
        const duration = String(row.dataset.duration || "").trim();
        const cover = String(row.dataset.cover || "").trim();

        const titleNode = document.getElementById("selected-track-panel-title");
        const metaNode = document.getElementById("selected-track-panel-meta");
        const coverNode = document.getElementById("selected-track-panel-cover");
        const placeholder = document.getElementById("selected-track-panel-cover-placeholder");
        const localStatus = document.getElementById("selected-track-local-status");
        const stemsStatus = document.getElementById("selected-track-stems-status");
        const actions = document.getElementById("ls-shared-track-actions");

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

        if (actions) {
            actions.hidden = false;
            const trackLink = document.getElementById("ls-shared-google-track");
            const albumLink = document.getElementById("ls-shared-google-album");
            const trackQuery = [artist, title, "song"].filter(Boolean).join(" ");
            const albumQuery = [artist, album, "album"].filter(Boolean).join(" ");
            if (trackLink) trackLink.href = "https://www.google.com/search?q=" + encodeURIComponent(trackQuery || title);
            if (albumLink) albumLink.href = "https://www.google.com/search?q=" + encodeURIComponent(albumQuery || album || artist);
        }
    }

    function clearSharedPanelMode() {
        document.getElementById("selected-track-panel")?.classList.remove("is-shared-track");
        const actions = document.getElementById("ls-shared-track-actions");
        if (actions) actions.hidden = true;
    }

    function playRow(row, autoplay = true) {
        if (!row) return false;
        updatePanelFromRow(row);
        const button = row.querySelector(".ls-cover-play-btn");
        const player = window.LS?.player;
        if (!button || !player || typeof player.loadFromButton !== "function") return false;
        player.loadFromButton(button, autoplay);
        player.focusMainPlay?.();
        return true;
    }

    function applyAlbumTheme(root) {
        const image = qs(root, "#ls-shared-album-cover");
        const hero = qs(root, "#ls-shared-album-hero");
        if (!image || !hero) return;

        const apply = () => {
            if (!image.naturalWidth || !image.naturalHeight) return;
            try {
                const canvas = document.createElement("canvas");
                canvas.width = 40;
                canvas.height = 40;
                const ctx = canvas.getContext("2d", { willReadFrequently: true });
                ctx.drawImage(image, 0, 0, 40, 40);
                const pixels = ctx.getImageData(0, 0, 40, 40).data;
                const buckets = new Map();
                for (let i = 0; i < pixels.length; i += 4) {
                    if (pixels[i + 3] < 180) continue;
                    const r0 = pixels[i], g0 = pixels[i + 1], b0 = pixels[i + 2];
                    const max = Math.max(r0, g0, b0), min = Math.min(r0, g0, b0);
                    const lum = .2126 * r0 + .7152 * g0 + .0722 * b0;
                    if (lum < 24 || (min > 222 && max > 238)) continue;
                    const r = (r0 >> 4) * 16 + 8;
                    const g = (g0 >> 4) * 16 + 8;
                    const b = (b0 >> 4) * 16 + 8;
                    const key = r + "," + g + "," + b;
                    const sat = (max - min) / Math.max(1, max);
                    buckets.set(key, (buckets.get(key) || 0) + 1 + sat * 1.8);
                }
                let picked = [72, 102, 88], score = -1;
                buckets.forEach((value, key) => {
                    if (value > score) {
                        score = value;
                        picked = key.split(",").map(Number);
                    }
                });
                const mix = (a, b, amount) => a.map((value, i) => Math.round(value * (1 - amount) + b[i] * amount));
                const lum = .2126 * picked[0] + .7152 * picked[1] + .0722 * picked[2];
                const light = mix(picked, [255,255,255], lum < 95 ? .30 : .18);
                const dark = light.map((value) => Math.round(value * .80));
                hero.style.setProperty("--ls-album-hero", "rgb(" + light.join(",") + ")");
                hero.style.setProperty("--ls-album-hero-dark", "rgb(" + dark.join(",") + ")");
            } catch (_) {}
        };

        if (image.complete) apply();
        else image.addEventListener("load", apply, { once: true });
    }

    function initMyLibrary(root, view) {
        const selectedDb = String(view.dataset.selectedDb || "");
        const query = String(view.dataset.query || "");
        const form = qs(root, "#ls-shared-my-search-form");

        form?.addEventListener("submit", (event) => {
            event.preventDefault();
            const data = new FormData(form);
            const params = new URLSearchParams();
            for (const [key, value] of data.entries()) {
                if (typeof value === "string" && value.trim()) params.set(key, value);
            }
            navigate("/my-library" + (params.toString() ? "?" + params.toString() : ""));
        });

        qs(root, "#ls-shared-db-select")?.addEventListener("change", (event) => {
            const params = new URLSearchParams();
            if (event.target.value) params.set("db", event.target.value);
            if (query) params.set("q", query);
            navigate("/my-library" + (params.toString() ? "?" + params.toString() : ""));
        });

        qs(root, "#ls-shared-grid-view")?.addEventListener("click", () => {
            const params = new URLSearchParams();
            if (selectedDb) params.set("db", selectedDb);
            if (query) params.set("q", query);
            navigate("/my-library" + (params.toString() ? "?" + params.toString() : ""));
        });

        qs(root, "#ls-shared-list-view")?.addEventListener("click", () => {
            const params = new URLSearchParams();
            if (selectedDb) params.set("db", selectedDb);
            if (query) params.set("q", query);
            params.set("view", "list");
            navigate("/my-library?" + params.toString());
        });

        const modal = document.getElementById("ls-shared-new-db-modal");
        const openModal = () => {
            modal?.classList.add("open");
            modal?.setAttribute("aria-hidden", "false");
        };
        const closeModal = () => {
            modal?.classList.remove("open");
            modal?.setAttribute("aria-hidden", "true");
        };

        qs(root, "#ls-shared-new-db")?.addEventListener("click", openModal);
        qs(root, "#empty-new-db")?.addEventListener("click", openModal);
        document.getElementById("ls-shared-modal-close")?.addEventListener("click", closeModal);
        document.getElementById("ls-shared-modal-cancel")?.addEventListener("click", closeModal);

        document.getElementById("ls-shared-choose-root")?.addEventListener("click", async () => {
            const input = document.getElementById("ls-shared-music-db-root");
            const response = await fetch(
                "/choose-music-db-root?initial=" + encodeURIComponent(String(input?.value || "")),
                { cache: "no-store" }
            );
            const data = await response.json();
            if (data.ok && data.path && input) input.value = data.path;
        });

        document.getElementById("ls-shared-music-db-import")?.addEventListener("click", async () => {
            const status = document.getElementById("ls-shared-music-db-status");
            const button = document.getElementById("ls-shared-music-db-import");
            if (button) button.disabled = true;
            if (status) {
                status.className = "status";
                status.textContent = "Skenēju mūzikas mapi…";
            }
            try {
                const data = await post("/music-db-import", {
                    name: document.getElementById("ls-shared-music-db-name")?.value || "",
                    root_folder: document.getElementById("ls-shared-music-db-root")?.value || "",
                    default_genre: document.getElementById("ls-shared-music-db-genre")?.value || "",
                });
                if (status) {
                    status.className = "status ok";
                    status.textContent = "Gatavs: " + data.track_count + " dziesmas.";
                }
                window.setTimeout(() => navigate("/my-library?db=" + encodeURIComponent(data.name)), 250);
            } catch (error) {
                if (status) {
                    status.className = "status error";
                    status.textContent = String(error?.message || error);
                }
            } finally {
                if (button) button.disabled = false;
            }
        });

        applyAlbumTheme(root);
    }

    function initPlaylist(root, view) {
        const playlistId = String(view.dataset.playlistId || "");
        const pendingTrackId = String(view.dataset.pendingTrackId || "");

        qs(root, "#ls-shared-playlist-search")?.addEventListener("input", (event) => {
            const needle = String(event.target.value || "").trim().toLocaleLowerCase();
            qsa(root, ".playlist-card").forEach((card) => {
                card.hidden = Boolean(needle && !String(card.textContent || "").toLocaleLowerCase().includes(needle));
            });
        });

        qs(root, "#playlist-new-card")?.addEventListener("click", async () => {
            const name = window.prompt("Playlist name");
            if (!name) return;
            try {
                const data = await post("/playlist-create", { name });
                const id = data.playlist?.id;
                if (pendingTrackId && id) {
                    await post("/playlist-add-track", { playlist_id: id, track_id: pendingTrackId });
                }
                if (id) navigate("/playlists?id=" + encodeURIComponent(id));
            } catch (error) {
                window.alert(error.message);
            }
        });

        if (!playlistId) return;

        qs(root, "#playlist-rename")?.addEventListener("click", async () => {
            const current = qs(root, "#playlist-title")?.textContent || "";
            const name = window.prompt("Playlist name", current);
            if (!name || name === current) return;
            try {
                await post("/playlist-rename", { playlist_id: playlistId, name });
                navigate("/playlists?id=" + encodeURIComponent(playlistId));
            } catch (error) {
                window.alert(error.message);
            }
        });

        qs(root, "#playlist-delete")?.addEventListener("click", async () => {
            if (!window.confirm("Delete this playlist? Songs will not be deleted.")) return;
            try {
                await post("/playlist-delete", { playlist_id: playlistId });
                navigate("/playlists");
            } catch (error) {
                window.alert(error.message);
            }
        });

        qs(root, "#ls-shared-playlist-detail-search")?.addEventListener("input", (event) => {
            const needle = String(event.target.value || "").trim().toLocaleLowerCase();
            qsa(root, ".playlist-track-row").forEach((row) => {
                const hidden = Boolean(needle && !String(row.textContent || "").toLocaleLowerCase().includes(needle));
                row.hidden = hidden;
                row.classList.toggle("row-hidden", hidden);
            });
        });

        qsa(root, ".playlist-track-remove").forEach((button) => {
            button.addEventListener("click", async (event) => {
                event.stopPropagation();
                try {
                    await post("/playlist-remove-track", {
                        playlist_id: playlistId,
                        track_id: button.dataset.trackId || "",
                    });
                    button.closest(".playlist-track-row")?.remove();
                    qsa(root, ".playlist-track-row").forEach((row, index) => {
                        const number = row.querySelector(".playlist-track-number");
                        if (number) number.textContent = String(index + 1);
                    });
                } catch (error) {
                    window.alert(error.message);
                }
            });
        });

        let dragged = null;
        const rowsBox = qs(root, "#playlist-tracks");
        rowsBox?.addEventListener("dragstart", (event) => {
            dragged = event.target.closest(".playlist-track-row");
            dragged?.classList.add("dragging");
        });
        rowsBox?.addEventListener("dragover", (event) => {
            event.preventDefault();
            const target = event.target.closest(".playlist-track-row");
            if (!dragged || !target || target === dragged) return;
            const rect = target.getBoundingClientRect();
            rowsBox.insertBefore(dragged, event.clientY > rect.top + rect.height / 2 ? target.nextSibling : target);
        });
        rowsBox?.addEventListener("dragend", async () => {
            if (!dragged) return;
            dragged.classList.remove("dragging");
            dragged = null;
            const ids = qsa(rowsBox, ".playlist-track-row").map((row) => row.dataset.trackId || "");
            try {
                await post("/playlist-reorder", { playlist_id: playlistId, track_ids: ids.join(",") });
            } catch (error) {
                window.alert(error.message);
            }
        });
    }

    function init(root) {
        const view = qs(root, "#ls-shared-view");
        if (!view || view.dataset.lsMounted === "1") return false;
        view.dataset.lsMounted = "1";

        const title = String(view.dataset.viewTitle || "").trim();
        if (title) document.title = title;

        root.addEventListener("click", (event) => {
            const row = event.target.closest("[data-ls-player-row]");
            if (!row || !root.contains(row)) return;
            updatePanelFromRow(row);

            const playButton = event.target.closest(".ls-cover-play-btn");
            if (!playButton) return;
            event.preventDefault();
            event.stopPropagation();
            playRow(row, true);
        });

        qs(root, "#ls-shared-play-all")?.addEventListener("click", () => {
            const row = qsa(root, "[data-ls-player-row]").find((item) => !item.hidden && !item.classList.contains("row-hidden"));
            if (row) playRow(row, true);
        });

        qs(root, "#ls-shared-search-in-list")?.addEventListener("input", (event) => {
            const needle = String(event.target.value || "").trim().toLocaleLowerCase();
            qsa(root, "[data-ls-player-row]").forEach((row) => {
                const hidden = Boolean(needle && !String(row.textContent || "").toLocaleLowerCase().includes(needle));
                row.hidden = hidden;
                row.classList.toggle("row-hidden", hidden);
            });
        });

        if (view.dataset.section === "my-library") initMyLibrary(root, view);
        if (view.dataset.section === "playlists") initPlaylist(root, view);
        return true;
    }

    document.addEventListener("ls-track-playback-started", (event) => {
        const source = String(event?.detail?.source || "");
        if (source !== "my-library" && source !== "playlists") return;
        const row = event.detail?.row || document.querySelector(
            '[data-ls-player-row][data-track-id="' + CSS.escape(String(event.detail?.trackId || "")) + '"]'
        );
        if (row) updatePanelFromRow(row);
    });

    document.addEventListener("ls-selected-track-changed", (event) => {
        if (event?.detail?.source === "selection") clearSharedPanelMode();
    });

    window.LSSharedViews = { init, updatePanelFromRow, clearSharedPanelMode };
})();
