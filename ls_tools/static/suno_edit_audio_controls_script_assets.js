        document.addEventListener("click", async (event) => {
            const sunoButton = event.target.closest(".edit-suno-btn");
            if (sunoButton) {
                event.preventDefault();
                event.stopPropagation();
                const audioUrl = sunoButton.dataset.audioUrl || "";
                const trackId = sunoButton.dataset.trackId || "";
                const title = sunoButton.dataset.title || "";
                if (!audioUrl && !trackId) { return; }

                sunoButton.disabled = true;
                const originalText = sunoButton.innerText;
                sunoButton.innerText = "Wait";
                try {
                    let localPath = "";
                    if (trackId) {
                        const localParams = new URLSearchParams();
                        localParams.set("track_id", trackId);
                        const localPathResponse = await fetch("/local-audio-path?" + localParams.toString());
                        if (localPathResponse.ok) {
                            localPath = (await localPathResponse.text()).trim();
                        }
                    }

                    let response;
                    if (localPath) {
                        const params = new URLSearchParams();
                        params.set("path", localPath);
                        response = await fetch("/edit-local?" + params.toString());
                        if (!response.ok && response.status !== 204) {
                            alert("Could not open linked local audio in editor.");
                        }
                    } else {
                        const params = new URLSearchParams();
                        params.set("audio_url", audioUrl);
                        params.set("track_id", trackId);
                        params.set("title", title);
                        response = await fetch("/edit-suno?" + params.toString());
                        if (!response.ok && response.status !== 204) {
                            alert("Could not find/open linked local audio.");
                        }
                    }
                } catch (error) {
                    alert("Could not open audio in editor.");
                } finally {
                    sunoButton.disabled = false;
                    sunoButton.innerText = originalText;
                }
                return;
            }

            const localButton = event.target.closest(".edit-local-btn");
            if (localButton) {
                event.preventDefault();
                event.stopPropagation();
                const localPath = localButton.dataset.localPath || "";
                if (!localPath) { return; }
                const params = new URLSearchParams();
                params.set("path", localPath);
                try {
                    const response = await fetch("/edit-local?" + params.toString());
                    if (!response.ok && response.status !== 204) {
                        alert("Could not open audio editor.");
                    }
                } catch (error) {
                    alert("Could not open audio editor.");
                }
                return;
            }

            const loopButton = event.target.closest(".loop-audio-btn");
            if (!loopButton) { return; }
            event.preventDefault();
            event.stopPropagation();
            const playerBlock = loopButton.closest(".player-block");
            const audio = playerBlock ? playerBlock.querySelector("audio") : null;
            if (!audio) { return; }

            audio.loop = !audio.loop;
            loopButton.classList.toggle("active", audio.loop);
            loopButton.innerText = audio.loop ? "Loop ON" : "Loop";
            loopButton.title = audio.loop
                ? "Loop ieslēgts: šis audio atkārtosies bezgalīgi"
                : "Loop: atskaņot šo audio bezgalīgi";

            if (audio.loop) {
                setAutoplayListEnabled(false, true);
                const fragment = playerBlock.closest(".fragment-row");
                if (fragment) {
                    fragment.querySelectorAll("audio").forEach((otherAudio) => {
                        if (otherAudio !== audio && !otherAudio.paused) { otherAudio.pause(); }
                    });
                }
                if (lastActiveAudio && lastActiveAudio !== audio && !lastActiveAudio.paused) {
                    lastActiveAudio.pause();
                }
                lastActiveAudio = audio;
                if (abStart !== null && abEnd !== null && abEnd > abStart) {
                    audio.currentTime = abStart;
                }
            }
        });
