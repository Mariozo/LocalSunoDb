(function () {
    "use strict";

    const finder = document.getElementById("finder-search-box");
    const input = document.getElementById("finder-search-input");
    const closeButton = document.getElementById("finder-search-close");
    const flagsSlot = document.getElementById("ls-flags-tags-dock-slot");
    const flagsDockToggle = document.querySelector(".user-tag-panel-dock-toggle");
    const elzaDockToggle = document.getElementById("ls-elza-dock-toggle");
    if (!finder || !input || !closeButton) { return; }
    if (finder.dataset.lsSearchFacelift === "1") { return; }
    finder.dataset.lsSearchFacelift = "1";
    finder.classList.add("ls-search-facelift");
    finder.setAttribute("aria-label", "Search");

    if (flagsDockToggle) { flagsDockToggle.classList.add("ls-panel-dock-toggle"); }
    if (elzaDockToggle) { elzaDockToggle.classList.add("ls-panel-dock-toggle"); }

    const row = finder.querySelector(".finder-search-row");
    const options = finder.querySelector(".finder-options-row");
    if (!row || !options) { return; }

    const header = document.createElement("div");
    header.className = "finder-search-header";

    const heading = document.createElement("div");
    heading.innerHTML = '<div class="finder-search-title">Meklēšana</div><div class="finder-search-subtitle">Ctrl+F</div>';

    const headerActions = document.createElement("div");
    headerActions.className = "finder-search-header-actions";

    const dockButton = document.createElement("button");
    dockButton.type = "button";
    dockButton.id = "finder-search-dock-toggle";
    dockButton.className = "ls-panel-dock-toggle finder-search-dock-toggle";
    dockButton.textContent = "⇲";
    dockButton.title = "Dock Search";
    dockButton.setAttribute("aria-label", "Dock Search");
    dockButton.setAttribute("aria-pressed", "false");

    closeButton.title = "Aizvērt";
    closeButton.setAttribute("aria-label", "Aizvērt");
    headerActions.appendChild(dockButton);
    headerActions.appendChild(closeButton);
    header.appendChild(heading);
    header.appendChild(headerActions);

    const body = document.createElement("div");
    body.className = "finder-search-body";
    finder.insertBefore(header, finder.firstElementChild);
    body.appendChild(row);
    body.appendChild(options);
    finder.appendChild(body);

    const icon = row.querySelector(".finder-search-icon");
    if (icon) {
        icon.textContent = "⌕";
        icon.setAttribute("aria-hidden", "true");
    }

    const inputWrap = document.createElement("div");
    inputWrap.className = "finder-search-input-wrap";
    row.insertBefore(inputWrap, input);
    inputWrap.appendChild(input);
    input.placeholder = "Meklēt dziesmu, Workspace, Track ID, 1+*, #tag…";

    const clearButton = document.createElement("button");
    clearButton.type = "button";
    clearButton.id = "finder-search-clear";
    clearButton.className = "finder-input-clear";
    clearButton.textContent = "×";
    clearButton.title = "Notīrīt tekstu";
    clearButton.setAttribute("aria-label", "Notīrīt tekstu");
    inputWrap.appendChild(clearButton);

    const previousButton = document.getElementById("finder-search-prev");
    const nextButton = document.getElementById("finder-search-next");
    if (previousButton) {
        previousButton.title = "Iepriekšējais rezultāts";
        previousButton.setAttribute("aria-label", "Iepriekšējais rezultāts");
    }
    if (nextButton) {
        nextButton.title = "Nākamais rezultāts";
        nextButton.setAttribute("aria-label", "Nākamais rezultāts");
    }

    let dockSlot = null;
    if (flagsSlot && flagsSlot.parentElement) {
        dockSlot = document.createElement("div");
        dockSlot.id = "ls-finder-search-dock-slot";
        dockSlot.className = "ls-finder-search-dock-slot ls-finder-search-dock-empty";
        dockSlot.setAttribute("aria-label", "Search");
        flagsSlot.parentElement.insertBefore(dockSlot, flagsSlot);
    } else {
        dockButton.hidden = true;
    }

    const STORAGE_KEY = "ls_finder_search_docked";

    function isOpen() {
        return finder.style.display === "block";
    }

    function isDocked() {
        return finder.classList.contains("finder-search-box-docked");
    }

    function syncClearButton() {
        clearButton.disabled = !(input.value || "").length;
    }

    function syncDockButton() {
        const docked = isDocked();
        const label = docked ? "Undock Search" : "Dock Search";
        dockButton.textContent = docked ? "⇱" : "⇲";
        dockButton.title = label;
        dockButton.setAttribute("aria-label", label);
        dockButton.setAttribute("aria-pressed", docked ? "true" : "false");
    }

    function activateDock() {
        if (!dockSlot) { return false; }
        const visibleInDock = isDocked() && isOpen();
        dockSlot.classList.toggle("ls-finder-search-dock-empty", !visibleInDock);
        if (
            visibleInDock &&
            window.LS &&
            window.LS.rightDock &&
            typeof window.LS.rightDock.activate === "function"
        ) {
            window.LS.rightDock.activate(dockSlot);
        }
        return visibleInDock;
    }

    function setDocked(nextDocked, persist) {
        const docked = Boolean(nextDocked && dockSlot);
        if (docked) {
            dockSlot.appendChild(finder);
            finder.classList.add("finder-search-box-docked");
        } else {
            document.body.appendChild(finder);
            finder.classList.remove("finder-search-box-docked");
        }
        syncDockButton();
        activateDock();
        if (persist !== false) {
            try {
                window.localStorage.setItem(STORAGE_KEY, docked ? "1" : "0");
            } catch (error) {}
        }
        return docked;
    }

    clearButton.addEventListener("click", function () {
        input.value = "";
        input.dispatchEvent(new Event("input", {bubbles: true}));
        syncClearButton();
        input.focus();
    });

    input.addEventListener("input", syncClearButton);

    dockButton.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        setDocked(!isDocked(), true);
        if (isOpen()) { input.focus(); }
    });

    const observer = new MutationObserver(function () {
        activateDock();
    });
    observer.observe(finder, {
        attributes: true,
        attributeFilter: ["style", "class"]
    });

    let startsDocked = false;
    try {
        startsDocked = window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (error) {}
    setDocked(startsDocked, false);
    syncClearButton();
    activateDock();
})();

/* MiniEdit 16.aug.2026 — unified Float resize only; LS Elza owns message DOM. */
(function () {
    "use strict";

    function makeFloatResizeSafe(node, dockHost, dockClass, sizeKey) {
        if (!node || !dockHost || node.dataset.lsMiniFloatResize === "1") { return; }
        node.dataset.lsMiniFloatResize = "1";
        node.classList.add("ls-mini-float-resizable");

        function saveAndClearFloatSize() {
            if (node.style.width) { node.dataset[sizeKey + "Width"] = node.style.width; }
            if (node.style.height) { node.dataset[sizeKey + "Height"] = node.style.height; }
            node.style.width = "";
            node.style.height = "";
        }

        function restoreFloatSize() {
            const width = node.dataset[sizeKey + "Width"] || "";
            const height = node.dataset[sizeKey + "Height"] || "";
            if (!node.style.width && width) { node.style.width = width; }
            if (!node.style.height && height) { node.style.height = height; }
        }

        function syncDockState() {
            if (dockHost.classList.contains(dockClass)) {
                saveAndClearFloatSize();
            } else {
                restoreFloatSize();
            }
        }

        const observer = new MutationObserver(syncDockState);
        observer.observe(dockHost, { attributes: true, attributeFilter: ["class"] });
        syncDockState();
    }

    function normalizeFloatPanels() {
        const finder = document.getElementById("finder-search-box");
        const flags = document.getElementById("user-tag-panel");
        const elzaModal = document.getElementById("ls-elza-modal");
        const elzaDialog = document.getElementById("ls-elza-dialog");

        makeFloatResizeSafe(finder, finder, "finder-search-box-docked", "lsMiniSearch");
        makeFloatResizeSafe(flags, flags, "user-tag-panel-docked", "lsMiniFlags");
        makeFloatResizeSafe(elzaDialog, elzaModal, "ls-elza-docked", "lsMiniElza");
    }

    function start() {
        normalizeFloatPanels();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, { once: true });
    } else {
        start();
    }
})();

/* MiniEdit 15.aug.2026 — Float drag parity for Search and Flags & Tags. */
(function () {
    "use strict";

    function isInteractive(target) {
        return Boolean(target && target.closest && target.closest(
            "button, input, textarea, select, option, a, label, [role='button']"
        ));
    }

    function makeFloatDraggable(node, handle, dockClass, storageKey) {
        if (!node || !handle || node.dataset.lsMiniFloatDrag === "1") { return; }
        node.dataset.lsMiniFloatDrag = "1";
        handle.classList.add("ls-mini-float-drag-handle");

        let drag = null;

        function isDocked() {
            return node.classList.contains(dockClass);
        }

        function clamp(left, top) {
            const margin = 6;
            const width = Math.max(1, node.offsetWidth || 1);
            const height = Math.max(1, node.offsetHeight || 1);
            const maxLeft = Math.max(margin, window.innerWidth - width - margin);
            const maxTop = Math.max(margin, window.innerHeight - height - margin);
            return {
                left: Math.max(margin, Math.min(maxLeft, left)),
                top: Math.max(margin, Math.min(maxTop, top))
            };
        }

        function savePosition() {
            if (isDocked()) { return; }
            const rect = node.getBoundingClientRect();
            try {
                window.localStorage.setItem(storageKey, JSON.stringify({
                    left: Math.round(rect.left),
                    top: Math.round(rect.top)
                }));
            } catch (error) {}
        }

        function restorePosition() {
            if (isDocked()) { return; }
            let saved = null;
            try {
                saved = JSON.parse(window.localStorage.getItem(storageKey) || "null");
            } catch (error) {}
            if (!saved || !Number.isFinite(Number(saved.left)) || !Number.isFinite(Number(saved.top))) {
                return;
            }
            const point = clamp(Number(saved.left), Number(saved.top));
            node.style.right = "auto";
            node.style.bottom = "auto";
            node.style.left = point.left + "px";
            node.style.top = point.top + "px";
        }

        function onPointerDown(event) {
            if (isDocked() || isInteractive(event.target)) { return; }
            if (event.button !== undefined && event.button !== 0) { return; }

            const rect = node.getBoundingClientRect();
            drag = {
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                startLeft: rect.left,
                startTop: rect.top
            };

            node.style.right = "auto";
            node.style.bottom = "auto";
            node.style.left = rect.left + "px";
            node.style.top = rect.top + "px";
            node.classList.add("ls-mini-float-dragging");
            event.preventDefault();
            try { handle.setPointerCapture(event.pointerId); } catch (error) {}
        }

        function onPointerMove(event) {
            if (!drag || event.pointerId !== drag.pointerId || isDocked()) { return; }
            const point = clamp(
                drag.startLeft + (event.clientX - drag.startX),
                drag.startTop + (event.clientY - drag.startY)
            );
            node.style.left = point.left + "px";
            node.style.top = point.top + "px";
            event.preventDefault();
        }

        function finishDrag(event) {
            if (!drag || event.pointerId !== drag.pointerId) { return; }
            drag = null;
            node.classList.remove("ls-mini-float-dragging");
            try { handle.releasePointerCapture(event.pointerId); } catch (error) {}
            savePosition();
        }

        handle.addEventListener("pointerdown", onPointerDown);
        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerup", finishDrag);
        window.addEventListener("pointercancel", finishDrag);

        const dockObserver = new MutationObserver(function () {
            if (isDocked()) {
                drag = null;
                if (node.classList.contains("ls-mini-float-dragging")) {
                    node.classList.remove("ls-mini-float-dragging");
                }
            } else {
                window.requestAnimationFrame(restorePosition);
            }
        });
        dockObserver.observe(node, {attributes: true, attributeFilter: ["class"]});

        restorePosition();
    }

    function start() {
        const search = document.getElementById("finder-search-box");
        const flags = document.getElementById("user-tag-panel");

        makeFloatDraggable(
            search,
            search ? search.querySelector(".finder-search-header") : null,
            "finder-search-box-docked",
            "ls_mini_search_float_position"
        );
        makeFloatDraggable(
            flags,
            flags ? flags.querySelector(".user-tag-panel-header") : null,
            "user-tag-panel-docked",
            "ls_mini_flags_float_position"
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start, {once: true});
    } else {
        start();
    }
})();
