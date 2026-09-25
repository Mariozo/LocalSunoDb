import base64
import difflib
import hashlib
import importlib.util
import socket
import threading
import html
import json
import os
import shutil
import mimetypes
import re
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import warnings
import wave
import webbrowser
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from ls_core.runtime import *


LOCAL_BROWSER_AUDIO_CACHE_DIR = TEMP_DIR / "browser_audio_cache"


def open_files_in_audio_editor(local_paths):
    paths = []
    for value in local_paths or []:
        p = Path(urllib.parse.unquote(str(value or "")).strip().strip('"'))
        if p.exists() and p.is_file():
            paths.append(str(p))

    if not paths:
        return False, "No existing local files selected"

    editor = find_audio_editor()
    if editor:
        # Multi-file Audacity import is safest through a LOF list.
        # v3.35/v3.36 used a too-minimal LOF and some Audacity builds opened then closed.
        # Use the documented LOF syntax: one file command per line, with offset 0.
        # Do not add a "window" command here; we want one project window.
        if len(paths) > 1:
            EDIT_CACHE_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            lof_path = EDIT_CACHE_DIR / f"selected_stems_{stamp}.lof"
            lines = ["# LocalSunoDb selected stems for Audacity"]
            for path in paths:
                safe_path = str(path).replace('"', "")
                lines.append(f'file "{safe_path}" offset 0')
            lof_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
            subprocess.Popen([str(editor), str(lof_path)], cwd=str(EDIT_CACHE_DIR))
            focus_windows_by_title(title_parts=["audacity"], class_names=[], timeout=3.0)
            return True, f"Opened {len(paths)} file(s) via Audacity LOF list: {lof_path}"

        subprocess.Popen([str(editor), paths[0]])
        focus_windows_by_title(title_parts=["audacity"], class_names=[], timeout=2.5)
        return True, "Opened 1 file in Audacity"

    reveal_file_in_explorer(paths[0])
    return True, "Audacity not found; opened first selected file in Explorer"

LS_AUDIO_OUTPUT_POWERSHELL = r'''param(
    [ValidateSet("state", "set")]
    [string]$Action = "state",
    [string]$DeviceId = ""
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$cacheRoot = Join-Path $env:LOCALAPPDATA "LocalSunoDb"
if (-not (Test-Path -LiteralPath $cacheRoot)) {
    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
}

$source = @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace LocalSunoDbAudio {
    public enum EDataFlow { eRender = 0, eCapture = 1, eAll = 2 }
    public enum ERole { eConsole = 0, eMultimedia = 1, eCommunications = 2 }
    [Flags] public enum DeviceState : uint { Active = 0x00000001 }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROPERTYKEY {
        public Guid fmtid;
        public uint pid;
        public PROPERTYKEY(Guid formatId, uint propertyId) { fmtid = formatId; pid = propertyId; }
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct PROPVARIANT {
        [FieldOffset(0)] public ushort vt;
        [FieldOffset(8)] public IntPtr pointerValue;
        public string StringValue() {
            return vt == 31 && pointerValue != IntPtr.Zero
                ? (Marshal.PtrToStringUni(pointerValue) ?? "") : "";
        }
    }

    [ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-C0A52C7B1E90"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceCollection {
        [PreserveSig] int GetCount(out uint count);
        [PreserveSig] int Item(uint index, out IMMDevice device);
    }

    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice {
        [PreserveSig] int Activate(ref Guid iid, int clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object interfacePointer);
        [PreserveSig] int OpenPropertyStore(int accessMode, out IPropertyStore properties);
        [PreserveSig] int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
        [PreserveSig] int GetState(out uint state);
    }

    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore {
        [PreserveSig] int GetCount(out uint propertyCount);
        [PreserveSig] int GetAt(uint propertyIndex, out PROPERTYKEY key);
        [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT value);
        [PreserveSig] int SetValue(ref PROPERTYKEY key, ref PROPVARIANT value);
        [PreserveSig] int Commit();
    }

    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator {
        [PreserveSig] int EnumAudioEndpoints(EDataFlow dataFlow, DeviceState stateMask, out IMMDeviceCollection devices);
        [PreserveSig] int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice endpoint);
        [PreserveSig] int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IMMDevice device);
        [PreserveSig] int RegisterEndpointNotificationCallback(IntPtr client);
        [PreserveSig] int UnregisterEndpointNotificationCallback(IntPtr client);
    }

    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    class MMDeviceEnumeratorComObject { }

    [ComImport, Guid("F8679F50-850A-41CF-9C72-430F290290C8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPolicyConfig {
        [PreserveSig] int GetMixFormat(string deviceId, IntPtr format);
        [PreserveSig] int GetDeviceFormat(string deviceId, int isDefault, IntPtr format);
        [PreserveSig] int ResetDeviceFormat(string deviceId);
        [PreserveSig] int SetDeviceFormat(string deviceId, IntPtr endpointFormat, IntPtr mixFormat);
        [PreserveSig] int GetProcessingPeriod(string deviceId, int isDefault, IntPtr defaultPeriod, IntPtr minimumPeriod);
        [PreserveSig] int SetProcessingPeriod(string deviceId, IntPtr period);
        [PreserveSig] int GetShareMode(string deviceId, IntPtr mode);
        [PreserveSig] int SetShareMode(string deviceId, IntPtr mode);
        [PreserveSig] int GetPropertyValue(string deviceId, ref PROPERTYKEY key, out PROPVARIANT value);
        [PreserveSig] int SetPropertyValue(string deviceId, ref PROPERTYKEY key, ref PROPVARIANT value);
        [PreserveSig] int SetDefaultEndpoint(string deviceId, ERole role);
        [PreserveSig] int SetEndpointVisibility(string deviceId, int visible);
    }

    [ComImport, Guid("870AF99C-171D-4F9E-AF0D-E63DF40C2BC9")]
    class PolicyConfigClient { }

    [ComImport, Guid("568B9108-44BF-40B4-9006-86AFE5B5A620"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPolicyConfigVista {
        [PreserveSig] int GetMixFormat(string deviceId, IntPtr format);
        [PreserveSig] int GetDeviceFormat(string deviceId, int isDefault, IntPtr format);
        [PreserveSig] int ResetDeviceFormat(string deviceId);
        [PreserveSig] int SetDeviceFormat(string deviceId, IntPtr endpointFormat, IntPtr mixFormat);
        [PreserveSig] int GetProcessingPeriod(string deviceId, int isDefault, IntPtr defaultPeriod, IntPtr minimumPeriod);
        [PreserveSig] int SetProcessingPeriod(string deviceId, IntPtr period);
        [PreserveSig] int GetShareMode(string deviceId, IntPtr mode);
        [PreserveSig] int SetShareMode(string deviceId, IntPtr mode);
        [PreserveSig] int GetPropertyValue(string deviceId, ref PROPERTYKEY key, out PROPVARIANT value);
        [PreserveSig] int SetPropertyValue(string deviceId, ref PROPERTYKEY key, ref PROPVARIANT value);
        [PreserveSig] int SetDefaultEndpoint(string deviceId, ERole role);
        [PreserveSig] int SetEndpointVisibility(string deviceId, int visible);
    }

    [ComImport, Guid("294935CE-F637-4E7C-A41B-AB255460B862")]
    class PolicyConfigVistaClient { }

    public sealed class DeviceInfo {
        public string Id { get; set; }
        public string Name { get; set; }
        public bool IsDefault { get; set; }
    }

    public static class AudioEndpoints {
        static readonly PROPERTYKEY FriendlyNameKey = new PROPERTYKEY(
            new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"), 14
        );

        [DllImport("ole32.dll")]
        static extern int PropVariantClear(ref PROPVARIANT value);

        static void Check(int hresult) {
            if (hresult < 0) Marshal.ThrowExceptionForHR(hresult, new IntPtr(-1));
        }

        static string DeviceName(IMMDevice device) {
            IPropertyStore store = null;
            PROPVARIANT value = new PROPVARIANT();
            try {
                Check(device.OpenPropertyStore(0, out store));
                PROPERTYKEY key = FriendlyNameKey;
                Check(store.GetValue(ref key, out value));
                return value.StringValue();
            } finally {
                try { PropVariantClear(ref value); } catch { }
                if (store != null) Marshal.FinalReleaseComObject(store);
            }
        }

        public static string DefaultId() {
            IMMDeviceEnumerator enumerator = null;
            IMMDevice defaultDevice = null;
            try {
                enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                if (enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender, ERole.eMultimedia, out defaultDevice) < 0 || defaultDevice == null) {
                    return "";
                }
                string id;
                Check(defaultDevice.GetId(out id));
                return id ?? "";
            } finally {
                if (defaultDevice != null) Marshal.FinalReleaseComObject(defaultDevice);
                if (enumerator != null) Marshal.FinalReleaseComObject(enumerator);
            }
        }

        public static DeviceInfo[] List() {
            IMMDeviceEnumerator enumerator = null;
            IMMDeviceCollection collection = null;
            string defaultId = DefaultId();
            try {
                enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
                Check(enumerator.EnumAudioEndpoints(EDataFlow.eRender, DeviceState.Active, out collection));
                uint count;
                Check(collection.GetCount(out count));
                var result = new List<DeviceInfo>();
                for (uint index = 0; index < count; index++) {
                    IMMDevice device = null;
                    try {
                        Check(collection.Item(index, out device));
                        string id;
                        Check(device.GetId(out id));
                        string name;
                        try { name = DeviceName(device); }
                        catch { name = id ?? ""; }
                        result.Add(new DeviceInfo {
                            Id = id ?? "",
                            Name = String.IsNullOrWhiteSpace(name) ? (id ?? "") : name,
                            IsDefault = String.Equals(id, defaultId, StringComparison.OrdinalIgnoreCase)
                        });
                    } finally {
                        if (device != null) Marshal.FinalReleaseComObject(device);
                    }
                }
                return result.ToArray();
            } finally {
                if (collection != null) Marshal.FinalReleaseComObject(collection);
                if (enumerator != null) Marshal.FinalReleaseComObject(enumerator);
            }
        }

        static void SetCurrent(string deviceId) {
            IPolicyConfig policy = null;
            try {
                policy = (IPolicyConfig)(new PolicyConfigClient());
                Check(policy.SetDefaultEndpoint(deviceId, ERole.eConsole));
                Check(policy.SetDefaultEndpoint(deviceId, ERole.eMultimedia));
                Check(policy.SetDefaultEndpoint(deviceId, ERole.eCommunications));
            } finally {
                if (policy != null) Marshal.FinalReleaseComObject(policy);
            }
        }

        static void SetVista(string deviceId) {
            IPolicyConfigVista policy = null;
            try {
                policy = (IPolicyConfigVista)(new PolicyConfigVistaClient());
                Check(policy.SetDefaultEndpoint(deviceId, ERole.eConsole));
                Check(policy.SetDefaultEndpoint(deviceId, ERole.eMultimedia));
                Check(policy.SetDefaultEndpoint(deviceId, ERole.eCommunications));
            } finally {
                if (policy != null) Marshal.FinalReleaseComObject(policy);
            }
        }

        public static void SetDefault(string deviceId) {
            if (String.IsNullOrWhiteSpace(deviceId)) throw new ArgumentException("Missing audio endpoint ID");
            try { SetCurrent(deviceId); }
            catch { SetVista(deviceId); }
        }
    }
}
"@

# The assembly name follows the source hash. A code update therefore cannot
# reuse an older cached DLL with an incompatible device-enumeration contract.
$sourceBytes = [System.Text.Encoding]::UTF8.GetBytes($source)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
try {
    $sourceHash = ([System.BitConverter]::ToString($sha256.ComputeHash($sourceBytes))).Replace("-", "").ToLowerInvariant()
} finally {
    $sha256.Dispose()
}
$dllPath = Join-Path $cacheRoot ("LsAudioOutput_" + $sourceHash.Substring(0, 16) + ".dll")
if (-not (Test-Path -LiteralPath $dllPath)) {
    # Add-Type loads the compiled type in this process while also caching it.
    Add-Type -TypeDefinition $source -Language CSharp -OutputAssembly $dllPath
} else {
    try {
        Add-Type -Path $dllPath
    } catch {
        # A partial or incompatible cache must never leave Settings empty.
        Remove-Item -LiteralPath $dllPath -Force -ErrorAction SilentlyContinue
        Add-Type -TypeDefinition $source -Language CSharp -OutputAssembly $dllPath
    }
}

function Get-PnpRenderEndpoints([string]$DefaultId) {
    $result = @()
    $prefix = "SWD\MMDEVAPI\"
    try {
        $items = @(Get-PnpDevice -Class AudioEndpoint -PresentOnly -ErrorAction Stop)
        foreach ($item in $items) {
            $instanceId = [string]$item.InstanceId
            if (-not $instanceId.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            $id = $instanceId.Substring($prefix.Length)
            # Render endpoints use the 0.0.0 MMDevice namespace. Capture endpoints
            # use 0.0.1 and must not appear in the playback-output selectors.
            if (-not $id.StartsWith("{0.0.0.", [System.StringComparison]::OrdinalIgnoreCase)) { continue }
            $name = [string]$item.FriendlyName
            if ([string]::IsNullOrWhiteSpace($name)) { $name = [string]$item.Name }
            if ([string]::IsNullOrWhiteSpace($name)) { continue }
            $result += [pscustomobject]@{
                Id = $id
                Name = $name
                IsDefault = [string]::Equals($id, $DefaultId, [System.StringComparison]::OrdinalIgnoreCase)
            }
        }
    } catch { }
    return @($result)
}

function Get-RegistryRenderEndpoints([string]$DefaultId) {
    $result = @()
    $root = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
    $friendlyNameProperty = "{a45c254e-df1c-4efd-8020-67d146a850e0},14"
    try {
        foreach ($endpointKey in @(Get-ChildItem -LiteralPath $root -ErrorAction Stop)) {
            $state = 1
            try {
                $stateValue = (Get-ItemProperty -LiteralPath $endpointKey.PSPath -Name "DeviceState" -ErrorAction Stop).DeviceState
                if ($null -ne $stateValue) { $state = [int]$stateValue }
            } catch { }
            if ($state -ne 1) { continue }

            $name = ""
            $propertiesPath = Join-Path $endpointKey.PSPath "Properties"
            try {
                $name = [string](Get-ItemPropertyValue -LiteralPath $propertiesPath -Name $friendlyNameProperty -ErrorAction Stop)
            } catch { }
            if ([string]::IsNullOrWhiteSpace($name)) { continue }
            $endpointGuid = [string]$endpointKey.PSChildName
            $id = "{0.0.0.00000000}." + $endpointGuid
            $result += [pscustomobject]@{
                Id = $id
                Name = $name
                IsDefault = [string]::Equals($id, $DefaultId, [System.StringComparison]::OrdinalIgnoreCase)
            }
        }
    } catch { }
    return @($result)
}

try {
    if ($Action -eq "set") {
        if ([string]::IsNullOrWhiteSpace($DeviceId)) { throw "Nav norādīta audio izeja." }
        [LocalSunoDbAudio.AudioEndpoints]::SetDefault($DeviceId)
        Start-Sleep -Milliseconds 60
        $defaultId = ""
        try { $defaultId = [LocalSunoDbAudio.AudioEndpoints]::DefaultId() } catch { }
        [pscustomobject]@{
            ok = $true
            devices = @()
            default_id = $defaultId
            source = "set-fast"
            helper_version = 4
        } | ConvertTo-Json -Depth 4 -Compress
        exit 0
    }

    $defaultId = ""
    try { $defaultId = [LocalSunoDbAudio.AudioEndpoints]::DefaultId() } catch { }
    $mmDevices = @()
    try { $mmDevices = @([LocalSunoDbAudio.AudioEndpoints]::List()) } catch { }
    $pnpDevices = @(Get-PnpRenderEndpoints -DefaultId $defaultId)

    # Merge by the full MMDevice endpoint ID. PnP supplies the reliable Windows
    # friendly name, while Core Audio supplies the authoritative default state.
    $deviceMap = @{}
    foreach ($item in $mmDevices) {
        $id = [string]$item.Id
        if ([string]::IsNullOrWhiteSpace($id)) { continue }
        $deviceMap[$id.ToLowerInvariant()] = [pscustomobject]@{
            Id = $id
            Name = [string]$item.Name
            IsDefault = [bool]$item.IsDefault
        }
    }
    foreach ($item in $pnpDevices) {
        $id = [string]$item.Id
        if ([string]::IsNullOrWhiteSpace($id)) { continue }
        $key = $id.ToLowerInvariant()
        if ($deviceMap.ContainsKey($key)) {
            $existing = $deviceMap[$key]
            $deviceMap[$key] = [pscustomobject]@{
                Id = $id
                Name = [string]$item.Name
                IsDefault = ([bool]$existing.IsDefault -or [bool]$item.IsDefault)
            }
        } else {
            $deviceMap[$key] = $item
        }
    }

    $registryDevices = @(Get-RegistryRenderEndpoints -DefaultId $defaultId)
    foreach ($item in $registryDevices) {
        $id = [string]$item.Id
        if ([string]::IsNullOrWhiteSpace($id)) { continue }
        $key = $id.ToLowerInvariant()
        if ($deviceMap.ContainsKey($key)) {
            $existing = $deviceMap[$key]
            $existingName = [string]$existing.Name
            if (
                [string]::IsNullOrWhiteSpace($existingName) -or
                $existingName -eq $id -or
                $existingName -match '^\{[0-9a-fA-F-]+\}$'
            ) {
                $deviceMap[$key] = [pscustomobject]@{
                    Id = $id
                    Name = [string]$item.Name
                    IsDefault = ([bool]$existing.IsDefault -or [bool]$item.IsDefault)
                }
            }
        } else {
            $deviceMap[$key] = $item
        }
    }

    $devices = @($deviceMap.Values | Sort-Object -Property Name)
    $sourceParts = @("mmdevice")
    if ($pnpDevices.Count -gt 0) { $sourceParts += "pnp" }
    if ($registryDevices.Count -gt 0) { $sourceParts += "registry" }
    $sourceName = $sourceParts -join "+"
    if ($devices.Count -eq 0) {
        throw "Windows neatrada nevienu aktīvu atskaņošanas ierīci."
    }
    [pscustomobject]@{
        ok = $true
        devices = @($devices)
        default_id = $defaultId
        source = $sourceName
        helper_version = 4
    } | ConvertTo-Json -Depth 6 -Compress
} catch {
    [pscustomobject]@{
        ok = $false
        error = $_.Exception.Message
        devices = @()
        helper_version = 3
    } | ConvertTo-Json -Depth 6 -Compress
    exit 1
}
'''

def _ls_audio_output_fold(value):
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    text = "".join(
        character for character in text
        if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"\s+", " ", text).strip()

def _ls_audio_output_score(device, role):
    name = _ls_audio_output_fold((device or {}).get("name"))
    if not name:
        return -1000
    umc_terms = (
        "umc", "behringer", "usb audio codec", "umc404", "umc204",
        "umc202", "umc1820", "out 1-2", "playback 1-2",
    )
    if role == "headphones":
        score = 0
        if any(term in name for term in umc_terms):
            score += 200
        if "headphones" in name or "austinas" in name:
            score += 35
        if "umc" in name:
            score += 100
        if "behringer" in name:
            score += 80
        return score if score else -1000
    if any(term in name for term in umc_terms):
        return -1000
    score = 0
    if "speakers" in name or "skalruni" in name:
        score += 200
    if "realtek" in name:
        score += 100
    if "high definition audio" in name:
        score += 60
    if "speaker" in name:
        score += 35
    return score if score else -1000

def _ls_audio_output_powershell_path():
    candidates = [
        shutil.which("powershell.exe"),
        shutil.which("pwsh.exe"),
        str(
            Path(os.environ.get("SystemRoot", r"C:\\Windows")) /
            "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        ),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return ""

def _ensure_ls_audio_output_helper():
    expected = LS_AUDIO_OUTPUT_POWERSHELL.replace("\r\n", "\n")
    try:
        current = LS_AUDIO_OUTPUT_HELPER_PATH.read_text(
            encoding="utf-8", errors="replace"
        ).replace("\r\n", "\n").lstrip("\ufeff")
    except Exception:
        current = ""
    if current == expected:
        return LS_AUDIO_OUTPUT_HELPER_PATH
    LS_AUDIO_OUTPUT_HELPER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = LS_AUDIO_OUTPUT_HELPER_PATH.with_suffix(".tmp")
    temp_path.write_text(expected, encoding="utf-8-sig")
    temp_path.replace(LS_AUDIO_OUTPUT_HELPER_PATH)
    return LS_AUDIO_OUTPUT_HELPER_PATH

def _run_ls_audio_output_helper(action="state", device_id=""):
    if os.name != "nt":
        return {
            "ok": False,
            "error": "Windows audio izejas pārslēgšana ir pieejama tikai Windows vidē.",
            "devices": [],
        }
    powershell_path = _ls_audio_output_powershell_path()
    if not powershell_path:
        return {"ok": False, "error": "Windows PowerShell netika atrasts.", "devices": []}
    helper_path = _ensure_ls_audio_output_helper()
    command = [
        powershell_path, "-NoLogo", "-NoProfile", "-NonInteractive",
        "-WindowStyle", "Hidden",
        "-ExecutionPolicy", "Bypass", "-File", str(helper_path),
        "-Action", str(action or "state"),
    ]
    if device_id:
        command.extend(["-DeviceId", str(device_id)])
    try:
        audio_startupinfo = None
        if os.name == "nt":
            audio_startupinfo = subprocess.STARTUPINFO()
            audio_startupinfo.dwFlags |= getattr(
                subprocess, "STARTF_USESHOWWINDOW", 0
            )
            audio_startupinfo.wShowWindow = 0
        result = subprocess.run(
            command,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            startupinfo=audio_startupinfo,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Windows audio izejas pārbaude pārsniedza laika limitu.", "devices": []}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "devices": []}
    payload = None
    for line in reversed((result.stdout or "").splitlines()):
        line = line.strip().lstrip("\ufeff")
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(payload, dict):
        detail = (result.stderr or result.stdout or "").strip()
        return {
            "ok": False,
            "error": detail[:500] or "Windows audio izejas stāvokli neizdevās nolasīt.",
            "devices": [],
        }
    return payload

def _normalize_ls_audio_output_devices(raw_devices):
    """Normalize PowerShell endpoint JSON, including one-item array collapse."""
    if isinstance(raw_devices, str):
        try:
            raw_devices = json.loads(raw_devices)
        except Exception:
            raw_devices = []
    if isinstance(raw_devices, dict):
        if any(key in raw_devices for key in ("Id", "id", "Name", "name")):
            raw_devices = [raw_devices]
        else:
            raw_devices = raw_devices.get("devices") or raw_devices.get("value") or []
            if isinstance(raw_devices, dict):
                raw_devices = [raw_devices]
    if not isinstance(raw_devices, (list, tuple)):
        raw_devices = []

    result = []
    seen = set()
    for item in raw_devices:
        if not isinstance(item, dict):
            continue
        device_id = str(item.get("Id") or item.get("id") or "").strip()
        name = str(item.get("Name") or item.get("name") or device_id).strip()
        key = device_id.casefold()
        if not device_id or key in seen:
            continue
        seen.add(key)
        result.append({
            "id": device_id,
            "name": name or device_id,
            "is_default": bool(item.get("IsDefault") or item.get("is_default")),
        })
    return result

def _choose_ls_audio_output_device(devices, role, configured_id=""):
    configured_key = str(configured_id or "").strip().casefold()
    if configured_key:
        for device in devices:
            if str(device.get("id") or "").casefold() == configured_key:
                return device
    scored = [(_ls_audio_output_score(device, role), device) for device in devices]
    scored = [item for item in scored if item[0] > 0]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], _ls_audio_output_fold(item[1].get("name"))))
    return scored[0][1]

def _ls_audio_output_find_by_id(devices, device_id):
    wanted = str(device_id or "").strip().casefold()
    if not wanted:
        return None
    return next(
        (
            device for device in devices
            if str(device.get("id") or "").strip().casefold() == wanted
        ),
        None,
    )

def get_ls_audio_output_state(force=False):
    now = time.monotonic()
    with LS_AUDIO_OUTPUT_LOCK:
        cached_payload = LS_AUDIO_OUTPUT_CACHE.get("payload")
        cached_at = float(LS_AUDIO_OUTPUT_CACHE.get("updated_at") or 0.0)
        if not force and isinstance(cached_payload, dict) and now - cached_at < 2.0:
            return dict(cached_payload)
        raw = _run_ls_audio_output_helper("state")
        if not raw.get("ok"):
            payload = {
                "ok": False,
                "available": False,
                "can_toggle": False,
                "mode": "unknown",
                "devices": [],
                "error": str(
                    raw.get("error") or "Audio izejas stāvoklis nav pieejams."
                ),
            }
            LS_AUDIO_OUTPUT_CACHE.update({"updated_at": now, "payload": payload})
            return dict(payload)

        devices = _normalize_ls_audio_output_devices(raw.get("devices"))
        if not devices:
            payload = {
                "ok": False,
                "available": False,
                "can_toggle": False,
                "mode": "unknown",
                "devices": [],
                "error": (
                    "Windows neizdevās nolasīt nevienu aktīvu atskaņošanas "
                    "ierīci. Pārbaudi Windows Sound > Output un atver Settings vēlreiz."
                ),
            }
            LS_AUDIO_OUTPUT_CACHE.update({"updated_at": now, "payload": payload})
            return dict(payload)
        settings = get_settings()
        configured_speakers_id = str(
            settings.get("audio_output_speakers_id") or ""
        ).strip()
        configured_headphones_id = str(
            settings.get("audio_output_headphones_id") or ""
        ).strip()
        speakers = _ls_audio_output_find_by_id(
            devices, configured_speakers_id
        )
        headphones = _ls_audio_output_find_by_id(
            devices, configured_headphones_id
        )
        suggested_speakers = _choose_ls_audio_output_device(
            devices, "speakers", ""
        )
        suggested_headphones = _choose_ls_audio_output_device(
            devices, "headphones", ""
        )
        current = next(
            (device for device in devices if device.get("is_default")),
            None,
        )
        current_id = str((current or {}).get("id") or "")

        if (
            headphones and
            current_id.casefold() == str(headphones.get("id") or "").casefold()
        ):
            mode, target = "headphones", speakers
        elif (
            speakers and
            current_id.casefold() == str(speakers.get("id") or "").casefold()
        ):
            mode, target = "speakers", headphones
        else:
            mode, target = "other", headphones or speakers

        can_toggle = bool(
            current and speakers and headphones and
            str(speakers.get("id") or "").casefold() !=
            str(headphones.get("id") or "").casefold()
        )
        missing = []
        if not configured_speakers_id:
            missing.append("Settings nav izvēlēta skaļruņu izeja")
        elif not speakers:
            missing.append("izvēlētā skaļruņu izeja nav pieejama")
        if not configured_headphones_id:
            missing.append("Settings nav izvēlēta austiņu izeja")
        elif not headphones:
            missing.append("izvēlētā austiņu izeja nav pieejama")

        payload = {
            "ok": True,
            "available": True,
            "can_toggle": can_toggle,
            "mode": mode,
            "current_name": str((current or {}).get("name") or "Nav noteikts"),
            "current_id": current_id,
            "devices": devices,
            "speakers_id": configured_speakers_id,
            "headphones_id": configured_headphones_id,
            "speakers_name": str((speakers or {}).get("name") or ""),
            "headphones_name": str((headphones or {}).get("name") or ""),
            "suggested_speakers_id": str(
                (suggested_speakers or {}).get("id") or ""
            ),
            "suggested_headphones_id": str(
                (suggested_headphones or {}).get("id") or ""
            ),
            "target_name": str((target or {}).get("name") or ""),
            "target_id": str((target or {}).get("id") or ""),
            "error": "; ".join(missing) + "." if missing else "",
        }
        LS_AUDIO_OUTPUT_CACHE.update({"updated_at": now, "payload": payload})
        return dict(payload)

def set_ls_audio_output_devices(speakers_id, headphones_id):
    speakers_id = str(speakers_id or "").strip()
    headphones_id = str(headphones_id or "").strip()
    if not speakers_id or not headphones_id:
        return {
            "ok": False,
            "error": "Izvēlies gan skaļruņu, gan austiņu Windows audio izeju.",
        }
    if speakers_id.casefold() == headphones_id.casefold():
        return {
            "ok": False,
            "error": "Skaļruņu un austiņu izejai jābūt atšķirīgām.",
        }

    raw = _run_ls_audio_output_helper("state")
    if not raw.get("ok"):
        return {
            "ok": False,
            "error": str(raw.get("error") or "Audio izejas nav pieejamas."),
        }
    devices = _normalize_ls_audio_output_devices(raw.get("devices"))
    speakers = _ls_audio_output_find_by_id(devices, speakers_id)
    headphones = _ls_audio_output_find_by_id(devices, headphones_id)
    if not speakers or not headphones:
        return {
            "ok": False,
            "error": "Viena no izvēlētajām Windows audio izejām vairs nav pieejama.",
        }

    save_settings({
        "audio_output_speakers_id": str(speakers.get("id") or ""),
        "audio_output_headphones_id": str(headphones.get("id") or ""),
    })
    LS_AUDIO_OUTPUT_CACHE.update({"updated_at": 0.0, "payload": None})
    payload = get_ls_audio_output_state(force=True)
    payload["saved"] = True
    return payload

def toggle_ls_audio_output():
    with LS_AUDIO_OUTPUT_LOCK:
        cached_payload = LS_AUDIO_OUTPUT_CACHE.get("payload")
        state = dict(cached_payload) if isinstance(cached_payload, dict) else {}
        if not state.get("ok") or not state.get("can_toggle"):
            state = get_ls_audio_output_state(force=True)
        if not state.get("ok") or not state.get("can_toggle"):
            return state

        target_id = str(state.get("target_id") or "").strip()
        if not target_id:
            return {
                **state, "ok": False, "can_toggle": False,
                "error": "Pārslēgšanas mērķa audio izeja nav atrasta.",
            }

        result = _run_ls_audio_output_helper("set", target_id)
        if not result.get("ok"):
            return {
                **state, "ok": False,
                "error": str(result.get("error") or "Audio izeju neizdevās pārslēgt."),
            }

        confirmed_id = str(result.get("default_id") or "").strip()
        if confirmed_id and confirmed_id.casefold() != target_id.casefold():
            return {
                **state,
                "ok": False,
                "error": "Windows neapstiprināja izvēlētās audio izejas aktivizēšanu.",
            }

        speakers_id = str(state.get("speakers_id") or "").strip()
        headphones_id = str(state.get("headphones_id") or "").strip()
        switched_to_headphones = (
            target_id.casefold() == headphones_id.casefold()
        )
        current_name = str((
            state.get("headphones_name") if switched_to_headphones
            else state.get("speakers_name")
        ) or "Nav noteikts")
        next_target_id = speakers_id if switched_to_headphones else headphones_id
        next_target_name = str((
            state.get("speakers_name") if switched_to_headphones
            else state.get("headphones_name")
        ) or "")
        refreshed = {
            **state,
            "ok": True,
            "available": True,
            "can_toggle": True,
            "mode": "headphones" if switched_to_headphones else "speakers",
            "current_id": target_id,
            "current_name": current_name,
            "target_id": next_target_id,
            "target_name": next_target_name,
            "error": "",
        }
        LS_AUDIO_OUTPUT_CACHE.update({
            "updated_at": time.monotonic(),
            "payload": refreshed,
        })
        return dict(refreshed)




















def find_ffmpeg_exe():
    for candidate in FFMPEG_CANDIDATES:
        if str(candidate).lower() == "ffmpeg":
            return "ffmpeg"
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return "ffmpeg"


def _browser_safe_local_audio_cache_key(source_path):
    source = Path(source_path).resolve()
    stat = source.stat()
    identity = f"{source}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha256(identity.encode("utf-8", errors="surrogatepass")).hexdigest()


def _is_browser_safe_pcm16_wav(path):
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file() or candidate.stat().st_size <= 44:
        return False
    try:
        with wave.open(str(candidate), "rb") as wav_file:
            return (
                wav_file.getcomptype() == "NONE"
                and wav_file.getsampwidth() == 2
                and wav_file.getframerate() == 48000
                and wav_file.getnchannels() == 2
            )
    except (wave.Error, EOFError, OSError):
        return False


def ensure_browser_safe_local_audio(local_path):
    """Return a cached PCM16/48kHz/stereo WAV suitable for browser playback.

    The original linked audio is never modified. The cache key includes source path,
    size and mtime so a changed source automatically produces a fresh cache file.
    """
    source = Path(str(local_path or "").strip().strip('"'))
    if not source.exists() or not source.is_file():
        raise FileNotFoundError("Local audio file not found")

    # Canonical local media may already be in the exact browser-safe LS format.
    # In that case serve the linked source directly; do not invoke ffmpeg or
    # create a redundant cache copy.
    if _is_browser_safe_pcm16_wav(source):
        return str(source)

    cache_dir = Path(LOCAL_BROWSER_AUDIO_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = _browser_safe_local_audio_cache_key(source)
    target = cache_dir / f"{cache_key}.wav"
    if _is_browser_safe_pcm16_wav(target):
        return str(target)

    fd, temp_name = tempfile.mkstemp(
        prefix=f"{cache_key}.",
        suffix=".part.wav",
        dir=str(cache_dir),
    )
    os.close(fd)
    temp_target = Path(temp_name)
    try:
        temp_target.unlink(missing_ok=True)
        command = [
            find_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(temp_target),
        ]

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = 0

        subprocess.run(
            command,
            cwd=BASE_DIR,
            timeout=300,
            check=True,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            startupinfo=startupinfo,
        )
        if not _is_browser_safe_pcm16_wav(temp_target):
            raise RuntimeError("ffmpeg did not create browser-safe PCM16 WAV")
        os.replace(str(temp_target), str(target))
        return str(target)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Local audio conversion timed out") from exc
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(error or "Local audio conversion failed") from exc
    except FileNotFoundError as exc:
        if source.exists():
            raise RuntimeError("ffmpeg not found") from exc
        raise
    finally:
        try:
            temp_target.unlink(missing_ok=True)
        except OSError:
            pass

def waveform_cache_key(track_id, audio_url):
    return waveform_cache_name(track_id, audio_url)

def generate_waveform_bytes(track_id, audio_url):
    """Generate a waveform PNG in memory and return bytes.

    v4.05 no longer writes waveform PNG previews to the waveforms folder.
    The PNG is cached only in process memory for the current LocalSunoDb run.
    First open may still take a moment because ffmpeg must read the audio,
    but reopening the same waveform in the same run is instant.
    """
    if not audio_url:
        return None, "Missing audio URL"

    key = waveform_cache_key(track_id, audio_url)
    cached = WAVEFORM_MEMORY_CACHE.get(key)
    if cached:
        return cached, ""

    command = [
        find_ffmpeg_exe(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        audio_url,
        "-filter_complex",
        "aformat=channel_layouts=mono,showwavespic=s=1200x160:colors=0047c7:scale=sqrt",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-",
    ]

    try:
        waveform_startupinfo = None
        if os.name == "nt":
            waveform_startupinfo = subprocess.STARTUPINFO()
            waveform_startupinfo.dwFlags |= getattr(
                subprocess, "STARTF_USESHOWWINDOW", 0
            )
            waveform_startupinfo.wShowWindow = 0
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            timeout=60,
            check=True,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            startupinfo=waveform_startupinfo,
        )
    except subprocess.TimeoutExpired:
        return None, "ffmpeg timeout"
    except subprocess.CalledProcessError as e:
        error = (e.stderr or b"").decode("utf-8", errors="replace").strip() or "ffmpeg failed"
        return None, error
    except FileNotFoundError:
        return None, "ffmpeg not found"

    png_data = result.stdout or b""
    if not png_data:
        return None, "waveform PNG was not created"

    WAVEFORM_MEMORY_CACHE[key] = png_data
    return png_data, ""

def send_no_content(handler):
    handler.send_response(204)
    handler.end_headers()

def focus_windows_by_title(
    title_parts=None,
    class_names=None,
    timeout=2.0,
    topmost_seconds=0.0,
):
    """Best-effort: raise a matching Windows window, optionally with a short topmost pulse."""
    if os.name != "nt":
        return False

    title_parts = [str(x).lower() for x in (title_parts or []) if str(x).strip()]
    class_names = [str(x).lower() for x in (class_names or []) if str(x).strip()]

    if not title_parts and not class_names:
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        IsWindowVisible = user32.IsWindowVisible
        GetWindowTextW = user32.GetWindowTextW
        GetWindowTextLengthW = user32.GetWindowTextLengthW
        GetClassNameW = user32.GetClassNameW
        ShowWindow = user32.ShowWindow
        SetForegroundWindow = user32.SetForegroundWindow
        BringWindowToTop = user32.BringWindowToTop
        SetWindowPos = user32.SetWindowPos
        SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        SetWindowPos.restype = wintypes.BOOL
        AttachThreadInput = user32.AttachThreadInput
        GetForegroundWindow = user32.GetForegroundWindow
        GetWindowThreadProcessId = user32.GetWindowThreadProcessId
        GetCurrentThreadId = kernel32.GetCurrentThreadId

        SW_RESTORE = 9
        SW_SHOW = 5
        HWND_TOPMOST = ctypes.c_void_p(-1)
        HWND_NOTOPMOST = ctypes.c_void_p(-2)
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040

        deadline = time.time() + timeout
        found_hwnd = None

        while time.time() < deadline and not found_hwnd:
            matches = []

            def enum_proc(hwnd, lparam):
                if not IsWindowVisible(hwnd):
                    return True

                length = GetWindowTextLengthW(hwnd)
                title_buffer = ctypes.create_unicode_buffer(length + 1)
                GetWindowTextW(hwnd, title_buffer, length + 1)
                title = (title_buffer.value or "").lower()

                class_buffer = ctypes.create_unicode_buffer(256)
                GetClassNameW(hwnd, class_buffer, 256)
                class_name = (class_buffer.value or "").lower()

                title_ok = any(part in title for part in title_parts) if title_parts else False
                class_ok = class_name in class_names if class_names else False

                if title_ok or class_ok:
                    matches.append(hwnd)

                return True

            EnumWindows(EnumWindowsProc(enum_proc), 0)

            if matches:
                found_hwnd = matches[0]
                break

            time.sleep(0.12)

        if not found_hwnd:
            return False

        pulse_seconds = max(0.0, float(topmost_seconds or 0.0))
        if pulse_seconds > 0:
            SetWindowPos(
                found_hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
            )

            def release_topmost():
                time.sleep(pulse_seconds)
                try:
                    SetWindowPos(
                        found_hwnd,
                        HWND_NOTOPMOST,
                        0,
                        0,
                        0,
                        0,
                        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
                    )
                except Exception:
                    pass

            threading.Thread(
                target=release_topmost,
                name="ls-update-release-topmost",
                daemon=True,
            ).start()

        # Preserve a visible window's current normal/maximized state.
        # SW_RESTORE would shrink a maximized Chrome window to its normal size.
        if user32.IsIconic(found_hwnd):
            ShowWindow(found_hwnd, SW_RESTORE)
        elif not IsWindowVisible(found_hwnd):
            ShowWindow(found_hwnd, SW_SHOW)
        BringWindowToTop(found_hwnd)

        # Try the normal way first.
        if SetForegroundWindow(found_hwnd):
            return True

        # Then try a stronger, but still standard, foreground handoff.
        current_thread = GetCurrentThreadId()
        foreground_hwnd = GetForegroundWindow()
        foreground_thread = GetWindowThreadProcessId(foreground_hwnd, None) if foreground_hwnd else 0
        target_thread = GetWindowThreadProcessId(found_hwnd, None)

        if foreground_thread:
            AttachThreadInput(current_thread, foreground_thread, True)
        if target_thread:
            AttachThreadInput(current_thread, target_thread, True)

        try:
            if user32.IsIconic(found_hwnd):
                ShowWindow(found_hwnd, SW_RESTORE)
            elif not IsWindowVisible(found_hwnd):
                ShowWindow(found_hwnd, SW_SHOW)
            BringWindowToTop(found_hwnd)
            SetForegroundWindow(found_hwnd)
        finally:
            if target_thread:
                AttachThreadInput(current_thread, target_thread, False)
            if foreground_thread:
                AttachThreadInput(current_thread, foreground_thread, False)

        return True

    except Exception:
        return False


def find_audio_editor():
    for path in AUDIO_EDITOR_CANDIDATES:
        if path.exists():
            return path
    return None

def open_file_in_audio_editor(local_path):
    """Open a local WAV in Audacity if available; otherwise reveal it in Explorer."""
    local_path = str(local_path)
    path_obj = Path(local_path)

    editor = find_audio_editor()

    if editor:
        subprocess.Popen([str(editor), local_path])
        focus_windows_by_title(
            title_parts=[
                path_obj.stem,
                path_obj.name,
                "audacity",
            ],
            class_names=[],
            timeout=2.5,
        )
    else:
        reveal_file_in_explorer(local_path)

def open_file_with_default_app(local_path):
    """Open a local file and try to focus the player app."""
    local_path = str(local_path)
    path_obj = Path(local_path)

    os.startfile(local_path)

    focus_windows_by_title(
        title_parts=[
            path_obj.stem,
            path_obj.name,
            "musicbee",
            "music bee",
            "media player",
            "windows media player",
            "groove",
        ],
        class_names=[],
        timeout=2.5,
    )

def safe_filename_part(value, max_length=70):
    text = str(value or "").strip()
    text = re.sub(r'[<>:"/\\|?*]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" ._")

    if not text:
        text = "suno_audio"

    return text[:max_length].strip(" ._") or "suno_audio"

def extract_suno_page_image_url(track_id):
    """Best-effort: fetch the public Suno song page and extract its cover image URL."""
    track_id = str(track_id or "").strip()

    if not track_id:
        return ""

    page_url = f"https://suno.com/song/{urllib.parse.quote(track_id)}"
    request = urllib.request.Request(
        page_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        html_text = response.read().decode("utf-8", errors="ignore")

    patterns = [
        r'<meta[^>]+property=["\\\']og:image["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
        r'<meta[^>]+content=["\\\']([^"\\\']+)["\\\'][^>]+property=["\\\']og:image["\\\']',
        r'https://cdn[12]\.suno\.ai/[^"\\\'<> ]*image[^"\\\'<> ]*',
        r'https://cdn[12]\.suno\.ai/[^"\\\'<> ]*%s[^"\\\'<> ]*' % re.escape(track_id),
    ]

    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1) if match.lastindex else match.group(0)
            candidate = html.unescape(candidate).strip()
            if candidate.startswith("http"):
                return candidate

    return ""

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def reveal_file_in_explorer(local_path):
    """Open Explorer with the exact file selected, then try to focus Explorer."""
    local_path = str(local_path)
    path_obj = Path(local_path)

    # This form is more reliable than passing /select with embedded quotes in an argv list.
    subprocess.Popen(f'explorer.exe /select,"{local_path}"', shell=False)

    focus_windows_by_title(
        title_parts=[path_obj.parent.name, path_obj.name, path_obj.stem],
        class_names=["cabinetwclass", "explorewclass"],
        timeout=2.5,
    )

