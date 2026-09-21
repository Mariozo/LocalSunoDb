(() => {
    function applyImportBranding() {
        document.querySelectorAll('a[href="/downloader"], a[href$="/downloader"]').forEach((link) => {
            if (link.getAttribute("title") === "Downloader") {
                link.setAttribute("title", "Imports");
            }
            const label = link.querySelector(".ls-sidebar-label");
            if (label && label.textContent.trim() === "Downloader") {
                label.textContent = "Imports";
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", applyImportBranding, {once: true});
    } else {
        applyImportBranding();
    }
})();
