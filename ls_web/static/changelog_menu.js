(() => {
    function installChangelogMenuEntry() {
        const popover = document.getElementById("ls-sidebar-tools-popover");
        if (!popover || document.getElementById("open-ls-changelog-btn")) {
            return;
        }
        const button = document.createElement("button");
        button.type = "button";
        button.id = "open-ls-changelog-btn";
        button.textContent = "Izmaiņu žurnāls";
        button.addEventListener("click", () => {
            window.location.href = "/help?changelog=1";
        });
        popover.appendChild(button);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", installChangelogMenuEntry, { once: true });
    } else {
        installChangelogMenuEntry();
    }
})();
