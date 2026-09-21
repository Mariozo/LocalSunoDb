(function () {
    "use strict";

    const bootstrap = window.LS_RIGHT_DOCK_BOOTSTRAP || {};
    const panel = bootstrap.flagsTagsPanel || null;
    const slot = bootstrap.flagsTagsSlot || null;
    const toggle = bootstrap.flagsTagsToggle || null;
    if (!panel || !slot || !toggle) { return; }

    const STORAGE_KEY = "ls_flags_tags_docked";
    const LS = window.LS = window.LS || {};
    LS.library = LS.library || {};

    function isOpen() {
        return panel.getAttribute("aria-hidden") === "false" &&
            !panel.classList.contains("hidden");
    }

    function isDocked() {
        return panel.classList.contains("user-tag-panel-docked");
    }

    function syncToggle() {
        const docked = isDocked();
        const label = docked ? "Float Flags and Tags" : "Dock Flags and Tags";
        toggle.textContent = docked ? "⇱" : "⇲";
        toggle.title = label;
        toggle.setAttribute("aria-label", label);
        toggle.setAttribute("aria-pressed", docked ? "true" : "false");
    }

    function activate() {
        const visibleInDock = isDocked() && isOpen();
        slot.classList.toggle("ls-flags-tags-dock-empty", !visibleInDock);
        if (
            visibleInDock &&
            LS.rightDock &&
            typeof LS.rightDock.activate === "function"
        ) {
            LS.rightDock.activate(slot);
        }
        return visibleInDock;
    }

    function setDocked(nextDocked, persist=true) {
        const docked = Boolean(nextDocked);
        if (docked) {
            slot.appendChild(panel);
            panel.classList.add("user-tag-panel-docked");
        } else {
            document.body.appendChild(panel);
            panel.classList.remove("user-tag-panel-docked");
        }
        syncToggle();
        activate();
        if (persist) {
            try {
                window.localStorage.setItem(STORAGE_KEY, docked ? "1" : "0");
            } catch (error) {}
        }
        return docked;
    }

    toggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        setDocked(!isDocked());
    });

    const observer = new MutationObserver(activate);
    observer.observe(panel, {
        attributes: true,
        attributeFilter: ["class", "aria-hidden"],
    });

    let startsDocked = false;
    try {
        startsDocked = window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (error) {}
    setDocked(startsDocked, false);

    LS.library.flagsTagsDock = Object.assign(
        LS.library.flagsTagsDock || {},
        {activate, isDocked, setDocked}
    );
})();
