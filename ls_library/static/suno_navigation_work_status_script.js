        function stopAllPlaybackForNavigation() {
            document.querySelectorAll("audio").forEach((audio) => {
                try {
                    audio.pause();
                    audio.removeAttribute("src");
                    audio.load();
                } catch (error) {}
            });
        }

        document.querySelectorAll("form").forEach((form) => {
            let clickedSubmit = null;
            form.querySelectorAll('button[type="submit"]').forEach((button) => {
                button.addEventListener("click", () => {
                    clickedSubmit = button;
                });
            });
            form.addEventListener("submit", () => {
                stopAllPlaybackForNavigation();
                const label = clickedSubmit ? (clickedSubmit.dataset.busyLabel || clickedSubmit.innerText || "Working...") : "Working...";
                const isRefresh = clickedSubmit && clickedSubmit.classList.contains("refresh-db-btn");
                if (isRefresh) {
                    showBusy(label, "Suno CSV, metadata, Kind and local WAV sync are running. Please do not close this page.");
                } else {
                    showBusy(label, "Loading results...");
                }
            });
        });