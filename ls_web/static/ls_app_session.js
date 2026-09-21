(() => {
    if (window.__lsAppSessionV5463) { return; }
    window.__lsAppSessionV5463 = true;

    const endpoint = "/ls-lifecycle/app-session";
    const sessionId = (() => {
        try {
            if (window.crypto && typeof window.crypto.randomUUID === "function") {
                return window.crypto.randomUUID();
            }
        } catch (error) {}
        return "ls-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
    })();

    function bodyFor(eventName) {
        const body = new URLSearchParams();
        body.set("session_id", sessionId);
        body.set("event", eventName);
        return body;
    }

    function heartbeat() {
        fetch(endpoint, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            body: bodyFor("heartbeat"),
            cache: "no-store",
            credentials: "same-origin",
            keepalive: true
        }).catch(() => {});
    }

    heartbeat();
    const heartbeatTimer = window.setInterval(heartbeat, 750);

    window.addEventListener("pagehide", () => {
        window.clearInterval(heartbeatTimer);
        const closingBody = bodyFor("closing");
        try {
            if (navigator.sendBeacon) {
                navigator.sendBeacon(endpoint, closingBody);
                return;
            }
        } catch (error) {}
        fetch(endpoint, {
            method: "POST",
            body: closingBody,
            cache: "no-store",
            credentials: "same-origin",
            keepalive: true
        }).catch(() => {});
    }, {once: true});
})();
