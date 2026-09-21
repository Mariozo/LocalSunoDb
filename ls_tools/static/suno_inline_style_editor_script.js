        function setSaveStatus(button, message, ok) {
            const cell = button.closest(".style-cell");
            const status = cell ? cell.querySelector(".style-save-status") : null;
            if (!status) { return; }
            status.innerText = message;
            status.style.color = ok ? "#188038" : "#a50e0e";
        }

        table.addEventListener("input", (event) => {
            const textarea = event.target.closest(".style-edit");
            if (!textarea || !table.contains(textarea)) { return; }
            const cell = textarea.closest(".style-cell");
            const button = cell ? cell.querySelector(".style-save") : null;
            const status = cell ? cell.querySelector(".style-save-status") : null;
            if (!button) { return; }
            const original = textarea.dataset.original || "";
            const current = textarea.value || "";
            button.disabled = current === original;
            if (status) { status.innerText = ""; }
        });

        table.addEventListener("click", async (event) => {
            const button = event.target.closest(".style-save");
            if (!button || !table.contains(button)) { return; }
            event.preventDefault();
            event.stopPropagation();
            const cell = button.closest(".style-cell");
            const textarea = cell ? cell.querySelector(".style-edit") : null;
            if (!textarea) { return; }
            const styleText = textarea.value || "";
            const trackId = button.dataset.trackId || "";

            button.disabled = true;
            setSaveStatus(button, "Saving...", true);
            const body = new URLSearchParams();
            body.set("track_id", trackId);
            body.set("style", styleText);

            try {
                const response = await fetch("/save-style", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: body.toString()
                });
                const text = await response.text();
                if (!response.ok) {
                    setSaveStatus(button, text || "Save failed", false);
                    button.disabled = false;
                } else {
                    textarea.dataset.original = styleText;
                    cell.dataset.sort = styleText.toLowerCase();
                    cell.title = styleText;
                    setSaveStatus(button, "Saved", true);
                    button.disabled = true;
                }
            } catch (error) {
                setSaveStatus(button, "Save failed", false);
                button.disabled = false;
            }
        });
