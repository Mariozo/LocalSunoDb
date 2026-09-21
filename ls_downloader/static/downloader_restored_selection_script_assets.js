        function escHtml(value) {
            return String(value === null || value === undefined ? "" : value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
        }

        function updateRestoredSelectedCount() {
            const label = document.getElementById("selected-count-label");
            if (label) {
                const count = metaResult.querySelectorAll(".update-row-check:checked").length;
                label.innerText = "Atlasīti: " + count;
            }
        }

        function getCurrentRefreshLimitNumber() {
            const limitSelect = document.getElementById("refresh-limit-select");
            const rawLimit = limitSelect ? limitSelect.value : "25";
            if (rawLimit === "all") { return Number.POSITIVE_INFINITY; }
            return parseInt(rawLimit || "25", 10) || 25;
        }

        function limitCurrentChecks(checks) {
            const limit = getCurrentRefreshLimitNumber();
            return isFinite(limit) ? checks.slice(0, limit) : checks;
        }

        function getCurrentSelectedUpdateIds(applyLimit=false) {
            let ids = Array.from(metaResult.querySelectorAll(".update-row-check:checked"))
                .map((check) => check.value)
                .filter((value) => value);
            if (applyLimit) {
                const limit = getCurrentRefreshLimitNumber();
                if (isFinite(limit)) { ids = ids.slice(0, limit); }
            }
            return ids;
        }

        function getCurrentSelectedTracklistChecks() {
            return Array.from(metaResult.querySelectorAll(".tracklist-new-check:checked"));
        }

        function updateDownloaderEmptyActions() {
            const hasNewTracks = metaResult.querySelectorAll(".tracklist-new-check").length > 0;
            [
                "listen-selected-tracklist-btn",
                "import-selected-tracklist-btn",
                "ignore-selected-tracklist-btn",
                "tracklist-select-all-btn",
                "tracklist-select-none-btn"
            ].forEach((id) => {
                const button = document.getElementById(id);
                if (button) { button.style.display = hasNewTracks ? "" : "none"; }
            });

            const titleUpdateButton = document.getElementById("update-selected-titles-btn");
            if (titleUpdateButton) {
                const hasChangedTitles = metaResult.querySelectorAll(".title-change-check").length > 0;
                const actionBar = titleUpdateButton.closest(".update-action-bar");
                if (actionBar) { actionBar.style.display = hasChangedTitles ? "" : "none"; }
            }
        }

