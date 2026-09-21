        function applyMainKindFilterByHotkey(key) {
            const form = document.getElementById("main-filter-form");
            if (!form) { return false; }

            const typeSelect = form.querySelector('select[name="kind_filter"]');
            if (!typeSelect) { return false; }

            const targets = {
                "a": {category: "", type: ""},
                "s": {category: "Song"},
                "i": {category: "Instrumental"},
                "r": {category: "__instrumental_review__"},
                "m": {type: "__has_stems__"},
                "l": {type: "__liked__"}
            };
            if (!(key in targets)) {
                return false;
            }

            const target = targets[key];
            const url = new URL(window.location.href);
            const currentCategories = url.searchParams.getAll("category_filter");
            const targetCategories = Object.prototype.hasOwnProperty.call(target, "category")
                ? (target.category ? [target.category] : [])
                : currentCategories;
            const categoryChanged = (
                currentCategories.join("\u0000") !== targetCategories.join("\u0000")
            );
            const typeChanged = Object.prototype.hasOwnProperty.call(target, "type") && typeSelect.value !== target.type;
            if (!categoryChanged && !typeChanged) {
                return true;
            }

            if (categoryChanged) {
                url.searchParams.delete("category_filter");
                url.searchParams.delete("category_mode");
                targetCategories.forEach(
                    (value) => url.searchParams.append("category_filter", value)
                );
            }
            if (typeChanged) { typeSelect.value = target.type; }
            if (Object.prototype.hasOwnProperty.call(target, "type")) {
                if (target.type) {
                    url.searchParams.set("kind_filter", target.type);
                } else {
                    url.searchParams.delete("kind_filter");
                }
            }
            url.searchParams.delete("rows");
            saveViewState();
            stopAllPlaybackForNavigation();
            const labelMap = {
                "a": "Switching to All...",
                "s": "Switching to Songs...",
                "i": "Switching to Instrumental...",
                "r": "Opening Instrumental review...",
                "m": "Switching to Stems...",
                "l": "Switching to Liked..."
            };
            showBusy(labelMap[key] || "Applying filter...", "Loading results...");
            setTimeout(() => { window.location.href = url.toString(); }, 40);
            return true;
        }

        document.addEventListener("keydown", (event) => {
            if (event.ctrlKey || event.altKey || event.metaKey) {
                return;
            }

            const tagName = (event.target && event.target.tagName || "").toLowerCase();
            if (tagName === "input" || tagName === "textarea" || tagName === "select") {
                return;
            }

            const key = (event.key || "").toLowerCase();
            if (key === "p") {
                toggleAutoplayListEnabled();
                event.preventDefault();
                event.stopPropagation();
                return;
            }
            if (applyMainKindFilterByHotkey(key)) {
                event.preventDefault();
                event.stopPropagation();
            }
        }, true);

        document.addEventListener("keydown", (event) => {
            if (event.code !== "Space") {
                return;
            }

            const target = event.target instanceof Element
                ? event.target
                : document.activeElement;
            const active = document.activeElement instanceof Element
                ? document.activeElement
                : target;
            const editableSelector = [
                "input:not([type='checkbox']):not([type='radio']):not([type='range']):not([type='button']):not([type='submit']):not([type='reset'])",
                "textarea",
                "select",
                "[contenteditable='true']"
            ].join(",");
            const blockedControlSelector = [
                "button",
                "label",
                "input[type='checkbox']",
                "input[type='radio']",
                "input[type='range']",
                "input[type='button']",
                "input[type='submit']",
                "input[type='reset']",
                "[role='button']",
                "[role='checkbox']",
                "[role='slider']",
                "dialog",
                "[role='dialog']",
                "[aria-modal='true']"
            ].join(",");

            // Editable fields keep their native Space behavior and never control playback.
            if (
                (target && target.closest && target.closest(editableSelector)) ||
                (active && active.closest && active.closest(editableSelector))
            ) {
                return;
            }

            if ((event.ctrlKey || event.metaKey) && !event.altKey) {
                // Ctrl+Space is reserved exclusively for selected Stems. With
                // the Stems layer closed it is deliberately a no-op and must
                // never fall through to the normal Space handler.
                event.preventDefault();
                event.stopImmediatePropagation();
                if (
                    !event.repeat &&
                    lsGlobalPlayer &&
                    typeof lsGlobalPlayer.isStemsViewOpen === "function" &&
                    lsGlobalPlayer.isStemsViewOpen() &&
                    typeof lsGlobalPlayer.activateStemPlayback === "function"
                ) {
                    lsGlobalPlayer.activateStemPlayback().catch((error) => {
                        alert(String(error && error.message || error || "Could not control selected Stems."));
                    });
                }
                return;
            }

            const focusedGlobalTransport = (
                (target && target.closest && target.closest("#ls-global-player")) ||
                (active && active.closest && active.closest("#ls-global-player"))
            );
            if (
                focusedGlobalTransport &&
                lsGlobalPlayer &&
                typeof lsGlobalPlayer.hasCurrentTrack === "function" &&
                lsGlobalPlayer.hasCurrentTrack()
            ) {
                event.preventDefault();
                event.stopImmediatePropagation();
                if (!event.repeat) { lsGlobalPlayer.togglePlayback(); }
                return;
            }

            // Other buttons, checkboxes, sliders and dialogs suppress Space entirely here.
            // This prevents both the global shortcut and native button activation.
            if (
                (target && target.closest && target.closest(blockedControlSelector)) ||
                (active && active.closest && active.closest(blockedControlSelector))
            ) {
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            if (
                lsGlobalPlayer &&
                typeof lsGlobalPlayer.hasCurrentTrack === "function" &&
                lsGlobalPlayer.hasCurrentTrack()
            ) {
                event.preventDefault();
                event.stopImmediatePropagation();
                if (!event.repeat) { lsGlobalPlayer.togglePlayback(); }
                return;
            }

            const visibleStemBlock = currentStemBlock && !currentStemBlock.classList.contains("hidden")
                ? currentStemBlock
                : Array.from(document.querySelectorAll(".stem-block:not(.hidden)")).find((block) => !block.closest(".fragment-row")?.classList.contains("hidden"));

            if (visibleStemBlock) {
                event.preventDefault();
                event.stopPropagation();
                toggleStemSpacePause(visibleStemBlock);
                return;
            }

            const globalAudio = lsGlobalPlayer ? lsGlobalPlayer.getAudio() : null;
            if (lastActiveAudio && globalAudio && lastActiveAudio !== globalAudio) {
                // Compare playback is a fallback only when the main player has no track.
                event.preventDefault();
                event.stopPropagation();
                if (lastActiveAudio.paused) {
                    lastActiveAudio.play().catch(() => {});
                } else {
                    lastActiveAudio.pause();
                }
            }
        }, true);



