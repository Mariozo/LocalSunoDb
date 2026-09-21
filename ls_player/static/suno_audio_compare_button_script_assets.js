        table.addEventListener("click", (event) => {
            const button = event.target.closest(".compare-btn");
            if (!button || !table.contains(button)) { return; }
            event.preventDefault();
            event.stopPropagation();

            const trackRow = button.closest("tr.track-row");
            const fragmentRow = getFragmentRow(trackRow);
            if (!fragmentRow) { return; }
            const sunoBlock = fragmentRow.querySelector(".suno-block");
            const localBlock = fragmentRow.querySelector(".local-block");
            const stemBlock = fragmentRow.querySelector(".stem-block");
            const isHidden = fragmentRow.classList.contains("hidden");

            closeOtherPlayers(fragmentRow);
            if (stemBlock) { stemBlock.classList.add("hidden"); }

            if (isHidden) {
                const currentSunoPlayback = buildSunoCurrentPlaybackUrl(
                    button.dataset.trackId,
                    button.dataset.audio || ""
                );
                const sunoAudio = setupPlayerBlock(
                    sunoBlock,
                    currentSunoPlayback,
                    currentSunoPlayback,
                    button.dataset.trackId,
                    null
                );

                const localEditButton = localBlock ? localBlock.querySelector(".edit-local-btn") : null;
                if (localEditButton) {
                    localEditButton.dataset.localPath = button.dataset.localPath || "";
                }

                if (localBlock) {
                    setupPlayerBlock(
                        localBlock,
                        button.dataset.localAudio,
                        button.dataset.localPath,
                        button.dataset.trackId + "_local",
                        null
                    );
                }

                fragmentRow.classList.remove("hidden");
                setPlayerHighlight(trackRow, fragmentRow);
                if (sunoAudio) {
                    sunoAudio.play().catch(() => {});
                    lastActiveAudio = sunoAudio;
                    sunoAudio.focus();
                }
                button.classList.add("active");
            } else {
                fragmentRow.querySelectorAll("audio").forEach((audio) => audio.pause());
                fragmentRow.classList.add("hidden");
                trackRow.classList.remove("player-open");
                fragmentRow.classList.remove("player-open");
                button.classList.remove("active");
            }
        });
