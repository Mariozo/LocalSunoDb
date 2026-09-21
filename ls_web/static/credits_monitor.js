(() => {
        const updateCredits = (data) => {
            if (!data || data.credits_remaining === null || data.credits_remaining === undefined) {
                return;
            }
            const value = String(data.credits_remaining);
            const detail = data.stale && data.message
                ? "Credits Remaining · last known value · " + data.message
                : "Credits Remaining";
            document.querySelectorAll(".ls-sidebar-profile-credits").forEach((node) => {
                node.textContent = value;
                node.title = detail;
            });
            document.querySelectorAll(".ls-profile-card-credits").forEach((node) => {
                node.textContent = value + " Credits Remaining";
                node.title = detail;
            });
        };

        const refreshCredits = async () => {
            try {
                const response = await fetch("/suno-credits-status?_=" + Date.now(), {
                    cache: "no-store"
                });
                const data = await response.json();
                updateCredits(data);
            } catch (error) {
                // Keep the last known value; credits must never block LS UI.
            }
        };

        refreshCredits();
        window.setInterval(refreshCredits, 5 * 60 * 1000);
    })();
