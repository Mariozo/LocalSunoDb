        const refreshTips = [
            "Padoms: ja parādās 429, pagaidi 5–10 minūtes un turpini ar limitu 10.",
            "Padoms: metadatu atjaunošana raksta tikai tukšos laukus — esošie dati netiek pārrakstīti.",
            "Padoms: pēc katras lielākas partijas vari palaist verify_suno_meta_updates_v1.py.",
            "Padoms: raw_json nozīmē, ka konkrētais ieraksts jau ir pārbaudīts pret Suno API.",
            "Padoms: ja token kļūst nederīgs, atver suno.com — Token Bridge to nosūtīs LS vēlreiz."
        ];

        const downloaderDailyTips = [
            "Dienas padoms: ja Suno API sāk atgriezt 429, pagaidi 5–10 minūtes un turpini ar mazāku limitu.",
            "Dienas padoms: dziesmu saraksta atjaunošana ir priekšskatījums — tā pati par sevi DB nemaina.",
            "Dienas padoms: Token Bridge jābūt tajā pašā Chrome profilā, kurā esi pieslēdzies Suno.",
            "Dienas padoms: ja tokena statuss rāda, ka tokens saglabāts, Token Bridge profils un Suno pieslēgums sakrīt.",
            "Dienas padoms: DB metadatu pārbaude atrod trūkstošos laukus un pirms rakstīšanas rāda atlasāmu sarakstu.",
            "Dienas padoms: automātiskais metadatu režīms pirms rakstīšanas izveido vienu DB rezerves kopiju.",
            "Dienas padoms: WAV importu sāc no LS Suno bibliotēkas, izvēloties vienu dziesmu.",
            "Dienas padoms: Statuss / žurnāls rāda pēdējo darbību, bet uzlecošais lodziņš rāda sākumu un padomu."
        ];

        function getDownloaderDailyTip() {
            const index = Math.floor(Math.random() * downloaderDailyTips.length);
            return downloaderDailyTips[index] || "Dienas padoms: LS rāda darbības sākumu pirms gaida ārējo atbildi.";
        }

        function hideDownloaderTipPopup() {
            if (downloaderTipTimer) {
                clearTimeout(downloaderTipTimer);
                downloaderTipTimer = null;
            }
            if (!downloaderTipToast) { return; }
            downloaderTipToast.classList.remove("show");
            downloaderTipToast.setAttribute("aria-hidden", "true");
        }

        function scheduleDownloaderTipHide(delayMs=4200) {
            if (downloaderTipTimer) {
                clearTimeout(downloaderTipTimer);
            }
            downloaderTipTimer = setTimeout(() => {
                hideDownloaderTipPopup();
            }, Math.max(0, Number(delayMs) || 0));
        }

        function cleanWaitingTipText(value) {
            return String(value || "")
                .replace(/^(?:Dienas\s+padoms|Padoms|Tip):\s*/i, "")
                .trim();
        }

        function openDownloaderTipInElza(
            tipValue=downloaderTipPromptText,
            sourcePanel="toast"
        ) {
            const tip = cleanWaitingTipText(tipValue);
            if (!tip) { return; }
            if (sourcePanel === "refresh") {
                hideRefreshWait(true);
            } else {
                hideDownloaderTipPopup();
            }
            applyDownloaderElzaCollapsed(false, true);

            const elzaInput = document.getElementById("ls-elza-input");
            const elzaOpenButton = document.getElementById("ls-elza-open-btn");
            if (elzaOpenButton) {
                elzaOpenButton.click();
            }
            if (!elzaInput) { return; }

            const question = "Paskaidro plašāk šo padomu: " + tip;
            const currentDraft = String(elzaInput.value || "").trim();
            elzaInput.value = currentDraft
                ? currentDraft + "\n\n" + question
                : question;
            elzaInput.dispatchEvent(new Event("input", { bubbles: true }));
            elzaInput.focus();
            elzaInput.setSelectionRange(elzaInput.value.length, elzaInput.value.length);
        }

        function showDownloaderTipPopup(actionLabel="Importa darbība", detail="") {
            if (!downloaderTipToast || !downloaderTipTitle || !downloaderTipText) { return; }
            downloaderTipTitle.innerText = "Notiek: " + (actionLabel || "Importa darbība");
            const tip = detail || getDownloaderDailyTip();
            downloaderTipPromptText = String(tip).replace(/^Dienas padoms:\s*/i, "").trim();
            downloaderTipText.innerHTML = "<strong>Padoms:</strong> " + escHtml(downloaderTipPromptText);
            downloaderTipToast.classList.add("show");
            downloaderTipToast.setAttribute("aria-hidden", "false");
            scheduleDownloaderTipHide(4200);
        }

        if (downloaderTipToast) {
            downloaderTipToast.addEventListener("mouseenter", () => {
                if (downloaderTipToast.classList.contains("show")) {
                    scheduleDownloaderTipHide(12000);
                }
            });
        }

        if (downloaderTipText) {
            downloaderTipText.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                openDownloaderTipInElza();
            });
            downloaderTipText.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") { return; }
                event.preventDefault();
                event.stopPropagation();
                openDownloaderTipInElza();
            });
        }

        function showRefreshWait(text, totalCount=0) {
            refreshWaitHoldUntil = 0;
            if (refreshWaitHideDelayTimer) {
                clearTimeout(refreshWaitHideDelayTimer);
                refreshWaitHideDelayTimer = null;
            }
            if (refreshWaitText && text) {
                refreshWaitText.innerHTML = text;
            }
            let remaining = parseInt(totalCount || 0, 10) || 0;
            if (refreshWaitCounter) {
                refreshWaitCounter.innerText = remaining > 0
                    ? "LS atjauno " + remaining + " ierakstus..."
                    : "LS atjauno metadatus…";
            }
            if (refreshWaitTip) {
                const tip = refreshTips[Math.floor(Math.random() * refreshTips.length)];
                refreshWaitTip.innerText = tip;
            }
            if (refreshWaitTimer) {
                clearInterval(refreshWaitTimer);
                refreshWaitTimer = null;
            }
            if (remaining > 0) {
                refreshWaitTimer = setInterval(() => {
                    remaining = Math.max(0, remaining - 1);
                    if (refreshWaitCounter) {
                        refreshWaitCounter.innerText = remaining > 0
                            ? "LS atjauno " + remaining + " ierakstus..."
                            : "LS gaida Suno API atbildi…";
                    }
                }, 1250);
            }
            if (refreshWait) {
                refreshWait.style.display = "";
                refreshWait.classList.add("show");
                refreshWait.setAttribute("aria-hidden", "false");
            }
        }

        function hideRefreshWait(force=false) {
            if (refreshWaitTimer) {
                clearInterval(refreshWaitTimer);
                refreshWaitTimer = null;
            }
            const remainingHold = refreshWaitHoldUntil - Date.now();
            if (!force && remainingHold > 0) {
                if (refreshWaitHideDelayTimer) {
                    clearTimeout(refreshWaitHideDelayTimer);
                }
                refreshWaitHideDelayTimer = setTimeout(() => {
                    hideRefreshWait(true);
                }, remainingHold);
                return;
            }
            refreshWaitHoldUntil = 0;
            if (refreshWaitHideDelayTimer) {
                clearTimeout(refreshWaitHideDelayTimer);
                refreshWaitHideDelayTimer = null;
            }
            if (refreshWait) {
                refreshWait.classList.remove("show");
                refreshWait.setAttribute("aria-hidden", "true");
                refreshWait.style.display = "none";
            }
        }

        if (refreshWait) {
            refreshWait.addEventListener("mouseenter", () => {
                if (!refreshWait.classList.contains("show")) { return; }
                refreshWaitHoldUntil = Date.now() + 12000;
                if (refreshWaitHideDelayTimer) {
                    clearTimeout(refreshWaitHideDelayTimer);
                    refreshWaitHideDelayTimer = setTimeout(() => {
                        hideRefreshWait(true);
                    }, 12000);
                }
            });
        }

        if (refreshWaitTip) {
            const openRefreshTipInElza = (event) => {
                event.preventDefault();
                event.stopPropagation();
                openDownloaderTipInElza(refreshWaitTip.textContent, "refresh");
            };
            refreshWaitTip.addEventListener("click", openRefreshTipInElza);
            refreshWaitTip.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") { return; }
                openRefreshTipInElza(event);
            });
        }

        function forceCloseDownloaderWorkingPopup() {
            if (refreshWaitTimer) {
                clearInterval(refreshWaitTimer);
                refreshWaitTimer = null;
            }
            refreshWaitHoldUntil = 0;
            if (refreshWaitHideDelayTimer) {
                clearTimeout(refreshWaitHideDelayTimer);
                refreshWaitHideDelayTimer = null;
            }
            document.querySelectorAll("#ls-refresh-wait, .ls-refresh-wait, #busy-backdrop, .busy-backdrop").forEach((node) => {
                node.classList.remove("show");
                node.setAttribute("aria-hidden", "true");
                node.style.display = "none";
            });
            const active = document.activeElement;
            if (active && active.blur) {
                try { active.blur(); } catch (error) {}
            }
        }

