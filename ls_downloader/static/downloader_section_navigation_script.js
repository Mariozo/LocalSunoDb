        function setActiveDownloaderSection(sectionName, scrollToSection=false, updateHash=false) {
            const section = downloaderSectionNames.has(sectionName) ? sectionName : "connection";
            const targetPanel = document.querySelector(`[data-downloader-section="${section}"]`);
            document.querySelectorAll("[data-downloader-section]").forEach((panel) => {
                panel.classList.remove("downloader-section-hidden");
            });
            document.querySelectorAll("[data-downloader-section-target]").forEach((button) => {
                const active = button.dataset.downloaderSectionTarget === section;
                button.classList.toggle("active", active);
                button.setAttribute("aria-current", active ? "location" : "false");
            });
            if (updateHash) {
                try { history.replaceState(null, "", "#" + section); } catch (error) {}
            }
            if (scrollToSection && targetPanel) {
                targetPanel.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }

        function getInitialDownloaderSection() {
            const hash = String(window.location.hash || "").replace(/^#/, "").trim().toLowerCase();
            if (downloaderSectionNames.has(hash)) { return hash; }
            return "connection";
        }

        document.querySelectorAll("[data-downloader-section-target]").forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                setActiveDownloaderSection(
                    button.dataset.downloaderSectionTarget || "connection",
                    true,
                    true
                );
            });
        });

        setActiveDownloaderSection(getInitialDownloaderSection(), false, false);

        if ("IntersectionObserver" in window) {
            const downloaderSectionObserver = new IntersectionObserver((entries) => {
                const visibleEntries = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((left, right) => {
                        const ratioDifference = right.intersectionRatio - left.intersectionRatio;
                        if (ratioDifference) { return ratioDifference; }
                        return Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top);
                    });
                if (!visibleEntries.length) { return; }
                const entry = visibleEntries[0];
                const section = String(entry.target.dataset.downloaderSection || "").trim().toLowerCase();
                if (downloaderSectionNames.has(section)) {
                    setActiveDownloaderSection(section, false, false);
                }
            }, {
                root: null,
                rootMargin: "-10% 0px -60% 0px",
                threshold: [0, 0.25, 0.5, 0.75],
            });
            document.querySelectorAll("[data-downloader-section]").forEach((panel) => {
                downloaderSectionObserver.observe(panel);
            });
        }

        window.addEventListener("hashchange", () => {
            setActiveDownloaderSection(getInitialDownloaderSection(), true, false);
        });
