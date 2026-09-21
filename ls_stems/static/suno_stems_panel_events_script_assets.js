        document.querySelectorAll(".stems-btn").forEach((button) => {
            button.addEventListener("click", async () => {
                if (!lsGlobalPlayer) { return; }
                if (!lsGlobalPlayer.loadFromStemButton(button)) {
                    alert("This track cannot be loaded into the global player.");
                    return;
                }
                await lsGlobalPlayer.toggleStems();
            });
        });

