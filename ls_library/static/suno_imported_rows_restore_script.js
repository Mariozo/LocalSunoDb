        // Pre-check just-imported rows. Scroll/F5 restoration is handled by the
        // anchor-based v4.72 main-view position state above.
        try {
            const importedIds = JSON.parse(localStorage.getItem("ls_last_imported_ids") || "[]");
            if (Array.isArray(importedIds) && importedIds.length) {
                const importedSet = new Set(importedIds.map((x) => String(x || "").toLowerCase()));
                document.querySelectorAll(".track-check").forEach((check) => {
                    if (importedSet.has(String(check.value || "").toLowerCase())) {
                        check.checked = true;
                        const row = check.closest("tr.track-row");
                        if (row) {
                            row.classList.remove("just-imported-row");
                        }
                    }
                });
            }
        } catch (error) {}