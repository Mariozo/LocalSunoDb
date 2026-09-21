(function () {
    "use strict";

    const LS = window.LS = window.LS || {};

    function activate(slot) {
        if (!slot || !slot.parentElement) { return false; }
        const parent = slot.parentElement;
        if (parent.firstElementChild !== slot) {
            parent.insertBefore(slot, parent.firstElementChild);
        }
        if (typeof parent.scrollTop === "number") {
            parent.scrollTop = 0;
        }
        return true;
    }

    LS.rightDock = Object.assign(LS.rightDock || {}, {activate});
})();
