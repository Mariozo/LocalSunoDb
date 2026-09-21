        const busyBackdrop = document.getElementById("busy-backdrop");
        const busyTitle = document.getElementById("busy-title");
        const busyText = document.getElementById("busy-text");
        const busyTip = document.getElementById("busy-tip");
        const busyBox = busyBackdrop
            ? busyBackdrop.querySelector(".busy-box")
            : null;
        let busyHoldUntil = 0;
        let busyHideDelayTimer = null;

        const tipOfTheDay = [
            "Zaļa Play poga nozīmē, ka šim ierakstam ir piesaistīti Stems.",
            "Search laukā vari meklēt arī pēc lokālā WAV faila nosaukuma vai mapes nosaukuma.",
            "Dzeltens īkšķis pie nosaukuma nozīmē, ka ieraksts ir Liked.",
            "[No title] joprojām ir klikšķināms — LS atver Suno ierakstu pēc Track ID.",
            "Klikšķis uz thumbnail atver lielāko Suno vāciņa attēlu.",
            "Style lauks ir rediģējams lokāli; Save saglabā izmaiņas LS datubāzē.",
            "Refresh DB / Sync var ilgt vairākas minūtes, jo tiek skenēti arī lokālie WAV.",
            "Ja Compare sleju šķiro Z–A, augšā nonāk ieraksti ar lokālo WAV.",
            "Rows iestatījums nosaka, cik rindu sākumā ielādēt, lai lapa paliek ātra."
        ];

        function getRandomTip() {
            const index = Math.floor(Math.random() * tipOfTheDay.length);
            return tipOfTheDay[index];
        }

        function showBusy(title, text) {
            if (!busyBackdrop) {
                return;
            }
            busyHoldUntil = 0;
            if (busyHideDelayTimer) {
                clearTimeout(busyHideDelayTimer);
                busyHideDelayTimer = null;
            }
            busyTitle.innerText = title || "Working...";
            busyText.innerText = text || "Please wait.";
            if (busyTip) {
                busyTip.innerHTML = "<strong>Tip:</strong> " + getRandomTip();
            }
            busyBackdrop.style.display = "flex";
        }

        function hideBusy(force=false) {
            if (!busyBackdrop) { return; }
            const remainingHold = busyHoldUntil - Date.now();
            if (!force && remainingHold > 0) {
                if (busyHideDelayTimer) {
                    clearTimeout(busyHideDelayTimer);
                }
                busyHideDelayTimer = setTimeout(() => {
                    hideBusy(true);
                }, remainingHold);
                return;
            }
            busyHoldUntil = 0;
            if (busyHideDelayTimer) {
                clearTimeout(busyHideDelayTimer);
                busyHideDelayTimer = null;
            }
            busyBackdrop.style.display = "none";
        }

        function cleanBusyTipText(value) {
            return String(value || "")
                .replace(/^(?:Dienas\s+padoms|Padoms|Tip):\s*/i, "")
                .trim();
        }

        function openBusyTipInElza() {
            const tip = cleanBusyTipText(
                busyTip ? busyTip.textContent : ""
            );
            if (!tip) { return; }
            hideBusy(true);

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
            elzaInput.setSelectionRange(
                elzaInput.value.length,
                elzaInput.value.length
            );
        }

        if (busyBox) {
            busyBox.addEventListener("mouseenter", () => {
                if (!busyBackdrop || busyBackdrop.style.display !== "flex") {
                    return;
                }
                busyHoldUntil = Date.now() + 12000;
                if (busyHideDelayTimer) {
                    clearTimeout(busyHideDelayTimer);
                    busyHideDelayTimer = setTimeout(() => {
                        hideBusy(true);
                    }, 12000);
                }
            });
        }

        if (busyTip) {
            busyTip.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();
                openBusyTipInElza();
            });
            busyTip.addEventListener("keydown", (event) => {
                if (event.key !== "Enter" && event.key !== " ") { return; }
                event.preventDefault();
                event.stopPropagation();
                openBusyTipInElza();
            });
        }