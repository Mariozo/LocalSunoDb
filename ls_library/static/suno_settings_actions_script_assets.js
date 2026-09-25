        if (chooseAudioLibraryRootButton) {
            chooseAudioLibraryRootButton.addEventListener("click", async () => {
                if (settingsStatus) { settingsStatus.innerText = "Choose Audio Library root folder..."; }
                try {
                    const response = await fetch("/choose-audio-library-root");
                    const text = await response.text();
                    if (!response.ok) { throw new Error(text || "Could not choose folder"); }
                    if (text && audioLibraryRootInput) { audioLibraryRootInput.value = text; }
                    if (settingsStatus) { settingsStatus.innerText = text ? "Selected: " + text : "Cancelled"; }
                } catch (error) {
                    if (settingsStatus) { settingsStatus.innerText = error.message; }
                }
            });
        }

        if (saveAudioLibraryRootButton) {
            saveAudioLibraryRootButton.addEventListener("click", async () => {
                if (!audioLibraryRootInput) { return; }
                const body = new URLSearchParams();
                body.set("audio_library_root_folder", audioLibraryRootInput.value || "");
                try {
                    const response = await fetch("/set-audio-library-root", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });
                    const text = await response.text();
                    if (!response.ok) { throw new Error(text || "Save failed"); }
                    audioLibraryRootInput.value = text;
                    if (settingsStatus) { settingsStatus.innerText = "Audio Library root saved: " + text; }
                } catch (error) {
                    if (settingsStatus) { settingsStatus.innerText = error.message; }
                }
            });
        }

        if (
            saveAudioOutputDevicesButton &&
            audioOutputSpeakersSelect &&
            audioOutputHeadphonesSelect
        ) {
            saveAudioOutputDevicesButton.addEventListener("click", async () => {
                const body = new URLSearchParams();
                body.set("audio_output_speakers_id", audioOutputSpeakersSelect.value || "");
                body.set("audio_output_headphones_id", audioOutputHeadphonesSelect.value || "");
                if (settingsStatus) { settingsStatus.innerText = "Saglabā audio izejas..."; }
                try {
                    const response = await fetch("/set-audio-output-devices", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });
                    const payload = await response.json();
                    if (!response.ok || !payload.ok) {
                        throw new Error(payload.error || "Audio izejas neizdevās saglabāt.");
                    }
                    if (settingsStatus) {
                        settingsStatus.innerText = "Windows skaļruņu un austiņu izejas saglabātas.";
                    }
                    document.dispatchEvent(new CustomEvent("ls-audio-output-settings-saved"));
                } catch (error) {
                    if (settingsStatus) {
                        settingsStatus.innerText = String(
                            error && error.message || "Audio izejas neizdevās saglabāt."
                        );
                    }
                }
            });
        }

        if (chooseStemRootButton && stemRootInput) {
            chooseStemRootButton.addEventListener("click", async () => {
                if (settingsStatus) { settingsStatus.innerText = "Choose folder in Windows dialog..."; }
                try {
                    const response = await fetch("/choose-stem-root");
                    const text = await response.text();
                    if (!response.ok) {
                        if (settingsStatus) { settingsStatus.innerText = text || "Could not choose folder."; }
                        return;
                    }
                    if (text) {
                        stemRootInput.value = text;
                        if (settingsStatus) { settingsStatus.innerText = "Saved: " + text; }
                    } else if (settingsStatus) {
                        settingsStatus.innerText = "Cancelled.";
                    }
                } catch (error) {
                    if (settingsStatus) { settingsStatus.innerText = "Could not choose folder."; }
                }
            });
        }

        if (saveStemRootButton && stemRootInput) {
            saveStemRootButton.addEventListener("click", async () => {
                const body = new URLSearchParams();
                body.set("stem_root_folder", stemRootInput.value || "");
                if (settingsStatus) { settingsStatus.innerText = "Saving..."; }
                try {
                    const response = await fetch("/set-stem-root", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });
                    const text = await response.text();
                    if (!response.ok) {
                        if (settingsStatus) { settingsStatus.innerText = text || "Could not save settings."; }
                        return;
                    }
                    if (settingsStatus) { settingsStatus.innerText = "Saved: " + text; }
                } catch (error) {
                    if (settingsStatus) { settingsStatus.innerText = "Could not save settings."; }
                }
            });
        }

        if (saveLsUpdateIntervalButton && lsUpdateIntervalInput) {
            saveLsUpdateIntervalButton.addEventListener("click", async () => {
                const body = new URLSearchParams();
                body.set(
                    "ls_update_check_interval_seconds",
                    lsUpdateIntervalInput.value || "0"
                );
                if (settingsStatus) { settingsStatus.innerText = "Saving..."; }
                try {
                    const response = await fetch("/set-ls-update-check-interval", {
                        method: "POST",
                        headers: { "Content-Type": "application/x-www-form-urlencoded" },
                        body: body.toString()
                    });
                    const text = await response.text();
                    if (!response.ok) {
                        throw new Error(text || "Could not save update interval.");
                    }
                    lsUpdateIntervalInput.value = text;
                    if (
                        window.LSUpdateController &&
                        typeof window.LSUpdateController.schedule === "function"
                    ) {
                        window.LSUpdateController.schedule(text, true);
                    }
                    try {
                        localStorage.setItem("ls_update_interval_seconds", text);
                    } catch (error) {}
                    if (settingsStatus) {
                        settingsStatus.innerText = text === "0"
                            ? "Automatic update checks are off."
                            : "Update check interval saved: " + text + " seconds.";
                    }
                } catch (error) {
                    if (settingsStatus) {
                        settingsStatus.innerText = String(
                            error && error.message || "Could not save update interval."
                        );
                    }
                }
            });
        }

        if (helpModalClose && helpModal) {
            helpModalClose.addEventListener("click", () => {
                helpModal.style.display = "none";
            });
        }

        if (helpModal) {
            helpModal.addEventListener("click", (event) => {
                if (event.target === helpModal) {
                    helpModal.style.display = "none";
                }
            });
        }



        async function loadFreshInstallState(openWhenNeeded=false) {
            if (!freshInstallModal) { return null; }
            const response = await fetch("/fresh-install-state", {cache:"no-store"});
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Neizdevās pārbaudīt LS datubāzi.");
            }
            if (freshInstallDbStatus) {
                const tracks = Number(payload.track_count || 0);
                const media = Number(payload.media_count || 0);
                freshInstallDbStatus.textContent =
                    "DB gatava: " + String(payload.db_path || "") +
                    " · " + tracks + " dziesmas · " + media + " audio faili";
            }
            if (freshInstallRootInput) {
                freshInstallRootInput.value = String(payload.audio_library_root_folder || "");
            }
            if (openWhenNeeded && payload.needs_setup) {
                freshInstallModal.style.display = "flex";
            }
            return payload;
        }

        if (openFreshInstallSetupButton && freshInstallModal) {
            openFreshInstallSetupButton.addEventListener("click", async () => {
                closeTopMenus();
                freshInstallModal.style.display = "flex";
                if (freshInstallStatus) { freshInstallStatus.textContent = ""; }
                try {
                    await loadFreshInstallState(false);
                } catch (error) {
                    if (freshInstallStatus) {
                        freshInstallStatus.textContent = String(error && error.message || error);
                    }
                }
            });
        }

        if (freshInstallClose && freshInstallModal) {
            freshInstallClose.addEventListener("click", () => {
                freshInstallModal.style.display = "none";
            });
        }

        if (freshInstallModal) {
            freshInstallModal.addEventListener("click", (event) => {
                if (event.target === freshInstallModal) {
                    freshInstallModal.style.display = "none";
                }
            });
        }

        if (freshInstallChooseRoot && freshInstallRootInput) {
            freshInstallChooseRoot.addEventListener("click", async () => {
                if (freshInstallStatus) {
                    freshInstallStatus.textContent = "Izvēlies lokālās audio bibliotēkas mapi…";
                }
                freshInstallChooseRoot.disabled = true;
                try {
                    const response = await fetch("/choose-audio-library-root", {cache:"no-store"});
                    const text = await response.text();
                    if (!response.ok) {
                        throw new Error(text || "Mapi neizdevās izvēlēties.");
                    }
                    if (text) {
                        freshInstallRootInput.value = text;
                        if (freshInstallStatus) {
                            freshInstallStatus.textContent = "Izvēlēta: " + text;
                        }
                    } else if (freshInstallStatus) {
                        freshInstallStatus.textContent = "Mapes izvēle atcelta.";
                    }
                } catch (error) {
                    if (freshInstallStatus) {
                        freshInstallStatus.textContent = String(error && error.message || error);
                    }
                } finally {
                    freshInstallChooseRoot.disabled = false;
                }
            });
        }

        if (freshInstallImport && freshInstallRootInput) {
            freshInstallImport.addEventListener("click", async () => {
                if (freshInstallImport.disabled) { return; }
                const root = String(freshInstallRootInput.value || "").trim();
                if (!root) {
                    if (freshInstallStatus) {
                        freshInstallStatus.textContent = "Vispirms izvēlies mapi ar lokālajām dziesmām.";
                    }
                    return;
                }
                freshInstallImport.disabled = true;
                if (freshInstallChooseRoot) { freshInstallChooseRoot.disabled = true; }
                if (freshInstallStatus) {
                    freshInstallStatus.textContent = "Skenē un importē lokālās dziesmas…";
                }
                try {
                    const body = new URLSearchParams();
                    body.set("audio_library_root_folder", root);
                    const response = await fetch("/import-local-library", {
                        method:"POST",
                        headers:{"Content-Type":"application/x-www-form-urlencoded"},
                        body:body.toString()
                    });
                    const payload = await response.json();
                    if (!response.ok || !payload.ok) {
                        throw new Error(payload.error || "Lokālo dziesmu imports neizdevās.");
                    }
                    const addedTracks = Number(payload.added_tracks || 0);
                    const addedMedia = Number(payload.added_media || 0);
                    const existingMedia = Number(payload.existing_media || 0);
                    if (freshInstallStatus) {
                        freshInstallStatus.textContent =
                            "Gatavs. Pievienotas " + addedTracks + " dziesmas un " +
                            addedMedia + " audio faili." +
                            (existingMedia ? " Jau DB bija " + existingMedia + " faili." : "");
                    }
                    await loadFreshInstallState(false);
                    window.setTimeout(() => window.location.reload(), 900);
                } catch (error) {
                    if (freshInstallStatus) {
                        freshInstallStatus.textContent = String(error && error.message || error);
                    }
                } finally {
                    freshInstallImport.disabled = false;
                    if (freshInstallChooseRoot) { freshInstallChooseRoot.disabled = false; }
                }
            });
        }

        if (freshInstallModal) {
            window.setTimeout(() => {
                loadFreshInstallState(true).catch(() => {});
            }, 0);
        }


        async function loadMusicDbPreview(name) {
            if (!musicDbPreview || !name) { return; }
            const response = await fetch(
                "/music-db-preview?name=" + encodeURIComponent(name) + "&limit=40",
                {cache:"no-store"}
            );
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "DB priekšskatījumu neizdevās nolasīt.");
            }
            musicDbPreview.replaceChildren();
            const heading = document.createElement("div");
            heading.style.fontWeight = "700";
            heading.style.marginBottom = "8px";
            heading.textContent = payload.name + " · metadatu secības priekšskatījums";
            musicDbPreview.appendChild(heading);

            (payload.rows || []).forEach((row) => {
                const line = document.createElement("div");
                line.style.padding = "3px 0";
                const bits = [];
                if (row.artist) { bits.push(String(row.artist)); }
                if (row.year) { bits.push(String(row.year)); }
                if (row.album) { bits.push(String(row.album)); }
                const no = Number(row.track_no || 0);
                const disc = Number(row.disc_no || 0);
                if (disc > 0) { bits.push("CD " + disc); }
                if (no > 0) { bits.push("#" + no); }
                if (row.genre) { bits.push(String(row.genre)); }
                if (Number(row.has_cover || 0)) { bits.push("🖼"); }
                const prefix = bits.length ? bits.join(" · ") + " — " : "";
                line.textContent = prefix + String(row.title || row.path || "");
                musicDbPreview.appendChild(line);
            });
            if (!(payload.rows || []).length) {
                const empty = document.createElement("div");
                empty.textContent = "DB vēl nav dziesmu.";
                musicDbPreview.appendChild(empty);
            }
            musicDbPreview.style.display = "block";
        }

        async function loadMusicDbList() {
            if (!musicDbList) { return; }
            const response = await fetch("/music-db-list", {cache:"no-store"});
            const payload = await response.json();
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Mūzikas DB sarakstu neizdevās nolasīt.");
            }
            musicDbList.replaceChildren();
            const databases = Array.isArray(payload.databases) ? payload.databases : [];
            if (!databases.length) {
                const empty = document.createElement("div");
                empty.className = "muted";
                empty.textContent = "Atsevišķas mūzikas DB vēl nav izveidotas.";
                musicDbList.appendChild(empty);
                return;
            }

            databases.forEach((item) => {
                const button = document.createElement("button");
                button.type = "button";
                button.style.textAlign = "left";
                button.style.padding = "8px 10px";
                const summary = [
                    String(item.name || item.db_file || "Music DB"),
                    String(Number(item.track_count || 0)) + " dziesmas",
                    String(Number(item.artist_count || 0)) + " autori",
                    String(Number(item.cover_count || 0)) + " attēli"
                ];
                if (item.default_genre) { summary.push(String(item.default_genre)); }
                button.textContent = summary.join(" · ");
                button.addEventListener("click", async () => {
                    if (musicDbNameInput) { musicDbNameInput.value = String(item.name || ""); }
                    if (musicDbGenreInput) { musicDbGenreInput.value = String(item.default_genre || ""); }
                    if (musicDbRootInput) { musicDbRootInput.value = String(item.root_folder || ""); }
                    if (musicDbStatus) {
                        musicDbStatus.textContent = String(item.db_path || "");
                    }
                    try {
                        await loadMusicDbPreview(String(item.name || ""));
                    } catch (error) {
                        if (musicDbStatus) {
                            musicDbStatus.textContent = String(error && error.message || error);
                        }
                    }
                });
                musicDbList.appendChild(button);
            });
        }

        if (musicDbChooseRoot && musicDbRootInput) {
            musicDbChooseRoot.addEventListener("click", async () => {
                musicDbChooseRoot.disabled = true;
                if (musicDbStatus) {
                    musicDbStatus.textContent = "Izvēlies mūzikas kolekcijas mapi…";
                }
                try {
                    const response = await fetch("/choose-music-db-root", {cache:"no-store"});
                    const text = await response.text();
                    if (!response.ok) {
                        throw new Error(text || "Mapi neizdevās izvēlēties.");
                    }
                    if (text) {
                        musicDbRootInput.value = text;
                        if (musicDbStatus) { musicDbStatus.textContent = "Izvēlēta: " + text; }
                    } else if (musicDbStatus) {
                        musicDbStatus.textContent = "Mapes izvēle atcelta.";
                    }
                } catch (error) {
                    if (musicDbStatus) {
                        musicDbStatus.textContent = String(error && error.message || error);
                    }
                } finally {
                    musicDbChooseRoot.disabled = false;
                }
            });
        }

        if (musicDbImport && musicDbNameInput && musicDbRootInput) {
            musicDbImport.addEventListener("click", async () => {
                if (musicDbImport.disabled) { return; }
                const name = String(musicDbNameInput.value || "").trim();
                const root = String(musicDbRootInput.value || "").trim();
                const genre = String(musicDbGenreInput?.value || "").trim();
                if (!name || !root) {
                    if (musicDbStatus) {
                        musicDbStatus.textContent = "Ievadi DB nosaukumu un izvēlies mūzikas mapi.";
                    }
                    return;
                }

                musicDbImport.disabled = true;
                if (musicDbChooseRoot) { musicDbChooseRoot.disabled = true; }
                if (musicDbStatus) {
                    musicDbStatus.textContent = "Nolasa metadatus un veido " + name + " DB…";
                }
                try {
                    const body = new URLSearchParams();
                    body.set("name", name);
                    body.set("root_folder", root);
                    body.set("default_genre", genre);
                    const response = await fetch("/music-db-import", {
                        method:"POST",
                        headers:{"Content-Type":"application/x-www-form-urlencoded"},
                        body:body.toString()
                    });
                    const payload = await response.json();
                    if (!response.ok || !payload.ok) {
                        throw new Error(payload.error || "Mūzikas DB izveide neizdevās.");
                    }
                    if (musicDbStatus) {
                        musicDbStatus.textContent =
                            "Gatavs: " + payload.track_count + " dziesmas · +" +
                            payload.added + " jaunas · " + payload.updated + " atjaunotas · " +
                            payload.unchanged + " nemainītas · " + payload.cover_count +
                            " unikāli albuma attēli" +
                            (payload.errors ? " · kļūdas: " + payload.errors : "");
                    }
                    await loadMusicDbList();
                    await loadMusicDbPreview(payload.name);
                } catch (error) {
                    if (musicDbStatus) {
                        musicDbStatus.textContent = String(error && error.message || error);
                    }
                } finally {
                    musicDbImport.disabled = false;
                    if (musicDbChooseRoot) { musicDbChooseRoot.disabled = false; }
                }
            });
        }

        if (openFreshInstallSetupButton) {
            openFreshInstallSetupButton.addEventListener("click", () => {
                loadMusicDbList().catch((error) => {
                    if (musicDbStatus) {
                        musicDbStatus.textContent = String(error && error.message || error);
                    }
                });
            });
        }

        if (freshInstallModal) {
            window.setTimeout(() => {
                loadMusicDbList().catch(() => {});
            }, 0);
        }
