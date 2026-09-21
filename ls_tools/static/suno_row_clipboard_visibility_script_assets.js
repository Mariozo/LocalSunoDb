        document.addEventListener("click", async (event) => {
            const item = event.target.closest(
                ".menu-copy-id, .menu-copy-local-path, .menu-cache-suno-path, .menu-hide-track"
            );
            if (!item) { return; }
            event.preventDefault();
            event.stopPropagation();

            const wrap = item.closest(".row-menu-wrap");
            const button = wrap ? wrap.querySelector(".row-menu-btn") : null;
            const trackId = button ? (button.dataset.trackId || "") : "";
            const title = button ? (button.dataset.title || "") : "";
            closeRowMenus();

            if (item.classList.contains("menu-copy-id")) {
                if (!trackId) { return; }
                try { await navigator.clipboard.writeText(trackId); }
                catch (error) { prompt("Track ID:", trackId); }
                return;
            }

            if (item.classList.contains("menu-copy-local-path")) {
                if (!trackId) { return; }
                try {
                    const response = await fetch("/local-audio-path?track_id=" + encodeURIComponent(trackId));
                    const text = await response.text();
                    if (!response.ok) {
                        alert(text || "Šim ierakstam nav piesaistīts īsts lokāls WAV/MP3 fails.");
                        return;
                    }
                    const localPath = text || "";
                    if (!localPath) {
                        alert("Šim ierakstam nav piesaistīts īsts lokāls WAV/MP3 fails.");
                        return;
                    }
                    try { await navigator.clipboard.writeText(localPath); }
                    catch (error) { prompt("Pilns piesaistītā faila ceļš:", localPath); }
                } catch (error) {
                    alert("Neizdevās nolasīt piesaistītā faila ceļu.");
                }
                return;
            }

            if (item.classList.contains("menu-cache-suno-path")) {
                if (!button) { return; }
                const audioUrl = button.dataset.audioUrl || "";
                if (!audioUrl) {
                    alert("Šim ierakstam nav Suno audio URL, ko sagatavot.");
                    return;
                }
                item.disabled = true;
                const oldText = item.innerText;
                item.innerText = "Gatavo MP3...";
                try {
                    const params = new URLSearchParams();
                    params.set("audio_url", audioUrl);
                    params.set("track_id", trackId);
                    params.set("title", title);
                    const response = await fetch("/cache-suno-audio-path?" + params.toString());
                    const text = await response.text();
                    if (!response.ok) {
                        alert(text || "Neizdevās sagatavot lokālu Suno MP3 failu.");
                        return;
                    }
                    const localPath = text || "";
                    if (!localPath) {
                        alert("Suno MP3 ceļš netika saņemts.");
                        return;
                    }
                    try { await navigator.clipboard.writeText(localPath); }
                    catch (error) { prompt("Pagaidu Suno MP3 ceļš:", localPath); }
                } catch (error) {
                    alert("Neizdevās sagatavot lokālu Suno MP3 failu.");
                } finally {
                    item.disabled = false;
                    item.innerText = oldText;
                }
                return;
            }

            if (!trackId) { return; }
            const ok = confirm(
                "Hide this row from Finder?\n\n" + (title || trackId) +
                "\n\nIt will not delete anything from Suno or local files."
            );
            if (!ok) { return; }
            const body = new URLSearchParams();
            body.set("track_id", trackId);
            body.set("reason", "manual_hide_from_finder");
            try {
                const response = await fetch("/hide-track", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                if (!response.ok) {
                    const text = await response.text();
                    alert(text || "Could not hide row.");
                    return;
                }
                saveViewState();
                window.location.reload();
            } catch (error) {
                alert("Could not hide row.");
            }
        });
