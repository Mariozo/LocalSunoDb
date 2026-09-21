        async function refreshSelectedMetadataFromRestoredView(button) {
            const ids = getCurrentSelectedUpdateIds(true);
            if (!ids.length) {
                setStatus("Nav atzīmēta neviena rinda.", "error");
                return;
            }
            if (!confirm("Atjaunot metadatus " + ids.length + " dziesmai(-ām)?\n\nLS izveidos DB rezerves kopiju un rakstīs tikai tukšos laukus.")) {
                return;
            }

            button.disabled = true;
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
                            <thead><tr><th>ID</th><th>Nosaukums</th><th>Status</th><th>Lauki</th><th>Kļūda</th></tr></thead>
                            <tbody>${rowsHtml}</tbody>
                        </table>
                        ${data.rate_limited ? '<p class="status warn"><strong>Pieprasījumu limits.</strong> LS apstājās droši.</p>' : ''}
                        ${data.authentication_stopped ? '<p class="status warn"><strong>Sesija beigusies.</strong> LS apstājās droši. Atjauno Suno pieslēgumu un turpini.</p>' : ''}
                        ${data.total_conflicts ? '<p class="status warn"><strong>Nemainīti konflikti:</strong> ' + escHtml(data.total_conflicts) + '</p>' : ''}
                    </div>
                `;
                markDownloaderViewFresh();
                metaResult.innerHTML = lastRefreshReportHtml;
                setStatus("Atjaunošana pabeigta. Dziesmas: " + data.updated_tracks + ", lauki: " + data.total_fields + ", nemainīti konflikti: " + (data.total_conflicts || 0) + ", kļūdas: " + data.errors, data.errors ? "warn" : "ok");
                saveDownloaderState(true);
                setTimeout(() => runUpdatePreview(), 500);
            } catch (error) {
                setStatus(error.message, "error");
            } finally {
                hideRefreshWait();
                button.disabled = false;
            }
        }

        function listenSelectedFromRestoredView() {
            const checks = getCurrentSelectedTracklistChecks();
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
                saveDownloaderState(false);
            }
        }

        async function updateSelectedTitlesFromRestoredView() {
            const ids = Array.from(metaResult.querySelectorAll(".title-change-check:checked"))
                .map((check) => check.value)
                .filter((value) => value);
            if (!ids.length) {
                alert("Nav atzīmēta neviena nosaukuma izmaiņa.");
                return;
            }
            if (!confirm("Atjaunot " + ids.length + " nosaukumu(-us) LS DB no Suno.com?\n\nTiks izveidota DB rezerves kopija.")) { return; }
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
                const data = await response.json();
                if (!response.ok || !data.ok) { throw new Error(data.error || "Nosaukumu atjaunošana neizdevās"); }
                const box = document.getElementById("title-update-result");
                if (box) {
                    box.innerHTML = `<p class="status ok">Atjaunināti nosaukumi: ${escHtml(data.updated)}. Rezerves kopija: <code>${escHtml(data.backup || "")}</code></p>`;
                }
                setStatus("Nosaukumu atjaunošana pabeigta. Atjaunināti: " + data.updated, "ok");
                saveDownloaderState(true);
            } catch (error) {
                setStatus("Nosaukumu atjaunošanas kļūda: " + error.message, "error");
            }
        }

        async function ignoreSelectedFromRestoredView() {
            const checks = getCurrentSelectedTracklistChecks();
            const ids = checks.map((check) => check.value).filter((value) => value);
            if (!ids.length) {
                alert("Nav atzīmēts neviens Suno ieraksts ignorēšanai.");
                return;
            }
            if (!confirm("Ignorēt izvēlētos " + ids.length + " Suno ierakstus?")) { return; }
            try {
                const body = new URLSearchParams();
                body.set("track_ids", ids.join("\n"));
                const response = await fetch("/suno-ignore-selected-tracklist", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                const data = await response.json();
                if (!response.ok || !data.ok) { throw new Error(data.error || "Ignorēšana neizdevās"); }
                checks.forEach((check) => {
                    const row = check.closest("tr");
                    if (row) { row.remove(); }
                });
                setStatus("Ignorēti ieraksti: " + data.ignored_added + ".", "ok");
                saveDownloaderState(true);
            } catch (error) {
                setStatus("Ignorēšanas kļūda: " + error.message, "error");
            }
        }

