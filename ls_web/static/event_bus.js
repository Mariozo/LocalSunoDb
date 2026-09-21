(function () {
    "use strict";
    const LS = window.LS = window.LS || {};
    if (LS.bus) { return; }
    const target = new EventTarget();
    LS.events = Object.freeze({
        TRACK_SELECTED: "library:track-selected",
        TRACK_PLAYBACK_STARTED: "player:playback-started",
        PLAYER_STATE_CHANGED: "player:state-changed",
        STEMS_STATE_CHANGED: "stems:state-changed"
    });
    LS.bus = Object.freeze({
        on(name, handler) { target.addEventListener(name, handler); return () => target.removeEventListener(name, handler); },
        once(name, handler) { target.addEventListener(name, handler, { once: true }); },
        off(name, handler) { target.removeEventListener(name, handler); },
        emit(name, detail) { target.dispatchEvent(new CustomEvent(name, { detail: detail || {} })); }
    });
})();
