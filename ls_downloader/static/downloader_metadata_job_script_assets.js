        async function fetchJsonWithTimeout(url, options={}, timeoutMs=45000) {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), timeoutMs);
            try {
                const merged = Object.assign({}, options || {}, { signal: controller.signal });
                const response = await fetch(url, merged);
                const data = await response.json();
                return { response, data };
            } catch (error) {
                if (error && error.name === "AbortError") {
                    throw new Error("Darbība pārāk ilgi neatbildēja. Lodziņš aizvērts; mēģini vēlreiz vai pārbaudi PowerShell kļūdu.");
                }
                throw error;
            } finally {
                clearTimeout(timer);
            }
        }

        function setStatus(text, mode="") {
            metaStatus.className = "status " + mode;
            metaStatus.innerText = text;
            setDownloaderActionStatus(text, mode, false);
        }

        function renderAutomaticMetadataStatus(data) {
            if (!autoMetadataBackfillStatus || !autoMetadataBackfillBtn || !data) { return; }
            const running = Boolean(data.running);
            const status = String(data.status || "idle");
            const processed = parseInt(data.processed || 0, 10) || 0;
            const total = parseInt(data.total || 0, 10) || 0;
            const percent = Number(data.percent || 0).toFixed(1);
            autoMetadataBackfillStatus.style.display = "block";
            autoMetadataBackfillStatus.className = "status " + (
                running || status === "completed" ? "ok" :
                status === "idle" ? "" : "warn"
            );
            autoMetadataBackfillStatus.innerHTML = `
                <strong>${escHtml(data.message || status)}</strong><br>
                Progress: <strong>${processed} / ${total}</strong> (${percent}%)
                · atlikuši: <strong>${parseInt(data.remaining || 0, 10) || 0}</strong><br>
                Atjauninātas dziesmas: ${parseInt(data.updated_tracks || 0, 10) || 0}
                · lauki: ${parseInt(data.total_fields || 0, 10) || 0}
                · nemainīti konflikti: ${parseInt(data.total_conflicts || 0, 10) || 0}
                · kļūdas: ${parseInt(data.errors || 0, 10) || 0}
                ${data.current_title ? `<br>Pašlaik: ${escHtml(data.current_title)} <code>${escHtml(String(data.current_track_id || "").slice(0, 8))}</code> · ${escHtml(data.current_source || "")}` : ""}
            `;
            autoMetadataBackfillBtn.disabled = running;
            if (running) {
                autoMetadataBackfillBtn.textContent = "Metadatu papildināšana darbojas…";
            } else if (status === "stopped_401" || status === "stopped_429" || status === "stopped_errors" || status === "interrupted" || status === "failed") {
                autoMetadataBackfillBtn.textContent = "Turpināt automātisko metadatu papildināšanu";
            } else if (status === "completed") {
                autoMetadataBackfillBtn.textContent = "Pārbaudīt atlikušos metadatus automātiski";
            } else {
                autoMetadataBackfillBtn.textContent = "Papildināt metadatus automātiski";
            }
        }

        async function pollAutomaticMetadataStatus() {
            if (!autoMetadataBackfillBtn) { return; }
            try {
                const response = await fetch("/suno-metadata-backfill-status", { cache: "no-store" });
                const data = await response.json();
                if (response.ok && data.ok) { renderAutomaticMetadataStatus(data); }
            } catch (error) {
                // A page reload/server restart may briefly interrupt polling.
            }
        }

        if (autoMetadataBackfillBtn) {
            autoMetadataBackfillBtn.addEventListener("click", async () => {
                autoMetadataBackfillBtn.disabled = true;
                try {
                    if (window.lsRequestBackfillNotificationPermission) {
                        await window.lsRequestBackfillNotificationPermission();
                    }
                    const response = await fetch("/suno-start-full-metadata-backfill", { method: "POST" });
                    const data = await response.json();
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || "Neizdevās sākt automātisko metadatu papildināšanu");
                    }
                    renderAutomaticMetadataStatus(data);
                } catch (error) {
                    autoMetadataBackfillStatus.style.display = "block";
                    autoMetadataBackfillStatus.className = "status error";
                    autoMetadataBackfillStatus.textContent = error.message;
                    autoMetadataBackfillBtn.disabled = false;
                }
            });
            pollAutomaticMetadataStatus();
            setInterval(pollAutomaticMetadataStatus, 2500);
        }

        if (repairProvenDbBtn) {
            repairProvenDbBtn.addEventListener("click", async () => {
                repairProvenDbBtn.disabled = true;
                setStatus("Pārbauda pierādītos DB konfliktus…");
                try {
                    const previewResponse = await fetch(
                        "/suno-structured-repair-preview",
                        { cache: "no-store" }
                    );
                    const preview = await previewResponse.json();
                    if (!previewResponse.ok || !preview.ok) {
                        throw new Error(preview.error || "DB labošanas priekšskatījums neizdevās");
                    }
                    const totalChanges = (
                        Number(preview.structured_rows || 0)
                        + Number(preview.confirmed_prompt_rows || 0)
                        + Number(preview.bpm_migrations || 0)
                        + Number(preview.ui_cache_rows || 0)
                    );
                    if (!totalChanges) {
                        setStatus("Pierādīto DB konfliktu pārbaude pabeigta. Nekas vairs nav jālabo.", "ok");
                        metaResult.innerHTML = (
                            '<p class="status ok">Nav palikuši pierādīti strukturēti DB konflikti.</p>'
                        );
                        return;
                    }
                    const approved = window.confirm(
                        "Labot pierādītos LS DB konfliktus?\n\n"
                        + "Strukturētās rindas: " + preview.structured_rows + "\n"
                        + "Strukturētie lauki: " + preview.structured_field_updates + "\n"
                        + "Apstiprinātās Prompt rindas: " + preview.confirmed_prompt_rows + "\n"
                        + "No UI keša saglabātās BPM vērtības: " + preview.bpm_migrations + "\n"
                        + "UI metadatu keša rindas: " + preview.ui_cache_rows + "\n\n"
                        + "LS vispirms izveidos un pārbaudīs DB rezerves kopiju. "
                        + "Nosaukumi, Lyrics, Prompt, Style un lietotāja lauki netiks mainīti."
                    );
                    if (!approved) {
                        setStatus("DB labošana atcelta.");
                        return;
                    }
                    showRefreshWait(
                        "LS izveido pārbaudītu DB rezerves kopiju un labo tikai pierādītos strukturētos konfliktus.",
                        0
                    );
                    const response = await fetch(
                        "/suno-apply-structured-repair",
                        { method: "POST" }
                    );
                    const data = await response.json();
                    if (!response.ok || !data.ok) {
                        throw new Error(data.error || "DB labošana neizdevās");
                    }
                    const remaining = data.remaining || {};
                    setStatus(
                        "DB labošana pabeigta. Rindas: " + Number(data.applied_structured_rows || 0)
                        + ", lauki: " + Number(data.applied_structured_fields || 0)
                        + ", Prompt rindas: " + Number(data.applied_prompt_rows || 0)
                        + ", saglabātie BPM: " + Number(data.applied_bpm_migrations || 0)
                        + ", UI kešs: " + Number(data.applied_ui_cache_rows || 0) + ".",
                        "ok"
                    );
                    metaResult.innerHTML = (
                        '<h3>DB labošana pabeigta</h3>'
                        + '<p class="status ok">'
                        + 'Strukturētās rindas: <strong>' + escHtml(data.applied_structured_rows || 0) + '</strong>; '
                        + 'lauki: <strong>' + escHtml(data.applied_structured_fields || 0) + '</strong>.<br>'
                        + 'Apstiprinātās Prompt rindas: <strong>' + escHtml(data.applied_prompt_rows || 0) + '</strong>; '
                        + 'lauki: <strong>' + escHtml(data.applied_prompt_fields || 0) + '</strong>.<br>'
                        + 'No UI keša saglabātie BPM: <strong>' + escHtml(data.applied_bpm_migrations || 0) + '</strong>; '
                        + 'Sinhronizētās UI keša rindas: <strong>' + escHtml(data.applied_ui_cache_rows || 0) + '</strong>.<br>'
                        + 'Atlikušie pierādītie strukturētie konflikti: <strong>' + escHtml(remaining.structured_rows || 0) + '</strong>.<br>'
                        + 'Rezerves kopija: <code>' + escHtml(data.backup || "") + '</code><br>'
                        + 'Atskaite: <code>' + escHtml(data.report || "") + '</code>'
                        + '</p>'
                    );
                } catch (error) {
                    setStatus(error.message || "DB labošana neizdevās", "error");
                } finally {
                    hideRefreshWait();
                    repairProvenDbBtn.disabled = false;
                }
            });
        }

