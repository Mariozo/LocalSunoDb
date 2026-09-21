        if (checkAll) {
            checkAll.addEventListener("change", () => {
                const checks = table.querySelectorAll("tbody .track-check");
                checks.forEach((check) => {
                    check.checked = checkAll.checked;
                });

                updateOpenSelectedButton();
                saveSunoSelection();
            });
        }

