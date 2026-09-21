        const downloaderActionNames = {
            "renew-suno-login-btn": "Atjaunot Suno pieslēgumu",
            "bridge-setup-btn": "Token Bridge iestatīšana",
            "save-token-btn": "Saglabāt tokenu",
            "clear-token-btn": "Notīrīt tokenu",
            "refresh-tracklist-btn": "Atjaunot dziesmu sarakstu",
            "update-preview-btn": "Pārbaudīt DB metadatus",
            "auto-metadata-backfill-btn": "Pārbaudīt metadatus automātiski",
            "preview-meta-btn": "Metadatu priekšskatījums",
            "refresh-selected-meta-btn": "Atjaunot izvēlētos metadatus",
            "preview-first-selected-btn": "Priekšskatīt pirmo izvēlēto",
            "select-all-shown-btn": "Atlasīt pirmos pēc limita",
            "select-none-btn": "Noņemt atlasi",
            "select-lyrics-prompt-btn": "Atlasīt lyrics/prompt",
            "import-selected-tracklist-btn": "Importēt izvēlētos",
            "update-selected-titles-btn": "Atjaunot izvēlētos nosaukumus",
            "ignore-selected-tracklist-btn": "Ignorēt izvēlētos",
            "open-last-imported-btn": "Atvērt pēdējos importētos",
            "clear-downloader-state-btn": "Notīrīt saglabāto importa skatu",
            "meta-preview-close-btn": "Aizvērt priekšskatījumu"
        };

        function setDownloaderActionStatus(text, mode="", mirrorToLog=true) {
            const safeText = text || "Gatavs — gaida darbību.";
            // v5.103: no persistent inline status above Downloader columns.
            // Only the short central working/tip popup is used for action feedback.
            if (mirrorToLog && metaStatus && safeText.indexOf("Darbība sākta:") !== 0) {
                metaStatus.className = "status " + (mode || "");
                metaStatus.innerText = safeText;
            }
            if (safeText.indexOf("Darbība sākta:") === 0) {
                showDownloaderTipPopup(safeText.replace("Darbība sākta:", "").trim());
            }
        }

        function actionLabelForElement(element) {
            if (!element) { return ""; }
            return element.dataset.actionLabel || downloaderActionNames[element.id] || (element.innerText || element.textContent || "").trim();
        }

        document.addEventListener("click", (event) => {
            const actionElement = event.target && event.target.closest ? event.target.closest("button, a.btn") : null;
            if (!actionElement || !document.body.contains(actionElement)) { return; }
            if (actionElement.disabled || actionElement.getAttribute("aria-disabled") === "true") { return; }
            if (!actionElement.dataset.actionLabel && !downloaderActionNames[actionElement.id]) { return; }
            const label = actionLabelForElement(actionElement);
            if (!label) { return; }
            setDownloaderActionStatus("Darbība sākta: " + label);
        }, true);

