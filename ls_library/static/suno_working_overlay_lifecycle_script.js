        // Browser Back / mouse Back can restore a frozen page with the busy overlay still visible.
        // Always clear it when the page is restored from bfcache or becomes active again.
        window.addEventListener("pageshow", () => {
            hideBusy(true);
        });

        window.addEventListener("popstate", () => {
            hideBusy(true);
        });

        window.addEventListener("focus", () => {
            hideBusy(true);
        });

        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                hideBusy(true);
            }
        });