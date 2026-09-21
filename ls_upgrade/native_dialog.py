"""Single native Windows Upgrade dialog.

UI-only module for the modular LS Upgrade subsystem. It communicates with the
running UpgradeCoordinator over HTTP and never imports the main LS app.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .bootstrapper import decode_payload


BG = "#22382E"
PANEL = "#2D493C"
PANEL_BORDER = "#5A7468"
TEXT = "#FFFFFF"
MUTED = "#C6D0CB"
PENDING_BG = "#14271F"
PENDING_BORDER = "#40594C"
PENDING_BADGE = "#22372D"
PENDING_BADGE_TEXT = "#789084"
PENDING_TEXT = "#D4DDD8"
ACTIVE_BG = "#2D493C"
ACTIVE_BORDER = "#79A78D"
ACTIVE_BADGE = "#237E4D"
DONE_BG = "#1D4B31"
DONE_BORDER = "#43B76E"
DONE_BADGE = "#0C8E43"
ERROR_BG = "#4A2828"
ERROR_BORDER = "#C85C5C"
ERROR_BADGE = "#9C3434"
SUCCESS_TEXT = "#E4F7EB"
ERROR_TEXT = "#FFE1E1"

DIALOG_TITLE = "LocalSunoDb atjaunināšana"
WINDOWS_DIALOG_MUTEX = r"Local\LocalSunoDbUpgradeDialog_v1"


def http_json(
    base_url: str,
    path: str,
    data: dict[str, Any] | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    if data is None:
        request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    else:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=encoded,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Cache-Control": "no-cache",
            },
        )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
            if isinstance(payload, dict) and payload.get("error"):
                raise RuntimeError(str(payload.get("error"))) from exc
        except RuntimeError:
            raise
        except Exception:
            pass
        raise RuntimeError(body.strip() or f"HTTP {exc.code}: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LocalSunoDb atgrieza nederīgus Upgrade datus")
    return payload


def _rounded_rectangle(canvas: Any, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> int:
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return int(canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs))


def _enable_rounded_window(window: Any) -> None:
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.c_void_p(int(window.winfo_id()))
        attribute = ctypes.c_int(33)  # DWMWA_WINDOW_CORNER_PREFERENCE
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            attribute,
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
    except Exception:
        pass



def _windows_find_dialog_windows() -> list[tuple[int, int]]:
    """Return visible top-level Upgrade windows as (hwnd, pid)."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[tuple[int, int]] = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @WNDENUMPROC
    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        if buffer.value != DIALOG_TITLE:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.append((int(hwnd), int(pid.value)))
        return True

    user32.EnumWindows(callback, 0)
    return found


def _windows_activate_existing_dialog() -> bool:
    if os.name != "nt":
        return False
    import ctypes

    user32 = ctypes.windll.user32
    windows = _windows_find_dialog_windows()
    if not windows:
        return False
    hwnd, _pid = windows[0]
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    return True


def _windows_acquire_dialog_mutex() -> tuple[Any | None, bool]:
    """Return (handle, acquired). acquired=False means another new dialog owns it."""
    if os.name != "nt":
        return None, True
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, False, WINDOWS_DIALOG_MUTEX)
    if not handle:
        return None, True
    already_exists = int(kernel32.GetLastError()) == 183  # ERROR_ALREADY_EXISTS
    if already_exists:
        kernel32.CloseHandle(handle)
        return None, False
    return handle, True


def _windows_release_dialog_mutex(handle: Any | None) -> None:
    if os.name == "nt" and handle:
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass


def run_dialog(payload: dict[str, Any]) -> int:
    import tkinter as tk
    from tkinter import font as tkfont

    base_url = str(payload.get("base_url") or "http://127.0.0.1:8765")
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), dict) else {}
    info_message = str(payload.get("info_message") or "").strip()
    informational = bool(info_message) and not candidate
    running_version = str(payload.get("running_version") or "")
    expected_version = str(candidate.get("new_version") or candidate.get("version") or "")
    signature = str(candidate.get("signature") or "")
    install_mode = str(candidate.get("install_mode") or "standard").strip().casefold()
    emergency_install = bool(candidate.get("emergency_install")) or install_mode == "emergency"
    raw_points = candidate.get("upgrade_points") if isinstance(candidate.get("upgrade_points"), list) else []
    upgrade_points = [str(item).strip() for item in raw_points if str(item).strip()][:8]

    root = tk.Tk()
    root.title(DIALOG_TITLE)
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    content_offset = 144 if not informational else 0
    width, height = 610, 576 + content_offset
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max(0, int((screen_width - width) / 2))
    y = max(0, int((screen_height - height) / 2))
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(width, height)
    root.maxsize(width, height)

    normal_font = tkfont.Font(family="Segoe UI", size=11)
    small_font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
    title_font = tkfont.Font(family="Segoe UI", size=18, weight="bold")
    version_font = tkfont.Font(family="Segoe UI", size=16, weight="bold")
    step_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")

    tk.Label(
        root,
        text="LocalSunoDb atjaunināšana",
        bg=BG,
        fg=TEXT,
        font=title_font,
        anchor="w",
    ).place(x=27, y=30, width=556, height=34)
    if informational:
        subtitle = info_message
    elif emergency_install:
        subtitle = "Atrasts ārkārtas labojums: versijas numurs nav tiešais nākamais, bet pakotnes bāze atbilst pašreizējai LS versijai."
    else:
        subtitle = "Mapē Downloads ir pieejama jaunāka LocalSunoDb versija."
    tk.Label(
        root,
        text=subtitle,
        bg=BG,
        fg=MUTED,
        font=normal_font,
        anchor="w",
        justify="left",
        wraplength=556,
    ).place(x=27, y=86, width=556, height=42)

    version_canvas = tk.Canvas(root, width=558, height=79, bg=BG, highlightthickness=0, bd=0)
    version_canvas.place(x=27, y=146)
    _rounded_rectangle(
        version_canvas, 1, 1, 557, 78, 12,
        fill=PANEL, outline=PANEL_BORDER, width=1,
    )
    version_canvas.create_text(16, 17, text="DARBOJAS", fill="#BFC9C4", font=small_font, anchor="w")
    version_canvas.create_text(16, 52, text=running_version or "—", fill=TEXT, font=version_font, anchor="w")
    version_canvas.create_text(279, 42, text="→", fill="#8DE2AF", font=version_font, anchor="center")
    version_canvas.create_text(
        542, 17,
        text="ĀRKĀRTAS LABOJUMS" if emergency_install else "JAUNĀKĀ PIEEJAMĀ",
        fill="#BFC9C4", font=small_font, anchor="e",
    )
    version_canvas.create_text(542, 52, text=expected_version or "—", fill=TEXT, font=version_font, anchor="e")

    if not informational:
        notes_canvas = tk.Canvas(root, width=558, height=126, bg=BG, highlightthickness=0, bd=0)
        notes_canvas.place(x=27, y=239)
        _rounded_rectangle(
            notes_canvas, 1, 1, 557, 125, 11,
            fill=PANEL, outline=PANEL_BORDER, width=1,
        )
        notes_canvas.create_text(
            16, 17, text="SVARĪGĀKIE UPGRADE PUNKTI", fill="#BFC9C4", font=small_font, anchor="w",
        )
        notes_text = tk.Text(
            root,
            bg=PANEL,
            fg="#E5ECE8",
            insertbackground=TEXT,
            selectbackground="#426553",
            selectforeground=TEXT,
            font=normal_font,
            wrap="word",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            cursor="arrow",
        )
        notes_scroll = tk.Scrollbar(root, orient="vertical", command=notes_text.yview)
        notes_text.configure(yscrollcommand=notes_scroll.set)
        notes_text.place(x=43, y=270, width=492, height=78)
        notes_scroll.place(x=541, y=270, width=18, height=78)
        visible_points = upgrade_points or ["Šai pakotnei nav pievienots svarīgāko izmaiņu apraksts."]
        notes_text.insert("1.0", "\n".join(f"• {point}" for point in visible_points))
        notes_text.configure(state="disabled")

    stage_styles = {
        "pending": (PENDING_BG, PENDING_BORDER, PENDING_BADGE, PENDING_BADGE_TEXT, PENDING_TEXT),
        "active": (ACTIVE_BG, ACTIVE_BORDER, ACTIVE_BADGE, TEXT, TEXT),
        "done": (DONE_BG, DONE_BORDER, DONE_BADGE, TEXT, TEXT),
        "error": (ERROR_BG, ERROR_BORDER, ERROR_BADGE, TEXT, ERROR_TEXT),
    }
    stage_widgets: dict[int, dict[str, Any]] = {}

    def make_stage(number: int, label: str, y_position: int) -> None:
        canvas = tk.Canvas(root, width=558, height=49, bg=BG, highlightthickness=0, bd=0)
        canvas.place(x=27, y=y_position)
        background = _rounded_rectangle(
            canvas, 1, 1, 557, 48, 11,
            fill=PENDING_BG, outline=PENDING_BORDER, width=1,
        )
        badge = canvas.create_oval(12, 10, 40, 38, fill=PENDING_BADGE, outline=PENDING_BORDER, width=1)
        number_text = canvas.create_text(26, 24, text=str(number), fill=PENDING_BADGE_TEXT, font=step_font, anchor="center")
        label_text = canvas.create_text(53, 24, text=label, fill=PENDING_TEXT, font=step_font, anchor="w")
        stage_widgets[number] = {
            "canvas": canvas,
            "background": background,
            "badge": badge,
            "number": number_text,
            "label": label_text,
        }

    make_stage(1, "Pakotne un manifests pārbaudīti", 239 + content_offset)
    make_stage(
        2,
        "Instalēt LocalSunoDb ārkārtas labojumu" if emergency_install else "Instalēt LocalSunoDb atjauninājumu",
        301 + content_offset,
    )
    make_stage(3, "Jaunā versija apstiprināta", 363 + content_offset)

    message_canvas = tk.Canvas(root, width=558, height=68, bg=BG, highlightthickness=0, bd=0)
    message_canvas.place(x=27, y=425 + content_offset)
    message_background = _rounded_rectangle(
        message_canvas, 1, 1, 557, 67, 10,
        fill=PANEL, outline=PANEL_BORDER, width=1,
    )
    message_text = message_canvas.create_text(
        16,
        13,
        text=(
            info_message
            if informational
            else (
                f"1. Pakotne un manifests ir pārbaudīti.\nĀrkārtas lēciens {running_version} → {expected_version}; instalācija tiks pilnībā reģistrēta."
                if emergency_install
                else "1. Pakotne un manifests ir pārbaudīti.\nNospied “Instalēt atjauninājumu”, lai turpinātu."
            )
        ),
        fill="#C9D2CE",
        font=normal_font,
        anchor="nw",
        width=520,
    )

    def set_stage(number: int, state_name: str, label: str | None = None) -> None:
        background, border, badge, badge_text, text_color = stage_styles[state_name]
        widget = stage_widgets[number]
        canvas = widget["canvas"]
        canvas.itemconfigure(widget["background"], fill=background, outline=border)
        canvas.itemconfigure(widget["badge"], fill=badge, outline=border)
        canvas.itemconfigure(widget["number"], fill=badge_text)
        canvas.itemconfigure(widget["label"], fill=text_color)
        if label is not None:
            canvas.itemconfigure(widget["label"], text=label)

    def set_message(value: str, mode: str = "normal") -> None:
        styles = {
            "normal": (PANEL, PANEL_BORDER, "#C9D2CE"),
            "success": (DONE_BG, DONE_BORDER, SUCCESS_TEXT),
            "error": (ERROR_BG, ERROR_BORDER, ERROR_TEXT),
        }
        fill, outline, foreground = styles[mode]
        message_canvas.itemconfigure(message_background, fill=fill, outline=outline)
        message_canvas.itemconfigure(message_text, text=str(value), fill=foreground)

    buttons: dict[str, dict[str, Any]] = {}
    button_y = 507 + content_offset

    def make_button(name: str, x_position: int, width_value: int, text: str, palette: tuple[str, str, str], command: Any) -> dict[str, Any]:
        canvas = tk.Canvas(
            root,
            width=width_value,
            height=40,
            bg=BG,
            highlightthickness=0,
            bd=0,
            takefocus=1,
            cursor="hand2",
        )
        canvas.place(x=x_position, y=button_y)
        item = _rounded_rectangle(
            canvas, 1, 1, width_value - 1, 39, 16,
            fill=palette[0], outline=palette[1], width=1,
        )
        label = canvas.create_text(width_value // 2, 20, text=text, fill=TEXT, font=normal_font, anchor="center")
        button = {
            "name": name,
            "canvas": canvas,
            "item": item,
            "label": label,
            "palette": palette,
            "command": command,
            "enabled": True,
            "x": x_position,
            "width": width_value,
        }

        def invoke(_event: Any = None) -> str:
            if button["enabled"]:
                button["command"]()
            return "break"

        def enter(_event: Any = None) -> None:
            if button["enabled"]:
                canvas.itemconfigure(item, fill=palette[2])

        def leave(_event: Any = None) -> None:
            if button["enabled"]:
                canvas.itemconfigure(item, fill=palette[0])

        for target in (canvas,):
            target.bind("<Button-1>", invoke)
            target.bind("<Return>", invoke)
            target.bind("<space>", invoke)
            target.bind("<Enter>", enter)
            target.bind("<Leave>", leave)
        return button

    def set_button_enabled(button: dict[str, Any], enabled: bool) -> None:
        button["enabled"] = bool(enabled)
        canvas = button["canvas"]
        palette = button["palette"]
        if enabled:
            canvas.configure(cursor="hand2")
            canvas.itemconfigure(button["item"], fill=palette[0], outline=palette[1])
            canvas.itemconfigure(button["label"], fill=TEXT)
        else:
            canvas.configure(cursor="arrow")
            canvas.itemconfigure(button["item"], fill="#31423A", outline="#495B52")
            canvas.itemconfigure(button["label"], fill="#8EA097")

    def set_button_text(button: dict[str, Any], value: str) -> None:
        button["canvas"].itemconfigure(button["label"], text=value)

    def set_button_visible(button: dict[str, Any], visible: bool) -> None:
        if visible:
            button["canvas"].place(x=button["x"], y=button_y)
        else:
            button["canvas"].place_forget()

    def move_button(button: dict[str, Any], x_position: int) -> None:
        button["x"] = x_position
        button["canvas"].place(x=x_position, y=button_y)

    state = {"busy": False, "completed": False, "closed": False, "transaction_id": ""}

    def close_dialog() -> None:
        """Always allow the native window to close.

        Before installation this is a normal candidate rejection. During an
        active transaction it closes only the UI; the coordinator/bootstrapper
        continues safely in the background and remains recoverable.
        """
        if state["closed"]:
            return
        if not state["busy"] and not state["completed"] and signature:
            try:
                http_json(base_url, "/ls-upgrade/reject", {"signature": signature}, timeout=1.5)
            except Exception:
                pass
        state["closed"] = True
        try:
            root.destroy()
        except Exception:
            pass

    def post_ui(callback: Any, *args: Any) -> None:
        if state["closed"]:
            return
        try:
            root.after(0, callback, *args)
        except Exception:
            pass

    def show_success(version: str) -> None:
        if state["closed"]:
            return
        state["busy"] = False
        state["completed"] = True

        # Final-state contract: after a verified Upgrade the transient 1/2/3
        # progress rows disappear and their space becomes the change log.
        for widget in stage_widgets.values():
            widget["canvas"].place_forget()

        notes_canvas.configure(height=311)
        notes_canvas.delete("all")
        _rounded_rectangle(
            notes_canvas, 1, 1, 557, 310, 11,
            fill=PANEL, outline=PANEL_BORDER, width=1,
        )
        notes_canvas.create_text(
            16, 23, text="Izmaiņu žurnāls", fill="#E5ECE8", font=normal_font, anchor="w",
        )
        notes_text.place(x=43, y=270, width=492, height=257)
        notes_scroll.place(x=541, y=270, width=18, height=257)

        set_message(
            f"LocalSunoDb {version or expected_version} ir veiksmīgi palaists.\nEsošais LS Chrome app logs atjaunosies automātiski.",
            "success",
        )
        set_button_visible(buttons["install"], False)
        set_button_visible(buttons["emergency"], False)
        set_button_visible(buttons["close"], True)
        move_button(buttons["close"], 501)
        set_button_text(buttons["close"], "OK")
        set_button_enabled(buttons["close"], True)
        buttons["close"]["canvas"].focus_set()

    def show_error(error_text: str) -> None:
        if state["closed"]:
            return
        state["busy"] = False
        set_stage(2, "error", "Atjaunināšana neizdevās")
        set_stage(3, "pending", "Jaunā versija nav apstiprināta")
        set_message(error_text or "Upgrade neizdevās; iepriekšējā versija tika atjaunota.", "error")
        set_button_visible(buttons["install"], False)
        set_button_visible(buttons["emergency"], False)
        move_button(buttons["close"], 501)
        set_button_text(buttons["close"], "Aizvērt")
        set_button_enabled(buttons["close"], True)
        buttons["close"]["canvas"].focus_set()

    def poll_status() -> None:
        connection_lost = False
        # Bootstrapper has bounded stop/READY/HTTP/rollback waits. The UI must be
        # bounded as well so it can never remain on “Pārbauda…” forever when both
        # the new and restored servers are unreachable.
        deadline = time.monotonic() + 150.0
        while not state["closed"] and time.monotonic() < deadline:
            try:
                transaction_id = str(state.get("transaction_id") or "")
                status_path = "/ls-upgrade/status"
                if transaction_id:
                    status_path += "?transaction_id=" + urllib.parse.quote(transaction_id)
                current = http_json(base_url, status_path, timeout=1.5)
                current_state = str(current.get("state") or "")
                if current_state in {"preparing", "installing", "staged", "committing", "restarting"}:
                    post_ui(set_stage, 2, "active", "Instalē LocalSunoDb atjauninājumu…")
                    post_ui(set_message, "2. Tiek instalēta pārbaudītā pakotne un pārstartēts LS.\nUpgrade logs paliek atvērts, kamēr instalēšana turpinās.")
                elif current_state == "verifying":
                    post_ui(set_stage, 2, "done", "LocalSunoDb atjaunināts")
                    post_ui(set_stage, 3, "active", "Pārbauda jaunās versijas startu…")
                    post_ui(set_message, "3. Jaunā LocalSunoDb versija ir uzinstalēta.\nTiek pārbaudīta tās palaišana un versijas identitāte.")
                elif current_state == "completed":
                    version = str(current.get("expected_version") or expected_version)
                    post_ui(show_success, version)
                    return
                elif current_state in {"failed", "rolled_back"}:
                    error = str(current.get("error") or "Upgrade neizdevās; iepriekšējā versija tika atjaunota.")
                    post_ui(show_error, error)
                    return
                connection_lost = False
            except Exception:
                # This is expected while the old server stops and the new server starts.
                if not connection_lost:
                    connection_lost = True
                    post_ui(set_stage, 2, "active", "Pabeidz LocalSunoDb atjaunināšanu…")
                    post_ui(set_message, "2. Faili ir instalēti. LocalSunoDb tiek pārstartēts.\nUpgrade logs paliek atvērts, kamēr pārstartēšana turpinās.")
            time.sleep(0.6)
        if not state["closed"]:
            post_ui(
                show_error,
                "Upgrade statusu neizdevās apstiprināt noteiktajā laikā. "
                "Instalēšana vairs netiek gaidīta bezgalīgi; pārbaudi, vai LocalSunoDb darbojas, un apskati Upgrade žurnālu.",
            )

    def install_worker(requested_mode: str) -> None:
        try:
            result = http_json(
                base_url,
                "/install-ls-update",
                {
                    "source_name": candidate.get("source_name") or candidate.get("zip_name") or "",
                    "source_sha256": candidate.get("source_sha256") or "",
                    "manifest_sha256": candidate.get("manifest_sha256") or "",
                    "signature": signature,
                    "install_mode": requested_mode,
                },
                # install endpoint performs staging + isolated source preflight
                # before any downtime; allow the full 30s probe budget plus disk I/O.
                timeout=60.0,
            )
            if not result.get("ok"):
                raise RuntimeError(str(result.get("error") or "Upgrade instalēšanu neizdevās sākt"))
            state["transaction_id"] = str(result.get("transaction_id") or "")
            post_ui(set_stage, 2, "active", "Instalē LocalSunoDb atjauninājumu…")
            threading.Thread(target=poll_status, name="ls-upgrade-dialog-status", daemon=True).start()
        except Exception as exc:
            post_ui(show_error, str(exc))

    def start_install(requested_mode: str) -> None:
        if state["busy"] or state["completed"]:
            return
        state["busy"] = True
        set_button_visible(buttons["close"], False)
        set_button_enabled(buttons["install"], False)
        set_button_enabled(buttons["emergency"], False)
        if requested_mode == "emergency":
            set_button_text(buttons["emergency"], "Pārbauda…")
        else:
            set_button_text(buttons["install"], "Pārbauda…")
        set_stage(1, "done", "Pakotne un manifests pārbaudīti")
        set_stage(
            2,
            "active",
            "Instalē ārkārtas labojumu un pārstartē LS…" if requested_mode == "emergency" else "Instalē LocalSunoDb atjauninājumu…",
        )
        set_stage(3, "pending", "Jaunā versija apstiprināta")
        set_message(
            "2. Tiek instalēts pārbaudītais ārkārtas labojums un pārstartēts LS.\nUpgrade logs paliek atvērts, kamēr instalēšana turpinās."
            if requested_mode == "emergency"
            else "2. Tiek instalēta pārbaudītā pakotne un pārstartēts LS.\nUpgrade logs paliek atvērts, kamēr instalēšana turpinās."
        )
        threading.Thread(
            target=install_worker,
            args=(requested_mode,),
            name="ls-upgrade-dialog-install",
            daemon=True,
        ).start()

    buttons["close"] = make_button(
        "close", 322, 82, "Aizvērt", ("#405249", "#667A70", "#4A5F54"), close_dialog,
    )
    buttons["install"] = make_button(
        "install", 412, 173, "Instalēt atjauninājumu", ("#0C8E43", "#29B861", "#10A34E"), lambda: start_install("standard"),
    )
    buttons["emergency"] = make_button(
        "emergency", 349, 234, "Instalēt ārkārtas labojumu", ("#8A5A12", "#D4A04A", "#A86F18"), lambda: start_install("emergency"),
    )

    root.protocol("WM_DELETE_WINDOW", close_dialog)
    root.bind("<Escape>", lambda _event: close_dialog())
    if informational:
        set_stage(1, "done", "Downloads mape pārbaudīta")
        set_stage(2, "pending", "Jaunāka versija nav atrasta")
        set_stage(3, "pending", "Atjaunināšana nav nepieciešama")
        set_button_visible(buttons["install"], False)
        set_button_visible(buttons["emergency"], False)
        move_button(buttons["close"], 501)
    elif emergency_install:
        set_stage(1, "done", "Pakotne un manifests pārbaudīti")
        set_stage(2, "pending", "Instalēt LocalSunoDb ārkārtas labojumu")
        set_stage(3, "pending", "Jaunā versija apstiprināta")
        set_button_visible(buttons["install"], False)
        move_button(buttons["close"], 259)
    else:
        set_stage(1, "done", "Pakotne un manifests pārbaudīti")
        set_stage(2, "pending", "Instalēt LocalSunoDb atjauninājumu")
        set_stage(3, "pending", "Jaunā versija apstiprināta")
        set_button_visible(buttons["emergency"], False)
    _enable_rounded_window(root)

    # One initial foreground request only. No periodic focus/topmost pulse is used.
    root.after(80, root.lift)
    root.after(100, root.focus_force)
    root.after(120, lambda: buttons[
        "close" if informational else ("emergency" if emergency_install else "install")
    ]["canvas"].focus_set())
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args(argv)

    mutex_handle, acquired = _windows_acquire_dialog_mutex()
    if not acquired:
        _windows_activate_existing_dialog()
        return 0
    try:
        return run_dialog(decode_payload(args.payload))
    finally:
        _windows_release_dialog_mutex(mutex_handle)


if __name__ == "__main__":
    raise SystemExit(main())
