        // v5.69: Suno-like draggable widths for both side panels.
        const LS_SIDEBAR_WIDTH_KEY = "ls_suno_sidebar_width";
        const LS_SELECTED_PANEL_WIDTH_KEY = "ls_selected_panel_width";
        const lsPanelRoot = document.documentElement;
        const lsSidebarResizeHandle = document.getElementById("ls-sidebar-resizer");
        const lsSelectedResizeHandle = document.getElementById("ls-selected-panel-resizer");
        const lsPanelLimits = {
            sidebar: { min: 230, max: 360, fallback: 260 },
            selected: { min: 240, max: 620, fallback: 330 }
        };

        function lsPanelConfig(kind) {
            return kind === "sidebar"
                ? {
                    variable: "--ls-suno-sidebar-width",
                    key: LS_SIDEBAR_WIDTH_KEY,
                    handle: lsSidebarResizeHandle,
                    limits: lsPanelLimits.sidebar
                }
                : {
                    variable: "--ls-selected-panel-width",
                    key: LS_SELECTED_PANEL_WIDTH_KEY,
                    handle: lsSelectedResizeHandle,
                    limits: lsPanelLimits.selected
                };
        }

        function lsCurrentPanelWidth(kind) {
            const config = lsPanelConfig(kind);
            const raw = getComputedStyle(lsPanelRoot)
                .getPropertyValue(config.variable);
            const parsed = Number.parseFloat(raw);
            return Number.isFinite(parsed)
                ? parsed
                : config.limits.fallback;
        }

        function lsPanelMaximum(kind) {
            const config = lsPanelConfig(kind);
            const otherKind = kind === "sidebar" ? "selected" : "sidebar";
            const otherWidth = lsCurrentPanelWidth(otherKind);
            const viewportWidth = Math.max(
                window.innerWidth || 0,
                document.documentElement.clientWidth || 0
            );
            const centerMinimum = viewportWidth >= 1200 ? 520 : 360;
            const available = viewportWidth - otherWidth - centerMinimum;
            return Math.max(
                config.limits.min,
                Math.min(config.limits.max, available)
            );
        }

        function lsClampPanelWidth(kind, width) {
            const config = lsPanelConfig(kind);
            const parsed = Number.parseFloat(String(width));
            const next = Number.isFinite(parsed)
                ? parsed
                : config.limits.fallback;
            return Math.round(Math.max(
                config.limits.min,
                Math.min(lsPanelMaximum(kind), next)
            ));
        }

        function lsUpdatePanelHandleAria(kind) {
            const config = lsPanelConfig(kind);
            if (!config.handle) { return; }
            config.handle.setAttribute(
                "aria-valuemin",
                String(config.limits.min)
            );
            config.handle.setAttribute(
                "aria-valuemax",
                String(Math.round(lsPanelMaximum(kind)))
            );
            config.handle.setAttribute(
                "aria-valuenow",
                String(Math.round(lsCurrentPanelWidth(kind)))
            );
        }

        function lsSetPanelWidth(kind, width, persist=false) {
            const config = lsPanelConfig(kind);
            const next = lsClampPanelWidth(kind, width);
            lsPanelRoot.style.setProperty(config.variable, next + "px");
            lsUpdatePanelHandleAria(kind);
            lsUpdatePanelHandleAria(kind === "sidebar" ? "selected" : "sidebar");
            if (persist) {
                try {
                    localStorage.setItem(config.key, String(next));
                } catch (error) {}
            }
            return next;
        }

        function lsRestorePanelWidth(kind) {
            const config = lsPanelConfig(kind);
            let stored = "";
            try {
                stored = localStorage.getItem(config.key) || "";
            } catch (error) {}
            if (stored) {
                lsSetPanelWidth(kind, stored, false);
            } else {
                lsUpdatePanelHandleAria(kind);
            }
        }

        const lsActivePanelResizes = {
            sidebar: null,
            selected: null
        };

        function lsStartPanelResize(kind, event) {
            if (event.button !== undefined && event.button !== 0) { return; }
            const config = lsPanelConfig(kind);
            if (!config.handle) { return; }
            event.preventDefault();
            lsActivePanelResizes[kind] = {
                pointerId: event.pointerId,
                startX: event.clientX,
                startWidth: lsCurrentPanelWidth(kind)
            };
            document.body.classList.add("ls-panel-resizing");
            config.handle.classList.add("active");
            config.handle.setPointerCapture(event.pointerId);
        }

        function lsMovePanelResize(kind, event) {
            const config = lsPanelConfig(kind);
            const resize = lsActivePanelResizes[kind];
            if (!config.handle || !resize || event.pointerId !== resize.pointerId) {
                return;
            }
            const delta = event.clientX - resize.startX;
            const requested = kind === "sidebar"
                ? resize.startWidth + delta
                : resize.startWidth - delta;
            lsSetPanelWidth(kind, requested, false);
        }

        function lsFinishPanelResize(kind, event) {
            const config = lsPanelConfig(kind);
            const resize = lsActivePanelResizes[kind];
            if (!config.handle || !resize || event.pointerId !== resize.pointerId) {
                return;
            }
            lsActivePanelResizes[kind] = null;
            config.handle.classList.remove("active");
            if (!lsActivePanelResizes.sidebar && !lsActivePanelResizes.selected) {
                document.body.classList.remove("ls-panel-resizing");
            }
            lsSetPanelWidth(kind, lsCurrentPanelWidth(kind), true);
        }

        function lsResizePanelWithKeyboard(kind, event) {
            const config = lsPanelConfig(kind);
            let requested = lsCurrentPanelWidth(kind);
            if (event.key === "Home") {
                requested = config.limits.min;
            } else if (event.key === "End") {
                requested = config.limits.max;
            } else if (event.key === "ArrowLeft") {
                requested += kind === "sidebar" ? -10 : 10;
            } else if (event.key === "ArrowRight") {
                requested += kind === "sidebar" ? 10 : -10;
            } else {
                return;
            }
            event.preventDefault();
            lsSetPanelWidth(kind, requested, true);
        }

        if (lsSidebarResizeHandle) {
            lsSidebarResizeHandle.addEventListener(
                "pointerdown",
                (event) => lsStartPanelResize("sidebar", event)
            );
            lsSidebarResizeHandle.addEventListener(
                "pointermove",
                (event) => lsMovePanelResize("sidebar", event)
            );
            lsSidebarResizeHandle.addEventListener(
                "pointerup",
                (event) => lsFinishPanelResize("sidebar", event)
            );
            lsSidebarResizeHandle.addEventListener(
                "pointercancel",
                (event) => lsFinishPanelResize("sidebar", event)
            );
            lsSidebarResizeHandle.addEventListener(
                "keydown",
                (event) => lsResizePanelWithKeyboard("sidebar", event)
            );
        }

        if (lsSelectedResizeHandle) {
            lsSelectedResizeHandle.addEventListener(
                "pointerdown",
                (event) => lsStartPanelResize("selected", event)
            );
            window.addEventListener(
                "pointermove",
                (event) => lsMovePanelResize("selected", event)
            );
            window.addEventListener(
                "pointerup",
                (event) => lsFinishPanelResize("selected", event)
            );
            window.addEventListener(
                "pointercancel",
                (event) => lsFinishPanelResize("selected", event)
            );
            lsSelectedResizeHandle.addEventListener(
                "keydown",
                (event) => lsResizePanelWithKeyboard("selected", event)
            );
        }

        lsRestorePanelWidth("sidebar");
        lsRestorePanelWidth("selected");
        window.addEventListener("resize", () => {
            ["sidebar", "selected"].forEach((kind) => {
                const config = lsPanelConfig(kind);
                if (lsPanelRoot.style.getPropertyValue(config.variable)) {
                    lsSetPanelWidth(kind, lsCurrentPanelWidth(kind), false);
                } else {
                    lsUpdatePanelHandleAria(kind);
                }
            });
        });

        // v5.73: Suno-style open/closed navigation state.
        const LS_SIDEBAR_COLLAPSED_KEY = "ls_suno_sidebar_collapsed";
        const lsSidebarCollapseButton = document.getElementById("ls-sidebar-collapse-btn");

        function lsApplySidebarCollapsed(collapsed, persist=false) {
            const isCollapsed = !!collapsed;
            document.documentElement.classList.toggle("ls-sidebar-collapsed", isCollapsed);
            document.body.classList.toggle("ls-sidebar-collapsed", isCollapsed);
            if (lsSidebarCollapseButton) {
                lsSidebarCollapseButton.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
                lsSidebarCollapseButton.setAttribute(
                    "aria-label",
                    isCollapsed ? "Open navigation panel" : "Close navigation panel"
                );
                lsSidebarCollapseButton.title = isCollapsed
                    ? "Open navigation panel"
                    : "Close navigation panel";
            }
            if (persist) {
                try {
                    localStorage.setItem(LS_SIDEBAR_COLLAPSED_KEY, isCollapsed ? "1" : "0");
                } catch (error) {}
            }
            lsUpdatePanelHandleAria("selected");
        }

        let lsSidebarStartsCollapsed = false;
        try {
            lsSidebarStartsCollapsed = localStorage.getItem(LS_SIDEBAR_COLLAPSED_KEY) === "1";
        } catch (error) {}
        lsApplySidebarCollapsed(lsSidebarStartsCollapsed, false);

        if (lsSidebarCollapseButton) {
            lsSidebarCollapseButton.addEventListener("click", () => {
                const next = !document.documentElement.classList.contains("ls-sidebar-collapsed");
                lsApplySidebarCollapsed(next, true);
            });
        }
