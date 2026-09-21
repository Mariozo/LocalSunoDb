        let lsWavPickerReturning = false;

        function returnWavPickerTrack(trackId) {
            if (!LS_WAV_PICKER_MODE || lsWavPickerReturning) { return; }
            const cleanTrackId = String(trackId || "").trim();
            if (!cleanTrackId) { return; }
            lsWavPickerReturning = true;
            try {
                window.sessionStorage.setItem(
                    "ls_pending_wav_track_id",
                    cleanTrackId
                );
            } catch (error) {}
            if (typeof showBusy === "function") {
                showBusy(
                    "Returning to Downloader…",
                    "The selected Track ID is being prepared for Local family confirmation."
                );
            }
            const target = "/downloader?selected_wav_track_id="
                + encodeURIComponent(cleanTrackId)
                + "#audio";
            window.location.assign(target);
        }

        function hydrateSelectionRows() {
            if (LS_WAV_PICKER_MODE) {
                table.classList.add("selection-mode", "wav-picker-mode");
                table.querySelectorAll("tbody .track-check").forEach((check) => {
                    check.checked = false;
                    const cell = check.closest(".ls-track-cover-control") || check.closest(".select-cell");
                    if (cell && !cell.querySelector(".wav-picker-choose")) {
                        const chooseButton = document.createElement("button");
                        chooseButton.type = "button";
                        chooseButton.className = "wav-picker-choose";
                        chooseButton.dataset.trackId = String(check.value || "").trim();
                        chooseButton.textContent = "Choose";
                        chooseButton.title = "Choose this track and return to Downloader";
                        cell.appendChild(chooseButton);
                    }
                });
                if (checkAll) { checkAll.checked = false; }
            }
            restoreSunoSelection();
            updateOpenSelectedButton();
        }

        if (LS_WAV_PICKER_MODE) {
            table.addEventListener("click", (event) => {
                const chooseButton = event.target.closest(".wav-picker-choose");
                if (chooseButton) {
                    event.preventDefault();
                    event.stopPropagation();
                    returnWavPickerTrack(chooseButton.dataset.trackId || "");
                    return;
                }
                const row = event.target.closest("tr.track-row");
                if (!row || event.target.closest("a, button, input, textarea, select, details, summary, audio")) {
                    return;
                }
                event.preventDefault();
                event.stopPropagation();
                returnWavPickerTrack(row.dataset.trackId || "");
            }, true);
        }

        table.addEventListener("change", (event) => {
            const check = event.target.closest("tbody .track-check");
            if (!check || !table.contains(check)) { return; }
            if (LS_WAV_PICKER_MODE && check.checked) {
                table.querySelectorAll("tbody .track-check").forEach((other) => {
                    if (other !== check) { other.checked = false; }
                });
                updateOpenSelectedButton();
                returnWavPickerTrack(check.value || "");
                return;
            }
            updateOpenSelectedButton();
            saveSunoSelection();
        });

        document.addEventListener("ls-library-rows-added", hydrateSelectionRows);
        hydrateSelectionRows();

        window.addEventListener("pagehide", saveSunoSelection);
        window.addEventListener("beforeunload", saveSunoSelection);

        function openUrlInNewTab(url) {
            const link = document.createElement("a");
            link.href = url;
            link.target = "_blank";
            link.rel = "noopener";
            link.style.display = "none";
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }