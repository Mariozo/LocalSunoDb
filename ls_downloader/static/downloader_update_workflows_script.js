        async function runUpdatePreview() {
            markDownloaderViewFresh();
            if (metaResult) {
                metaResult.innerHTML = '<div class="status warn">Sākta DB metadatu pārbaude. Gaida /suno-update-preview…</div>';
            }
            setStatus("Sākta DB metadatu pārbaude. Gaida /suno-update-preview…", "warn");
            showDownloaderTipPopup("DB metadatu pārbaude", "LS sāk metadatu pārbaudi un gaida DB/API atbildi.");
            showRefreshWait("LS veido metadatu pārbaudes priekšskatījumu. Ja Suno vai DB neatbild, lodziņš aizvērsies automātiski.", 0);
            if (!lastRefreshReportHtml) {
                metaResult.innerHTML = "";
            }

            try {
                const { response, data } = await fetchJsonWithTimeout("/suno-update-preview", {}, 45000);
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "DB metadatu pārbaudes priekšskatījums neizdevās");
                }

                if (data.fallback) {
                    setStatus("Metadatu pārbaude rezerves režīmā pabeigta. Kandidāti: " + data.missing_total + ". Pilnās pārbaudes kļūda: " + (data.fallback_error || "nezināma"), "warn");
                } else {
                    setStatus("Metadatu pārbaude pabeigta. Kandidāti: " + data.missing_total + ", Suno API: " + data.api_needed + ", saglabātie dati: " + data.stored_fillable + ", konflikti: " + data.conflict_rows + ".", "ok");
                }

                let counts = "";
                Object.entries(data.field_counts || {}).forEach(([key, value]) => {
                    counts += `<span class="pill yes">${escHtml(key)}: ${escHtml(value)}</span> `;
                });

                let rows = "";
                (data.rows || []).forEach((item) => {
                    let details = `<strong>${escHtml(item.source || "")}</strong>`;
                    if ((item.missing || []).length) {
                        details += `<br>Trūkst: ${escHtml((item.missing || []).join(", "))}`;
                    }
                    if ((item.fillable || []).length) {
                        details += `<br>Aizpildāms: ${escHtml((item.fillable || []).join(", "))}`;
                    }
                    if ((item.conflicts || []).length) {
                        details += `<br><span class="status warn">Nemainīti konflikti: ${escHtml((item.conflicts || []).join(", "))}</span>`;
                    }
                    rows += `
                        <tr>
                            <td><input type="checkbox" class="update-row-check" value="${escHtml(item.id)}" data-missing="${escHtml((item.missing || []).join(','))}"></td>
                            <td><button type="button" class="small-preview-btn" data-id="${escHtml(item.id)}">Priekšskatīt</button></td>
                            <td><strong>${escHtml(item.title)}</strong><br><span class="muted"><code>${escHtml(item.short_id)}</code></span></td>
                            <td>${escHtml(item.workspace)}</td>
                            <td class="missing-list">${details}</td>
                        </tr>
                    `;
                });

                const updatePreviewHtml = `
                    ${lastRefreshReportHtml || ""}
                    <div class="update-preview-scroll">
                    <h3>LS metadatu pārbaudes priekšskatījums</h3>
                    <p class="muted">
                        Aktīvās LS rindas: <strong>${escHtml(data.total_active)}</strong>;
                        derīgās parastās rindas: <strong>${escHtml(data.eligible_total)}</strong>;
                        kandidāti: <strong>${escHtml(data.missing_total)}</strong>.<br>
                        Droši izslēgti — Stemi: <strong>${escHtml(data.excluded_stems)}</strong>,
                        Edit/Section: <strong>${escHtml(data.excluded_edits)}</strong>.
                        Labojumi no saglabātajiem datiem: <strong>${escHtml(data.stored_fillable)}</strong>;
                        Nepieciešams Suno API: <strong>${escHtml(data.api_needed)}</strong>;
                        konfliktu rindas: <strong>${escHtml(data.conflict_rows)}</strong>.
                        ${data.fallback ? `<br><span class="status warn">Rezerves režīms: ${escHtml(data.fallback_error || "pilnā pārbaude neizdevās")}</span>` : ""}
                    </p>
                    <p>${counts}</p>
                    <div class="update-action-bar">
                        <button type="button" class="green" id="refresh-selected-meta-btn">Atjaunot izvēlētos metadatus</button>
                        <button type="button" class="secondary" id="preview-first-selected-btn">Priekšskatīt pirmo izvēlēto</button>
                        <button type="button" class="secondary" id="select-all-shown-btn">Atlasīt pirmos pēc limita</button>
                        <button type="button" class="secondary" id="select-none-btn">Noņemt atlasi</button>
                        <button type="button" class="secondary" id="select-lyrics-prompt-btn">Atlasīt lyrics/prompt</button>
                        <label class="inline-limit-label">Limit
                            <select id="refresh-limit-select">
                                <option value="10">10</option>
                                <option value="25" selected>25</option>
                                <option value="50">50</option>
                                <option value="100">100</option>
                                <option value="all">visi atlasītie</option>
                            </select>
                        </label>
                        <span class="muted" id="selected-count-label">Atlasīti: 0</span>
                    </div>
                    <table class="preview-table select-table">
                        <thead>
                            <tr>
                                <th><input type="checkbox" id="update-check-all"></th>
                                <th>Darbība</th>
                                <th>Nosaukums</th>
                                <th>Darba telpa</th>
                                <th>Avots / metadatu pārbaude</th>
                            </tr>
                        </thead>
                        <tbody>${rows || '<tr><td colspan="5">Nav kandidātu ar trūkstošiem metadatiem.</td></tr>'}</tbody>
                    </table>
                    <p class="muted">
                        Izvēlēto metadatu atjaunošana izveido drošu WAL-aware DB rezerves kopiju un aizpilda tikai tukšos laukus.
                        Esošie konflikti netiek pārrakstīti. Pie 401 vai 429 partija apstājas automātiski.
                    </p>
                    </div>
                `;
                metaResult.innerHTML = updatePreviewHtml;

                function updateSelectedCountLabel() {
                    const label = document.getElementById("selected-count-label");
                    if (!label) { return; }
                    const count = document.querySelectorAll(".update-row-check:checked").length;
                    label.innerText = "Atlasīti: " + count;
                }

                function getRefreshLimitNumber() {
                    const limitSelect = document.getElementById("refresh-limit-select");
                    const rawLimit = limitSelect ? limitSelect.value : "25";
                    if (rawLimit === "all") {
                        return Number.POSITIVE_INFINITY;
                    }
                    return parseInt(rawLimit || "25", 10) || 25;
                }

                function limitChecks(checks) {
                    const limit = getRefreshLimitNumber();
                    return isFinite(limit) ? checks.slice(0, limit) : checks;
                }

                const checkAll = document.getElementById("update-check-all");
                if (checkAll) {
                    checkAll.addEventListener("change", () => {
                        const allChecks = Array.from(document.querySelectorAll(".update-row-check"));
                        allChecks.forEach((check) => { check.checked = false; });
                        if (checkAll.checked) {
                            limitChecks(allChecks).forEach((check) => { check.checked = true; });
                        }
                        updateSelectedCountLabel();
                    });
                }

                document.querySelectorAll(".update-row-check").forEach((check) => {
                    check.addEventListener("change", updateSelectedCountLabel);
                });

                const selectAllShownBtn = document.getElementById("select-all-shown-btn");
                if (selectAllShownBtn) {
                    selectAllShownBtn.addEventListener("click", () => {
                        const allChecks = Array.from(document.querySelectorAll(".update-row-check"));
                        allChecks.forEach((check) => { check.checked = false; });
                        limitChecks(allChecks).forEach((check) => { check.checked = true; });
                        if (checkAll) { checkAll.checked = false; }
                        updateSelectedCountLabel();
                    });
                }

                const selectNoneBtn = document.getElementById("select-none-btn");
                if (selectNoneBtn) {
                    selectNoneBtn.addEventListener("click", () => {
                        document.querySelectorAll(".update-row-check").forEach((check) => {
                            check.checked = false;
                        });
                        if (checkAll) { checkAll.checked = false; }
                        updateSelectedCountLabel();
                    });
                }

                const selectLyricsPromptBtn = document.getElementById("select-lyrics-prompt-btn");
                if (selectLyricsPromptBtn) {
                    selectLyricsPromptBtn.addEventListener("click", () => {
                        const allChecks = Array.from(document.querySelectorAll(".update-row-check"));
                        allChecks.forEach((check) => { check.checked = false; });
                        const matches = allChecks.filter((check) => {
                            const missing = (check.dataset.missing || "").toLowerCase();
                            return missing.includes("lyrics") || missing.includes("prompt");
                        });
                        limitChecks(matches).forEach((check) => { check.checked = true; });
                        if (checkAll) { checkAll.checked = false; }
                        updateSelectedCountLabel();
                    });
                }

                const refreshLimitSelect = document.getElementById("refresh-limit-select");
                if (refreshLimitSelect) {
                    refreshLimitSelect.addEventListener("change", () => {
                        // Keep existing manual checks, but the select-helper buttons will now use the new limit.
                        updateSelectedCountLabel();
                    });
                }

                updateSelectedCountLabel();

                document.querySelectorAll(".small-preview-btn").forEach((btn) => {
                    btn.addEventListener("click", () => {
                        trackIdInput.value = btn.dataset.id || "";
                        previewMetaBtn.click();
                    });
                });
                function getSelectedUpdateIds(applyLimit=false) {
                    let ids = Array.from(document.querySelectorAll(".update-row-check:checked"))
                        .map((check) => check.value)
                        .filter((value) => value);

                    if (applyLimit) {
                        const limitSelect = document.getElementById("refresh-limit-select");
                        const rawLimit = limitSelect ? limitSelect.value : "25";
                        if (rawLimit !== "all") {
                            const limit = parseInt(rawLimit || "25", 10) || 25;
                            ids = ids.slice(0, limit);
                        }
                    }
                    return ids;
                }

                const previewFirstBtn = document.getElementById("preview-first-selected-btn");
                if (previewFirstBtn) {
                    previewFirstBtn.addEventListener("click", () => {
                        const ids = getSelectedUpdateIds(false);
                        if (!ids.length) {
                            setStatus("Nav atzīmēta neviena rinda.", "error");
                            return;
                        }
                        trackIdInput.value = ids[0];
                        previewMetaBtn.click();
                    });
                }

                const refreshSelectedBtn = document.getElementById("refresh-selected-meta-btn");
                if (refreshSelectedBtn) {
                    refreshSelectedBtn.addEventListener("click", async () => {
                        const ids = getSelectedUpdateIds(true);
                        if (!ids.length) {
                            setStatus("Nav atzīmēta neviena rinda.", "error");
                            return;
                        }

                        if (!confirm("Atjaunot metadatus " + ids.length + " dziesmai(-ām)?\n\nLS izveidos DB rezerves kopiju un rakstīs tikai tukšos laukus.\nLimits tiek piemērots jau atlasīšanas brīdī.")) {
                            return;
                        }

                        refreshSelectedBtn.disabled = true;
                        setStatus("Atjaunina izvēlētos metadatus no saglabātajiem datiem / Suno API…");
                        showRefreshWait("LS refreshē <strong>" + escHtml(ids.length) + "</strong> ierakstus.<br>Vispirms tiek izmantoti saglabātie Suno dati, pēc tam — API.", ids.length);

                        try {
                            const body = new URLSearchParams();
                            body.set("track_ids", ids.join("\n"));
                            body.set("overwrite", "0");

                            const response = await fetch("/suno-refresh-selected-metadata", {
                                method: "POST",
                                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                                body: body.toString()
                            });
                            const data = await response.json();

                            if (!response.ok || !data.ok) {
                                throw new Error(data.error || "Izvēlēto metadatu atjaunošana neizdevās");
                            }

                            setStatus("Atjaunošana pabeigta. Dziesmas: " + data.updated_tracks + ", lauki: " + data.total_fields + ", nemainīti konflikti: " + (data.total_conflicts || 0) + ", kļūdas: " + data.errors, data.errors ? "warn" : "ok");

                            let rowsHtml = "";
                            (data.rows || []).forEach((row) => {
                                rowsHtml += `
                                    <tr>
                                        <td><code>${escHtml(row.short_id || "")}</code></td>
                                        <td>${escHtml(row.title || row.track_id || "")}</td>
                                        <td>${escHtml(row.status || "")}</td>
                                        <td>${escHtml((row.fields || []).join(", "))}</td>
                                        <td>${escHtml(row.error || "")}</td>
                                    </tr>
                                `;
                            });

                            lastRefreshReportHtml = `
                                <div class="last-refresh-report">
                                    <h3>Izvēlēto metadatu atjaunošanas rezultāts</h3>
                                    <p class="muted">
                                        Rezerves kopija: <code>${escHtml(data.backup || "")}</code><br>
                                        Atskaite: <code>${escHtml(data.report || "")}</code>
                                    </p>
                                    <table class="preview-table">
                                        <thead>
                                            <tr><th>ID</th><th>Nosaukums</th><th>Status</th><th>Lauki</th><th>Kļūda</th></tr>
                                        </thead>
                                        <tbody>${rowsHtml}</tbody>
                                    </table>
                                    ${data.rate_limited ? '<p class="status warn"><strong>Pieprasījumu limits.</strong> LS apstājās droši. Pagaidi 5–10 minūtes un turpini ar mazāku limitu.</p>' : ''}
                                    ${data.authentication_stopped ? '<p class="status warn"><strong>Sesija beigusies.</strong> LS apstājās droši. Atjauno Suno pieslēgumu un turpini.</p>' : ''}
                                    ${data.total_conflicts ? '<p class="status warn"><strong>Nemainīti konflikti:</strong> ' + escHtml(data.total_conflicts) + '</p>' : ''}
                                    <p class="muted"><strong>Atjaunošanas atskaite paliek atvērta.</strong> Metadatu pārbaudes saraksts pārlasīsies zem šīs atskaites.</p>
                                </div>
                            `;
                            metaResult.innerHTML = lastRefreshReportHtml;
                            setTimeout(() => {
                                runUpdatePreview();
                            }, 1000);
                            if (data.rate_limited || data.authentication_stopped) {
                                setStatus("Atjaunošana droši apturēta pēc pieprasījuma " + data.stopped_after + ". Pēc 401 atjauno pieslēgumu, pēc 429 pagaidi un tad turpini.", "warn");
                            } else {
                                setStatus("Atjaunošana pabeigta. Dziesmas: " + data.updated_tracks + ", lauki: " + data.total_fields + ", nemainīti konflikti: " + (data.total_conflicts || 0) + ", kļūdas: " + data.errors, "ok");
                            }
                        } catch (error) {
                            setStatus(error.message, "error");
                        } finally {
                            hideRefreshWait();
                            refreshSelectedBtn.disabled = false;
                        }
                    });
                }

            } catch (error) {
                setStatus(error.message, "error");
            } finally {
                // v5.102: close both old refresh overlay and restored v4 busy overlay.
                hideRefreshWait();
                forceCloseDownloaderWorkingPopup();
            }
        }

        if (updatePreviewBtn) {
            // v5.104: direct assignment avoids a stale inline onclick that could show Working
            // without running the real Update preview.
            updatePreviewBtn.onclick = (event) => {
                event.preventDefault();
                event.stopPropagation();
                return runUpdatePreview();
            };
        }

        if (refreshTracklistBtn) {
            refreshTracklistBtn.addEventListener("click", async () => {
                markDownloaderViewFresh();
                lastRefreshReportHtml = "";
                metaResult.innerHTML = "";
                setStatus("Lasa jaunākos Suno darba telpu ierakstus…");
                showRefreshWait("LS lasa jaunākos Suno darba telpas ierakstus un salīdzina ar DB.", 1);
                try {
                    const response = await fetch("/suno-tracklist-preview?limit=100&workspace_id=latest");
                    const data = await response.json();
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || "Dziesmu saraksta atjaunošana neizdevās");
                    }

                    let newRows = "";
                    (data.new_items || []).forEach((item) => {
                        newRows += `
                            <tr>
                                <td><input type="checkbox" class="tracklist-new-check" value="${escHtml(item.id || "")}" data-title="${escHtml(item.title || "")}" data-audio-url="${escHtml(item.audio_url || "")}" autocomplete="off" data-default-unchecked="1"></td>
                                <td><code>${escHtml(item.short_id || "")}</code></td>
                                <td><strong>${escHtml(item.title || "")}</strong><br><span class="muted">${escHtml(item.created_at || "")}</span></td>
                                <td>${escHtml(item.workspace || "")}</td>
                                <td>${escHtml(item.model_name || "")}</td>
                                <td>
                                    ${item.has_lyrics ? '<span class="pill yes">lyrics</span>' : '<span class="pill no">nav lyrics</span>'}
                                    ${item.has_prompt ? '<span class="pill yes">prompt</span>' : '<span class="pill no">nav prompt</span>'}
                                    ${item.has_style ? '<span class="pill yes">style</span>' : '<span class="pill no">nav style</span>'}
                                </td>
                            </tr>
                        `;
                    });

                    let changedRows = "";
                    (data.changed_items || []).forEach((item) => {
                        changedRows += `
                            <tr>
                                <td><input type="checkbox" class="title-change-check" value="${escHtml(item.id || "")}"></td>
                                <td><code>${escHtml(item.short_id || "")}</code></td>
                                <td>${escHtml(item.ls_title || "")}</td>
                                <td><strong>${escHtml(item.title || "")}</strong></td>
                                <td>${escHtml(item.workspace || "")}</td>
                            </tr>
                        `;
                    });

                    let existingRows = "";
                    (data.existing_items || []).forEach((item) => {
                        existingRows += `
                            <tr>
                                <td><code>${escHtml(item.short_id || "")}</code></td>
                                <td>${escHtml(item.title || "")}</td>
                                <td>${escHtml(item.workspace || "")}</td>
                            </tr>
                        `;
                    });

                    metaResult.innerHTML = `
                        ${lastRefreshReportHtml || ""}
                        <div class="update-preview-scroll">
                            <h3>Jaunākās Suno darba telpas — kas jauns?</h3>
                            <p class="muted">
                                Saņemti raw: <strong>${escHtml(data.fetched)}</strong>,
                                parastie ieraksti: <strong>${escHtml(data.regular_fetched)}</strong>,
                                izlaisti stemi: <strong>${escHtml(data.skipped_stems)}</strong>,
                                ignorēti: <strong>${escHtml(data.skipped_ignored || 0)}</strong>,
                                jauni Suno, bet nav LS: <strong>${escHtml(data.new_count)}</strong>,
                                mainīti nosaukumi: <strong>${escHtml(data.changed_count || 0)}</strong>,
                                jau ir LS: <strong>${escHtml(data.existing_count)}</strong>.
                            </p>
                            <p class="muted">
                                Pārbaudītās darba telpas:
                                ${(data.workspaces_scanned || []).map((w) => `<span class="field-pill">${escHtml(w.name || w.id)}: ${escHtml(w.regular || 0)} parasti, ${escHtml(w.stems || 0)} stemi</span>`).join(" ")}
                            </p>
                            <h3>Jaunie parastie Suno ieraksti, kuru nav LS DB</h3>
                            <table class="preview-table">
                                <thead><tr><th>Importēt</th><th>ID</th><th>Nosaukums / created_at</th><th>Darba telpa</th><th>Modelis</th><th>API lauki</th></tr></thead>
                                <tbody>${newRows || '<tr><td colspan="6">Nav jaunu ierakstu šajā pēdējo 100 Suno ierakstu pārbaudē.</td></tr>'}</tbody>
                            </table>
                            <div class="tracklist-action-strip" data-tracklist-actions-version="2">
                                <details class="tracklist-tools" open>
                                    <summary>Darbības / atlases rīki</summary>
                                    <div class="tracklist-action-groups">
                                        <div class="tracklist-primary-actions">
                                            <button type="button" class="purple" id="listen-selected-tracklist-btn">Noklausīties izvēlētos</button>
                                            <button type="button" class="green" id="import-selected-tracklist-btn">Importēt izvēlētos jaunos LS DB</button>
                                            <button type="button" class="secondary" id="ignore-selected-tracklist-btn">Ignorēt izvēlētos</button>
                                        </div>
                                        <div class="tracklist-secondary-actions">
                                            <button type="button" class="secondary" id="show-ignored-tracklist-btn">Rādīt ignorētos</button>
                                            <button type="button" class="secondary" id="tracklist-select-all-btn">Atlasīt visus jaunos</button>
                                            <button type="button" class="secondary" id="tracklist-select-none-btn">Noņemt atlasi</button>
                                            <button type="button" class="secondary" id="clear-downloader-state-btn">Notīrīt saglabāto skatu</button>
                                        </div>
                                        <p class="muted tracklist-action-help">Noklausīšanās rāda atskaņotājus zem pogām. Imports pievieno LS DB. Ignorētie turpmāk sarakstā netiek rādīti.</p>
                                    </div>
                                </details>
                            </div>
                            <div id="tracklist-audio-preview"></div>
                            <div id="tracklist-import-result"></div>
                            <h3>Jau ir LS DB, bet Suno.com nosaukums ir mainīts</h3>
                            <table class="preview-table">
                                <thead><tr><th>Piemērot</th><th>ID</th><th>LS nosaukums</th><th>Suno nosaukums</th><th>Darba telpa</th></tr></thead>
                                <tbody>${changedRows || '<tr><td colspan="5">Nav nosaukumu izmaiņu šajā Suno darba telpu pārbaudē.</td></tr>'}</tbody>
                            </table>
                            <div class="update-action-bar">
                                <button type="button" class="green" id="update-selected-titles-btn">Atjaunot izvēlētos nosaukumus LS DB</button>
                                <span class="muted">Atjauno tikai nosaukuma laukus. Pirms rakstīšanas izveido rezerves kopiju.</span>
                            </div>
                            <div id="title-update-result"></div>

                            <h3>Jau ir LS DB — jaunākais paraugs</h3>
                            <table class="preview-table">
                                <thead><tr><th>ID</th><th>Nosaukums</th><th>Darba telpa</th></tr></thead>
                                <tbody>${existingRows || '<tr><td colspan="3">Nav sakritību.</td></tr>'}</tbody>
                            </table>
                            <p class="muted">
                                Šis ir tikai priekšskatījums. Drošs imports ar rezerves kopiju tiek veikts tikai atzīmētajiem jaunajiem ierakstiem.
                            </p>
                        </div>
                    `;
                    document.querySelectorAll(".tracklist-new-check").forEach((check) => {
                        check.checked = false;
                        check.defaultChecked = false;
                    });
                    updateDownloaderEmptyActions();

                    const tracklistSelectAllBtn = document.getElementById("tracklist-select-all-btn");
                    const tracklistSelectNoneBtn = document.getElementById("tracklist-select-none-btn");
                    const listenSelectedTracklistBtn = document.getElementById("listen-selected-tracklist-btn");
                    const importSelectedTracklistBtn = document.getElementById("import-selected-tracklist-btn");
                    const ignoreSelectedTracklistBtn = document.getElementById("ignore-selected-tracklist-btn");
                    const showIgnoredTracklistBtn = document.getElementById("show-ignored-tracklist-btn");
                    const clearDownloaderStateBtn = document.getElementById("clear-downloader-state-btn");
                    const updateSelectedTitlesBtn = document.getElementById("update-selected-titles-btn");

                    function getSelectedTracklistIds() {
                        return Array.from(document.querySelectorAll(".tracklist-new-check:checked"))
                            .map((check) => check.value)
                            .filter((value) => value);
                    }

                    if (listenSelectedTracklistBtn) {
                        listenSelectedTracklistBtn.addEventListener("click", () => {
                            const checks = Array.from(document.querySelectorAll(".tracklist-new-check:checked"));
                            const box = document.getElementById("tracklist-audio-preview");
                            if (!checks.length) {
                                alert("Nav atzīmēts neviens Suno ieraksts noklausīšanai.");
                                return;
                            }
                            let audioRows = "";
                            checks.forEach((check, index) => {
                                const title = check.dataset.title || check.value || "";
                                const trackId = String(check.value || "").trim();
                                const sunoUrl = trackId ? "https://suno.com/song/" + encodeURIComponent(trackId) : "https://suno.com/";
                                const sunoPlayUrl = trackId ? "https://suno.com/embed/" + encodeURIComponent(trackId) + "?auto_play=true&autoplay=1" : sunoUrl;
                                audioRows += `
                                    <tr>
                                        <td>${index + 1}</td>
                                        <td><strong>${escHtml(title)}</strong><br><code>${escHtml(trackId.slice(0, 8))}</code></td>
                                        <td><a class="suno-open-play-btn" href="${escHtml(sunoPlayUrl)}" target="_blank" rel="noopener" title="Atvērt un atskaņot dziesmu Suno.com" aria-label="Atvērt ${escHtml(title)} Suno.com">▶</a></td>
                                    </tr>
                                `;
                            });
                            if (box) {
                                box.innerHTML = `
                                    <h3>Noklausīties izvēlētos — Suno.com</h3>
                                    <table class="preview-table">
                                        <thead><tr><th>#</th><th>Nosaukums</th><th>Suno.com</th></tr></thead>
                                        <tbody>${audioRows}</tbody>
                                    </table>
                                `;
                                box.scrollIntoView({ block: "nearest", behavior: "smooth" });
                            }
                        });
                    }

                    if (updateSelectedTitlesBtn) {
                        updateSelectedTitlesBtn.addEventListener("click", async () => {
                            const ids = Array.from(document.querySelectorAll(".title-change-check:checked"))
                                .map((check) => check.value)
                                .filter((value) => value);
                            if (!ids.length) {
                                alert("Nav atzīmēta neviena nosaukuma izmaiņa.");
                                return;
                            }
                            if (!confirm("Atjaunot " + ids.length + " nosaukumu(-us) LS DB no Suno.com?\n\nTiks izveidota DB rezerves kopija.")) {
                                return;
                            }
                            try {
                                const body = new URLSearchParams();
                                body.set("track_ids", ids.join("\n"));
                                body.set("workspace_id", "latest");
                                body.set("limit", "100");
                                const response = await fetch("/suno-update-selected-titles", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                                    body: body.toString()
                                });
                                const updateData = await response.json();
                                if (!response.ok || !updateData.ok) {
                                    throw new Error(updateData.error || "Nosaukumu atjaunošana neizdevās");
                                }
                                const box = document.getElementById("title-update-result");
                                if (box) {
                                    box.innerHTML = `<p class="status ok">Atjaunināti nosaukumi: ${escHtml(updateData.updated)}. Rezerves kopija: <code>${escHtml(updateData.backup || "")}</code></p>`;
                                }
                                setStatus("Nosaukumu atjaunošana pabeigta. Atjaunināti: " + updateData.updated, "ok");
                            } catch (error) {
                                setStatus("Nosaukumu atjaunošanas kļūda: " + error.message, "error");
                            }
                        });
                    }

                    if (tracklistSelectAllBtn) {
                        tracklistSelectAllBtn.addEventListener("click", () => {
                            document.querySelectorAll(".tracklist-new-check").forEach((check) => check.checked = true);
                            saveDownloaderState(false);
                        });
                    }
                    if (tracklistSelectNoneBtn) {
                        tracklistSelectNoneBtn.addEventListener("click", () => {
                            document.querySelectorAll(".tracklist-new-check").forEach((check) => check.checked = false);
                            saveDownloaderState(false);
                        });
                    }
                    if (clearDownloaderStateBtn) {
                        clearDownloaderStateBtn.addEventListener("click", async () => {
                            await clearSavedDownloaderView();
                        });
                    }
                    if (showIgnoredTracklistBtn) {
                        showIgnoredTracklistBtn.addEventListener("click", async () => {
                            await showIgnoredTracklist();
                        });
                    }
                    if (ignoreSelectedTracklistBtn) {
                        ignoreSelectedTracklistBtn.addEventListener("click", async () => {
                            const ids = getSelectedTracklistIds();
                            if (!ids.length) {
                                alert("Nav atzīmēts neviens Suno ieraksts ignorēšanai.");
                                return;
                            }
                            if (!confirm("Ignorēt izvēlētos " + ids.length + " Suno ierakstus?\n\nTie netiks dzēsti no Suno.com, tikai vairs netiks rādīti LS sarakstā “Kas jauns?”.")) {
                                return;
                            }
                            try {
                                const body = new URLSearchParams();
                                body.set("track_ids", ids.join("\n"));
                                const response = await fetch("/suno-ignore-selected-tracklist", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                                    body: body.toString()
                                });
                                const ignoreData = await response.json();
                                if (!response.ok || !ignoreData.ok) {
                                    throw new Error(ignoreData.error || "Ignorēšana neizdevās");
                                }
                                setStatus("Ignorēti ieraksti: " + ignoreData.ignored_added + ". Atjauno dziesmu sarakstu, lai tos paslēptu.", "ok");
                                document.querySelectorAll(".tracklist-new-check:checked").forEach((check) => {
                                    const row = check.closest("tr");
                                    if (row) { row.remove(); }
                                });
                            } catch (error) {
                                setStatus("Ignorēšanas kļūda: " + error.message, "error");
                            }
                        });
                    }

                    if (importSelectedTracklistBtn) {
                        importSelectedTracklistBtn.addEventListener("click", async () => {
                            const ids = getSelectedTracklistIds();
                            const resultBox = document.getElementById("tracklist-import-result");
                            if (!ids.length) {
                                alert("Nav atzīmēts neviens jaunais Suno ieraksts.");
                                return;
                            }
                            if (!confirm("Importēt izvēlētos " + ids.length + " jaunos Suno ierakstus LS DB?\n\nTiks izveidota DB rezerves kopija. Audio faili vēl netiks lejupielādēti.")) {
                                return;
                            }
                            showRefreshWait("LS importē <strong>" + escHtml(ids.length) + "</strong> jaunos Suno ierakstus DB.", ids.length);
                            try {
                                const body = new URLSearchParams();
                                body.set("track_ids", ids.join("\n"));
                                body.set("workspace_id", "latest");
                                body.set("limit", "100");
                                const response = await fetch("/suno-import-selected-tracklist", {
                                    method: "POST",
                                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                                    body: body.toString()
                                });
                                const importData = await response.json();
                                if (!response.ok || !importData.ok) {
                                    throw new Error(importData.error || "Imports neizdevās");
                                }
                                let importRows = "";
                                (importData.rows || []).forEach((row) => {
                                    importRows += `
                                        <tr>
                                            <td><code>${escHtml(row.short_id || "")}</code></td>
                                            <td>${escHtml(row.title || "")}</td>
                                            <td>${escHtml(row.status || "")}</td>
                                            <td>${escHtml(row.error || "")}</td>
                                        </tr>
                                    `;
                                });
                                try {
                                    if (Array.isArray(importData.last_imported_ids) && importData.last_imported_ids.length) {
                                        localStorage.setItem("ls_last_imported_ids", JSON.stringify(importData.last_imported_ids));
                                    }
                                } catch (error) {}
                                const exactJustImported = Number(importData.inserted || 0) > 0
                                    && Number(importData.skipped_existing || 0) === 0
                                    && Number(importData.errors || 0) === 0
                                    && importData.last_imported_url;
                                const openUrl = exactJustImported ? importData.last_imported_url : importData.selected_url;
                                const openLabel = exactJustImported ? "Atvērt tikko importētos Suno datubāzē" : "Atvērt izvēlētos Suno datubāzē";
                                const openLink = openUrl
                                    ? `<a class="btn" href="${escHtml(openUrl)}">${escHtml(openLabel)}</a>`
                                    : "";
                                if (resultBox) {
                                    resultBox.innerHTML = `
                                        <h3>Importa rezultāts</h3>
                                        <p class="status ok">
                                            Pievienoti: ${escHtml(importData.inserted)}.
                                            Izlaisti jau esošie: ${escHtml(importData.skipped_existing)}.
                                            Rezerves kopija: <code>${escHtml(importData.backup || "")}</code><br>
                                            Atskaite: <code>${escHtml(importData.report || "")}</code><br>
                                            ${openLink}
                                        </p>
                                        <table class="preview-table">
                                            <thead><tr><th>ID</th><th>Nosaukums</th><th>Status</th><th>Kļūda</th></tr></thead>
                                            <tbody>${importRows}</tbody>
                                        </table>
                                        <p class="muted">Spied <strong>${escHtml(openLabel)}</strong>. Tur būs tieši šīs atlases ieraksti, atzīmēti ar checkbox.</p>
                                    `;
                                }
                                setStatus("Import OK. Pievienoti: " + importData.inserted + ", izlaisti jau esošie: " + importData.skipped_existing + ".", "ok");
                            } catch (error) {
                                setStatus("Importa kļūda: " + error.message, "error");
                            } finally {
                                hideRefreshWait();
                            }
                        });
                    }

                    setStatus("Dziesmu saraksta priekšskatījums pabeigts. Parastie: " + data.regular_fetched + ", izlaisti stemi: " + data.skipped_stems + ", ignorēti: " + (data.skipped_ignored || 0) + ", jauni: " + data.new_count + ", mainīti nosaukumi: " + (data.changed_count || 0) + ", jau esoši: " + data.existing_count, (data.new_count || data.changed_count) ? "warn" : "ok");
                } catch (error) {
                    setStatus("Dziesmu saraksta kļūda: " + error.message, "error");
                } finally {
                    hideRefreshWait();
                }
            });
        }

        previewMetaBtn.addEventListener("click", async () => {
            markDownloaderViewFresh();
            const trackId = (trackIdInput.value || "").trim();
            if (!trackId) {
                setStatus("Trūkst Track ID.", "error");
                return;
            }

            const stateBeforePreview = collectDownloaderState();
            setStatus("Iegūst metadatus no Suno API…");
            metaResult.innerHTML = "";

            try {
                const response = await fetch("/suno-meta-preview?track_id=" + encodeURIComponent(trackId));
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "Metadatu priekšskatījums neizdevās");
                }

                setStatus("Priekšskatījums pabeigts. Aizpildāmi lauki: " + data.fillable_count, "ok");

                let rows = "";
                (data.fields || []).forEach((item) => {
                    rows += `
                        <tr>
                            <td><code>${escHtml(item.api_key)}</code></td>
                            <td><code>${escHtml(item.db_column || "-")}</code></td>
                            <td>${item.api_present ? '<span class="pill yes">jā</span>' : '<span class="pill no">nē</span>'}</td>
                            <td>${item.db_empty ? '<span class="pill yes">tukšs</span>' : '<span class="pill no">aizpildīts</span>'}</td>
                            <td>${item.can_fill ? '<span class="pill yes">aizpildīt</span>' : '<span class="pill no">izlaist</span>'}</td>
                            <td>${escHtml(item.api_preview)}</td>
                        </tr>
                    `;
                });

                const savedBeforePreview = stateBeforePreview.html || "";
                metaResult.innerHTML = `
                    <div class="update-action-bar">
                        <button type="button" class="secondary" id="meta-preview-back-btn">Atpakaļ uz iepriekšējo sarakstu</button>
                        <button type="button" class="secondary" id="meta-preview-close-btn">Aizvērt priekšskatījumu</button>
                    </div>
                    <h3>${escHtml(data.title || data.track_id)}</h3>
                    <p class="muted">Track ID: <code>${escHtml(data.track_id)}</code> | LS DB: <strong>${data.found_in_db ? "JĀ" : "NĒ"}</strong></p>
                    <table class="preview-table">
                        <thead>
                            <tr>
                                <th>API lauks</th>
                                <th>DB kolonna</th>
                                <th>API</th>
                                <th>DB</th>
                                <th>Darbība</th>
                                <th>API priekšskatījums</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                    <h3>API metadatu kopsavilkums</h3>
                    <pre>${escHtml(JSON.stringify(data.api_meta || {}, null, 2))}</pre>
                `;
                const backBtn = document.getElementById("meta-preview-back-btn");
                const closeBtn = document.getElementById("meta-preview-close-btn");
                if (backBtn) {
                    backBtn.addEventListener("click", () => {
                        const savedHtml = savedBeforePreview || "";
                        if (savedHtml) {
                            metaResult.innerHTML = savedHtml;
                            downloaderRestoredView = true;
                            metaResult.dataset.restoredView = "1";
                            applyDownloaderControlState(stateBeforePreview);
                            setStatus("Atgriezās iepriekšējā sarakstā.", "ok");
                            saveDownloaderState(true);
                        } else {
                            runUpdatePreview();
                        }
                    });
                }
                if (closeBtn) {
                    closeBtn.addEventListener("click", () => {
                        markDownloaderViewFresh();
                        metaResult.innerHTML = "";
                        setStatus("Priekšskatījums aizvērts.", "ok");
                    });
                }
            } catch (error) {
                setStatus(error.message, "error");
            }
        });

        const mainMenuBtn = document.getElementById("main-menu-btn");
        const mainMenu = document.getElementById("main-menu");
        const profileMenuBtn = document.getElementById("profile-menu-btn");
        const profileMenu = document.getElementById("profile-menu");

        function closeTopMenus(except=null) {
            [mainMenu, profileMenu].forEach((menu) => {
                if (menu && menu !== except) {
                    menu.classList.add("hidden");
                }
            });
        }

        if (mainMenuBtn && mainMenu) {
            mainMenuBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                const willOpen = mainMenu.classList.contains("hidden");
                closeTopMenus(mainMenu);
                mainMenu.classList.toggle("hidden", !willOpen);
            });
        }

        if (profileMenuBtn && profileMenu) {
            profileMenuBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                const willOpen = profileMenu.classList.contains("hidden");
                closeTopMenus(profileMenu);
                profileMenu.classList.toggle("hidden", !willOpen);
            });
        }

        document.addEventListener("click", () => closeTopMenus());
