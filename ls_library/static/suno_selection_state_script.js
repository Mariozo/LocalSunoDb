        function getSelectedWavTrackRows() {
            return Array.from(table.querySelectorAll("tbody .track-check:checked"))
                .map((check) => check.closest("tr.track-row"))
                .filter(Boolean);
        }

        function getSelectedLocalWavTrackRows() {
            return getSelectedWavTrackRows().filter((row) => {
                const playButton = row.querySelector(".play-btn");
                if (!playButton) { return false; }
                const localPath = String(playButton.dataset.localPath || "").trim();
                const localAudio = String(playButton.dataset.localAudio || "").trim();
                return Boolean(localPath && localAudio && /\.wav$/i.test(localPath));
            });
        }

        function getLocalWavCompareSelectionState() {
            const selectedRows = getSelectedWavTrackRows();
            const localWavRows = getSelectedLocalWavTrackRows();
            return {
                selectedRows: selectedRows,
                localWavRows: localWavRows,
                selectedCount: selectedRows.length,
                localWavCount: localWavRows.length,
                compareReady: selectedRows.length >= 2 && localWavRows.length === selectedRows.length,
            };
        }

        window.LS = window.LS || {};
        window.LS.library = Object.assign(window.LS.library || {}, {
            getSelectedWavTrackIds() {
                return getSelectedWavTrackRows()
                    .map((row) => String(row.dataset.trackId || "").trim())
                    .filter(Boolean);
            },
            getSelectedLocalWavTrackIds() {
                return getSelectedLocalWavTrackRows()
                    .map((row) => String(row.dataset.trackId || "").trim())
                    .filter(Boolean);
            },
            isLocalWavCompareReady() {
                return getLocalWavCompareSelectionState().compareReady;
            },
        });

        function updateOpenSelectedButton() {
            const compareSelection = getLocalWavCompareSelectionState();
            const checkedCount = compareSelection.selectedCount;
            if (openSelected) {
                openSelected.disabled = checkedCount <= 1;
            }
            if (compareThisButton) {
                compareThisButton.style.display = "none";
                compareThisButton.disabled = true;
                compareThisButton.innerText = "Compare This";
                compareThisButton.title = "Compare selected WAV files from the Player bar.";
            }

            document.dispatchEvent(new CustomEvent(
                "ls-library-wav-selection-changed",
                {
                    detail: {
                        selectedCount: compareSelection.selectedCount,
                        localWavCount: compareSelection.localWavCount,
                        compareReady: compareSelection.compareReady,
                    }
                }
            ));

            if (wavSelectModeButton) {
                wavSelectModeButton.innerText = LS_WAV_PICKER_MODE
                    ? "Cancel WAV selection"
                    : (table.classList.contains("selection-mode") ? "Unselect WAV" : "Select WAV");
            }
        }

        const SUNO_SELECTION_STATE_KEY = "ls_suno_selection_v484";

        function getSunoSelectionViewKey() {
            return window.location.pathname + window.location.search;
        }

        function readSunoSelectionState() {
            try {
                const data = JSON.parse(localStorage.getItem(SUNO_SELECTION_STATE_KEY) || "{}");
                return data && typeof data === "object" ? data : {};
            } catch (error) {
                return {};
            }
        }

        function saveSunoSelection() {
            try {
                const state = readSunoSelectionState();
                const ids = Array.from(table.querySelectorAll("tbody .track-check:checked"))
                    .map((check) => String(check.value || "").trim())
                    .filter((value) => value);
                state[getSunoSelectionViewKey()] = { ids: ids, saved_at: Date.now() };
                localStorage.setItem(SUNO_SELECTION_STATE_KEY, JSON.stringify(state));
            } catch (error) {}
        }

        function restoreSunoSelection() {
            if (LS_WAV_PICKER_MODE) { return; }
            try {
                const state = readSunoSelectionState();
                const saved = state[getSunoSelectionViewKey()];
                if (!saved || !Array.isArray(saved.ids)) { return; }
                const wanted = new Set(saved.ids.map((value) => String(value || "").toLowerCase()));
                table.querySelectorAll("tbody .track-check").forEach((check) => {
                    const key = String(check.value || "").toLowerCase();
                    check.checked = wanted.has(key);
                });
            } catch (error) {}
        }

