        const lsDownloaderRoot = document.body && document.body.id === "ls-downloader" ? document.body : null;
        const sunoConnectionState = lsDownloaderRoot ? lsDownloaderRoot.querySelector("#suno-connection-state") : null;
        const sunoConnectionTitle = lsDownloaderRoot ? lsDownloaderRoot.querySelector("#suno-connection-title") : null;
        const sunoConnectionNote = lsDownloaderRoot ? lsDownloaderRoot.querySelector("#suno-connection-note") : null;
        const repairTokenBridgeBtn = lsDownloaderRoot ? lsDownloaderRoot.querySelector("#repair-token-bridge-btn") : null;
        const SUNO_CONNECTION_GRACE_MS = 4000;
        const SUNO_AUTH_ACTION_SELECTOR = [
            "#refresh-tracklist-btn",
            "#auto-metadata-backfill-btn",
            "#preview-meta-btn",
            "#refresh-selected-meta-btn",
            "#preview-first-selected-btn",
            ".small-preview-btn",
            "#import-selected-tracklist-btn",
            "#update-selected-titles-btn",
            "#downloader-wav-download",
        ].join(", ");
        const sunoConnectionOpenedAt = Date.now();
        let sunoConnectionLastStatus = null;
        let tokenBridgeRecoveryActive = false;
        const TOKEN_BRIDGE_LIVENESS_SOURCE = "ls-suno-token-bridge-local-v1";
        const TOKEN_BRIDGE_LIVENESS_PROBE = "LS_SUNO_LOCAL_LIVENESS_PROBE";
        const TOKEN_BRIDGE_LIVENESS_RESPONSE = "LS_SUNO_LOCAL_LIVENESS_RESPONSE";
        const TOKEN_BRIDGE_LIVENESS_MARKER_ID = "ls-suno-token-bridge-liveness";
        const TOKEN_BRIDGE_HEARTBEAT_MAX_AGE_MS = 3500;
        let bridgeLivenessActive = false;
        let bridgeLivenessExtensionVersion = "";

        function makeTokenBridgeProbeId() {
            return (
                "ls-" + Date.now().toString(36) + "-" +
                Math.random().toString(36).slice(2, 14)
            );
        }

        function probeTokenBridgeLiveness(timeoutMs=SUNO_CONNECTION_GRACE_MS) {
            return new Promise((resolve) => {
                const timeout = Math.max(
                    250,
                    Number(timeoutMs) || SUNO_CONNECTION_GRACE_MS
                );
                const deadline = Date.now() + timeout;
                let timer = null;

                const readHeartbeat = () => {
                    const marker = document.getElementById(
                        TOKEN_BRIDGE_LIVENESS_MARKER_ID
                    );
                    if (!marker) {
                        return null;
                    }

                    const seenAt = Number(
                        marker.getAttribute("data-seen-at") || "0"
                    );
                    const extensionVersion = String(
                        marker.getAttribute("data-extension-version") || ""
                    );
                    const age = Date.now() - seenAt;

                    if (
                        !Number.isFinite(seenAt) ||
                        seenAt <= 0 ||
                        age < 0 ||
                        age > TOKEN_BRIDGE_HEARTBEAT_MAX_AGE_MS
                    ) {
                        return null;
                    }

                    return {
                        active: true,
                        extensionVersion,
                    };
                };

                const finish = (result) => {
                    if (timer !== null) {
                        window.clearTimeout(timer);
                    }
                    const active = Boolean(result && result.active);
                    bridgeLivenessActive = active;
                    bridgeLivenessExtensionVersion = active
                        ? String(result.extensionVersion || "")
                        : "";
                    resolve({
                        active: bridgeLivenessActive,
                        extensionVersion: bridgeLivenessExtensionVersion,
                    });
                };

                const check = () => {
                    const heartbeat = readHeartbeat();
                    if (heartbeat) {
                        finish(heartbeat);
                        return;
                    }
                    if (Date.now() >= deadline) {
                        finish(null);
                        return;
                    }
                    timer = window.setTimeout(check, 100);
                };

                check();
            });
        }

        function setSunoLoginRenewStatus(text, mode="") {
            if (sunoLoginRenewStatus) {
                sunoLoginRenewStatus.style.display = "block";
                sunoLoginRenewStatus.className = "status " + mode;
                sunoLoginRenewStatus.innerText = text || "";
            }
            setDownloaderActionStatus(text || "", mode || "");
        }

        function setSunoConnectionView(level, title, note, showRepair=false) {
            if (sunoConnectionState) {
                sunoConnectionState.className = "connection-state-pill " + (level || "warn");
            }
            if (sunoConnectionTitle) {
                sunoConnectionTitle.textContent = title || "";
            }
            if (sunoConnectionNote) {
                sunoConnectionNote.textContent = note || "";
            }
            if (repairTokenBridgeBtn) {
                repairTokenBridgeBtn.hidden = !showRepair;
                if (!tokenBridgeRecoveryActive) {
                    repairTokenBridgeBtn.disabled = false;
                }
            }
        }

        function setSunoAuthActionsBlocked(blocked) {
            const shouldBlock = Boolean(blocked);
            window.lsSunoAuthBlocked = shouldBlock;
            (lsDownloaderRoot ? lsDownloaderRoot.querySelectorAll(SUNO_AUTH_ACTION_SELECTOR) : []).forEach((element) => {
                if (!element) { return; }
                if (shouldBlock) {
                    if (element.dataset.lsConnectionBlockApplied !== "1") {
                        element.dataset.lsConnectionBlockApplied = "1";
                        element.dataset.lsConnectionPointerEvents = String(
                            element.style.pointerEvents || ""
                        );
                        element.dataset.lsConnectionOpacity = String(
                            element.style.opacity || ""
                        );
                        const previousTabIndex = element.getAttribute("tabindex");
                        element.dataset.lsConnectionHadTabIndex = (
                            previousTabIndex === null ? "0" : "1"
                        );
                        element.dataset.lsConnectionTabIndex = previousTabIndex || "";
                        if (element.getAttribute("aria-disabled") === null) {
                            element.dataset.lsConnectionAriaByUs = "1";
                        }
                    }
                    element.style.pointerEvents = "none";
                    element.style.opacity = "0.55";
                    element.setAttribute("tabindex", "-1");
                    element.setAttribute("aria-disabled", "true");
                    return;
                }
                if (element.dataset.lsConnectionBlockApplied === "1") {
                    element.style.pointerEvents = (
                        element.dataset.lsConnectionPointerEvents || ""
                    );
                    element.style.opacity = (
                        element.dataset.lsConnectionOpacity || ""
                    );
                    if (element.dataset.lsConnectionHadTabIndex === "1") {
                        element.setAttribute(
                            "tabindex",
                            element.dataset.lsConnectionTabIndex || ""
                        );
                    } else {
                        element.removeAttribute("tabindex");
                    }
                    delete element.dataset.lsConnectionBlockApplied;
                    delete element.dataset.lsConnectionPointerEvents;
                    delete element.dataset.lsConnectionOpacity;
                    delete element.dataset.lsConnectionHadTabIndex;
                    delete element.dataset.lsConnectionTabIndex;
                }
                if (element.dataset.lsConnectionAriaByUs === "1") {
                    element.removeAttribute("aria-disabled");
                    delete element.dataset.lsConnectionAriaByUs;
                }
            });
        }

        function applySunoConnectionStatus(data, options={}) {
            if (!data) { return null; }
            sunoConnectionLastStatus = data;

            const tokenSaved = Boolean(data.token_saved);
            const tokenInvalid = Boolean(data.token_invalid_at);
            const tokenInvalidCurrent = Boolean(data.token_invalid_current_process);
            const bridgeActive = Boolean(data.bridgeLivenessActive);
            bridgeLivenessActive = bridgeActive;
            const allowGrace = options.allowGrace !== false;
            const graceActive = (
                allowGrace
                && !bridgeActive
                && (Date.now() - sunoConnectionOpenedAt) < SUNO_CONNECTION_GRACE_MS
            );
            const authBlocked = !tokenSaved || (tokenInvalid && (!bridgeActive || tokenInvalidCurrent));
            setSunoAuthActionsBlocked(authBlocked);

            if (graceActive) {
                setSunoConnectionView(
                    "warn",
                    "Pārbauda Suno savienojumu…",
                    "Gaida LS Suno Token Bridge signālu pirms gala secinājuma.",
                    false
                );
                return { state: "checking", authBlocked };
            }

            if (tokenSaved && !tokenInvalid && bridgeActive) {
                setSunoConnectionView(
                    "ok",
                    "Suno savienojums ir gatavs",
                    "Suno tokens un Token Bridge ir gatavi darbam.",
                    false
                );
                return { state: "ready", authBlocked: false };
            }

            if (!bridgeActive && tokenSaved && !tokenInvalid) {
                setSunoConnectionView(
                    "warn",
                    "Token Bridge nav pieslēgts",
                    "Esošais Suno tokens vēl ir derīgs; darbības var turpināt, bet automātiska tokena atjaunošana nav pieejama.",
                    true
                );
                return { state: "bridge_offline_token_valid", authBlocked: false };
            }

            if (!bridgeActive && tokenInvalid) {
                setSunoConnectionView(
                    "warn",
                    "Suno savienojums jāatjauno",
                    "Saglabātais Suno tokens nav derīgs, un Token Bridge nav pieslēgts.",
                    true
                );
                return { state: "bridge_offline_token_invalid", authBlocked: true };
            }

            if (!bridgeActive && !tokenSaved) {
                setSunoConnectionView(
                    "warn",
                    "Suno savienojums nav gatavs",
                    "Suno tokens nav saglabāts, un Token Bridge nav pieslēgts.",
                    true
                );
                return { state: "bridge_offline_no_token", authBlocked: true };
            }

            if (bridgeActive && tokenInvalid && tokenInvalidCurrent) {
                setSunoConnectionView(
                    "warn",
                    "Suno autorizācija jāatjauno",
                    "Suno noraidīja autorizāciju šajā LS sesijā. Atjauno Suno pieslēgumu.",
                    false
                );
                return { state: "bridge_ready_token_invalid", authBlocked: true };
            }

            if (bridgeActive && tokenInvalid) {
                setSunoConnectionView(
                    "warn",
                    "Suno autorizācija tiks pārbaudīta",
                    "Token Bridge ir pieslēgts; nākamā Suno darbība pārbaudīs saglabāto autorizāciju.",
                    false
                );
                return { state: "bridge_ready_token_unverified", authBlocked: false };
            }

            setSunoConnectionView(
                "warn",
                "Gaida Suno autorizāciju",
                "Token Bridge ir pieslēgts, bet LS vēl nav saņēmis Suno tokenu.",
                false
            );
            return { state: "bridge_ready_no_token", authBlocked: true };
        }

        function localizeBridgeDiagnosis(data) {
            const code = String((data && data.diagnosis_code) || "");
            const byCode = {
                session_expired: {
                    summary: "Suno noraidīja saglabāto autorizāciju šajā LS sesijā.",
                    action: "Atjauno Suno pieslēgumu un izpildi vienu autorizētu pieprasījumu.",
                },
                session_unverified: {
                    summary: "Saglabātā Suno autorizācija pēc LS restarta vēl nav pārbaudīta.",
                    action: "Turpini ar nākamo Suno darbību; LS izmantos tās reālo API atbildi.",
                },
                extension_offline: {
                    summary: "Token Bridge paplašinājums nav savienots ar LS.",
                    action: "Pārlādē paplašinājumu chrome://extensions/.",
                },
                page_not_reporting: {
                    summary: "Paplašinājums ir savienots, bet nav saņemta aktuāla Suno lapas diagnostika.",
                    action: "Atver vai pārlādē Suno cilni un pagaidi dažas sekundes.",
                },
                page_bridge_missing: {
                    summary: "Suno lapas tilts nepabeidza ielādi.",
                    action: "Pārlādē Suno cilni. Ja problēma saglabājas, pārlādē paplašinājumu.",
                },
                fetch_hook_inactive: {
                    summary: "Suno aizvietoja fetch pārtvērēju; gaida automātisku atjaunošanu.",
                    action: "Pagaidi līdz divām sekundēm. Tiltam jāatjaunojas automātiski.",
                },
                waiting_for_api_request: {
                    summary: "Lapas tilts ir gatavs, bet Suno API pieprasījums vēl nav redzēts.",
                    action: "Atskaņo dziesmu vai atver Suno bibliotēku, lai izraisītu API pieprasījumu.",
                },
                authorization_missing: {
                    summary: "Suno API pieprasījums tika redzēts bez Authorization galvenes.",
                    action: "Pārbaudi, vai esi pieslēdzies Suno. Suno autorizācijas izmaiņām var būt vajadzīgs atjauninājums.",
                },
                relay_pending: {
                    summary: "Autorizācija ir atrasta, bet LS vēl nav saņēmis tokenu.",
                    action: "Pagaidi dažas sekundes. Ja nekas nemainās, pārlādē paplašinājumu.",
                },
                healthy: {
                    summary: "Visas Token Bridge pārbaudes ir izturētas.",
                    action: "Darbība nav nepieciešama.",
                },
            };
            return byCode[code] || {
                summary: String((data && data.diagnosis_summary) || "Gaida statusu…"),
                action: String((data && data.diagnosis_action) || "Gaidi nākamo diagnostikas atjauninājumu."),
            };
        }

        function renderBridgeDiagnostics(data) {
            if (!bridgeDiagnosticPanel || !bridgeDiagnosticText || !data) {
                return;
            }

            const relayCurrent = Boolean(
                data.bridge_last_token_at &&
                (
                    !data.page_instance_id ||
                    data.last_token_page_instance_id === data.page_instance_id
                )
            );
            const activeBridge = Object.prototype.hasOwnProperty.call(
                data,
                "bridgeLivenessActive"
            ) ? Boolean(data.bridgeLivenessActive) : false;
            const rows = [
                ["Lapas tilts", data.page_loaded ? "OK" : "Nav atrasts"],
                ["Fetch pārtvērējs", data.fetch_hook_active ? "Aktīvs" : "Neaktīvs"],
                ["Pašatjaunošanās", String(data.fetch_repair_count || 0)],
                ["Suno API pieprasījums", data.last_api_request_at ? "Redzēts" : "Nav redzēts"],
                ["Autorizācija", data.last_authorization_at ? "Atrasta" : "Nav atrasta"],
                ["Paplašinājuma pārsūtīšana", relayCurrent ? "OK" : "Gaida"],
                ["LS savienojums", activeBridge ? "OK" : "Bezsaistē"],
            ];
            if (data.last_fetch_repair_at) {
                rows.push(["Pēdējais labojums", data.last_fetch_repair_at]);
            }
            if (data.previous_worker_error) {
                rows.push(["Atkopta kļūda", data.previous_worker_error]);
            }

            const details = rows.map((item) => (
                String(item[0]).padEnd(20, " ") + " " + String(item[1])
            ));
            details.push("");
            const diagnosis = localizeBridgeDiagnosis(data);
            details.push("Diagnoze: " + diagnosis.summary);
            details.push("Darbība: " + diagnosis.action);

            bridgeDiagnosticText.textContent = details.join("\n");
            bridgeDiagnosticPanel.className = (
                "bridge-diagnostic " + (data.diagnosis_level || "warn")
            );
        }

        async function refreshBridgeDiagnostics(options={}) {
            try {
                const probeTimeoutMs = options.probeTimeoutMs === undefined
                    ? SUNO_CONNECTION_GRACE_MS
                    : Number(options.probeTimeoutMs);
                const liveness = await probeTokenBridgeLiveness(probeTimeoutMs);
                const response = await fetch(
                    "/suno-token-status?_=" + Date.now(),
                    { cache: "no-store" }
                );
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(data.error || "Neizdevās nolasīt diagnostiku");
                }
                data.bridgeLivenessActive = Boolean(liveness && liveness.active);
                data.bridgeLivenessExtensionVersion = (
                    liveness && liveness.extensionVersion || ""
                );
                renderBridgeDiagnostics(data);
                applySunoConnectionStatus(data, options);
                return data;
            } catch (error) {
                if (bridgeDiagnosticPanel && bridgeDiagnosticText) {
                    bridgeDiagnosticPanel.className = "bridge-diagnostic error";
                    bridgeDiagnosticText.textContent = (
                        "Diagnostika nav pieejama\n\nDarbība: pārlādē Importa lapu.\n" +
                        String(error && error.message || error || "Nezināma kļūda")
                    );
                }
                if (!sunoConnectionLastStatus) {
                    setSunoConnectionView(
                        "warn",
                        "Suno savienojuma pārbaude neizdevās",
                        "Imports nevar nolasīt Token Bridge statusu.",
                        false
                    );
                }
                return null;
            }
        }

        function sleepMs(ms) {
            return new Promise((resolve) => setTimeout(resolve, ms));
        }

        async function refreshInitialSunoConnection() {
            setSunoConnectionView(
                "warn",
                "Pārbauda Suno savienojumu…",
                "Pārbauda, vai LS Suno Token Bridge pašlaik ir ieslēgts.",
                false
            );
            return refreshBridgeDiagnostics({
                allowGrace: false,
                probeTimeoutMs: SUNO_CONNECTION_GRACE_MS,
            });
        }

        async function waitForFreshSunoToken(previousUpdatedAt) {
            const deadline = Date.now() + 120000;
            while (Date.now() < deadline) {
                const liveness = await probeTokenBridgeLiveness(1000);
                const response = await fetch(
                    "/suno-token-status?_=" + Date.now(),
                    { cache: "no-store" }
                );
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(
                        data.error || "Neizdevās nolasīt Suno tokena statusu"
                    );
                }

                data.bridgeLivenessActive = Boolean(liveness && liveness.active);
                data.bridgeLivenessExtensionVersion = (
                    liveness && liveness.extensionVersion || ""
                );
                renderBridgeDiagnostics(data);
                applySunoConnectionStatus(data, { allowGrace: false });

                if (
                    data.token_saved
                    && !data.token_invalid_at
                    && data.token_updated_at
                    && data.token_updated_at !== previousUpdatedAt
                ) {
                    return data;
                }

                const diagnosis = localizeBridgeDiagnosis(data);
                const bridgeText = [
                    diagnosis.summary || "Gaida LS Token Bridge.",
                    diagnosis.action || ""
                ].filter(Boolean).join(" ");
                setSunoLoginRenewStatus(bridgeText);
                await sleepMs(1000);
            }

            throw new Error(
                "Jauns tokens netika saņemts. Pārbaudi Token Bridge diagnostiku augstāk."
            );
        }

        async function renewSunoLoginAndWait() {
            if (renewSunoLoginBtn) {
                renewSunoLoginBtn.classList.add("working");
                renewSunoLoginBtn.setAttribute("aria-disabled", "true");
            }
            try {
                setSunoLoginRenewStatus(
                    "Atver Suno Create. Gaida jaunu Token Bridge autorizāciju…"
                );

                const response = await fetch(
                    "/start-suno-token-renewal",
                    { method: "POST" }
                );
                let data = {};
                try { data = await response.json(); } catch (parseError) { data = {}; }
                if (!response.ok || !data.ok) {
                    throw new Error(
                        data.error || "Neizdevās sākt Suno tokena atjaunošanu"
                    );
                }

                const freshData = await waitForFreshSunoToken(
                    data.previous_token_updated_at || ""
                );
                applySunoConnectionStatus(freshData, { allowGrace: false });
                setSunoLoginRenewStatus(
                    "Jaunā Suno autorizācija saglabāta. Pārlādē…",
                    "ok"
                );
                setTimeout(() => location.reload(), 700);
                return freshData;
            } catch (error) {
                if (renewSunoLoginBtn) {
                    renewSunoLoginBtn.classList.remove("working");
                    renewSunoLoginBtn.setAttribute("aria-disabled", "false");
                }
                throw error;
            }
        }

        async function waitForBridgeConnection() {
            const deadline = Date.now() + 300000;
            while (Date.now() < deadline) {
                const data = await refreshBridgeDiagnostics({
                    allowGrace: false,
                    probeTimeoutMs: 1000,
                });
                if (data && data.bridgeLivenessActive) {
                    return data;
                }
                setSunoLoginRenewStatus(
                    "Gaida LS Suno Token Bridge savienojumu. Pēc “Load unpacked” LS to pārbaudīs automātiski."
                );
                await sleepMs(1000);
            }
            throw new Error(
                "Token Bridge signāls netika saņemts. Pārbaudi, vai Chrome paplašinājums ir ielādēts un ieslēgts."
            );
        }

        async function copyTokenBridgeSetupNavigation(data) {
            const extensionsUrl = String(
                data.extensions_url || "chrome://extensions/"
            );
            let copied = false;
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    await navigator.clipboard.writeText(extensionsUrl);
                    copied = true;
                }
            } catch (error) {
                copied = false;
            }
            if (!copied) {
                try {
                    const copyField = document.createElement("textarea");
                    copyField.value = extensionsUrl;
                    copyField.setAttribute("readonly", "readonly");
                    copyField.style.position = "fixed";
                    copyField.style.opacity = "0";
                    document.body.appendChild(copyField);
                    copyField.select();
                    copied = document.execCommand("copy");
                    copyField.remove();
                } catch (error) {
                    copied = false;
                }
            }
            return copied
                ? "Token Bridge mape ir atvērta un chrome://extensions/ nokopēts. Adreses joslā spied Ctrl+V un Enter. "
                : "Token Bridge mape ir atvērta. Chrome adreses joslā ievadi chrome://extensions/. ";
        }

        async function runTokenBridgeRepair() {
            if (tokenBridgeRecoveryActive) { return; }
            tokenBridgeRecoveryActive = true;
            if (repairTokenBridgeBtn) {
                repairTokenBridgeBtn.disabled = true;
                repairTokenBridgeBtn.classList.add("working");
            }
            if (bridgeSetupBtn) {
                bridgeSetupBtn.disabled = true;
            }

            try {
                const response = await fetch(
                    "/open-token-bridge-setup",
                    { method: "POST" }
                );
                const data = await response.json();
                if (!response.ok || !data.ok) {
                    throw new Error(
                        data.error || "Neizdevās atvērt Token Bridge iestatīšanu"
                    );
                }

                const navigationInstruction = await copyTokenBridgeSetupNavigation(data);
                setSunoLoginRenewStatus(
                    navigationInstruction
                    + "Ieslēdz izstrādātāja režīmu, izvēlies “Load unpacked” un norādi mapi: "
                    + (data.folder || "")
                    + ". Pēc paplašinājuma ielādes vai pārlādes pārlādē Importa cilni; LS savienojumu pārbaudīs automātiski."
                );

                const bridgeData = await waitForBridgeConnection();
                if (bridgeData.token_invalid_at || !bridgeData.token_saved) {
                    setSunoLoginRenewStatus(
                        "Token Bridge ir pieslēgts. LS tagad atjauno Suno autorizāciju."
                    );
                    await renewSunoLoginAndWait();
                    return;
                }

                applySunoConnectionStatus(bridgeData, { allowGrace: false });
                setSunoLoginRenewStatus(
                    "Token Bridge ir pieslēgts. Suno savienojums ir gatavs.",
                    "ok"
                );
            } catch (error) {
                setSunoLoginRenewStatus(
                    error.message || "Token Bridge atjaunošana neizdevās",
                    "error"
                );
            } finally {
                tokenBridgeRecoveryActive = false;
                if (repairTokenBridgeBtn) {
                    repairTokenBridgeBtn.classList.remove("working");
                    if (!repairTokenBridgeBtn.hidden) {
                        repairTokenBridgeBtn.disabled = false;
                    }
                }
                if (bridgeSetupBtn) {
                    bridgeSetupBtn.disabled = false;
                }
            }
        }

        lsDownloaderRoot && lsDownloaderRoot.addEventListener("click", (event) => {
            if (!window.lsSunoAuthBlocked) { return; }
            const target = event.target && event.target.closest
                ? event.target.closest(SUNO_AUTH_ACTION_SELECTOR)
                : null;
            if (!target) { return; }
            event.preventDefault();
            if (event.stopImmediatePropagation) {
                event.stopImmediatePropagation();
            }
            target.setAttribute("aria-disabled", "true");
            setSunoLoginRenewStatus(
                "Suno autorizācija nav pieejama. Atjauno Token Bridge/Suno savienojumu un mēģini vēlreiz.",
                "error"
            );
        }, true);

        refreshInitialSunoConnection();
        window.setInterval(() => {
            if (!document.hidden) {
                refreshBridgeDiagnostics({
                    allowGrace: false,
                    probeTimeoutMs: 1000,
                });
            }
        }, 15000);

        if (renewSunoLoginBtn) {
            renewSunoLoginBtn.addEventListener("click", async (event) => {
                event.preventDefault();
                try {
                    await renewSunoLoginAndWait();
                } catch (error) {
                    setSunoLoginRenewStatus(
                        (error.message || "Tokena atjaunošana neizdevās") + " Ja Suno Create neatvērās, atver to manuāli.",
                        "error"
                    );
                }
            });
        }

        if (bridgeSetupBtn) {
            bridgeSetupBtn.addEventListener("click", runTokenBridgeRepair);
        }
        if (repairTokenBridgeBtn) {
            repairTokenBridgeBtn.addEventListener("click", runTokenBridgeRepair);
        }

        async function saveToken(token) {
            const body = new URLSearchParams();
            body.set("suno_api_token", token || "");
            const response = await fetch("/set-suno-api-token", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: body.toString()
            });
            const text = await response.text();
            if (!response.ok) {
                throw new Error(text || "Neizdevās saglabāt tokenu");
            }
            return text;
        }

        saveTokenBtn.addEventListener("click", async () => {
            try {
                setStatus("Saglabā tokenu…");
                const msg = await saveToken(tokenInput.value);
                setStatus(msg + ". Pārlādē lapu…", "ok");
                setTimeout(() => location.reload(), 600);
            } catch (error) {
                setStatus(error.message, "error");
            }
        });

        clearTokenBtn.addEventListener("click", async () => {
            try {
                tokenInput.value = "";
                const msg = await saveToken("");
                setStatus(msg + ". Pārlādē lapu…", "ok");
                setTimeout(() => location.reload(), 600);
            } catch (error) {
                setStatus(error.message, "error");
            }
        });
