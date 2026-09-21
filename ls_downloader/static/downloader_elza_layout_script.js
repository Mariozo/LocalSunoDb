        function applyDownloaderElzaWidth(widthValue, persist=false) {
            const width = Math.max(300, Math.min(620, parseInt(widthValue || 330, 10) || 330));
            document.documentElement.style.setProperty("--ls-downloader-elza-width", width + "px");
            if (persist) {
                try { localStorage.setItem(downloaderElzaWidthKey, String(width)); } catch (error) {}
            }
        }

        try {
            applyDownloaderElzaWidth(localStorage.getItem(downloaderElzaWidthKey) || "330", false);
        } catch (error) {
            applyDownloaderElzaWidth(330, false);
        }

        if (downloaderElzaResizer && downloaderElzaPanel) {
            let resizeStart = null;
            downloaderElzaResizer.addEventListener("pointerdown", (event) => {
                resizeStart = {
                    pointerId: event.pointerId,
                    startX: event.clientX,
                    startWidth: downloaderElzaPanel.getBoundingClientRect().width,
                };
                document.body.classList.add("ls-downloader-elza-resizing");
                downloaderElzaResizer.setPointerCapture(event.pointerId);
                event.preventDefault();
            });
            downloaderElzaResizer.addEventListener("pointermove", (event) => {
                if (!resizeStart || event.pointerId !== resizeStart.pointerId) { return; }
                const nextWidth = resizeStart.startWidth - (event.clientX - resizeStart.startX);
                applyDownloaderElzaWidth(nextWidth, false);
            });
            function finishDownloaderElzaResize(event) {
                if (!resizeStart || event.pointerId !== resizeStart.pointerId) { return; }
                const nextWidth = downloaderElzaPanel.getBoundingClientRect().width;
                resizeStart = null;
                document.body.classList.remove("ls-downloader-elza-resizing");
                applyDownloaderElzaWidth(nextWidth, true);
            }
            downloaderElzaResizer.addEventListener("pointerup", finishDownloaderElzaResize);
            downloaderElzaResizer.addEventListener("pointercancel", finishDownloaderElzaResize);
        }
