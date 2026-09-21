        const wavPreviewBackdrop = document.getElementById("wav-preview-backdrop");
        const wavPreviewSunoTitle = document.getElementById("wav-preview-suno-title");
        const wavPreviewFamily = document.getElementById("wav-preview-family");
        const wavPreviewCategory = document.getElementById("wav-preview-category");
        const wavPreviewVariant = document.getElementById("wav-preview-variant");
        const wavPreviewPath = document.getElementById("wav-preview-path");
        const wavPreviewStems = document.getElementById("wav-preview-stems");
        const wavPreviewCancel = document.getElementById("wav-preview-cancel");
        const wavPreviewConfirm = document.getElementById("wav-preview-confirm");
        const wavFamilyConfirmation = document.getElementById("wav-family-confirmation");
        const wavFamilyBadge = document.getElementById("wav-family-badge");
        const wavFamilyChange = document.getElementById("wav-family-change");
        const wavFamilyChoice = document.getElementById("wav-family-choice");
        const wavFamilyChoiceNote = document.getElementById("wav-family-choice-note");
        const wavFamilyExisting = document.getElementById("wav-family-existing");
        const wavFamilyUseExisting = document.getElementById("wav-family-use-existing");
        const wavFamilyNew = document.getElementById("wav-family-new");
        const wavFamilyCreateNew = document.getElementById("wav-family-create-new");
        const wavFamilyChoiceStatus = document.getElementById("wav-family-choice-status");

        function setWavFamilyChoiceStatus(message, isError=false) {
            if (!wavFamilyChoiceStatus) { return; }
            wavFamilyChoiceStatus.textContent = message || "";
            wavFamilyChoiceStatus.classList.toggle("error", Boolean(isError));
        }

        function renderWavFamilyOptions(row) {
            if (!wavFamilyExisting) { return; }
            wavFamilyExisting.innerHTML = "";

            const options = Array.isArray(row.family_options)
                ? row.family_options
                : [];
            const mappedTitle = String(row.mapped_family_title || "").trim();

            if (!options.length) {
                const emptyOption = document.createElement("option");
                emptyOption.value = "";
                emptyOption.textContent = "No existing Local families";
                wavFamilyExisting.appendChild(emptyOption);
                wavFamilyExisting.disabled = true;
                wavFamilyUseExisting.disabled = true;
            } else {
                wavFamilyExisting.disabled = false;
                wavFamilyUseExisting.disabled = false;

                options.forEach((item, index) => {
                    const option = document.createElement("option");
                    const title = String((item && item.title) || "").trim();
                    const categories = Array.isArray(item && item.categories)
                        ? item.categories.filter(Boolean).join(" + ")
                        : "";
                    const similarity = Math.round(
                        Number((item && item.similarity) || 0) * 100
                    );
                    const suggested = Boolean(item && item.is_similar);
                    option.value = title;
                    option.textContent = (
                        (suggested ? "Suggested " + similarity + "% — " : "")
                        + title
                        + (categories ? " [" + categories + "]" : "")
                    );
                    if (
                        mappedTitle
                        && title.toLocaleLowerCase() === mappedTitle.toLocaleLowerCase()
                    ) {
                        option.selected = true;
                    } else if (!mappedTitle && suggested && index === 0) {
                        option.selected = true;
                    }
                    wavFamilyExisting.appendChild(option);
                });
            }

            if (wavFamilyNew) {
                wavFamilyNew.value = String(
                    row.proposed_family_title
                    || row.local_family_title
                    || row.title
                    || ""
                ).trim();
            }

            const similar = Array.isArray(row.similar_families)
                ? row.similar_families
                : [];
            if (wavFamilyChoiceNote) {
                if (similar.length) {
                    wavFamilyChoiceNote.textContent = (
                        "LS found " + String(similar.length)
                        + " similar existing family name(s). "
                        + "Choose one, or create a separate family."
                    );
                } else {
                    wavFamilyChoiceNote.textContent = (
                        "No close existing family was found. "
                        + "Create a new family, or choose any existing family from the list."
                    );
                }
            }
        }

        function applyWavPreviewRow(row, forceChoice=false) {
            wavPreviewSunoTitle.textContent = row.title || "";
            wavPreviewFamily.textContent = row.local_family_title || "";
            wavPreviewCategory.textContent = row.category || "";
            wavPreviewVariant.textContent = row.variant || "";
            wavPreviewPath.textContent = row.target_path || "";
            wavPreviewStems.textContent = row.stems_folder || "";

            const confirmed = Boolean(row.family_confirmed) && !forceChoice;
            if (wavFamilyConfirmation) {
                wavFamilyConfirmation.classList.toggle("confirmed", confirmed);
            }
            if (wavFamilyBadge) {
                wavFamilyBadge.textContent = confirmed
                    ? "Local family confirmed for this Track ID"
                    : "Local family not confirmed";
            }
            if (wavFamilyChange) {
                wavFamilyChange.style.display = confirmed ? "inline-flex" : "none";
            }
            if (wavFamilyChoice) {
                wavFamilyChoice.style.display = confirmed ? "none" : "grid";
            }
            if (wavPreviewConfirm) {
                wavPreviewConfirm.disabled = !confirmed;
                wavPreviewConfirm.title = confirmed
                    ? "Download WAV to the confirmed Local family"
                    : "Confirm the Local family first";
            }

            if (!confirmed) {
                renderWavFamilyOptions(row);
            }
        }

        function showWavDownloadPreview(initialRow) {
            return new Promise((resolve) => {
                if (!wavPreviewBackdrop) {
                    resolve(null);
                    return;
                }

                let currentRow = Object.assign({}, initialRow || {});
                let finished = false;
                let familyRequestActive = false;

                const setFamilyButtonsBusy = (busy) => {
                    familyRequestActive = Boolean(busy);
                    if (wavFamilyUseExisting) {
                        wavFamilyUseExisting.disabled = familyRequestActive
                            || !wavFamilyExisting
                            || wavFamilyExisting.disabled;
                    }
                    if (wavFamilyCreateNew) {
                        wavFamilyCreateNew.disabled = familyRequestActive;
                    }
                    if (wavFamilyChange) {
                        wavFamilyChange.disabled = familyRequestActive;
                    }
                };

                const confirmFamily = async (action, familyTitle) => {
                    if (familyRequestActive) { return; }
                    const cleanTitle = String(familyTitle || "").trim();
                    if (!cleanTitle) {
                        setWavFamilyChoiceStatus(
                            "Choose or enter a Local family title.",
                            true
                        );
                        return;
                    }

                    setFamilyButtonsBusy(true);
                    setWavFamilyChoiceStatus("Saving Track ID → Local family...");

                    try {
                        const body = new URLSearchParams();
                        body.set("track_id", currentRow.track_id || "");
                        body.set("action", action);
                        body.set("family_title", cleanTitle);

                        const response = await fetch("/confirm-local-family", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/x-www-form-urlencoded"
                            },
                            body: body.toString()
                        });
                        const data = await response.json();
                        if (!response.ok || !data.ok || !data.row) {
                            throw new Error(
                                data.error || "Could not confirm Local family"
                            );
                        }

                        currentRow = Object.assign({}, data.row);
                        applyWavPreviewRow(currentRow, false);
                        setWavFamilyChoiceStatus("");
                        wavPreviewConfirm.focus();
                    } catch (error) {
                        setWavFamilyChoiceStatus(
                            error.message || "Could not confirm Local family.",
                            true
                        );
                    } finally {
                        setFamilyButtonsBusy(false);
                    }
                };

                const finish = (value) => {
                    if (finished) { return; }
                    finished = true;
                    wavPreviewBackdrop.style.display = "none";
                    wavPreviewCancel.removeEventListener("click", onCancel);
                    wavPreviewConfirm.removeEventListener("click", onConfirm);
                    wavFamilyUseExisting.removeEventListener("click", onUseExisting);
                    wavFamilyCreateNew.removeEventListener("click", onCreateNew);
                    wavFamilyChange.removeEventListener("click", onChangeFamily);
                    wavFamilyNew.removeEventListener("keydown", onNewFamilyKeyDown);
                    wavPreviewBackdrop.removeEventListener("click", onBackdrop);
                    document.removeEventListener("keydown", onKeyDown);
                    resolve(value);
                };

                const onCancel = () => finish(null);
                const onConfirm = () => {
                    if (!currentRow.family_confirmed) {
                        setWavFamilyChoiceStatus(
                            "Confirm the Local family before downloading.",
                            true
                        );
                        return;
                    }
                    finish(currentRow);
                };
                const onUseExisting = () => {
                    confirmFamily(
                        "existing",
                        wavFamilyExisting ? wavFamilyExisting.value : ""
                    );
                };
                const onCreateNew = () => {
                    confirmFamily(
                        "new",
                        wavFamilyNew ? wavFamilyNew.value : ""
                    );
                };
                const onChangeFamily = () => {
                    setWavFamilyChoiceStatus("");
                    applyWavPreviewRow(currentRow, true);
                    if (wavFamilyNew) {
                        wavFamilyNew.value = String(
                            currentRow.local_family_title || ""
                        );
                    }
                    if (wavFamilyExisting && !wavFamilyExisting.disabled) {
                        wavFamilyExisting.focus();
                    } else if (wavFamilyNew) {
                        wavFamilyNew.focus();
                        wavFamilyNew.select();
                    }
                };
                const onNewFamilyKeyDown = (event) => {
                    if (event.key === "Enter") {
                        event.preventDefault();
                        onCreateNew();
                    }
                };
                const onBackdrop = (event) => {
                    if (event.target === wavPreviewBackdrop) {
                        finish(null);
                    }
                };
                const onKeyDown = (event) => {
                    if (event.key === "Escape") {
                        finish(null);
                    }
                };

                wavPreviewCancel.addEventListener("click", onCancel);
                wavPreviewConfirm.addEventListener("click", onConfirm);
                wavFamilyUseExisting.addEventListener("click", onUseExisting);
                wavFamilyCreateNew.addEventListener("click", onCreateNew);
                wavFamilyChange.addEventListener("click", onChangeFamily);
                wavFamilyNew.addEventListener("keydown", onNewFamilyKeyDown);
                wavPreviewBackdrop.addEventListener("click", onBackdrop);
                document.addEventListener("keydown", onKeyDown);

                setWavFamilyChoiceStatus("");
                applyWavPreviewRow(currentRow, false);
                wavPreviewBackdrop.style.display = "flex";

                if (currentRow.family_confirmed) {
                    wavPreviewConfirm.focus();
                } else if (wavFamilyExisting && !wavFamilyExisting.disabled) {
                    wavFamilyExisting.focus();
                } else if (wavFamilyNew) {
                    wavFamilyNew.focus();
                    wavFamilyNew.select();
                }
            });
        }


        function waitMs(ms) {
            return new Promise((resolve) => setTimeout(resolve, ms));
        }

        async function renewSunoTokenForWav() {
            showBusy(
                "Renewing Suno authorization...",
                "LS opened Suno in Chrome. The Token Bridge will return the fresh authorization and LS will retry automatically."
            );

            const startResponse = await fetch(
                "/start-suno-token-renewal",
                { method: "POST" }
            );
            const startData = await startResponse.json();
            if (!startResponse.ok || !startData.ok) {
                throw new Error(
                    startData.error || "Could not open Suno"
                );
            }

            const previousUpdatedAt =
                startData.previous_token_updated_at || "";
            const deadline = Date.now() + 120000;

            while (Date.now() < deadline) {
                const response = await fetch(
                    "/suno-token-status?_=" + Date.now(),
                    { cache: "no-store" }
                );
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(
                        data.error || "Could not read token status"
                    );
                }
                if (
                    data.token_saved
                    && data.token_updated_at
                    && data.token_updated_at !== previousUpdatedAt
                ) {
                    return true;
                }
                if (busyText) {
                    busyText.innerText = data.bridge_active
                        ? "Bridge active. Waiting for the fresh Suno API authorization..."
                        : "Waiting for LS Token Bridge. If this is the first use, open Downloader → Bridge setup.";
                }
                await waitMs(1000);
            }

            throw new Error(
                "No fresh token arrived. Open Downloader → Bridge setup once, then retry."
            );
        }

        function isSunoAuthExpiredResult(data) {
            if (data && data.auth_expired) {
                return true;
            }
            return Boolean(
                data
                && Array.isArray(data.rows)
                && data.rows.some((row) => {
                    const error = String(
                        (row && row.error) || ""
                    ).toLowerCase();
                    return error.includes("http 401")
                        || error.includes("token is expired");
                })
            );
        }

        const wavResultBackdrop = document.getElementById("wav-result-backdrop");
        const wavResultDownloaded = document.getElementById("wav-result-downloaded");
        const wavResultSkipped = document.getElementById("wav-result-skipped");
        const wavResultErrors = document.getElementById("wav-result-errors");
        const wavResultPath = document.getElementById("wav-result-path");
        const wavResultReport = document.getElementById("wav-result-report");
        const wavResultOk = document.getElementById("wav-result-ok");

        function showWavDownloadResult(data) {
            return new Promise((resolve) => {
                if (!wavResultBackdrop) {
                    resolve();
                    return;
                }

                const firstRow = (data.rows && data.rows.length) ? data.rows[0] : {};

                wavResultDownloaded.textContent = String(data.downloaded ?? 0);
                wavResultSkipped.textContent = String(data.skipped ?? 0);
                wavResultErrors.textContent = String(data.errors ?? 0);
                wavResultPath.textContent = firstRow.path || "";
                wavResultReport.textContent = data.report || "";

                let finished = false;

                const finish = () => {
                    if (finished) {
                        return;
                    }
                    finished = true;
                    wavResultBackdrop.style.display = "none";
                    wavResultOk.removeEventListener("click", onOk);
                    wavResultBackdrop.removeEventListener("click", onBackdrop);
                    document.removeEventListener("keydown", onKeyDown);
                    resolve();
                };

                const onOk = () => finish();
                const onBackdrop = (event) => {
                    if (event.target === wavResultBackdrop) {
                        finish();
                    }
                };
                const onKeyDown = (event) => {
                    if (event.key === "Escape" || event.key === "Enter") {
                        finish();
                    }
                };

                wavResultOk.addEventListener("click", onOk);
                wavResultBackdrop.addEventListener("click", onBackdrop);
                document.addEventListener("keydown", onKeyDown);

                wavResultBackdrop.style.display = "flex";
                wavResultOk.focus();
            });
        }