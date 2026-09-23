import ctypes
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path, PureWindowsPath

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ls_core.runtime import (
    APP_VERSION,
    APP_DIR,
    APP_ENTRYPOINT_PATH,
    HOST,
    HOST_ROOT,
    PORT,
    LS_VERSION_REGISTRY_PATH,
)


LS_SHORTCUT_FILENAME = "LocalSunoDb.lnk"
LS_LEGACY_LAUNCHER_FILENAME = "LocalSunoDbLauncher.cmd"
LS_CHROME_APP_LAUNCH_FLAG = "--launch-chrome-app"  # legacy alias
LS_BROWSER_TAB_LAUNCH_FLAG = "--launch-browser-tab"
LS_BACKEND_ONLY_FLAG = "--start-backend-only"
LS_BACKEND_SUPERVISOR_FLAG = "--backend-supervisor"
LS_BACKEND_AUTOSTART_INSTALL_FLAG = "--install-backend-autostart"
LS_BACKEND_RESTART_FLAG = "--restart-backend"
LS_BACKEND_RESTART_QUIET_FLAG = "--quiet-restart"
LS_BACKEND_RESTART_GUARD_PATH = Path(HOST_ROOT) / "Temp" / "ls_backend_restart.guard"
LS_BACKEND_RUN_VALUE_NAME = "LocalSunoDbBackend"
LS_BROWSER_MANAGED_FLAG = "--ls-browser-managed"
LS_APP_URL = f"http://{HOST}:{PORT}/"
LS_BACKEND_STATUS_URL = f"http://{HOST}:{PORT}/app-version"
LS_ICON_PATH = APP_DIR / "ls_web" / "static" / "LS.ico"
LS_APP_USER_MODEL_ID = "Mariozo.LocalSunoDb"
LS_CHROME_BASE_APP_ID = "Chrome"
LS_CHROME_DEFAULT_PROFILE = "Default"
LS_WM_CLOSE = 0x0010
LS_PWA_MANIFEST_ID = "/localsunodb"
LS_PWA_START_PATH = "/ls-pwa-start"



def _powershell_single_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _background_python_executable():
    executable = Path(sys.executable).resolve()
    if os.name == "nt" and executable.name.casefold() == "python.exe":
        candidate = executable.with_name("pythonw.exe")
        if candidate.is_file():
            return candidate
    return executable


def set_current_process_localsunodb_app_id():
    """Give the invisible launcher process the same explicit taskbar identity as the LS window."""
    if os.name != "nt":
        return False
    try:
        return int(ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(LS_APP_USER_MODEL_ID)) == 0
    except Exception:
        return False


def _notify_shell_shortcut_changed(shortcut_path):
    if os.name != "nt":
        return
    try:
        # Refresh this pinned .lnk, then invalidate shell association/icon caches.
        ctypes.windll.shell32.SHChangeNotify(
            0x00002000, 0x0005, ctypes.c_wchar_p(str(Path(shortcut_path))), None
        )  # SHCNE_UPDATEITEM + SHCNF_PATHW
        ctypes.windll.shell32.SHChangeNotify(
            0x08000000, 0x0000, None, None
        )  # SHCNE_ASSOCCHANGED + SHCNF_IDLIST
    except Exception:
        pass


def _hidden_process_kwargs():
    if os.name != "nt":
        return {"start_new_session": True}
    creationflags = 0
    creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
    creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    return {
        "creationflags": creationflags,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }


def build_localsunodb_window_identity(
    *,
    python_executable=None,
    launcher_path=None,
    icon_path=None,
):
    python_executable = Path(python_executable or _background_python_executable()).resolve()
    launcher_path = Path(launcher_path or Path(__file__).resolve()).resolve()
    icon_path = Path(icon_path or LS_ICON_PATH).resolve()
    relaunch_command = subprocess.list2cmdline([
        str(python_executable),
        str(launcher_path),
        LS_CHROME_APP_LAUNCH_FLAG,
    ])
    return {
        "app_id": LS_APP_USER_MODEL_ID,
        "relaunch_command": relaunch_command,
        "display_name": "LocalSunoDb",
        "icon_resource": str(icon_path) + ",0",
    }


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid_from_text(text):
    guid = _GUID()
    result = ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(str(text)), ctypes.byref(guid))
    if int(result) != 0:
        raise OSError(f"CLSIDFromString failed: 0x{int(result) & 0xffffffff:08x}")
    return guid


def _property_key_type():
    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_uint32)]

    return PROPERTYKEY


def _set_property_store_strings(store_ptr, properties):
    if not store_ptr:
        return False
    PROPERTYKEY = _property_key_type()
    fmtid = _guid_from_text("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}")
    vtable = ctypes.cast(store_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    set_value = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_void_p,
        ctypes.POINTER(PROPERTYKEY),
        ctypes.c_void_p,
    )(vtable[6])
    commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[7])
    propvariant_clear = ctypes.windll.ole32.PropVariantClear
    init_from_string = ctypes.windll.propsys.InitPropVariantFromString
    for pid, value in properties.items():
        key = PROPERTYKEY(fmtid, int(pid))
        variant = ctypes.create_string_buffer(24)
        hr = init_from_string(ctypes.c_wchar_p(str(value)), ctypes.byref(variant))
        if int(hr) != 0:
            return False
        try:
            hr = set_value(store_ptr, ctypes.byref(key), ctypes.byref(variant))
            if int(hr) != 0:
                return False
        finally:
            propvariant_clear(ctypes.byref(variant))
    return int(commit(store_ptr)) == 0


def _release_property_store(store_ptr):
    if not store_ptr:
        return
    vtable = ctypes.cast(store_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
    release(store_ptr)


def _write_window_string_properties(hwnd, properties):
    if os.name != "nt" or not hwnd:
        return False
    store = ctypes.c_void_p()
    iid = _guid_from_text("{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}")  # IID_IPropertyStore
    shell32 = ctypes.windll.shell32
    hr = shell32.SHGetPropertyStoreForWindow(ctypes.c_void_p(int(hwnd)), ctypes.byref(iid), ctypes.byref(store))
    if int(hr) != 0 or not store.value:
        return False
    try:
        return _set_property_store_strings(store, properties)
    finally:
        _release_property_store(store)


def _release_com_interface(interface_ptr):
    if not interface_ptr:
        return
    try:
        vtable = ctypes.cast(
            interface_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        release(interface_ptr)
    except Exception:
        pass


def _query_com_interface(interface_ptr, iid_text):
    if not interface_ptr:
        return None
    iid = _guid_from_text(iid_text)
    target = ctypes.c_void_p()
    vtable = ctypes.cast(
        interface_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    query_interface = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)
    )(vtable[0])
    hr = query_interface(interface_ptr, ctypes.byref(iid), ctypes.byref(target))
    if int(hr) < 0 or not target.value:
        return None
    return target


def _open_shell_link(shortcut_path):
    """Load one existing .lnk through IShellLinkW and return COM interfaces."""
    if os.name != "nt":
        return None
    path = Path(shortcut_path).resolve()
    if not path.is_file():
        return None

    ole32 = ctypes.windll.ole32
    initialized_here = False
    try:
        hr = ole32.CoInitializeEx(None, 0x2)  # COINIT_APARTMENTTHREADED
        # S_OK/S_FALSE mean this call must be balanced with CoUninitialize.
        initialized_here = int(hr) in (0, 1)
    except Exception:
        initialized_here = False

    clsid = _guid_from_text("{00021401-0000-0000-C000-000000000046}")  # CLSID_ShellLink
    iid_shell_link = _guid_from_text("{000214F9-0000-0000-C000-000000000046}")  # IShellLinkW
    shell_link = ctypes.c_void_p()
    co_create = ole32.CoCreateInstance
    co_create.argtypes = [
        ctypes.POINTER(_GUID), ctypes.c_void_p, ctypes.c_ulong,
        ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p),
    ]
    co_create.restype = ctypes.c_long
    hr = co_create(
        ctypes.byref(clsid), None, 0x1, ctypes.byref(iid_shell_link), ctypes.byref(shell_link)
    )
    if int(hr) < 0 or not shell_link.value:
        if initialized_here:
            ole32.CoUninitialize()
        return None

    persist_file = _query_com_interface(
        shell_link, "{0000010B-0000-0000-C000-000000000046}"
    )
    if not persist_file:
        _release_com_interface(shell_link)
        if initialized_here:
            ole32.CoUninitialize()
        return None

    try:
        vtable = ctypes.cast(
            persist_file, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        load = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong
        )(vtable[5])
        hr = load(persist_file, str(path), 0x2)  # STGM_READWRITE
        if int(hr) < 0:
            _release_com_interface(persist_file)
            _release_com_interface(shell_link)
            if initialized_here:
                ole32.CoUninitialize()
            return None
    except Exception:
        _release_com_interface(persist_file)
        _release_com_interface(shell_link)
        if initialized_here:
            ole32.CoUninitialize()
        return None

    return {
        "path": path,
        "shell_link": shell_link,
        "persist_file": persist_file,
        "initialized_here": initialized_here,
    }


def _close_shell_link(context):
    if not context:
        return
    _release_com_interface(context.get("persist_file"))
    _release_com_interface(context.get("shell_link"))
    if context.get("initialized_here"):
        try:
            ctypes.windll.ole32.CoUninitialize()
        except Exception:
            pass


def _shell_link_property_store(context):
    return _query_com_interface(
        (context or {}).get("shell_link"),
        "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}",  # IPropertyStore
    )


def _save_shell_link(context):
    persist_file = (context or {}).get("persist_file")
    path = (context or {}).get("path")
    if not persist_file or not path:
        return False
    vtable = ctypes.cast(
        persist_file, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
    ).contents
    save = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int
    )(vtable[6])
    return int(save(persist_file, str(path), 1)) >= 0


def _read_property_store_string(store_ptr, pid):
    if not store_ptr:
        return ""
    PROPERTYKEY = _property_key_type()
    fmtid = _guid_from_text("{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}")
    key = PROPERTYKEY(fmtid, int(pid))
    variant = ctypes.create_string_buffer(24)
    try:
        vtable = ctypes.cast(
            store_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        ).contents
        get_value = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY), ctypes.c_void_p
        )(vtable[5])
        hr = get_value(store_ptr, ctypes.byref(key), ctypes.byref(variant))
        if int(hr) < 0:
            return ""
        value_ptr = ctypes.c_wchar_p()
        hr = ctypes.windll.propsys.PropVariantToStringAlloc(
            ctypes.byref(variant), ctypes.byref(value_ptr)
        )
        if int(hr) < 0 or not value_ptr.value:
            return ""
        try:
            return str(value_ptr.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(value_ptr, ctypes.c_void_p))
    except Exception:
        return ""
    finally:
        try:
            ctypes.windll.ole32.PropVariantClear(ctypes.byref(variant))
        except Exception:
            pass


def _read_shortcut_app_user_model_id_native(shortcut_path):
    context = _open_shell_link(shortcut_path)
    if not context:
        return ""
    store = None
    try:
        store = _shell_link_property_store(context)
        return _read_property_store_string(store, 5)
    finally:
        _release_com_interface(store)
        _close_shell_link(context)


def _write_shortcut_string_properties(shortcut_path, properties):
    """Persist Shell Link properties through IShellLink/IPropertyStore.

    SHGetPropertyStoreFromParsingName() exposes the .lnk file as a shell item, but
    writing PKEY_AppUserModel_ID there is not equivalent to saving the property on
    the Shell Link object itself.  Windows taskbar grouping consumes the latter.
    """
    context = _open_shell_link(shortcut_path)
    if not context:
        return False
    store = None
    try:
        store = _shell_link_property_store(context)
        if not store or not _set_property_store_strings(store, properties):
            return False
        return _save_shell_link(context)
    finally:
        _release_com_interface(store)
        _close_shell_link(context)


def configure_localsunodb_window_identity(hwnd, *, property_writer=None):
    identity = build_localsunodb_window_identity()
    properties = {
        5: identity["app_id"],
        2: identity["relaunch_command"],
        4: identity["display_name"],
        3: identity["icon_resource"],
    }
    writer = property_writer or _write_window_string_properties
    try:
        return bool(writer(hwnd, properties))
    except Exception:
        return False


def set_localsunodb_shortcut_app_id(
    shortcut_path,
    *,
    app_user_model_id=None,
    property_writer=None,
    property_reader=None,
):
    writer = property_writer or _write_shortcut_string_properties
    reader = property_reader or _read_shortcut_app_user_model_id_native
    app_id = str(app_user_model_id or LS_APP_USER_MODEL_ID).strip() or LS_APP_USER_MODEL_ID
    try:
        path = Path(shortcut_path)
        if not bool(writer(path, {5: app_id})):
            return False
        # Custom writers are used by pure unit tests. Production always verifies
        # the value persisted in the Shell Link before Chrome is allowed to open.
        if property_writer is None or property_reader is not None:
            persisted = str(reader(path) or "").strip()
            if persisted.casefold() != app_id.casefold():
                return False
        _notify_shell_shortcut_changed(path)
        return True
    except Exception:
        return False


def _read_windows_shortcut_details(shortcut_path):
    if os.name != "nt":
        return None
    shortcut_path = Path(shortcut_path).resolve()
    if not shortcut_path.is_file():
        return None
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$wsh = New-Object -ComObject WScript.Shell",
        f"$shortcutPath = {_powershell_single_quote(shortcut_path)}",
        "$shortcut = $wsh.CreateShortcut($shortcutPath)",
        "$appId = ''",
        "try {",
        "  $shell = New-Object -ComObject Shell.Application",
        "  $folder = $shell.Namespace((Split-Path -Parent $shortcutPath))",
        "  $item = $folder.ParseName((Split-Path -Leaf $shortcutPath))",
        "  if ($null -ne $item) { $appId = [string]$item.ExtendedProperty('System.AppUserModel.ID') }",
        "} catch {}",
        "[pscustomobject]@{",
        "  target_path = [string]$shortcut.TargetPath",
        "  arguments = [string]$shortcut.Arguments",
        "  working_directory = [string]$shortcut.WorkingDirectory",
        "  icon_location = [string]$shortcut.IconLocation",
        "  app_user_model_id = [string]$appId",
        "} | ConvertTo-Json -Compress",
    ])
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return None
        payload = json.loads(str(result.stdout or "").strip())
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _chrome_id_alphabet(hex_text):
    table = "abcdefghijklmnop"
    return "".join(table[int(ch, 16)] for ch in str(hex_text).lower())


def expected_localsunodb_chrome_app_id():
    """Return Chrome's deterministic web-app id for the LS manifest identity."""
    unhashed = f"http://{HOST}:{PORT}{LS_PWA_MANIFEST_ID}"
    digest = hashlib.sha256(unhashed.encode("utf-8")).hexdigest()[:32]
    return _chrome_id_alphabet(digest)


def _extract_chrome_app_id(arguments):
    match = re.search(r"(?:^|\s)--app-id=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))", str(arguments or ""))
    if not match:
        return ""
    return str(next((value for value in match.groups() if value), "")).strip()


def _extract_chrome_profile_directory(arguments):
    match = re.search(r"(?:^|\s)--profile-directory=(?:\"([^\"]+)\"|'([^']+)'|([^\s]+))", str(arguments or ""))
    if not match:
        return ""
    return str(next((value for value in match.groups() if value), "")).strip()


def _default_pwa_shortcut_candidates():
    """Return possible Chrome PWA shortcuts without assuming Chrome's folder layout."""
    candidates = []
    roots = []
    try:
        roots.append(_desktop_dir())
    except Exception:
        pass
    try:
        roots.append(_start_menu_programs_dir())
    except Exception:
        pass
    seen = set()
    preferred = []
    others = []
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        try:
            paths = root.rglob("*.lnk")
        except Exception:
            paths = []
        for path in paths:
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            key = str(resolved).casefold()
            if key in seen:
                continue
            seen.add(key)
            if "localsunodb" in resolved.name.casefold():
                preferred.append(resolved)
            else:
                others.append(resolved)
    candidates.extend(preferred)
    candidates.extend(others)
    return candidates


def _looks_like_installed_chrome_pwa(details, *, expected_app_id=None):
    details = details or {}
    target_name = Path(str(details.get("target_path") or "")).name.casefold()
    arguments = str(details.get("arguments") or "")
    app_id = _extract_chrome_app_id(arguments)
    chrome_launcher = target_name in {"chrome_proxy.exe", "chrome_pwa_launcher.exe"}
    if not chrome_launcher and not ("chrome" in target_name and app_id):
        return False
    if not app_id:
        return False
    expected = str(expected_app_id or expected_localsunodb_chrome_app_id()).strip().casefold()
    if app_id.casefold() == expected:
        return True
    # Compatibility for an older LS PWA install whose computed Chrome id may
    # pre-date the explicit manifest id. Do not accept an unrelated Chrome app.
    haystack = " ".join(
        str(details.get(key) or "")
        for key in ("working_directory", "icon_location")
    ).casefold()
    return "localsunodb" in haystack


def find_installed_localsunodb_pwa_shortcut(
    *,
    candidate_paths=None,
    shortcut_reader=None,
):
    reader = shortcut_reader or _read_windows_shortcut_details
    candidates = list(candidate_paths) if candidate_paths is not None else _default_pwa_shortcut_candidates()
    expected = expected_localsunodb_chrome_app_id()
    for candidate in candidates:
        path = Path(candidate)
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        details = reader(path)
        if not _looks_like_installed_chrome_pwa(details, expected_app_id=expected):
            continue
        result = dict(details or {})
        result["path"] = path
        result["chrome_app_id"] = _extract_chrome_app_id(result.get("arguments"))
        result["profile_directory"] = _extract_chrome_profile_directory(result.get("arguments")) or "Default"
        result["source"] = "shortcut"
        return result
    return None


def _chrome_user_data_root():
    root = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if not root:
        return None
    path = Path(root) / "Google" / "Chrome" / "User Data"
    return path if path.is_dir() else None


def _chrome_last_used_profile_directory(*, user_data_root=None):
    root = Path(user_data_root) if user_data_root is not None else _chrome_user_data_root()
    if not root:
        return LS_CHROME_DEFAULT_PROFILE
    try:
        payload = json.loads((root / "Local State").read_text(encoding="utf-8"))
        value = str(((payload or {}).get("profile") or {}).get("last_used") or "").strip()
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        value = ""
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or Path(value).name != value
    ):
        return LS_CHROME_DEFAULT_PROFILE
    return value


def _chrome_profile_id(profile_directory, *, user_data_dir_name="User Data"):
    profile = str(profile_directory or LS_CHROME_DEFAULT_PROFILE).strip() or LS_CHROME_DEFAULT_PROFILE
    if profile.casefold() == LS_CHROME_DEFAULT_PROFILE.casefold():
        return ""
    basenames = f"{user_data_dir_name}.{profile}"
    return "".join(ch for ch in basenames if ch.isascii() and (ch.isalpha() or ch.isdigit() or ch == "."))


def expected_chrome_app_url_aumid(
    url,
    *,
    profile_directory=None,
    base_app_id=LS_CHROME_BASE_APP_ID,
    user_data_dir_name="User Data",
):
    """Mirror Chrome's Windows AUMID for a --app=<url> window."""
    target = str(url or LS_APP_URL).strip() or LS_APP_URL
    parsed = urllib.parse.urlsplit(target)
    host = str(parsed.hostname or "").strip()
    path = str(parsed.path or "/")
    if not host:
        raise ValueError("Chrome app URL nav derīga hosta.")
    app_name = f"{host}_{path}"
    components = [str(base_app_id or LS_CHROME_BASE_APP_ID).strip() or LS_CHROME_BASE_APP_ID, app_name]
    profile_id = _chrome_profile_id(
        profile_directory or LS_CHROME_DEFAULT_PROFILE,
        user_data_dir_name=user_data_dir_name,
    )
    if profile_id:
        components.append(profile_id)
    # Chrome joins the components with dots and replaces spaces. LS route names
    # are short enough that Chromium's component-shortening path is not needed.
    return ".".join(components).replace(" ", "_")


def _recover_localsunodb_pwa_aumid(app_id):
    """Recover Chrome's real PWA AUMID from an old PWA/custom pin if available."""
    token = ("_crx_" + str(app_id or "")).casefold()
    candidates = []
    appdata = str(os.environ.get("APPDATA") or "").strip()
    if appdata:
        taskbar = (
            Path(appdata)
            / "Microsoft"
            / "Internet Explorer"
            / "Quick Launch"
            / "User Pinned"
            / "TaskBar"
        )
        if taskbar.is_dir():
            candidates.extend(taskbar.glob("*.lnk"))
    candidates.extend(_default_pwa_shortcut_candidates())
    seen = set()
    for path in candidates:
        path = Path(path)
        key = str(path).casefold()
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        details = _read_windows_shortcut_details(path) or {}
        value = str(details.get("app_user_model_id") or "").strip()
        if value and token in value.casefold():
            return value
    return ""


def _profile_contains_localsunodb_pwa(profile_path, app_id):
    web_apps = Path(profile_path) / "Web Applications"
    if not web_apps.is_dir():
        return False
    direct_candidates = (
        web_apps / str(app_id),
        web_apps / ("_crx_" + str(app_id)),
    )
    if any(path.exists() for path in direct_candidates):
        return True
    try:
        for child in web_apps.iterdir():
            if str(app_id).casefold() in child.name.casefold():
                return True
    except OSError:
        pass
    return False


def find_installed_localsunodb_pwa_profile(*, user_data_root=None):
    """Recover a PWA install even when our old launcher overwrote Chrome's .lnk."""
    root = Path(user_data_root) if user_data_root is not None else _chrome_user_data_root()
    if not root or not root.is_dir():
        return None
    app_id = expected_localsunodb_chrome_app_id()
    preferred_names = ["Default"]
    try:
        preferred_names.extend(
            path.name for path in root.iterdir()
            if path.is_dir() and path.name.startswith("Profile ")
        )
    except OSError:
        pass
    seen = set()
    for name in preferred_names:
        if name in seen:
            continue
        seen.add(name)
        profile = root / name
        if _profile_contains_localsunodb_pwa(profile, app_id):
            return {
                "chrome_app_id": app_id,
                "profile_directory": name,
                "profile_path": str(profile),
                "app_user_model_id": _recover_localsunodb_pwa_aumid(app_id),
                "path": None,
                "source": "chrome_profile",
            }
    return None


def resolve_installed_localsunodb_pwa():
    return find_installed_localsunodb_pwa_shortcut() or find_installed_localsunodb_pwa_profile()

def sync_localsunodb_shortcut_pwa_identity(
    shortcut_path,
    *,
    pwa_details=None,
    property_writer=None,
):
    """Bind the launcher shortcut to Chrome's real installed PWA identity."""
    details = pwa_details or find_installed_localsunodb_pwa_shortcut()
    app_id = str((details or {}).get("app_user_model_id") or "").strip()
    if not app_id:
        return False
    return set_localsunodb_shortcut_app_id(
        shortcut_path,
        app_user_model_id=app_id,
        property_writer=property_writer,
    )


def _looks_like_localsunodb_launcher_shortcut(details, *, shortcut_path=None):
    """Recognize both the direct Chrome LS pin and the one-time legacy launcher pin."""
    details = details or {}
    target = str(details.get("target_path") or "").strip()
    arguments = str(details.get("arguments") or "").strip()
    working_directory = str(details.get("working_directory") or "").strip()
    icon_location = str(details.get("icon_location") or "").strip()
    target_name = PureWindowsPath(target.replace("/", "\\")).name.casefold()
    arguments_cf = arguments.casefold()
    haystack = " ".join((target, arguments, working_directory, icon_location)).casefold()

    # v1.14+ contract: the pinned shortcut is a native Windows .lnk whose
    # executable is Chrome itself.  This lets Windows group the pin with the
    # Chrome --app window without custom AppUserModelID manipulation.
    if target_name == "chrome.exe":
        if "--app=" in arguments_cf and f"{HOST}:{PORT}".casefold() in arguments_cf:
            return True

    # Migration contract used by v1.08-v1.13.  The first v1.14 launch can still
    # arrive through this old pin; it is rewritten in place before Chrome opens.
    if target_name in {"python.exe", "pythonw.exe"}:
        if LS_CHROME_APP_LAUNCH_FLAG.casefold() in arguments_cf and (
            "ls_tools\\launcher.py" in arguments_cf
            or "ls_tools/launcher.py" in arguments_cf
            or "localsunodb" in haystack
        ):
            return True

    if target_name == LS_LEGACY_LAUNCHER_FILENAME.casefold():
        return True
    if "localsunodblauncher" in haystack:
        return True

    path_name = Path(shortcut_path).stem.casefold() if shortcut_path else ""
    ls_like_name = (
        "localsunodb" in path_name
        or bool(re.fullmatch(r"ls(?:[ _-]*v)?[ _-]*\d+(?:[._-]\d+)*", path_name))
    )
    icon_raw = icon_location.split(",", 1)[0].strip().strip('"')
    icon_is_ls = PureWindowsPath(icon_raw.replace("/", "\\")).name.casefold() == "ls.ico"
    try:
        same_root = bool(working_directory) and Path(working_directory).resolve() == Path(HOST_ROOT).resolve()
    except Exception:
        same_root = False
    return bool(ls_like_name and (icon_is_ls or same_root or "localsunodb" in haystack))


def _read_windows_shortcuts_in_directory(root):
    """Read a directory of .lnk files in one PowerShell process."""
    if os.name != "nt":
        return []
    root = Path(root).resolve()
    if not root.is_dir():
        return []
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$wsh = New-Object -ComObject WScript.Shell",
        f"$root = {_powershell_single_quote(root)}",
        "$items = @()",
        "Get-ChildItem -LiteralPath $root -Filter '*.lnk' -File | ForEach-Object {",
        "  $shortcut = $wsh.CreateShortcut($_.FullName)",
        "  $appId = ''",
        "  try {",
        "    $shell = New-Object -ComObject Shell.Application",
        "    $folder = $shell.Namespace($_.DirectoryName)",
        "    $item = $folder.ParseName($_.Name)",
        "    if ($null -ne $item) { $appId = [string]$item.ExtendedProperty('System.AppUserModel.ID') }",
        "  } catch {}",
        "  $items += [pscustomobject]@{",
        "    path = [string]$_.FullName",
        "    target_path = [string]$shortcut.TargetPath",
        "    arguments = [string]$shortcut.Arguments",
        "    working_directory = [string]$shortcut.WorkingDirectory",
        "    icon_location = [string]$shortcut.IconLocation",
        "    app_user_model_id = [string]$appId",
        "  }",
        "}",
        "$items | ConvertTo-Json -Compress",
    ])
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            return []
        raw = str(result.stdout or "").strip()
        if not raw:
            return []
        payload = json.loads(raw)
        if isinstance(payload, dict):
            payload = [payload]
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _taskbar_pinned_shortcuts(*, root=None, shortcut_batch_reader=None, shortcut_reader=None):
    if root is None:
        appdata = str(os.environ.get("APPDATA") or "").strip()
        if not appdata:
            return []
        root = (
            Path(appdata)
            / "Microsoft"
            / "Internet Explorer"
            / "Quick Launch"
            / "User Pinned"
            / "TaskBar"
        )
    root = Path(root)
    if not root.is_dir():
        return []

    batch_reader = shortcut_batch_reader or _read_windows_shortcuts_in_directory
    details_list = []
    try:
        details_list = list(batch_reader(root) or [])
    except Exception:
        details_list = []

    # Fallback for tests/older Windows shells if batch enumeration fails.
    if not details_list:
        reader = shortcut_reader or _read_windows_shortcut_details
        for path in sorted(root.glob("*.lnk")):
            details = reader(path) or {}
            if isinstance(details, dict):
                details = dict(details)
                details["path"] = str(path)
                details_list.append(details)

    result = []
    seen = set()
    for details in details_list:
        if not isinstance(details, dict):
            continue
        raw_path = str(details.get("path") or "").strip()
        if not raw_path:
            continue
        path = Path(raw_path)
        key = str(path).casefold()
        if key in seen:
            continue
        if not _looks_like_localsunodb_launcher_shortcut(details, shortcut_path=path):
            continue
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        seen.add(key)
        result.append(path)
    return sorted(result)


def rebind_taskbar_localsunodb_shortcuts(
    *,
    pinned_paths=None,
    shortcut_writer=None,
    chrome_executable=None,
    profile_directory=None,
):
    """Rewrite existing LS taskbar pins in place as direct Chrome --app shortcuts."""
    paths = list(pinned_paths) if pinned_paths is not None else _taskbar_pinned_shortcuts()
    writer = shortcut_writer or _write_windows_shortcut
    spec = build_browser_tab_launcher_shortcut_spec()
    changed = 0
    for raw_path in paths:
        path = Path(raw_path)
        try:
            if not path.is_file():
                continue
            writer(path, spec)
            changed += 1
        except Exception:
            continue
    return changed


def sync_existing_localsunodb_shortcuts_to_pwa_identity(pwa_details=None):
    """Compatibility shim: v1.14 always normalizes LS shortcuts to direct Chrome --app."""
    details = dict(pwa_details or {})
    profile = str(details.get("profile_directory") or "").strip() or None
    changed = rebind_taskbar_localsunodb_shortcuts(profile_directory=profile)
    spec = build_chrome_app_shortcut_spec(profile_directory=profile)
    for candidate in (
        _start_menu_programs_dir() / LS_SHORTCUT_FILENAME,
        _desktop_dir() / LS_SHORTCUT_FILENAME,
    ):
        try:
            if Path(candidate).is_file():
                _write_windows_shortcut(candidate, spec)
                changed += 1
        except Exception:
            pass
    return changed


def find_chrome_executable():
    candidates = []
    for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        root = str(os.environ.get(variable) or "").strip()
        if root:
            candidates.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
    located = shutil.which("chrome.exe")
    if located:
        candidates.append(Path(located))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if resolved.is_file():
            return resolved
    raise RuntimeError("Google Chrome nav atrasts. LocalSunoDb Chrome app saīsni nevar palaist.")


def get_ls_backend_status(timeout=0.8):
    try:
        request = urllib.request.Request(LS_BACKEND_STATUS_URL, method="GET")
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            if int(response.status) != 200:
                return None
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if not isinstance(payload, dict) or not payload.get("server_ready"):
                return None
            return payload
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return None


def is_ls_backend_alive(timeout=0.8):
    return get_ls_backend_status(timeout=timeout) is not None


def build_localsunodb_app_url(last_view_url="/"):
    value = str(last_view_url or "/").strip()
    if not value.startswith("/") or value.startswith("//"):
        value = "/"
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme or parsed.netloc:
        value = "/"
    return LS_APP_URL.rstrip("/") + value


def wait_for_ls_backend(timeout=15.0, interval=0.15):
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        if is_ls_backend_alive(timeout=min(0.6, max(0.1, float(interval) * 3))):
            return True
        time.sleep(float(interval))
    return False


def _backend_status_version(status):
    if not isinstance(status, dict):
        return ""
    return str(status.get("running_version") or status.get("app_version") or "").strip()


def _backend_process_id(status):
    if not isinstance(status, dict):
        return 0
    try:
        value = int(status.get("process_id") or 0)
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _terminate_backend_process(status):
    """Terminate only the backend PID reported by LocalSunoDb's own status endpoint."""
    process_id = _backend_process_id(status)
    if not process_id or process_id == os.getpid():
        return False
    try:
        os.kill(process_id, 15)
        return True
    except OSError:
        return False


def _wait_for_backend_stopped(*, status_getter=None, timeout=6.0, interval=0.10):
    status_getter = status_getter or get_ls_backend_status
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        if status_getter() is None:
            return True
        time.sleep(float(interval))
    return status_getter() is None


def ensure_localsunodb_backend_ready(
    *,
    status_getter=None,
    backend_starter=None,
    backend_waiter=None,
    stale_window_closer=None,
    backend_terminator=None,
    backend_stop_waiter=None,
):
    """Return (status, cold_started) and never reuse a backend from another LS version."""
    status_getter = status_getter or get_ls_backend_status
    backend_starter = backend_starter or start_ls_backend
    backend_waiter = backend_waiter or wait_for_ls_backend
    stale_window_closer = stale_window_closer or close_stale_localsunodb_chrome_app_windows
    backend_terminator = backend_terminator or _terminate_backend_process
    backend_stop_waiter = backend_stop_waiter or _wait_for_backend_stopped

    status = status_getter()
    if status is not None and _backend_status_version(status) == APP_VERSION:
        return status, False

    # A patch can replace files while an older pythonw backend is still alive.
    # Never focus that stale server: close its Chrome app window, terminate only
    # the PID it reports itself, then start the currently installed entrypoint.
    try:
        stale_window_closer(include_localsunodb_titles=True)
    except TypeError:
        stale_window_closer()

    if status is not None:
        if not backend_terminator(status):
            raise RuntimeError(
                "LocalSunoDb iepriekšējo backend procesu neizdevās apturēt. "
                "Aizver LS un mēģini vēlreiz."
            )
        try:
            stopped = backend_stop_waiter(status_getter=status_getter)
        except TypeError:
            stopped = backend_stop_waiter()
        if not stopped:
            raise RuntimeError("LocalSunoDb iepriekšējais backend process neapstājās laikā.")

    backend_starter()
    if not backend_waiter():
        raise RuntimeError("LocalSunoDb backendu neizdevās palaist 15 sekunžu laikā.")
    status = status_getter()
    if status is None:
        raise RuntimeError("LocalSunoDb backend palaidās, bet gatavības pārbaude neatbild.")
    running_version = _backend_status_version(status)
    if running_version != APP_VERSION:
        raise RuntimeError(
            f"LocalSunoDb palaida {running_version or 'nezināmu versiju'}, "
            f"bet instalēta ir {APP_VERSION}."
        )
    return status, True


def restart_localsunodb_backend(
    *,
    status_getter=None,
    backend_starter=None,
    backend_waiter=None,
    backend_terminator=None,
    backend_stop_waiter=None,
    supervisor_starter=None,
    restart_guard_setter=None,
):
    """Explicitly restart the current backend even when APP_VERSION is unchanged.

    This is the development/runtime reload path: code can be replaced on disk,
    then one explicit restart loads the new files without a Windows restart.
    """
    status_getter = status_getter or get_ls_backend_status
    backend_starter = backend_starter or start_ls_backend
    backend_waiter = backend_waiter or wait_for_ls_backend
    backend_terminator = backend_terminator or _terminate_backend_process
    backend_stop_waiter = backend_stop_waiter or _wait_for_backend_stopped
    restart_guard_setter = restart_guard_setter or _set_backend_restart_guard

    previous_status = status_getter()
    previous_pid = _backend_process_id(previous_status)
    status = None

    restart_guard_setter(True)
    try:
        if previous_status is not None:
            if previous_pid == os.getpid():
                raise RuntimeError(
                    "Backend restart must be launched by the external LS restart helper."
                )
            if not backend_terminator(previous_status):
                raise RuntimeError(
                    "LocalSunoDb backend procesu neizdevās apturēt."
                )
            try:
                stopped = backend_stop_waiter(status_getter=status_getter)
            except TypeError:
                stopped = backend_stop_waiter()
            if not stopped:
                raise RuntimeError(
                    "LocalSunoDb backend process neapstājās laikā."
                )

        backend_starter()
        if not backend_waiter():
            raise RuntimeError(
                "LocalSunoDb backendu pēc restarta neizdevās palaist 15 sekunžu laikā."
            )

        status = status_getter()
        if status is None:
            raise RuntimeError(
                "LocalSunoDb backend palaidās, bet gatavības pārbaude neatbild."
            )
    finally:
        restart_guard_setter(False)

    return {
        "ok": True,
        "action": "backend_restarted",
        "previous_process_id": previous_pid,
        "process_id": _backend_process_id(status),
        "running_version": _backend_status_version(status),
    }


def _read_current_running_minor(registry_path=None):
    path = Path(registry_path or LS_VERSION_REGISTRY_PATH)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get("current_running")
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except Exception:
        return None


def resolve_current_entrypoint(registry_path=None, app_dir=None, fallback_entrypoint=None):
    app_dir = Path(app_dir or APP_DIR).resolve()
    fallback = Path(fallback_entrypoint or APP_ENTRYPOINT_PATH).resolve()
    if fallback.is_file():
        return fallback
    current = (app_dir / "LocalSunoDb.py").resolve()
    if current.is_file():
        return current
    raise RuntimeError("LocalSunoDb palaidējs neatrada LocalSunoDb.py failu.")

def start_ls_backend(entrypoint=None):
    # The clean repository has one stable direct Python launch contract:
    # LocalSunoDb.py in the repository root.
    target = resolve_current_entrypoint(fallback_entrypoint=entrypoint or APP_ENTRYPOINT_PATH)
    command = [str(_background_python_executable()), str(target), "--ls-restarted"]
    return subprocess.Popen(
        command,
        cwd=str(HOST_ROOT),
        **_hidden_process_kwargs(),
    )


class LocalSunoDbAppSessionLease:
    """Process-local lease for the one canonical LS Chrome App page session."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_session_id = ""
        self._seen = False
        self._last_heartbeat_at = None
        self._close_requested_at = None

    def heartbeat(self, session_id, *, now=None):
        session_id = str(session_id or "").strip()
        if not session_id:
            raise ValueError("LocalSunoDb app session id is required.")
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            self._active_session_id = session_id
            self._seen = True
            self._last_heartbeat_at = current
            self._close_requested_at = None

    def closing(self, session_id, *, now=None):
        session_id = str(session_id or "").strip()
        if not session_id:
            raise ValueError("LocalSunoDb app session id is required.")
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            if not self._seen or session_id != self._active_session_id:
                return False
            self._close_requested_at = current
            return True

    def should_close(self, *, now=None, close_grace=1.5):
        current = time.monotonic() if now is None else float(now)
        with self._lock:
            requested = self._close_requested_at
            return bool(
                self._seen
                and requested is not None
                and current - float(requested) >= float(close_grace)
            )


_LS_APP_SESSION_LEASE = LocalSunoDbAppSessionLease()


def record_localsunodb_app_session(session_id, event, *, now=None):
    """Record browser-session telemetry without owning the backend lifetime."""
    event = str(event or "").strip().casefold()
    if event == "heartbeat":
        _LS_APP_SESSION_LEASE.heartbeat(session_id, now=now)
        return {"ok": True, "event": "heartbeat"}
    if event == "closing":
        # v1.15: closing the Chrome app window must not stop the local server.
        # The pinned shortcut launches Chrome directly, so the backend is a
        # separate persistent process and must remain ready for the next click.
        return {"ok": True, "event": "closing", "accepted": False}
    raise ValueError("Unknown LocalSunoDb app session event.")


def watch_localsunodb_app_session(
    *,
    on_closed,
    stop_requested=None,
    lease=None,
    poll_interval=0.2,
    close_grace=1.5,
    monotonic=None,
    sleep=None,
):
    """Stop LS only after the current page explicitly reports pagehide/close."""
    stop_requested = stop_requested or (lambda: False)
    lease = lease or _LS_APP_SESSION_LEASE
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep
    while True:
        if stop_requested():
            return "stopped"
        if lease.should_close(now=monotonic(), close_grace=close_grace):
            if stop_requested():
                return "stopped"
            # v1.15: browser close is telemetry only; backend lifetime is independent.
            return "closed"
        sleep(float(poll_interval))


def start_localsunodb_app_session_watcher(*, on_closed, stop_requested=None):
    thread = threading.Thread(
        target=watch_localsunodb_app_session,
        kwargs={"on_closed": on_closed, "stop_requested": stop_requested},
        name="ls-chrome-app-session-watcher",
        daemon=True,
    )
    thread.start()
    return thread


def _is_localsunodb_chrome_app_title(title):
    folded = str(title or "").strip().casefold()
    if not ("localsunodb" in folded or "ls v" in folded or folded == "ls"):
        return False
    return not any(
        folded.endswith(suffix)
        for suffix in (
            " - google chrome",
            " – google chrome",
            " — google chrome",
        )
    )


def _is_localsunodb_chrome_window(hwnd, user32):
    if not user32.IsWindowVisible(hwnd):
        return False
    title_length = int(user32.GetWindowTextLengthW(hwnd))
    if title_length <= 0:
        return False
    title_buffer = ctypes.create_unicode_buffer(title_length + 1)
    user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
    if not _is_localsunodb_chrome_app_title(title_buffer.value):
        return False
    class_buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
    return str(class_buffer.value or "").startswith("Chrome_WidgetWin_")


def find_localsunodb_chrome_app_window():
    if os.name != "nt":
        return None
    try:
        user32 = ctypes.windll.user32
        found = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        @callback_type
        def callback(hwnd, _lparam):
            if _is_localsunodb_chrome_window(hwnd, user32):
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(callback, 0)
        return found[0] if found else None
    except Exception:
        return None


def _is_stale_localsunodb_chrome_app_title(title):
    return str(title or "").strip().casefold() in {"127.0.0.1", "localhost"}


def close_stale_localsunodb_chrome_app_windows(*, include_localsunodb_titles=False):
    """Close dead localhost windows; when backend is down also close any LS app shell."""
    if os.name != "nt":
        return 0
    try:
        user32 = ctypes.windll.user32
        found = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        @callback_type
        def callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            class_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buffer, len(class_buffer))
            if not str(class_buffer.value or "").startswith("Chrome_WidgetWin_"):
                return True
            title_length = int(user32.GetWindowTextLengthW(hwnd))
            if title_length <= 0:
                return True
            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
            title = title_buffer.value
            if _is_stale_localsunodb_chrome_app_title(title) or (
                include_localsunodb_titles and _is_localsunodb_chrome_app_title(title)
            ):
                found.append(hwnd)
            return True

        user32.EnumWindows(callback, 0)
        closed = 0
        for hwnd in found:
            if user32.PostMessageW(hwnd, LS_WM_CLOSE, 0, 0):
                closed += 1
        return closed
    except Exception:
        return 0


def close_localsunodb_chrome_app_window(*, hwnd=None, user32=None):
    if hwnd is None:
        hwnd = find_localsunodb_chrome_app_window()
    if not hwnd:
        return False
    if user32 is None:
        if os.name != "nt":
            return False
        user32 = ctypes.windll.user32
    try:
        return bool(user32.PostMessageW(hwnd, LS_WM_CLOSE, 0, 0))
    except Exception:
        return False


def _apply_localsunodb_window_identity(*, timeout=8.0, interval=0.10):
    if os.name != "nt":
        return False
    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        hwnd = find_localsunodb_chrome_app_window()
        if hwnd:
            return configure_localsunodb_window_identity(hwnd)
        time.sleep(float(interval))
    return False


def apply_localsunodb_window_identity_async():
    thread = threading.Thread(
        target=_apply_localsunodb_window_identity,
        name="ls-taskbar-window-identity",
        daemon=True,
    )
    thread.start()
    return thread


def localsunodb_chrome_app_window_exists():
    return find_localsunodb_chrome_app_window() is not None


def focus_existing_localsunodb_window():
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = find_localsunodb_chrome_app_window()
        if not hwnd:
            return False
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def watch_localsunodb_chrome_app(
    *,
    window_exists=None,
    on_closed=None,
    stop_requested=None,
    poll_interval=0.25,
    startup_timeout=60.0,
    close_grace=1.5,
    monotonic=None,
    sleep=None,
):
    """Watch the one LS Chrome app window without coupling to Chrome's process."""
    window_exists = window_exists or localsunodb_chrome_app_window_exists
    on_closed = on_closed or (lambda: None)
    stop_requested = stop_requested or (lambda: False)
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep

    startup_deadline = monotonic() + float(startup_timeout)
    seen_window = False
    missing_since = None

    while True:
        if stop_requested():
            return "stopped"

        now = monotonic()
        present = bool(window_exists())
        if present:
            seen_window = True
            missing_since = None
        elif seen_window:
            if missing_since is None:
                missing_since = now
            elif now - missing_since >= float(close_grace):
                if stop_requested():
                    return "stopped"
                # v1.15: the Chrome window no longer owns the backend process.
                return "closed"
        elif now >= startup_deadline:
            return "startup_timeout"

        sleep(float(poll_interval))


def start_localsunodb_chrome_window_watcher(*, on_closed, stop_requested=None):
    thread = threading.Thread(
        target=watch_localsunodb_chrome_app,
        kwargs={
            "on_closed": on_closed,
            "stop_requested": stop_requested,
        },
        name="ls-chrome-app-window-watcher",
        daemon=True,
    )
    thread.start()
    return thread

def open_localsunodb_pwa_install_page(
    chrome_executable=None,
    url=None,
    *,
    process_opener=None,
):
    """Open the one-time PWA installation page in a normal Chrome window."""
    chrome = Path(chrome_executable or find_chrome_executable()).resolve()
    install_url = str(url or f"http://{HOST}:{PORT}/ls-pwa-install").strip()
    opener = process_opener or subprocess.Popen
    command = [str(chrome), "--new-window", install_url]
    opener(
        command,
        cwd=str(Path(HOST_ROOT).resolve()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return {
        "ok": True,
        "action": "opened_pwa_install_page",
        "url": install_url,
        "message": "LocalSunoDb instalēšanas lapa ir atvērta parastā Chrome logā.",
    }


def _open_windows_shortcut(shortcut_path):
    if os.name != "nt":
        raise RuntimeError("Windows PWA saīsni var palaist tikai Windows vidē.")
    os.startfile(str(Path(shortcut_path).resolve()))


def _launch_installed_localsunodb_pwa(pwa, *, chrome_executable=None, shortcut_opener=None):
    details = dict(pwa or {})
    shortcut_path = details.get("path")
    if shortcut_path:
        opener = shortcut_opener or _open_windows_shortcut
        opener(shortcut_path)
        return {
            "ok": True,
            "action": "opened_installed_pwa",
            "pwa_path": str(shortcut_path),
            "chrome_app_id": str(details.get("chrome_app_id") or ""),
        }

    app_id = str(details.get("chrome_app_id") or "").strip()
    profile = str(details.get("profile_directory") or "Default").strip() or "Default"
    if not app_id:
        raise RuntimeError("LocalSunoDb Chrome Web App instalācijai nav atrodams app-id.")
    chrome = Path(chrome_executable or find_chrome_executable()).resolve()
    process = subprocess.Popen(
        [str(chrome), f"--profile-directory={profile}", f"--app-id={app_id}"],
        cwd=str(chrome.parent),
        **_hidden_process_kwargs(),
    )
    return {
        "ok": True,
        "action": "opened_installed_pwa_by_app_id",
        "process": process,
        "chrome_app_id": app_id,
        "profile_directory": profile,
    }


def _launch_localsunodb_app_url(
    url,
    *,
    chrome_executable=None,
    process_opener=None,
    profile_directory=None,
):
    """Launch the exact same Chrome --app contract used by the Windows shortcut."""
    target_url = str(url or LS_APP_URL).strip() or LS_APP_URL
    spec = build_chrome_app_shortcut_spec(
        chrome_executable=chrome_executable,
        profile_directory=profile_directory,
        app_url=target_url,
    )
    opener = process_opener or subprocess.Popen
    process = opener(
        [spec["target_path"], *spec["argv"]],
        cwd=spec["working_directory"],
        **_hidden_process_kwargs(),
    )
    return {
        "ok": True,
        "action": "opened_direct_chrome_app",
        "process": process,
        "url": target_url,
        "profile_directory": spec["profile_directory"],
    }


def _existing_localsunodb_shortcuts():
    candidates = []
    candidates.extend(_taskbar_pinned_shortcuts())
    try:
        candidates.append(_start_menu_programs_dir() / LS_SHORTCUT_FILENAME)
    except Exception:
        pass
    try:
        candidates.append(_desktop_dir() / LS_SHORTCUT_FILENAME)
    except Exception:
        pass
    seen = set()
    result = []
    for raw_path in candidates:
        path = Path(raw_path)
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            if path.is_file():
                result.append(path)
        except OSError:
            continue
    return result


def sync_existing_localsunodb_shortcuts_to_launcher_identity(*, property_writer=None):
    """Compatibility helper for older callers that still request LS's legacy AUMID."""
    changed = 0
    for path in _existing_localsunodb_shortcuts():
        if set_localsunodb_shortcut_app_id(
            path,
            app_user_model_id=LS_APP_USER_MODEL_ID,
            property_writer=property_writer,
        ):
            changed += 1
    return changed


LS_TASKBAR_BINDING_TRACE_PATH = Path(HOST_ROOT) / "Logs" / "ls_taskbar_binding_v113.json"


def _write_taskbar_binding_trace(payload):
    try:
        path = LS_TASKBAR_BINDING_TRACE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = dict(payload or {})
        data["app_version"] = APP_VERSION
        data["captured_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
    except Exception:
        return None


def sync_existing_localsunodb_shortcuts_to_chrome_app_identity(
    url,
    *,
    profile_directory=None,
    property_writer=None,
    property_reader=None,
    require_verified_taskbar_pin=True,
):
    """Bind and verify LS shortcuts against Chrome's native --app AUMID."""
    profile = str(
        profile_directory or _chrome_last_used_profile_directory() or LS_CHROME_DEFAULT_PROFILE
    ).strip() or LS_CHROME_DEFAULT_PROFILE
    app_id = expected_chrome_app_url_aumid(url, profile_directory=profile)
    taskbar_paths = list(_taskbar_pinned_shortcuts())
    taskbar_keys = {str(Path(path)).casefold() for path in taskbar_paths}
    changed = 0
    verified_taskbar = []
    failed = []
    for path in _existing_localsunodb_shortcuts():
        ok = set_localsunodb_shortcut_app_id(
            path,
            app_user_model_id=app_id,
            property_writer=property_writer,
            property_reader=property_reader,
        )
        if ok:
            changed += 1
            if str(Path(path)).casefold() in taskbar_keys:
                verified_taskbar.append(str(Path(path)))
        else:
            failed.append(str(Path(path)))

    trace = {
        "expected_app_user_model_id": app_id,
        "profile_directory": profile,
        "taskbar_paths": [str(Path(path)) for path in taskbar_paths],
        "verified_taskbar": list(verified_taskbar),
        "failed": list(failed),
    }
    if os.name == "nt":
        trace["persisted_taskbar_app_user_model_ids"] = {
            str(Path(path)): _read_shortcut_app_user_model_id_native(path)
            for path in taskbar_paths
        }
    _write_taskbar_binding_trace(trace)

    if require_verified_taskbar_pin and taskbar_paths and not verified_taskbar:
        raise RuntimeError(
            "LS piespraustās ikonas AppUserModelID neizdevās droši saglabāt; "
            "Chrome netika palaists, lai neveidotu vēl vienu taskbar ikonu. "
            "Diagnostika: Logs\\ls_taskbar_binding_v113.json"
        )

    return {
        "changed": changed,
        "verified_taskbar": verified_taskbar,
        "failed": failed,
        "app_user_model_id": app_id,
        "profile_directory": profile,
        "trace_path": str(LS_TASKBAR_BINDING_TRACE_PATH),
    }


def open_localsunodb_chrome_app(
    chrome_executable=None,
    url=None,
    *,
    profile_directory=None,
):
    """Open LS through the direct Chrome --app shortcut contract."""
    return _launch_localsunodb_app_url(
        url or LS_APP_URL,
        chrome_executable=chrome_executable,
        profile_directory=profile_directory,
    )


def open_or_focus_localsunodb_chrome_app(chrome_executable=None, url=None, *, profile_directory=None):
    if find_localsunodb_chrome_app_window() and focus_existing_localsunodb_window():
        return {"ok": True, "action": "focused_existing"}
    return open_localsunodb_chrome_app(
        chrome_executable=chrome_executable,
        url=url,
        profile_directory=profile_directory,
    )


def _acquire_backend_supervisor_mutex():
    """Keep exactly one hidden backend supervisor per Windows user session."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, r"Local\LocalSunoDb.BackendSupervisor.v1")
        if not handle:
            return None
        if int(kernel32.GetLastError()) == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return False
        return handle
    except Exception:
        return None


def _set_backend_restart_guard(active, *, path=None):
    guard_path = Path(path or LS_BACKEND_RESTART_GUARD_PATH)
    if active:
        guard_path.parent.mkdir(parents=True, exist_ok=True)
        guard_path.write_text(
            json.dumps({"pid": os.getpid(), "started_at": time.time()}),
            encoding="utf-8",
        )
        return guard_path
    try:
        guard_path.unlink()
    except FileNotFoundError:
        pass
    return guard_path


def _backend_restart_guard_active(*, path=None, max_age=60.0):
    guard_path = Path(path or LS_BACKEND_RESTART_GUARD_PATH)
    if not guard_path.is_file():
        return False
    try:
        age = max(0.0, time.time() - guard_path.stat().st_mtime)
    except OSError:
        return False
    if age <= float(max_age):
        return True
    try:
        guard_path.unlink()
    except OSError:
        pass
    return False


def supervise_localsunodb_backend_once(
    *,
    status_getter=None,
    backend_ensurer=None,
    restart_guard_checker=None,
):
    """One supervisor iteration.

    Any responding LocalSunoDb backend is left alone regardless of version.
    Version replacement belongs to the explicit restart/update path; otherwise
    an old supervisor can fight a newly installed backend forever.
    """
    status_getter = status_getter or (lambda: _fetch_backend_status(timeout=0.8))
    backend_ensurer = backend_ensurer or ensure_localsunodb_backend_ready
    restart_guard_checker = restart_guard_checker or _backend_restart_guard_active

    if restart_guard_checker():
        return "restart_in_progress"

    status = status_getter()
    if status is not None:
        return "backend_present"

    backend_ensurer()
    return "backend_started"


def run_localsunodb_backend_supervisor(*, initial_delay=2.0, poll_interval=0.75):
    """Compatibility endpoint: persistent backend supervision is retired."""
    return {"ok": True, "action": "supervisor_disabled"}


def start_localsunodb_backend_supervisor():
    """Start the hidden supervisor once; duplicate instances self-deduplicate."""
    command = [
        str(_background_python_executable()),
        str(Path(__file__).resolve()),
        LS_BACKEND_SUPERVISOR_FLAG,
    ]
    return subprocess.Popen(
        command,
        cwd=str(HOST_ROOT),
        **_hidden_process_kwargs(),
    )


def start_localsunodb_backend_restart_helper():
    """Launch one detached helper that can replace the currently running backend."""
    command = [
        str(_background_python_executable()),
        str(Path(__file__).resolve()),
        LS_BACKEND_RESTART_FLAG,
        LS_BACKEND_RESTART_QUIET_FLAG,
    ]
    return subprocess.Popen(
        command,
        cwd=str(HOST_ROOT),
        **_hidden_process_kwargs(),
    )


def build_backend_autostart_command(*, python_executable=None, launcher_path=None):
    """Build the per-user Windows Run command for the persistent LS backend."""
    python_executable = Path(python_executable or _background_python_executable()).resolve()
    launcher_path = Path(launcher_path or Path(__file__).resolve()).resolve()
    return subprocess.list2cmdline([
        str(python_executable),
        str(launcher_path),
        LS_BACKEND_ONLY_FLAG,
    ])


def install_localsunodb_backend_run_entry():
    """Persist backend bootstrap with the native HKCU Run mechanism; no admin rights."""
    if os.name != "nt":
        return None
    import winreg

    command = build_backend_autostart_command()
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        key_path,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(
            key,
            LS_BACKEND_RUN_VALUE_NAME,
            0,
            winreg.REG_SZ,
            command,
        )

    # v1.14/v1.15 used Startup-folder .lnk. Remove that legacy bootstrap so
    # there is one per-user autostart contract only.
    try:
        legacy_startup = (_startup_dir() / "LocalSunoDb Backend.lnk").resolve()
        if legacy_startup.is_file():
            legacy_startup.unlink()
    except Exception:
        pass
    return command



def _stop_legacy_backend_supervisors():
    """Stop only detached LocalSunoDb launcher processes using the retired supervisor flag."""
    if os.name != "nt":
        return 0
    launcher_path = str(Path(__file__).resolve())
    script = "\n".join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        f"$launcher = {_powershell_single_quote(launcher_path)}",
        "$count = 0",
        "Get-CimInstance Win32_Process | Where-Object {",
        "  $_.CommandLine -and",
        "  $_.CommandLine.Contains($launcher) -and",
        f"  $_.CommandLine.Contains({_powershell_single_quote(LS_BACKEND_SUPERVISOR_FLAG)})",
        "} | ForEach-Object {",
        "  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue",
        "  $count += 1",
        "}",
        "Write-Output $count",
    ])
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return int(str(completed.stdout or "0").strip().splitlines()[-1] or 0)
    except Exception:
        return 0


def uninstall_localsunodb_backend_autostart(*, stop_supervisors=False):
    """Remove the retired PWA-era per-user backend bootstrap without touching user data."""
    run_value_removed = False
    startup_shortcut_removed = False
    if os.name == "nt":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                try:
                    winreg.DeleteValue(key, LS_BACKEND_RUN_VALUE_NAME)
                    run_value_removed = True
                except FileNotFoundError:
                    pass
        except OSError:
            pass
        try:
            legacy_startup = (_startup_dir() / "LocalSunoDb Backend.lnk").resolve()
            if legacy_startup.is_file():
                legacy_startup.unlink()
                startup_shortcut_removed = True
        except OSError:
            pass
    stopped = _stop_legacy_backend_supervisors() if stop_supervisors else 0
    return {
        "ok": True,
        "run_value_removed": bool(run_value_removed),
        "startup_shortcut_removed": bool(startup_shortcut_removed),
        "supervisors_stopped": int(stopped),
    }

def install_localsunodb_backend_autostart():
    """Compatibility action: persistent backend autostart is no longer part of LocalSunoDb."""
    cleanup = uninstall_localsunodb_backend_autostart(stop_supervisors=True)
    return {
        "ok": True,
        "action": "backend_autostart_disabled",
        **cleanup,
    }


def run_localsunodb_backend_only(*, autostart_cleaner=None):
    """Retire an old Windows Run invocation instead of keeping LS alive in the background."""
    cleaner = autostart_cleaner or (
        lambda: uninstall_localsunodb_backend_autostart(stop_supervisors=True)
    )
    cleaner()
    return {"ok": True, "action": "legacy_backend_autostart_removed"}


def run_localsunodb_browser_tab(
    *,
    backend_ensurer=None,
    browser_opener=None,
    autostart_cleaner=None,
):
    """Suno Finder operating model: backend ready first, then an ordinary browser tab."""
    cleaner = autostart_cleaner or (
        lambda: uninstall_localsunodb_backend_autostart(stop_supervisors=True)
    )
    cleaner()
    ensure_backend = backend_ensurer or ensure_localsunodb_backend_ready
    status, cold_started = ensure_backend()
    target_url = build_localsunodb_app_url((status or {}).get("last_view_url"))
    opener = browser_opener or webbrowser.open
    browser_opened = bool(opener(target_url))
    return {
        "ok": True,
        "action": "backend_started_and_browser_opened" if cold_started else "browser_opened",
        "url": target_url,
        "browser_opened": browser_opened,
        "running_version": _backend_status_version(status),
    }


def run_localsunodb_chrome_app():
    """Legacy shortcut alias; Chrome app/PWA mode now opens the standard browser-tab flow."""
    return run_localsunodb_browser_tab()



def build_browser_tab_launcher_shortcut_spec(
    *,
    host_root=None,
    launcher_path=None,
    **_ignored,
):
    """Windows shortcut contract matching Suno Finder's stable CMD launcher."""
    host_root = Path(host_root or HOST_ROOT).resolve()
    launcher_path = Path(
        launcher_path or (host_root / "Start_LocalSunoDb.cmd")
    ).resolve()
    return {
        "target_path": str(launcher_path),
        "arguments": "",
        "working_directory": str(host_root),
        "icon_location": str(LS_ICON_PATH.resolve()) + ",0",
    }

def build_chrome_app_shortcut_spec(
    *,
    chrome_executable=None,
    host_root=None,
    profile_directory=None,
    app_url=None,
    **_ignored,
):
    """Native Windows shortcut contract: Chrome is the executable, LS.ico is cosmetic."""
    chrome_executable = Path(chrome_executable or find_chrome_executable()).resolve()
    host_root = Path(host_root or HOST_ROOT).resolve()
    profile = str(
        profile_directory or _chrome_last_used_profile_directory() or LS_CHROME_DEFAULT_PROFILE
    ).strip() or LS_CHROME_DEFAULT_PROFILE
    target_url = str(app_url or LS_APP_URL).strip() or LS_APP_URL
    arguments = subprocess.list2cmdline([
        f"--profile-directory={profile}",
        f"--app={target_url}",
    ])
    return {
        "target_path": str(chrome_executable),
        "arguments": arguments,
        "working_directory": str(chrome_executable.parent),
        "icon_location": str(LS_ICON_PATH.resolve()) + ",0",
        "profile_directory": profile,
        "app_url": target_url,
        "argv": [
            f"--profile-directory={profile}",
            f"--app={target_url}",
        ],
    }


def build_backend_startup_shortcut_spec(*, python_executable=None, launcher_path=None, host_root=None):
    python_executable = Path(python_executable or _background_python_executable()).resolve()
    launcher_path = Path(launcher_path or Path(__file__).resolve()).resolve()
    host_root = Path(host_root or HOST_ROOT).resolve()
    return {
        "target_path": str(python_executable),
        "arguments": subprocess.list2cmdline([str(launcher_path), LS_BACKEND_ONLY_FLAG]),
        "working_directory": str(host_root),
        "icon_location": str(LS_ICON_PATH.resolve()) + ",0",
    }


def _start_menu_programs_dir():
    appdata = str(os.environ.get("APPDATA") or "").strip()
    if not appdata:
        raise RuntimeError("Windows APPDATA mape nav pieejama.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def _startup_dir():
    appdata = str(os.environ.get("APPDATA") or "").strip()
    if not appdata:
        raise RuntimeError("Windows APPDATA mape nav pieejama.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _desktop_dir():
    profile = str(os.environ.get("USERPROFILE") or "").strip()
    if profile:
        return Path(profile) / "Desktop"
    return Path.home() / "Desktop"


def _write_windows_shortcut(shortcut_path, spec):
    shortcut_path = Path(shortcut_path).resolve()
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    ps_script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        "$shell = New-Object -ComObject WScript.Shell",
        f"$shortcut = $shell.CreateShortcut({_powershell_single_quote(shortcut_path)})",
        f"$shortcut.TargetPath = {_powershell_single_quote(spec['target_path'])}",
        f"$shortcut.Arguments = {_powershell_single_quote(spec['arguments'])}",
        f"$shortcut.WorkingDirectory = {_powershell_single_quote(spec['working_directory'])}",
        f"$shortcut.IconLocation = {_powershell_single_quote(spec['icon_location'])}",
        "$shortcut.Description = 'LocalSunoDb'",
        "$shortcut.Save()",
    ])
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
        ],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0 or not shortcut_path.is_file():
        error = str(result.stderr or result.stdout or "Windows saīsni neizdevās izveidot.").strip()
        raise RuntimeError(error)
    _notify_shell_shortcut_changed(shortcut_path)
    return shortcut_path


def _try_pin_shortcut_to_taskbar(shortcut_path):
    """Best-effort explicit user-requested taskbar pin; Windows may still require UI policy approval."""
    if os.name != "nt":
        return False
    shortcut_path = Path(shortcut_path).resolve()
    ps_script = "\n".join([
        "$ErrorActionPreference = 'SilentlyContinue'",
        "$shell = New-Object -ComObject Shell.Application",
        f"$folder = $shell.Namespace({_powershell_single_quote(shortcut_path.parent)})",
        f"$item = $folder.ParseName({_powershell_single_quote(shortcut_path.name)})",
        "if ($null -ne $item) { $item.InvokeVerb('taskbarpin') }",
    ])
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _launcher_shortcut_paths(pwa_details=None):
    pwa_path = Path(pwa_details["path"]).resolve() if (pwa_details or {}).get("path") else None
    start_default = (_start_menu_programs_dir() / LS_SHORTCUT_FILENAME).resolve()
    desktop_default = (_desktop_dir() / LS_SHORTCUT_FILENAME).resolve()

    def safe_path(default_path, fallback_path):
        if pwa_path is not None and str(default_path).casefold() == str(pwa_path).casefold():
            return Path(fallback_path).resolve()
        return default_path

    start_path = safe_path(
        start_default,
        _start_menu_programs_dir() / "LocalSunoDb Launcher" / LS_SHORTCUT_FILENAME,
    )
    desktop_path = safe_path(
        desktop_default,
        _desktop_dir() / "LocalSunoDb Launcher.lnk",
    )
    return start_path, desktop_path


def install_localsunodb_backend_startup_shortcut():
    if os.name != "nt":
        return None
    path = (_startup_dir() / "LocalSunoDb Backend.lnk").resolve()
    return _write_windows_shortcut(path, build_backend_startup_shortcut_spec())


def create_localsunodb_launcher_shortcut(*, profile_directory=None):
    if os.name != "nt":
        raise RuntimeError("LocalSunoDb Windows saīsni var izveidot tikai Windows vidē.")

    spec = build_browser_tab_launcher_shortcut_spec()
    start_path, desktop_path = _launcher_shortcut_paths(None)
    start_shortcut = _write_windows_shortcut(start_path, spec)
    desktop_shortcut = _write_windows_shortcut(desktop_path, spec)
    rebound = rebind_taskbar_localsunodb_shortcuts()

    legacy_cmd = (Path(HOST_ROOT) / LS_LEGACY_LAUNCHER_FILENAME).resolve()
    try:
        if legacy_cmd.is_file():
            legacy_cmd.unlink()
    except OSError:
        pass

    uninstall_localsunodb_backend_autostart(stop_supervisors=True)

    return {
        "ok": True,
        "shortcut_path": str(start_shortcut),
        "desktop_shortcut_path": str(desktop_shortcut),
        "taskbar_shortcuts_rewritten": int(rebound),
        "message": (
            "LocalSunoDb saīsne palaiž lokālo backendu un pēc gatavības atver "
            "parastu pārlūka cilni."
        ),
    }


def _record_launcher_error(exc):
    try:
        path = Path(HOST_ROOT) / "error.log"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                f"{datetime.now().astimezone().isoformat(timespec='seconds')} "
                f"LAUNCHER {type(exc).__name__}: {exc}\n"
            )
    except Exception:
        pass


def _show_launcher_error(exc):
    _record_launcher_error(exc)
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            0,
            str(exc),
            "LocalSunoDb",
            0x10,
        )
    except Exception:
        pass


def main():
    try:
        if LS_BACKEND_RESTART_FLAG in sys.argv:
            result = restart_localsunodb_backend()
            if os.name == "nt" and LS_BACKEND_RESTART_QUIET_FLAG not in sys.argv:
                try:
                    ctypes.windll.user32.MessageBoxW(
                        0,
                        (
                            "LocalSunoDb backend ir pārstartēts.\n"
                            f"Process ID: {int(result.get('process_id') or 0)}"
                        ),
                        "LocalSunoDb",
                        0x40,
                    )
                except Exception:
                    pass
            return 0
        if LS_BACKEND_SUPERVISOR_FLAG in sys.argv:
            run_localsunodb_backend_supervisor()
            return 0
        if LS_BACKEND_AUTOSTART_INSTALL_FLAG in sys.argv:
            install_localsunodb_backend_autostart()
            if os.name == "nt":
                try:
                    ctypes.windll.user32.MessageBoxW(
                        0,
                        f"LocalSunoDb {APP_VERSION}: vecais backend autostart ir atspējots.",
                        "LocalSunoDb",
                        0x40,
                    )
                except Exception:
                    pass
            return 0
        if LS_BACKEND_ONLY_FLAG in sys.argv:
            run_localsunodb_backend_only()
            return 0
        if LS_BROWSER_TAB_LAUNCH_FLAG in sys.argv or LS_CHROME_APP_LAUNCH_FLAG in sys.argv:
            run_localsunodb_browser_tab()
            return 0
        return 0
    except Exception as exc:
        _show_launcher_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
