        if (openSelected) {
            openSelected.addEventListener("click", () => {
                const checked = Array.from(table.querySelectorAll("tbody .track-check:checked"));

                if (openSelected.disabled) {
                    alert("Select at least 2 tracks first.");
                    return;
                }

                checked.forEach((check) => {
                    const trackId = check.value || "";

                    if (trackId) {
                        openUrlInNewTab("https://suno.com/song/" + encodeURIComponent(trackId));
                    }
                });
            });
        }

        if (wavSelectModeButton) {
            wavSelectModeButton.addEventListener("click", () => {
                if (!LS_WAV_PICKER_MODE) { return; }
                try {
                    window.sessionStorage.removeItem("ls_pending_wav_track_id");
                } catch (error) {}
                window.location.replace("/downloader#audio");
            });
        }


        // Public LIBRARY API is initialized by selection-state before Player startup.
        window.LS = window.LS || {};
        window.LS.library = window.LS.library || {};
