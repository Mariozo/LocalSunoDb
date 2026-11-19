(() => {
    "use strict";

    const card = document.getElementById("suno-mcp-proof-card");
    const summary = document.getElementById("suno-mcp-proof-summary");
    const result = document.getElementById("suno-mcp-proof-result");
    const connectBtn = document.getElementById("suno-mcp-connect-btn");
    const proofBtn = document.getElementById("suno-mcp-proof-btn");

    const readCard = document.getElementById("suno-mcp-read-card");
    const readSummary = document.getElementById("suno-mcp-read-summary");
    const readResult = document.getElementById("suno-mcp-read-result");
    const libraryBtn = document.getElementById("suno-mcp-library-btn");
    const playlistsBtn = document.getElementById("suno-mcp-playlists-btn");
    const playlistList = document.getElementById("suno-mcp-playlist-list");

    if (!card || !summary || !result || !connectBtn || !proofBtn) {
        return;
    }

    function setBusy(busy) {
        connectBtn.disabled = Boolean(busy);
        proofBtn.disabled = Boolean(busy);
    }

    function setState(level, text) {
        card.className = "status " + (level || "");
        summary.textContent = text || "";
    }

    function formatProof(data) {
        if (!data || !data.ok) {
            return "";
        }
        const account = data.account || {};
        const usage = data.usage || {};
        const library = data.library || {};
        const lines = [];

        if (account.display_name || account.handle) {
            const handle = account.handle ? " (@" + account.handle + ")" : "";
            lines.push("Konts: " + (account.display_name || "Suno") + handle);
        }
        if (usage.plan) {
            lines.push("Plāns: " + usage.plan + (usage.period ? " · " + usage.period : ""));
        }
        if (usage.credits_remaining !== null && usage.credits_remaining !== undefined) {
            lines.push("Kredīti: " + String(usage.credits_remaining));
        }
        if (
            usage.download_credits_remaining !== null &&
            usage.download_credits_remaining !== undefined
        ) {
            lines.push("Download kredīti: " + String(usage.download_credits_remaining));
        }

        const items = Array.isArray(library.items) ? library.items : [];
        lines.push("Library proof: " + String(items.length) + " ieraksti");
        items.forEach((item, index) => {
            const title = String(item.title || "(bez nosaukuma)");
            const id = String(item.id || "");
            lines.push(
                String(index + 1) + ". " + title +
                (id ? " · " + id.slice(0, 8) : "")
            );
        });
        lines.push("LS DB raksti: 0");
        lines.push("Maksas/spend tool izsaukumi: 0");
        return lines.join("\n");
    }

    function setReadBusy(busy) {
        if (libraryBtn) {
            libraryBtn.disabled = Boolean(busy);
        }
        if (playlistsBtn) {
            playlistsBtn.disabled = Boolean(busy);
        }
    }

    function setReadState(level, text) {
        if (readCard) {
            readCard.className = "status " + (level || "");
        }
        if (readSummary) {
            readSummary.textContent = text || "";
        }
    }

    function renderClipRows(data, heading) {
        const items = Array.isArray(data && data.items) ? data.items : [];
        const lines = [
            heading + ": " + String(items.length),
        ];
        items.forEach((item, index) => {
            const title = String(item.title || "(bez nosaukuma)");
            const id = String(item.id || "");
            const style = String(item.style || "");
            lines.push(
                String(index + 1) + ". " + title +
                (id ? " · " + id.slice(0, 8) : "") +
                (style ? " · " + style : "")
            );
        });
        if (data && data.next_cursor) {
            lines.push("Ir vēl ieraksti nākamajā MCP lapā.");
        }
        lines.push("LS DB raksti: 0");
        if (readResult) {
            readResult.textContent = lines.join("\n");
        }
    }

    async function fetchReadJson(url) {
        const response = await fetch(url + (url.includes("?") ? "&" : "?") + "_=" + Date.now(), {
            cache: "no-store",
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || ("HTTP " + response.status));
        }
        return data;
    }

    async function loadMcpLibrary() {
        setReadBusy(true);
        setReadState("warn", "Nolasa Suno Library caur MCP…");
        if (playlistList) {
            playlistList.replaceChildren();
        }
        if (readResult) {
            readResult.textContent = "";
        }
        try {
            const data = await fetchReadJson("/suno-mcp-library-read?limit=50");
            setReadState("ok", "MCP Library nolasīta. DB un Token Bridge nav mainīti.");
            renderClipRows(data, "Library ieraksti");
        } catch (error) {
            setReadState("error", "MCP Library nolasīšana neizdevās.");
            if (readResult) {
                readResult.textContent = String(error && error.message || error || "Nezināma kļūda");
            }
        } finally {
            setReadBusy(false);
        }
    }

    async function loadMcpPlaylistClips(playlistId, playlistName) {
        setReadBusy(true);
        setReadState("warn", "Nolasa playlist “" + playlistName + "” caur MCP…");
        if (readResult) {
            readResult.textContent = "";
        }
        try {
            const data = await fetchReadJson(
                "/suno-mcp-playlist-clips-read?id=" +
                encodeURIComponent(playlistId) +
                "&limit=50"
            );
            setReadState(
                "ok",
                "Playlist “" + playlistName + "” nolasīta caur MCP. DB nav mainīta."
            );
            renderClipRows(data, "Playlist “" + playlistName + "” dziesmas");
        } catch (error) {
            setReadState("error", "MCP playlist nolasīšana neizdevās.");
            if (readResult) {
                readResult.textContent = String(error && error.message || error || "Nezināma kļūda");
            }
        } finally {
            setReadBusy(false);
        }
    }

    async function loadMcpPlaylists() {
        setReadBusy(true);
        setReadState("warn", "Nolasa Suno playlists caur MCP…");
        if (playlistList) {
            playlistList.replaceChildren();
        }
        if (readResult) {
            readResult.textContent = "";
        }
        try {
            const data = await fetchReadJson("/suno-mcp-playlists-read?limit=50");
            const items = Array.isArray(data.items) ? data.items : [];
            setReadState(
                "ok",
                "MCP playlists nolasītas: " + String(items.length) + ". Izvēlies playlisti."
            );
            items.forEach((item) => {
                const id = String(item.id || "");
                if (!id || !playlistList) {
                    return;
                }
                const name = String(item.name || "(bez nosaukuma)");
                const button = document.createElement("button");
                button.type = "button";
                button.className = "secondary";
                button.textContent = name;
                button.addEventListener("click", () => {
                    loadMcpPlaylistClips(id, name);
                });
                playlistList.appendChild(button);
            });
            if (!items.length && readResult) {
                readResult.textContent = "Suno MCP neatgrieza nevienu playlisti.";
            }
            if (data.next_cursor && readResult) {
                readResult.textContent = "Parādītas pirmās 50 playlists; Suno MCP ziņo, ka ir vēl.";
            }
        } catch (error) {
            setReadState("error", "MCP playlist saraksta nolasīšana neizdevās.");
            if (readResult) {
                readResult.textContent = String(error && error.message || error || "Nezināma kļūda");
            }
        } finally {
            setReadBusy(false);
        }
    }

    async function readStatus(runProof) {
        const url = "/suno-mcp-proof-status?run=" + (runProof ? "1" : "0") + "&_=" + Date.now();
        const response = await fetch(url, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok || !data.ok) {
            throw new Error(data.error || ("HTTP " + response.status));
        }
        return data;
    }

    async function refreshStatus(runProof) {
        setBusy(true);
        try {
            if (runProof) {
                setState("warn", "Pārbauda oficiālo Suno MCP…");
                result.textContent = "";
            }
            const data = await readStatus(Boolean(runProof));
            if (!data.connected) {
                setState(
                    "warn",
                    "Oficiālais Suno MCP vēl nav pieslēgts. Token Bridge pašlaik netiek mainīts."
                );
                result.textContent = "";
                return;
            }

            if (runProof) {
                setState(
                    "ok",
                    "Suno MCP read-only proof PASS: account-me, account-usage un library-list."
                );
                result.textContent = formatProof(data);
                return;
            }

            if (data.proof && data.proof.ok) {
                setState("ok", "Oficiālais Suno MCP ir pieslēgts; pēdējais read-only proof ir PASS.");
                result.textContent = formatProof(data.proof);
            } else {
                setState(
                    "warn",
                    "Suno OAuth akreditācijas dati ir saglabāti. Spied “Pārbaudīt MCP”, lai izpildītu read-only proof."
                );
                result.textContent = "";
            }
        } catch (error) {
            setState("error", "Suno MCP pārbaude neizdevās.");
            result.textContent = String(error && error.message || error || "Nezināma kļūda");
        } finally {
            setBusy(false);
        }
    }

    connectBtn.addEventListener("click", async () => {
        const popup = window.open(
            "about:blank",
            "lsSunoMcpOAuth",
            "width=760,height=860,resizable=yes,scrollbars=yes"
        );
        setBusy(true);
        setState("warn", "Sagatavo Suno OAuth autorizāciju…");
        result.textContent = "";
        try {
            const response = await fetch("/suno-mcp-connect", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "",
            });
            const data = await response.json();
            if (!response.ok || !data.ok || !data.authorization_url) {
                throw new Error(data.error || ("HTTP " + response.status));
            }
            if (popup) {
                popup.location.href = data.authorization_url;
                popup.focus();
            } else {
                window.open(data.authorization_url, "_blank", "noopener");
            }
            setState(
                "warn",
                "Suno logā apstiprini OAuth pieslēgumu. Pēc atgriešanās LS proof tiks palaists automātiski."
            );
        } catch (error) {
            if (popup && !popup.closed) {
                popup.close();
            }
            setState("error", "Suno OAuth sākšana neizdevās.");
            result.textContent = String(error && error.message || error || "Nezināma kļūda");
        } finally {
            setBusy(false);
        }
    });

    proofBtn.addEventListener("click", () => refreshStatus(true));

    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) {
            return;
        }
        const data = event.data || {};
        if (data.type !== "LS_SUNO_MCP_OAUTH_COMPLETE") {
            return;
        }
        if (!data.ok) {
            setState("error", "Suno OAuth autorizācija neizdevās.");
            return;
        }
        window.setTimeout(() => refreshStatus(true), 300);
    });

    if (libraryBtn) {
        libraryBtn.addEventListener("click", loadMcpLibrary);
    }
    if (playlistsBtn) {
        playlistsBtn.addEventListener("click", loadMcpPlaylists);
    }

    refreshStatus(false);
})();
