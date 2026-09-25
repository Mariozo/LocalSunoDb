(() => {
    const table = document.getElementById("tracks-table");
    const tbody = table ? table.querySelector("tbody") : null;
    const tableWrap = table ? table.closest(".table-wrap") : null;
    const scrollRoot = table ? table.closest("main") : null;
    const sentinel = document.getElementById("library-lazy-sentinel");
    const resultCount = document.getElementById("ls-filter-result-count");
    if (!table || !tbody || !tableWrap || !sentinel) { return; }

    try {
        sessionStorage.setItem("ls.library.returnUrl", window.location.pathname + window.location.search);
    } catch (_) {}

    const BATCH_SIZE = 32;
    const PREFETCH_MARGIN_PX = 320;
    let nextCursor = "";
    let loadedCount = 0;
    let hasMore = true;
    let loading = false;
    let failed = false;
    let observer = null;

    function setSentinelText(text, state) {
        sentinel.dataset.state = state || "idle";
        const label = sentinel.querySelector(".show-more-info");
        if (label) { label.textContent = text || ""; }
    }

    function baseParams() {
        const params = new URLSearchParams(window.location.search);
        params.delete("rows");
        params.delete("limit");
        params.delete("db_refresh");
        params.delete("offset");
        params.delete("cursor");
        params.delete("index_start");
        params.delete("batch");
        return params;
    }

    function buildBatchUrl() {
        const params = baseParams();
        if (nextCursor) { params.set("cursor", nextCursor); }
        params.set("index_start", String(loadedCount));
        params.set("batch", String(BATCH_SIZE));
        return "/library-rows?" + params.toString();
    }

    function buildCountUrl() {
        return "/library-count?" + baseParams().toString();
    }

    function appendRowsHtml(html) {
        const markup = String(html || "");
        if (!markup) { return []; }
        const template = document.createElement("template");
        template.innerHTML = markup;
        const newRows = Array.from(template.content.querySelectorAll("tr"));
        tbody.appendChild(template.content);
        return newRows;
    }

    function showEmptyState() {
        if (tbody.querySelector("tr")) { return; }
        const row = document.createElement("tr");
        row.innerHTML = '<td colspan="9" class="empty">No active results found.</td>';
        tbody.appendChild(row);
    }

    function notifyRowsAdded(loaded, rows) {
        document.dispatchEvent(new CustomEvent("ls-library-rows-added", {
            detail: {
                loaded: Number(loaded || 0),
                loadedCount,
                hasMore,
                rows: Array.isArray(rows) ? rows : []
            }
        }));
        if (typeof applyVisibleRows === "function") {
            applyVisibleRows();
        }
    }

    async function loadResultCount() {
        if (!resultCount) { return; }
        resultCount.dataset.state = "loading";
        resultCount.textContent = "… tracks";
        try {
            const response = await fetch(buildCountUrl(), {
                cache: "no-store",
                headers: { "Accept": "application/json" }
            });
            const payload = await response.json();
            if (!response.ok || !payload || payload.ok !== true) {
                throw new Error("Library count failed");
            }
            resultCount.textContent = String(Number(payload.total || 0)) + " tracks";
            resultCount.dataset.state = "ready";
        } catch (_) {
            resultCount.textContent = "— tracks";
            resultCount.dataset.state = "error";
        }
    }

    async function loadNextBatch() {
        if (loading || !hasMore) { return; }
        loading = true;
        failed = false;
        setSentinelText("Ielādē dziesmas…", "loading");
        try {
            const response = await fetch(buildBatchUrl(), {
                cache: "no-store",
                headers: { "Accept": "application/json" }
            });
            const payload = await response.json();
            if (!response.ok || !payload || payload.ok !== true) {
                throw new Error(payload && payload.error ? payload.error : "Library lazy load failed");
            }

            const rows = appendRowsHtml(payload.html);
            const loaded = Math.max(0, Number(payload.loaded || 0));
            loadedCount += loaded;
            nextCursor = String(payload.next_cursor || "");
            hasMore = Boolean(payload.has_more && nextCursor);
            notifyRowsAdded(loaded, rows);

            if (!hasMore) {
                showEmptyState();
                setSentinelText("", "done");
                sentinel.hidden = true;
            } else {
                setSentinelText("", "idle");
                sentinel.hidden = false;
            }
        } catch (error) {
            failed = true;
            setSentinelText("Neizdevās ielādēt. Klikšķini, lai mēģinātu vēlreiz.", "error");
            sentinel.hidden = false;
            try { console.error("LocalSunoDb Library lazy load failed", error); } catch (_) {}
        } finally {
            loading = false;
        }
    }

    function startObserver() {
        if (observer || !hasMore) { return; }
        observer = new IntersectionObserver((entries) => {
            if (entries.some((entry) => entry.isIntersecting)) {
                loadNextBatch();
            }
        }, {
            // The Library's vertical scrollbar belongs to <main>. The sentinel
            // is a sibling after .table-wrap but remains inside that scroll root.
            root: scrollRoot,
            rootMargin: PREFETCH_MARGIN_PX + "px 0px",
            threshold: 0.01
        });
        observer.observe(sentinel);
    }

    async function initialLoad() {
        loadResultCount();
        await loadNextBatch();
        startObserver();
    }

    sentinel.addEventListener("click", () => {
        if (failed && !loading) { loadNextBatch(); }
    });

    window.LSLibraryLoadNextBatch = loadNextBatch;
    window.LSLibraryLazyState = () => ({
        nextCursor,
        loadedCount,
        hasMore,
        loading,
        failed,
        batchSize: BATCH_SIZE
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialLoad, { once: true });
    } else {
        initialLoad();
    }

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted || tbody.querySelector("tr.track-row")) { return; }
        nextCursor = "";
        loadedCount = 0;
        hasMore = true;
        loading = false;
        failed = false;
        tbody.replaceChildren();
        sentinel.hidden = false;
        initialLoad();
    });
})();
