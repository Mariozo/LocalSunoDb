        function isValidSunoTrackId(value) {
            return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
                String(value || "").trim()
            );
        }

        function buildSunoHostedEmbedUrl(trackId) {
            const value = String(trackId || "").trim();
            if (!isValidSunoTrackId(value)) { return ""; }
            return "https://suno.com/embed/" + value;
        }

        function buildSunoSongUrl(trackId) {
            const value = String(trackId || "").trim();
            if (!isValidSunoTrackId(value)) { return "https://suno.com/"; }
            return "https://suno.com/song/" + value;
        }

        function createSunoHostedPlayerController(root) {
            if (!root) { return null; }
            const mountNode = root.querySelector("#ls-suno-hosted-player-mount");
            const errorNode = root.querySelector("#ls-suno-hosted-player-error");
            const errorTextNode = root.querySelector("#ls-suno-hosted-player-error-text");
            const openLink = root.querySelector("#ls-suno-hosted-player-open");
            if (!mountNode || !errorNode || !errorTextNode || !openLink) { return null; }

            let mountedTrackId = "";

            function clearMount() {
                mountNode.replaceChildren();
                mountedTrackId = "";
            }

            function hideError() {
                errorNode.hidden = true;
                errorTextNode.textContent = "";
                openLink.textContent = "Atvērt Suno";
                openLink.setAttribute("href", "https://suno.com/");
            }

            function showError(trackId) {
                clearMount();
                errorTextNode.textContent = "Suno atskaņotāju neizdevās atvērt.";
                openLink.textContent = "Atvērt Suno";
                openLink.setAttribute("href", buildSunoSongUrl(trackId));
                openLink.setAttribute("target", "_blank");
                openLink.setAttribute("rel", "noopener noreferrer");
                errorNode.hidden = false;
            }

            function unmount() {
                clearMount();
                hideError();
            }

            function mount(trackId) {
                const value = String(trackId || "").trim();
                const embedUrl = buildSunoHostedEmbedUrl(value);
                unmount();
                if (!embedUrl) {
                    showError(value);
                    return false;
                }

                const iframe = document.createElement("iframe");
                iframe.setAttribute("src", embedUrl);
                iframe.setAttribute("title", "Suno hosted player");
                iframe.setAttribute("loading", "eager");
                iframe.setAttribute("allow", "autoplay; encrypted-media");
                iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
                iframe.setAttribute("frameborder", "0");
                iframe.addEventListener("error", () => showError(value), { once: true });
                mountNode.appendChild(iframe);
                mountedTrackId = value;
                return true;
            }

            function isMounted() {
                return Boolean(mountedTrackId);
            }

            return { mount, unmount, showError, isMounted };
        }
