(() => {
    const toolsPopover = document.getElementById("ls-sidebar-tools-popover");
    if (!toolsPopover) {
        return;
    }

    let installButton = toolsPopover.querySelector("[data-ls-pwa-install='1']");
    if (!installButton) {
        installButton = document.createElement("button");
        installButton.type = "button";
        installButton.dataset.lsPwaInstall = "1";
        installButton.textContent = "Instalēt LS uzdevumjoslai…";
        toolsPopover.appendChild(installButton);

        installButton.addEventListener("click", async () => {
            if (installButton.disabled) {
                return;
            }
            installButton.disabled = true;
            const previousText = installButton.textContent;
            installButton.textContent = "Atver instalēšanas lapu…";
            try {
                const response = await fetch("/ls-tools/open-pwa-install", {
                    method: "POST",
                    cache: "no-store",
                });
                const payload = await response.json();
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "LS instalēšanas lapu neizdevās atvērt.");
                }
            } catch (error) {
                window.alert(String(error && error.message || "LS instalēšanas lapu neizdevās atvērt."));
            } finally {
                installButton.disabled = false;
                installButton.textContent = previousText;
            }
        });
    }

    let shortcutButton = toolsPopover.querySelector("[data-ls-launcher-shortcut='1']");
    if (!shortcutButton) {
        shortcutButton = document.createElement("button");
        shortcutButton.type = "button";
        shortcutButton.dataset.lsLauncherShortcut = "1";
        shortcutButton.textContent = "Izveidot LocalSunoDb saīsni…";
        toolsPopover.appendChild(shortcutButton);

        shortcutButton.addEventListener("click", async () => {
            if (shortcutButton.disabled) {
                return;
            }
            shortcutButton.disabled = true;
            const previousText = shortcutButton.textContent;
            shortcutButton.textContent = "Veido saīsni…";
            try {
                const response = await fetch("/ls-tools/create-launcher-shortcut", {
                    method: "POST",
                    cache: "no-store",
                });
                const payload = await response.json();
                if (payload && payload.requires_pwa_install) {
                    const openInstall = window.confirm(
                        (payload.error || "Vispirms jāinstalē LocalSunoDb kā Chrome Web App.") +
                        "\n\nAtvērt LS instalēšanas lapu tagad?"
                    );
                    if (openInstall) {
                        const installResponse = await fetch("/ls-tools/open-pwa-install", {
                            method: "POST",
                            cache: "no-store",
                        });
                        const installPayload = await installResponse.json();
                        if (!installResponse.ok || !installPayload.ok) {
                            throw new Error(installPayload.error || "LS instalēšanas lapu neizdevās atvērt.");
                        }
                    }
                    return;
                }
                if (!response.ok || !payload.ok) {
                    throw new Error(payload.error || "LocalSunoDb saīsni neizdevās izveidot.");
                }
                window.alert(payload.message || "LocalSunoDb saīsne ir izveidota.");
            } catch (error) {
                window.alert(String(error && error.message || "LocalSunoDb saīsni neizdevās izveidot."));
            } finally {
                shortcutButton.disabled = false;
                shortcutButton.textContent = previousText;
            }
        });
    }
})();
