        if (mainMenuButton) {
            mainMenuButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                toggleTopMenu("main-menu");
            });
        }

        if (profileMenuButton) {
            profileMenuButton.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                toggleTopMenu("profile-menu");
            });
        }

        document.addEventListener("click", (event) => {
            if (!event.target.closest(".top-menu-wrap") && !event.target.closest(".profile-menu-wrap")) {
                closeTopMenus();
            }
        });

        if (openHelpButton && helpModal && helpModalText) {
            openHelpButton.addEventListener("click", async () => {
                closeTopMenus();
                helpModal.style.display = "flex";
                helpModalText.innerText = "Loading...";
                try {
                    const response = await fetch("/help-text");
                    helpModalText.innerText = await response.text();
                } catch (error) {
                    helpModalText.innerText = "Could not load Help.";
                }
            });
        }

        function fillAudioOutputSelect(selectNode, devices, selectedId, suggestedId) {
            if (!selectNode) { return; }
            const endpointList = Array.isArray(devices) ? devices : [];
            selectNode.innerHTML = "";
            const emptyOption = document.createElement("option");
            emptyOption.value = "";
            emptyOption.textContent = endpointList.length
                ? "— izvēlies Windows audio izeju —"
                : "— aktīvas Windows audio izejas nav atrastas —";
            selectNode.appendChild(emptyOption);
            endpointList.forEach((device) => {
                const option = document.createElement("option");
                option.value = String(device.id || "");
                option.textContent = String(device.name || device.id || "Audio output")
                    + (device.is_default ? " · pašreizējā" : "");
                selectNode.appendChild(option);
            });
            selectNode.disabled = endpointList.length === 0;
            const requested = String(selectedId || suggestedId || "");
            if (requested && Array.from(selectNode.options).some((item) => item.value === requested)) {
                selectNode.value = requested;
            }
        }

        async function loadAudioOutputSettings() {
            if (!audioOutputSpeakersSelect || !audioOutputHeadphonesSelect) { return; }
            const response = await fetch("/audio-output-state?refresh=1", {
                cache: "no-store"
            });
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Windows audio izejas neizdevās nolasīt.");
            }
            fillAudioOutputSelect(
                audioOutputSpeakersSelect,
                payload.devices,
                payload.speakers_id,
                payload.suggested_speakers_id
            );
            fillAudioOutputSelect(
                audioOutputHeadphonesSelect,
                payload.devices,
                payload.headphones_id,
                payload.suggested_headphones_id
            );
            if (!Array.isArray(payload.devices) || payload.devices.length === 0) {
                throw new Error(payload.error || "Windows audio izejas nav atrastas.");
            }
        }

        async function loadSettingsIntoModal() {
            if (!settingsModal || !stemRootInput) { return; }
            settingsModal.style.display = "flex";
            if (settingsStatus) { settingsStatus.innerText = "Loading..."; }
            try {
                const response = await fetch("/settings-json");
                const data = await response.json();
                if (audioLibraryRootInput) { audioLibraryRootInput.value = data.audio_library_root_folder || data.stem_root_folder || ""; }
                stemRootInput.value = data.stem_root_folder || "";
                if (lsUpdateIntervalInput) {
                    lsUpdateIntervalInput.value = String(
                        data.ls_update_check_interval_seconds ?? 10
                    );
                }
                await setAutoplayListEnabled(!!data.autoplay_list, false);
                await loadAudioOutputSettings();
                try { localStorage.setItem("ls_autoplay_list_enabled", autoplayListEnabled ? "1" : "0"); } catch (error) {}
                if (settingsStatus) { settingsStatus.innerText = ""; }
            } catch (error) {
                if (settingsStatus) { settingsStatus.innerText = String(error && error.message || "Could not load settings."); }
            }
        }

        if (openSettingsButton) {
            openSettingsButton.addEventListener("click", () => {
                closeTopMenus();
                loadSettingsIntoModal();
            });
        }

        if (settingsModalClose && settingsModal) {
            settingsModalClose.addEventListener("click", () => {
                settingsModal.style.display = "none";
            });
        }

        if (settingsModal) {
            settingsModal.addEventListener("click", (event) => {
                if (event.target === settingsModal) {
                    settingsModal.style.display = "none";
                }
            });
        }

        try {
            const savedAutoplay = localStorage.getItem("ls_autoplay_list_enabled");
            if (savedAutoplay !== null) {
                autoplayListEnabled = savedAutoplay === "1";
            }
        } catch (error) {}
        updateAutoplayUi();

        if (autoplayListCheckbox) {
            autoplayListCheckbox.addEventListener("change", async () => {
                await setAutoplayListEnabled(autoplayListCheckbox.checked, true);
            });
        }

        if (autoplayTopButton) {
            autoplayTopButton.addEventListener("click", async () => {
                await toggleAutoplayListEnabled();
            });
        }

