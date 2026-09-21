        function resetRowMenuPosition(menu) {
            if (!menu) { return; }
            menu.classList.remove("row-menu-up");
            menu.style.left = "0px";
            menu.style.top = "0px";
            menu.style.right = "auto";
            menu.style.bottom = "auto";
            menu.style.visibility = "";
        }

        function closeRowMenus() {
            document.querySelectorAll(".row-menu").forEach((menu) => {
                menu.classList.add("hidden");
                resetRowMenuPosition(menu);
            });
        }

        function positionRowMenu(button, menu) {
            const viewportMargin = 8;
            const gap = 4;
            const buttonRect = button.getBoundingClientRect();

            // Measure the real popup after it has been unhidden, but before display.
            menu.style.visibility = "hidden";
            menu.style.left = "0px";
            menu.style.top = "0px";
            menu.style.right = "auto";
            menu.style.bottom = "auto";

            const menuRect = menu.getBoundingClientRect();
            const menuWidth = menuRect.width || menu.offsetWidth || 220;
            const menuHeight = menuRect.height || menu.offsetHeight || 0;

            let left = buttonRect.right - menuWidth;
            left = Math.max(viewportMargin, Math.min(left, window.innerWidth - menuWidth - viewportMargin));

            let top = buttonRect.bottom + gap;
            const fitsBelow = top + menuHeight <= window.innerHeight - viewportMargin;
            const topAbove = buttonRect.top - menuHeight - gap;

            if (!fitsBelow && topAbove >= viewportMargin) {
                top = topAbove;
            } else {
                top = Math.max(viewportMargin, Math.min(top, window.innerHeight - menuHeight - viewportMargin));
            }

            menu.style.left = Math.round(left) + "px";
            menu.style.top = Math.round(top) + "px";
            menu.style.visibility = "visible";
        }

        // Always start with row menus closed, including browser BFCache/page restore cases.
        closeRowMenus();
        window.addEventListener("pageshow", () => closeRowMenus());
        window.addEventListener("resize", () => closeRowMenus());
        window.addEventListener("scroll", () => closeRowMenus(), true);

        document.addEventListener("click", (event) => {
            const button = event.target.closest(".row-menu-btn");
            if (button) {
                event.preventDefault();
                event.stopPropagation();
                const wrap = button.closest(".row-menu-wrap");
                const menu = wrap ? wrap.querySelector(".row-menu") : null;
                if (!menu) { return; }
                const wasHidden = menu.classList.contains("hidden");
                closeRowMenus();
                if (wasHidden) {
                    menu.classList.remove("hidden");
                    positionRowMenu(button, menu);
                }
                return;
            }

            const openItem = event.target.closest(".menu-open-suno");
            if (openItem) {
                event.preventDefault();
                event.stopPropagation();
                const wrap = openItem.closest(".row-menu-wrap");
                const rowButton = wrap ? wrap.querySelector(".row-menu-btn") : null;
                const url = rowButton ? rowButton.dataset.sunoUrl : "";
                closeRowMenus();
                if (url) { openUrlInNewTab(url); }
                return;
            }

            if (!event.target.closest(".row-menu-wrap")) {
                closeRowMenus();
            }
        });
        function resolveMainCategoryClick(
            oldCategory,
            isConfirmed,
            proposedCategory = "",
            keepAuditCurrent = false
        ) {
            if (proposedCategory) {
                return proposedCategory;
            }
            if (
                !isConfirmed
                && (oldCategory === "Song" || oldCategory === "Instrumental")
            ) {
                return oldCategory;
            }
            if (keepAuditCurrent) {
                return oldCategory;
            }
            return oldCategory === "Song" ? "Instrumental" : "Song";
        }

        function shouldRemoveConfirmedCategoryRow(
            activeCategories,
            savedCategory
        ) {
            return savedCategory === "Instrumental"
                && activeCategories.includes("__instrumental_review__");
        }

        function syncMainCategoryButtons(trackId, savedCategory) {
            const idKey = String(trackId || "").trim().toLowerCase();
            document.querySelectorAll(".main-category-toggle-btn").forEach((button) => {
                if (String(button.dataset.trackId || "").trim().toLowerCase() !== idKey) {
                    return;
                }

                button.dataset.category = savedCategory;
                button.dataset.confirmed = "true";
                button.innerText = savedCategory;
                button.classList.remove(
                    "main-category-song",
                    "main-category-instrumental",
                    "main-category-unknown",
                    "main-category-uncertain",
                    "main-category-confidence-weak",
                    "main-category-confidence-medium",
                    "main-category-confidence-special"
                );
                button.classList.add("main-category-confidence-strong");

                if (savedCategory === "Song") {
                    button.classList.add("main-category-song");
                    button.classList.remove("main-category-instrumental");
                } else {
                    button.classList.add("main-category-instrumental");
                    button.classList.remove("main-category-song");
                }

                button.title =
                    "Main category: " + savedCategory +
                    "; confidence: strong. Click to switch Song / Instrumental";
            });
        }

        function syncLikeButtons(trackId, liked) {
            const idKey = String(trackId || "").trim().toLowerCase();
            document.querySelectorAll(".like-toggle-btn").forEach((button) => {
                if (String(button.dataset.trackId || "").trim().toLowerCase() !== idKey) {
                    return;
                }

                button.dataset.liked = liked ? "true" : "false";
                button.title = liked ? "Remove Like" : "Add Like";
                button.classList.toggle("liked", liked);

                const cell = button.closest(".like-cell");
                if (cell) {
                    cell.dataset.sort = liked ? "yes" : "no";
                }
            });
        }

        function showIntentAuditDecisionStatus(message) {
            let status = document.getElementById("intent-audit-decision-status");
            if (!status) {
                status = document.createElement("div");
                status.id = "intent-audit-decision-status";
                status.className = "intent-audit-decision-status";
                document.body.appendChild(status);
            }
            status.textContent = String(message || "Saved");
            status.classList.add("show");
            window.clearTimeout(status._hideTimer);
            status._hideTimer = window.setTimeout(() => {
                status.classList.remove("show");
            }, 1800);
        }

        function stopAndRemoveResolvedAuditCandidate(trackRow, removeRow) {
            if (!trackRow) { return; }
            const fragmentRow = trackRow.nextElementSibling?.classList.contains("fragment-row")
                ? trackRow.nextElementSibling
                : null;
            if (fragmentRow) {
                fragmentRow.querySelectorAll("audio").forEach((audio) => {
                    audio.pause();
                    audio.loop = false;
                    try { audio.currentTime = 0; } catch (error) {}
                    if (lastActiveAudio === audio) {
                        lastActiveAudio = null;
                    }
                });
            }
            if (removeRow) {
                fragmentRow?.remove();
                trackRow.remove();
            } else {
                trackRow.querySelector(".intent-audit-badge")?.remove();
            }
        }

