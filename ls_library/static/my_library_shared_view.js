(() => {
    if (window.LSMyLibrarySelectionView) return;

    function shellNavigate(url) {
        if (typeof window.LSShellNavigate === "function") {
            const handled = window.LSShellNavigate(url);
            if (handled !== false) return;
        }
        window.location.href = url;
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

    window.LSMyLibrarySelectionView = { init };
})();
