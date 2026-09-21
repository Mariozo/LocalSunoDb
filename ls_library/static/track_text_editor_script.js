        const lyricsEditorModal = document.getElementById("lyrics-editor-modal");
        const lyricsEditorTitle = document.getElementById("lyrics-editor-title");
        const lyricsEditorTrackTitle = document.getElementById("lyrics-editor-track-title");
        const lyricsEditorTextarea = document.getElementById("lyrics-editor-textarea");
        const lyricsEditorStatus = document.getElementById("lyrics-editor-status");
        const lyricsEditorSave = document.getElementById("lyrics-editor-save");
        const lyricsEditorCancel = document.getElementById("lyrics-editor-cancel");
        const trackTextSource = document.getElementById("track-text-source");
        const trackTextTabs = Array.from(
            document.querySelectorAll(".track-text-tab")
        );

        let lyricsEditorTrackId = "";
        let lyricsEditorTrackTitleText = "";
        let lyricsEditorOriginalText = "";
        let lyricsEditorLoadSession = 0;
        let trackTextFields = {};
        let trackTextActiveField = "lyrics";
        let trackTextDrafts = {};

        function getTrackTextFieldData(fieldName) {
            const cleanField = ["lyrics", "prompt", "style"].includes(fieldName)
                ? fieldName
                : "lyrics";
            return trackTextFields[cleanField] || {
                label: cleanField.charAt(0).toUpperCase() + cleanField.slice(1),
                text: "",
                source_column: "",
                editable: cleanField === "lyrics",
                has_text: false,
                duplicate_of: ""
            };
        }

        function rememberActiveTrackTextDraft() {
            if (
                !lyricsEditorTextarea ||
                !trackTextActiveField ||
                lyricsEditorTextarea.disabled ||
                !Object.keys(trackTextFields || {}).length
            ) {
                return;
            }

            trackTextDrafts[trackTextActiveField] =
                String(lyricsEditorTextarea.value || "");
        }

        function updateLyricsEditorChangedState() {
            if (!lyricsEditorTextarea || !lyricsEditorSave) {
                return false;
            }

            const fieldData = getTrackTextFieldData(trackTextActiveField);
            const editable =
                trackTextActiveField === "lyrics" &&
                Boolean(fieldData.editable) &&
                !lyricsEditorTextarea.disabled;

            const changed =
                editable &&
                String(lyricsEditorTextarea.value || "") !==
                String(lyricsEditorOriginalText || "");

            lyricsEditorSave.style.display = editable ? "" : "none";
            lyricsEditorSave.disabled = !changed;
            lyricsEditorSave.classList.toggle("changed", changed);

            return changed;
        }

        function renderTrackTextField(fieldName, focusEditor=false) {
            rememberActiveTrackTextDraft();

            trackTextActiveField = ["lyrics", "prompt", "style"].includes(fieldName)
                ? fieldName
                : "lyrics";

            const fieldData = getTrackTextFieldData(trackTextActiveField);
            const label = String(fieldData.label || trackTextActiveField);
            const sourceColumn = String(fieldData.source_column || "");
            const duplicateOf = String(fieldData.duplicate_of || "");
            const editable =
                trackTextActiveField === "lyrics" &&
                Boolean(fieldData.editable);

            lyricsEditorTitle.textContent =
                editable ? "Edit " + label : label;

            const storedText = Object.prototype.hasOwnProperty.call(
                trackTextDrafts,
                trackTextActiveField
            )
                ? String(trackTextDrafts[trackTextActiveField] || "")
                : String(fieldData.text || "");

            lyricsEditorOriginalText = String(fieldData.text || "");
            lyricsEditorTextarea.value = storedText;
            lyricsEditorTextarea.disabled = false;
            lyricsEditorTextarea.readOnly = !editable;
            lyricsEditorTextarea.setAttribute(
                "aria-label",
                label + " text"
            );

            if (trackTextSource) {
                if (duplicateOf === "lyrics") {
                    trackTextSource.textContent =
                        "Duplicate of Lyrics — DB field: " +
                        (sourceColumn || "prompt") +
                        " — read only";
                } else if (sourceColumn) {
                    trackTextSource.textContent =
                        "DB field: " + sourceColumn +
                        (editable ? " — editable" : " — read only");
                } else {
                    trackTextSource.textContent =
                        "No " + label + " text in LS DB" +
                        (editable ? " — you can add it here" : "");
                }
            }

            trackTextTabs.forEach((tab) => {
                const tabField = String(tab.dataset.textField || "");
                const tabData = getTrackTextFieldData(tabField);
                tab.classList.toggle(
                    "active",
                    tabField === trackTextActiveField
                );
                tab.classList.toggle(
                    "empty",
                    !Boolean(tabData.has_text)
                );
                tab.setAttribute(
                    "aria-pressed",
                    tabField === trackTextActiveField ? "true" : "false"
                );
            });

            lyricsEditorStatus.textContent = "";
            lyricsEditorSave.textContent = "Save Lyrics";
            updateLyricsEditorChangedState();

            if (focusEditor) {
                requestAnimationFrame(() => {
                    lyricsEditorTextarea.focus();
                    lyricsEditorTextarea.setSelectionRange(0, 0);
                });
            }
        }

        function showTrackTextLoading(trackId, trackTitle, fieldName) {
            if (!lyricsEditorModal || !lyricsEditorTextarea || !trackId) {
                return;
            }

            lyricsEditorTrackId = String(trackId || "");
            lyricsEditorTrackTitleText = String(trackTitle || trackId);
            trackTextActiveField = ["lyrics", "prompt", "style"].includes(fieldName)
                ? fieldName
                : "lyrics";
            trackTextFields = {};
            trackTextDrafts = {};
            lyricsEditorOriginalText = "";

            lyricsEditorTrackTitle.textContent = lyricsEditorTrackTitleText;
            lyricsEditorTitle.textContent = "Track text";
            lyricsEditorTextarea.value = "";
            lyricsEditorTextarea.disabled = true;
            lyricsEditorTextarea.readOnly = true;
            lyricsEditorStatus.textContent = "Loading...";
            lyricsEditorSave.style.display = "none";
            lyricsEditorSave.disabled = true;
            lyricsEditorSave.classList.remove("changed");
            if (trackTextSource) {
                trackTextSource.textContent = "";
            }

            trackTextTabs.forEach((tab) => {
                tab.classList.remove("active", "empty");
            });

            lyricsEditorModal.style.display = "flex";
        }

        async function openTrackTextForTrack(
            trackId,
            trackTitle,
            fieldName="lyrics"
        ) {
            trackId = String(trackId || "").trim();
            if (!trackId) {
                return;
            }

            lyricsEditorLoadSession += 1;
            const session = lyricsEditorLoadSession;

            showTrackTextLoading(trackId, trackTitle, fieldName);

            try {
                const params = new URLSearchParams();
                params.set("track_id", trackId);

                const response = await fetch(
                    "/track-text-json?" + params.toString(),
                    { cache: "no-store" }
                );
                const data = await response.json();

                if (
                    session !== lyricsEditorLoadSession ||
                    trackId.toLowerCase() !==
                        String(lyricsEditorTrackId || "").toLowerCase()
                ) {
                    return;
                }

                if (!response.ok || !data.ok) {
                    throw new Error(
                        data.error || "Could not load track text."
                    );
                }

                lyricsEditorTrackId = String(data.track_id || trackId);
                lyricsEditorTrackTitleText = String(
                    data.title || trackTitle || trackId
                );
                lyricsEditorTrackTitle.textContent =
                    lyricsEditorTrackTitleText;
                trackTextFields = data.fields || {};
                trackTextDrafts = {};

                renderTrackTextField(fieldName, true);
            } catch (error) {
                if (session !== lyricsEditorLoadSession) {
                    return;
                }

                lyricsEditorTextarea.disabled = true;
                lyricsEditorTextarea.readOnly = true;
                lyricsEditorStatus.textContent =
                    error.message || "Could not load track text.";
                lyricsEditorSave.style.display = "none";
                lyricsEditorSave.disabled = true;
                lyricsEditorSave.classList.remove("changed");
            }
        }

        function openLyricsEditorForTrack(trackId, trackTitle) {
            return openTrackTextForTrack(
                trackId,
                trackTitle,
                "lyrics"
            );
        }

        function closeLyricsEditorWithoutSaving() {
            if (!lyricsEditorModal) {
                return;
            }

            lyricsEditorLoadSession += 1;
            lyricsEditorModal.style.display = "none";
            lyricsEditorTrackId = "";
            lyricsEditorTrackTitleText = "";
            lyricsEditorOriginalText = "";
            trackTextFields = {};
            trackTextDrafts = {};
            trackTextActiveField = "lyrics";
            lyricsEditorTextarea.value = "";
            lyricsEditorTextarea.disabled = false;
            lyricsEditorTextarea.readOnly = false;
            lyricsEditorStatus.textContent = "";
            lyricsEditorSave.style.display = "";
            lyricsEditorSave.disabled = true;
            lyricsEditorSave.classList.remove("changed");
            lyricsEditorSave.textContent = "Save Lyrics";
            if (trackTextSource) {
                trackTextSource.textContent = "";
            }
        }

        async function saveLyricsFromEditor() {
            if (
                trackTextActiveField !== "lyrics" ||
                !lyricsEditorTrackId ||
                !lyricsEditorTextarea ||
                !updateLyricsEditorChangedState()
            ) {
                return;
            }

            const lyricsText = lyricsEditorTextarea.value || "";
            const body = new URLSearchParams();
            body.set("track_id", lyricsEditorTrackId);
            body.set("lyrics", lyricsText);

            lyricsEditorSave.disabled = true;
            lyricsEditorSave.classList.remove("changed");
            lyricsEditorSave.textContent = "Saving...";
            lyricsEditorStatus.textContent = "";

            try {
                const response = await fetch("/save-lyrics", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    body: body.toString()
                });

                const responseText = await response.text();

                if (!response.ok) {
                    lyricsEditorStatus.textContent =
                        responseText || "Could not save Lyrics.";
                    lyricsEditorSave.textContent = "Save Lyrics";
                    updateLyricsEditorChangedState();
                    return;
                }

                lyricsEditorStatus.textContent = "Saved";
                saveViewState();
                window.location.reload();
            } catch (error) {
                lyricsEditorStatus.textContent =
                    "Could not save Lyrics.";
                lyricsEditorSave.textContent = "Save Lyrics";
                updateLyricsEditorChangedState();
            }
        }

        document.addEventListener("click", (event) => {
            const trigger = event.target.closest(".text-field-trigger");
            if (!trigger) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            openTrackTextForTrack(
                trigger.dataset.trackId || "",
                trigger.dataset.trackTitle || "",
                trigger.dataset.textField || "lyrics"
            );
        });

        document.addEventListener("keydown", (event) => {
            const trigger = event.target.closest
                ? event.target.closest(".text-field-trigger")
                : null;

            if (
                trigger &&
                (event.key === "Enter" || event.key === " ")
            ) {
                event.preventDefault();
                openTrackTextForTrack(
                    trigger.dataset.trackId || "",
                    trigger.dataset.trackTitle || "",
                    trigger.dataset.textField || "lyrics"
                );
                return;
            }

            if (
                event.key === "Escape" &&
                lyricsEditorModal &&
                lyricsEditorModal.style.display === "flex"
            ) {
                event.preventDefault();
                closeLyricsEditorWithoutSaving();
            }
        });

        trackTextTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                renderTrackTextField(
                    String(tab.dataset.textField || "lyrics"),
                    false
                );
            });
        });

        if (lyricsEditorTextarea) {
            lyricsEditorTextarea.addEventListener("input", () => {
                trackTextDrafts[trackTextActiveField] =
                    String(lyricsEditorTextarea.value || "");
                updateLyricsEditorChangedState();
            });
        }

        if (lyricsEditorSave) {
            lyricsEditorSave.addEventListener(
                "click",
                saveLyricsFromEditor
            );
        }

        if (lyricsEditorCancel) {
            lyricsEditorCancel.addEventListener(
                "click",
                closeLyricsEditorWithoutSaving
            );
        }

        if (lyricsEditorModal) {
            lyricsEditorModal.addEventListener("click", (event) => {
                if (event.target === lyricsEditorModal) {
                    closeLyricsEditorWithoutSaving();
                }
            });
        }
