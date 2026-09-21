(() => {
    const backfillMessages = new Map([
        ["Automatic metadata backfill is running.", "Notiek automātiska metadatu papildināšana."],
        ["Automatic metadata backfill completed.", "Metadatu automātiskā papildināšana pabeigta."],
        ["Automatic metadata backfill completed with individual row errors.", "Metadatu automātiskā papildināšana pabeigta ar kļūdām atsevišķās rindās."],
    ]);

    function replaceExactText(node, replacements) {
        if (!node) { return; }
        const value = String(node.textContent || "").trim();
        const replacement = replacements.get(value);
        if (replacement) { node.textContent = replacement; }
    }

    function localizeBackfillStatus() {
        const box = document.getElementById("auto-metadata-backfill-status");
        if (!box) { return; }
        replaceExactText(box.querySelector("strong"), backfillMessages);
    }

    function localizeTracklistPreview() {
        const root = document.getElementById("meta-result");
        if (!root) { return; }

        root.querySelectorAll(".pill").forEach((pill) => {
            const value = String(pill.textContent || "").trim();
            const map = {
                "lyrics": "vārdi",
                "nav lyrics": "nav vārdu",
                "prompt": "uzvedne",
                "nav prompt": "nav uzvednes",
                "style": "stils",
                "nav style": "nav stila",
                "no audio_url": "nav audio_url",
            };
            if (map[value]) { pill.textContent = map[value]; }
        });

        const lyricsPromptButton = document.getElementById("select-lyrics-prompt-btn");
        if (lyricsPromptButton && lyricsPromptButton.textContent.trim() === "Atlasīt lyrics/prompt") {
            lyricsPromptButton.textContent = "Atlasīt vārdus/uzvedni";
        }

        root.querySelectorAll("th").forEach((cell) => {
            if (cell.textContent.trim() === "Nosaukums / created_at") {
                cell.textContent = "Nosaukums / izveidots";
            }
        });

        root.querySelectorAll("p.muted").forEach((paragraph) => {
            paragraph.childNodes.forEach((node) => {
                if (node.nodeType !== Node.TEXT_NODE) { return; }
                if (node.textContent.includes("Saņemti raw:")) {
                    node.textContent = node.textContent.replace("Saņemti raw:", "Saņemti kopā:");
                }
            });
        });
    }

    function localizeImportPage() {
        localizeBackfillStatus();
        localizeTracklistPreview();
    }

    localizeImportPage();
    const observer = new MutationObserver(localizeImportPage);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
})();
