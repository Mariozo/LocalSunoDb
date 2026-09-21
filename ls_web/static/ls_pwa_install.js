(() => {
    let deferredPrompt = null;
    const dedicatedButton = document.getElementById("ls-pwa-install-button");
    const dedicatedStatus = document.getElementById("ls-pwa-install-status");

    function setStatus(text) {
        if (dedicatedStatus) dedicatedStatus.textContent = text;
    }

    function setReady() {
        if (!dedicatedButton) return;
        dedicatedButton.disabled = false;
        dedicatedButton.textContent = "Instalēt LocalSunoDb";
        setStatus("Chrome ir gatavs instalēt LocalSunoDb.");
    }

    function wait(ms) {
        return new Promise((resolve) => window.setTimeout(resolve, ms));
    }

    async function refreshLsShortcutsAfterInstall() {
        // Chrome may emit appinstalled just before its Windows .lnk is visible.
        // Retry briefly so the LS launcher receives the real PWA AppUserModelID.
        for (let attempt = 0; attempt < 10; attempt += 1) {
            try {
                const response = await fetch("/ls-tools/create-launcher-shortcut", {
                    method: "POST",
                    cache: "no-store",
                });
                const payload = await response.json();
                if (response.ok && payload && payload.ok) {
                    return true;
                }
                if (!payload || !payload.requires_pwa_install) {
                    return false;
                }
            } catch (_) {}
            await wait(500);
        }
        return false;
    }

    async function promptInstall() {
        if (!deferredPrompt) {
            setStatus("Chrome vēl nav sagatavojis instalēšanas dialogu. Pagaidi dažas sekundes.");
            return;
        }
        dedicatedButton.disabled = true;
        dedicatedButton.textContent = "Atver instalēšanas dialogu…";
        deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice;
        deferredPrompt = null;
        if (choice && choice.outcome === "accepted") {
            dedicatedButton.textContent = "Chrome pabeidz instalēšanu…";
            setStatus("Instalēšana apstiprināta. Gaidām Chrome pabeigšanu.");
        } else {
            dedicatedButton.disabled = false;
            dedicatedButton.textContent = "Instalēt LocalSunoDb";
            setStatus("Instalēšana tika atcelta. Vari mēģināt vēlreiz.");
        }
    }

    if (dedicatedButton) {
        dedicatedButton.addEventListener("click", promptInstall);
    }

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/ls-pwa-sw.js")
            .then(() => navigator.serviceWorker.ready)
            .then(() => {
                if (dedicatedButton && !deferredPrompt) {
                    setStatus("LocalSunoDb instalācijas serviss ir gatavs. Gaidām Chrome instalēšanas piedāvājumu.");
                }
            })
            .catch((error) => {
                if (dedicatedButton) {
                    setStatus("Chrome instalācijas servisu neizdevās sagatavot: " + String(error && error.message || error));
                }
            });
    } else if (dedicatedButton) {
        setStatus("Šis pārlūks neatbalsta nepieciešamo Web App instalācijas servisu.");
    }

    window.addEventListener("beforeinstallprompt", (event) => {
        event.preventDefault();
        deferredPrompt = event;
        setReady();
    });

    window.addEventListener("appinstalled", async () => {
        deferredPrompt = null;
        const shortcutsReady = await refreshLsShortcutsAfterInstall();
        if (dedicatedButton) {
            dedicatedButton.disabled = true;
            dedicatedButton.textContent = "LocalSunoDb ir instalēts";
            setStatus(
                shortcutsReady
                    ? "Gatavs. LS saīsnes saņēma Chrome Web App identitāti; šo cilni vari aizvērt."
                    : "LocalSunoDb ir instalēts. Ja saīsne vēl nav atjaunota, Rīki izvēlnē vienreiz nospied “Izveidot LocalSunoDb saīsni…”."
            );
        }
    });

    if (dedicatedButton) {
        window.setTimeout(() => {
            if (!deferredPrompt && dedicatedButton.disabled) {
                setStatus("Chrome vēl nepiedāvā automātisko instalēšanas dialogu. Ja poga neaktivizējas, Chrome ⋮ izvēlnē izvēlies “Instalēt lapu kā lietotni…” vai pārlādē šo lapu ar Ctrl+F5.");
                dedicatedButton.textContent = "Gaida Chrome instalēšanu…";
            }
        }, 5000);
    }
})();
