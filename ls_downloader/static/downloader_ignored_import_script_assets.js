        async function showIgnoredTracklist() {
            const resultBox = document.getElementById("tracklist-import-result") || document.getElementById("tracklist-audio-preview");
            try {
                const response = await fetch("/suno-ignored-tracklist");
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "Neizdevās parādīt ignorētos ierakstus");
                }
                const ids = data.ignored_ids || [];
                let rows = "";
                ids.forEach((tid, index) => {
                    rows += `
                        <tr>
                            <td><input type="checkbox" class="ignored-track-check" value="${escHtml(tid)}"></td>
                            <td>${index + 1}</td>
                            <td><code>${escHtml(String(tid).slice(0, 8))}</code></td>
                            <td><code>${escHtml(tid)}</code></td>
                        </tr>
                    `;
                });
                if (resultBox) {
                    resultBox.innerHTML = `
                        <h3>Ignorētie Suno Track ID</h3>
                        <p class="muted">Šie ID netiek rādīti atjaunotā dziesmu saraksta jauno ierakstu sadaļā. Atzīmē un spied “Atjaunot izvēlētos ignorētos”, ja tie jāatgriež.</p>
                        <table class="preview-table">
                            <thead><tr><th>Atjaunot</th><th>#</th><th>Īsais ID</th><th>Pilnais Track ID</th></tr></thead>
                            <tbody>${rows || '<tr><td colspan="4">Ignorēto saraksts ir tukšs.</td></tr>'}</tbody>
                        </table>
                        <div class="update-action-bar">
                            <button type="button" class="green" id="restore-selected-ignored-btn">Atjaunot izvēlētos ignorētos</button>
                            <span class="muted">Kopā ignorēti: ${escHtml(data.ignored_total || 0)}.</span>
                        </div>
                    `;
                    resultBox.scrollIntoView({ block: "nearest", behavior: "smooth" });
                }
                setStatus("Ignorēto saraksts ielādēts. Kopā: " + (data.ignored_total || 0), "ok");
                saveDownloaderState(true);
            } catch (error) {
                setStatus("Ignorēto saraksta kļūda: " + error.message, "error");
            }
        }

        async function restoreSelectedIgnoredTracklist() {
            const checks = Array.from(metaResult.querySelectorAll(".ignored-track-check:checked"));
            const ids = checks.map((check) => check.value).filter((value) => value);
            if (!ids.length) {
                alert("Nav atzīmēts neviens ignored ID atjaunošanai.");
                return;
            }
            if (!confirm("Atjaunot izvēlētos " + ids.length + " ignorētos Suno ID?\n\nTie atkal var parādīties nākamajā dziesmu saraksta atjaunošanā.")) {
                return;
            }
            try {
                const body = new URLSearchParams();
                body.set("track_ids", ids.join("\n"));
                const response = await fetch("/suno-restore-ignored-tracklist", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "Ignorēto atjaunošana neizdevās");
                }
                checks.forEach((check) => {
                    const row = check.closest("tr");
                    if (row) {
                        row.remove();
                    }
                });
                setStatus("Atjaunoti ignorētie ID: " + data.restored + ". Atjauno dziesmu sarakstu, lai tos atkal redzētu.", "ok");
                saveDownloaderState(true);
            } catch (error) {
                setStatus("Ignorēto atjaunošanas kļūda: " + error.message, "error");
            }
        }

        async function importSelectedFromRestoredView() {
            const ids = getCurrentSelectedTracklistChecks().map((check) => check.value).filter((value) => value);
            const resultBox = document.getElementById("tracklist-import-result");
            if (!ids.length) {
                alert("Nav atzīmēts neviens jaunais Suno ieraksts.");
                return;
            }
            if (!confirm("Importēt izvēlētos " + ids.length + " jaunos Suno ierakstus LS DB?\n\nTiks izveidota DB rezerves kopija.")) { return; }
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
                const data = await response.json();
                if (!response.ok || !data.ok) { throw new Error(data.error || "Imports neizdevās"); }
                try {
                    if (Array.isArray(data.last_imported_ids) && data.last_imported_ids.length) {
                        localStorage.setItem("ls_last_imported_ids", JSON.stringify(data.last_imported_ids));
                    }
                } catch (error) {}
                const exactJustImported = Number(data.inserted || 0) > 0
                    && Number(data.skipped_existing || 0) === 0
                    && Number(data.errors || 0) === 0
                    && data.last_imported_url;
                const openUrl = exactJustImported ? data.last_imported_url : data.selected_url;
                const openLabel = exactJustImported ? "Atvērt tikko importētos Suno datubāzē" : "Atvērt izvēlētos Suno datubāzē";
                const openLink = openUrl
                    ? `<a class="btn" href="${escHtml(openUrl)}">${escHtml(openLabel)}</a>`
                    : "";
                if (resultBox) {
                    resultBox.innerHTML = `
                        <h3>Importa rezultāts</h3>
                        <p class="status ok">
                            Pievienoti: ${escHtml(data.inserted)}. Izlaisti jau esošie: ${escHtml(data.skipped_existing)}.<br>
                            Rezerves kopija: <code>${escHtml(data.backup || "")}</code><br>
                            ${openLink}
                        </p>
                    `;
                }
                setStatus("Imports pabeigts. Pievienoti: " + data.inserted + ".", "ok");
                saveDownloaderState(true);
            } catch (error) {
                setStatus("Importa kļūda: " + error.message, "error");
            } finally {
                hideRefreshWait();
            }
        }

