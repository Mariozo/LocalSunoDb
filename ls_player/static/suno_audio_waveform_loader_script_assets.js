        function loadWaveform(playerBlock, trackId, audioUrl) {
            const image = playerBlock.querySelector(".waveform-image");
            const loading = playerBlock.querySelector(".wave-loading");
            const status = playerBlock.querySelector(".wave-status");

            const params = new URLSearchParams();
            params.set("track_id", trackId || "");
            params.set("audio_url", audioUrl || "");

            status.innerText = "loading waveform...";
            loading.innerText = "Loading waveform...";
            loading.style.display = "flex";
            image.style.display = "none";
            image.removeAttribute("src");

            image.onload = () => {
                loading.style.display = "none";
                image.style.display = "block";
                status.innerText = "waveform ready";
            };

            image.onerror = () => {
                loading.innerText = "Waveform failed";
                loading.style.display = "flex";
                image.style.display = "none";
                status.innerText = "waveform failed";
            };

            image.style.width = "100%";
            image.style.left = "0%";
            const directWaveformUrl = String(audioUrl || "").trim();
            image.src = directWaveformUrl.startsWith("/playback-waveform?")
                ? directWaveformUrl
                : "/waveform?" + params.toString();
        }

