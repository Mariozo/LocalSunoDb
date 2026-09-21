        const downloaderWavPanel = document.getElementById("downloader-wav-selection-panel");
        const downloaderWavTrackTitle = document.getElementById("downloader-wav-track-title");
        const downloaderWavTrackId = document.getElementById("downloader-wav-track-id");
        const downloaderWavProposedFamily = document.getElementById("downloader-wav-proposed-family");
        const downloaderWavUseProposed = document.getElementById("downloader-wav-use-proposed");
        const downloaderWavFamilyState = document.getElementById("downloader-wav-family-state");
        const downloaderWavAlternatives = document.getElementById("downloader-wav-alternatives");
        const downloaderWavExistingFamily = document.getElementById("downloader-wav-existing-family");
        const downloaderWavUseExisting = document.getElementById("downloader-wav-use-existing");
        const downloaderWavNewFamily = document.getElementById("downloader-wav-new-family");
        const downloaderWavCreateNew = document.getElementById("downloader-wav-create-new");
        const downloaderWavCategory = document.getElementById("downloader-wav-category");
        const downloaderWavVariant = document.getElementById("downloader-wav-variant");
        const downloaderWavTargetPath = document.getElementById("downloader-wav-target-path");
        const downloaderWavStemsPath = document.getElementById("downloader-wav-stems-path");
        const downloaderWavStatus = document.getElementById("downloader-wav-status");
        const downloaderWavDownload = document.getElementById("downloader-wav-download");
        const downloaderWavResult = document.getElementById("downloader-wav-result");
        const downloaderWavResultTitle = document.getElementById("downloader-wav-result-title");
        const downloaderWavResultText = document.getElementById("downloader-wav-result-text");
        const downloaderWavResultPath = document.getElementById("downloader-wav-result-path");
        let downloaderWavRow = null;
        let downloaderWavRequestActive = false;

        function setDownloaderWavStatus(message, mode="") {
            if (!downloaderWavStatus) { return; }
            downloaderWavStatus.className = "status " + (mode || "");
            downloaderWavStatus.textContent = message || "";
        }

        function setDownloaderWavBusy(busy) {
            downloaderWavRequestActive = Boolean(busy);
            [
                downloaderWavUseProposed,
                downloaderWavUseExisting,
                downloaderWavCreateNew,
                downloaderWavDownload,
            ].forEach((button) => {
                if (!button) { return; }
                button.disabled = downloaderWavRequestActive
                    || (button === downloaderWavDownload && !(downloaderWavRow && downloaderWavRow.family_confirmed));
            });
        }

        async function downloaderWavPost(url, values) {
            const body = new URLSearchParams();
            Object.entries(values || {}).forEach(([key, value]) => {
                body.set(key, String(value == null ? "" : value));
            });
            const response = await fetch(url, {
                method: "POST",
                headers: {"Content-Type": "application/x-www-form-urlencoded"},
                body: body.toString(),
            });
            let data = null;
            try { data = await response.json(); }
            catch (error) { data = null; }
            if (!response.ok || !data || !data.ok || Number(data.errors || 0) > 0) {
                const rowError = data && Array.isArray(data.rows) && data.rows[0]
                    ? String(data.rows[0].error || "")
                    : "";
                throw new Error(
                    (data && data.error)
                    || rowError
                    || ("Importa pieprasījums neizdevās: HTTP " + response.status)
                );
            }
            return data;
        }

        function populateDownloaderWavFamilies(row) {
            if (!downloaderWavExistingFamily) { return; }
            downloaderWavExistingFamily.innerHTML = "";
            const options = Array.isArray(row.family_options) ? row.family_options : [];
            const mappedTitle = String(row.mapped_family_title || "").trim();
            if (!options.length) {
                const option = document.createElement("option");
                option.value = "";
                option.textContent = "Nav esošu lokālo saimju";
                downloaderWavExistingFamily.appendChild(option);
                downloaderWavExistingFamily.disabled = true;
                if (downloaderWavUseExisting) { downloaderWavUseExisting.disabled = true; }
            } else {
                downloaderWavExistingFamily.disabled = false;
                options.forEach((item, index) => {
                    const option = document.createElement("option");
                    const title = String((item && item.title) || "").trim();
                    const similarity = Math.round(Number((item && item.similarity) || 0) * 100);
                    const categories = Array.isArray(item && item.categories)
                        ? item.categories.filter(Boolean).join(" + ")
                        : "";
                    option.value = title;
                    option.textContent = (
                        (item && item.is_similar ? "Ieteikts " + similarity + "% — " : "")
                        + title
                        + (categories ? " [" + categories + "]" : "")
                    );
                    if (
                        mappedTitle
                        && title.toLocaleLowerCase() === mappedTitle.toLocaleLowerCase()
                    ) {
                        option.selected = true;
                    } else if (!mappedTitle && item && item.is_similar && index === 0) {
                        option.selected = true;
                    }
                    downloaderWavExistingFamily.appendChild(option);
                });
            }
            if (downloaderWavNewFamily) {
                downloaderWavNewFamily.value = String(
                    row.proposed_family_title
                    || row.local_family_title
                    || row.title
                    || ""
                ).trim();
            }
        }

        function applyDownloaderWavRow(row) {
            downloaderWavRow = Object.assign({}, row || {});
            if (downloaderWavTrackTitle) {
                downloaderWavTrackTitle.textContent = downloaderWavRow.title || "";
            }
            if (downloaderWavTrackId) {
                downloaderWavTrackId.textContent = downloaderWavRow.track_id || "";
            }
            const proposedTitle = String(
                downloaderWavRow.proposed_family_title
                || downloaderWavRow.local_family_title
                || downloaderWavRow.title
                || ""
            ).trim();
            if (downloaderWavProposedFamily) {
                downloaderWavProposedFamily.textContent = proposedTitle;
            }
            if (downloaderWavCategory) {
                downloaderWavCategory.textContent = downloaderWavRow.category || "";
            }
            if (downloaderWavVariant) {
                downloaderWavVariant.textContent = downloaderWavRow.variant || "";
            }
            if (downloaderWavTargetPath) {
                downloaderWavTargetPath.textContent = downloaderWavRow.target_path || "";
            }
            if (downloaderWavStemsPath) {
                downloaderWavStemsPath.textContent = downloaderWavRow.stems_folder || "";
            }

            populateDownloaderWavFamilies(downloaderWavRow);
            const confirmed = Boolean(downloaderWavRow.family_confirmed);
            if (downloaderWavUseProposed) {
                downloaderWavUseProposed.hidden = confirmed;
                downloaderWavUseProposed.disabled = downloaderWavRequestActive;
            }
            if (downloaderWavFamilyState) {
                downloaderWavFamilyState.textContent = confirmed
                    ? "Lokālā saime apstiprināta šim Track ID"
                    : "Nepieciešams apstiprinājums";
                downloaderWavFamilyState.classList.toggle("confirmed", confirmed);
            }
            if (downloaderWavDownload) {
                downloaderWavDownload.disabled = downloaderWavRequestActive || !confirmed;
            }
            if (confirmed) {
                setDownloaderWavStatus(
                    "Lokālā saime apstiprināta. Pārbaudi precīzo ceļu un pēc tam importē WAV.",
                    "ok"
                );
            } else {
                setDownloaderWavStatus(
                    "Apstiprini ieteikto lokālo saimi vai izvēlies citu.",
                    "warn"
                );
            }
        }

        async function confirmDownloaderWavFamily(action, title) {
            if (downloaderWavRequestActive || !downloaderWavRow) { return; }
            const cleanTitle = String(title || "").trim();
            if (!cleanTitle) {
                setDownloaderWavStatus("Ievadi vai izvēlies lokālās saimes nosaukumu.", "error");
                return;
            }
            setDownloaderWavBusy(true);
            setDownloaderWavStatus("Saglabā Track ID → lokālā saime…");
            try {
                const data = await downloaderWavPost("/confirm-local-family", {
                    track_id: downloaderWavRow.track_id || "",
                    action: action,
                    family_title: cleanTitle,
                });
                applyDownloaderWavRow(data.row || {});
                if (downloaderWavAlternatives) {
                    downloaderWavAlternatives.removeAttribute("open");
                }
            } catch (error) {
                setDownloaderWavStatus(error.message || "Neizdevās apstiprināt lokālo saimi.", "error");
            } finally {
                setDownloaderWavBusy(false);
            }
        }

        if (downloaderWavUseProposed) {
            downloaderWavUseProposed.addEventListener("click", () => {
                if (!downloaderWavRow) { return; }
                const title = String(
                    downloaderWavRow.proposed_family_title
                    || downloaderWavRow.local_family_title
                    || downloaderWavRow.title
                    || ""
                ).trim();
                const options = Array.isArray(downloaderWavRow.family_options)
                    ? downloaderWavRow.family_options
                    : [];
                const exactExisting = options.some((item) =>
                    String((item && item.title) || "").trim().toLocaleLowerCase()
                    === title.toLocaleLowerCase()
                );
                confirmDownloaderWavFamily(exactExisting ? "existing" : "new", title);
            });
        }

        if (downloaderWavUseExisting) {
            downloaderWavUseExisting.addEventListener("click", () => {
                confirmDownloaderWavFamily(
                    "existing",
                    downloaderWavExistingFamily ? downloaderWavExistingFamily.value : ""
                );
            });
        }

        if (downloaderWavCreateNew) {
            downloaderWavCreateNew.addEventListener("click", () => {
                confirmDownloaderWavFamily(
                    "new",
                    downloaderWavNewFamily ? downloaderWavNewFamily.value : ""
                );
            });
        }

        if (downloaderWavNewFamily) {
            downloaderWavNewFamily.addEventListener("keydown", (event) => {
                if (event.key !== "Enter") { return; }
                event.preventDefault();
                confirmDownloaderWavFamily("new", downloaderWavNewFamily.value);
            });
        }

        if (downloaderWavDownload) {
            downloaderWavDownload.addEventListener("click", async () => {
                if (
                    downloaderWavRequestActive
                    || !downloaderWavRow
                    || !downloaderWavRow.family_confirmed
                ) { return; }
                setDownloaderWavBusy(true);
                downloaderWavDownload.textContent = "Importē WAV…";
                setDownloaderWavStatus(
                    "Suno sagatavo WAV. LS to saglabās lokāli un piesaistīs izvēlētajam Track ID."
                );
                if (downloaderWavResult) { downloaderWavResult.hidden = true; }
                try {
                    const data = await downloaderWavPost("/download-selected-wav", {
                        track_ids: downloaderWavRow.track_id || "",
                    });
                    const firstRow = Array.isArray(data.rows) && data.rows.length
                        ? data.rows[0]
                        : {};
                    const downloaded = Number(data.downloaded || 0);
                    const skipped = Number(data.skipped || 0);
                    if (downloaderWavResult) { downloaderWavResult.hidden = false; }
                    if (downloaderWavResultTitle) {
                        downloaderWavResultTitle.textContent = downloaded
                            ? "Importēts un piesaistīts"
                            : (skipped ? "Jau piesaistīts" : "Pabeigts");
                    }
                    if (downloaderWavResultText) {
                        downloaderWavResultText.textContent = (
                            "Importēts: " + downloaded
                            + " · Jau piesaistīts: " + skipped
                            + " · Kļūdas: " + Number(data.errors || 0)
                        );
                    }
                    if (downloaderWavResultPath) {
                        downloaderWavResultPath.textContent = firstRow.path || "";
                    }
                    setDownloaderWavStatus(
                        downloaded
                            ? "WAV importēts un piesaistīts izvēlētajam Track ID."
                            : "Šim Track ID jau ir piesaistīts lokāls WAV.",
                        "ok"
                    );
                    downloaderWavDownload.disabled = true;
                } catch (error) {
                    setDownloaderWavStatus(
                        error.message
                        || "WAV imports neizdevās. Sadaļā “Savienojums” atjauno Suno pieslēgumu un mēģini vēlreiz.",
                        "error"
                    );
                } finally {
                    downloaderWavRequestActive = false;
                    downloaderWavDownload.textContent = "Importēt WAV";
                    if (
                        downloaderWavRow
                        && downloaderWavRow.family_confirmed
                        && (!downloaderWavResult || downloaderWavResult.hidden)
                    ) {
                        downloaderWavDownload.disabled = false;
                    }
                    [
                        downloaderWavUseProposed,
                        downloaderWavUseExisting,
                        downloaderWavCreateNew,
                    ].forEach((button) => {
                        if (button) { button.disabled = false; }
                    });
                }
            });
        }

        async function loadDownloaderWavSelection() {
            const params = new URLSearchParams(window.location.search);
            let pendingTrackId = "";
            try {
                pendingTrackId = String(
                    window.sessionStorage.getItem("ls_pending_wav_track_id") || ""
                ).trim();
            } catch (error) {}
            const trackId = String(
                params.get("selected_wav_track_id") || pendingTrackId || ""
            ).trim();
            if (!trackId || !downloaderWavPanel) { return; }
            try {
                window.sessionStorage.removeItem("ls_pending_wav_track_id");
            } catch (error) {}
            downloaderWavPanel.hidden = false;
            setActiveDownloaderSection("audio", true, false);
            setDownloaderWavStatus("Ielādē izvēlēto dziesmu…");
            setDownloaderWavBusy(true);
            try {
                const data = await downloaderWavPost("/preview-selected-wav-download", {
                    track_ids: trackId,
                });
                const row = Array.isArray(data.rows) && data.rows.length
                    ? data.rows[0]
                    : null;
                if (!row) { throw new Error("Izvēlētās dziesmas priekšskatījums ir tukšs."); }
                applyDownloaderWavRow(row);
                window.requestAnimationFrame(() => {
                    downloaderWavPanel.scrollIntoView({behavior: "smooth", block: "start"});
                });
            } catch (error) {
                setDownloaderWavStatus(
                    error.message || "Neizdevās ielādēt izvēlēto dziesmu.",
                    "error"
                );
            } finally {
                setDownloaderWavBusy(false);
            }
        }

        loadDownloaderWavSelection();
