"""Side-effect-free runtime probe used by the LS Upgrade preflight."""
from __future__ import annotations

import builtins
import dis
import importlib
import inspect
import json
from pathlib import Path

from ls_core.runtime import APP_BASED_ON, APP_DIR, APP_ENTRYPOINT_PATH, APP_VERSION, LS_UPDATE_PROBE_MARKER


def _manifest():
    with (APP_DIR / "ls_architecture_manifest.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _module_names_from_manifest(manifest):
    names = set()
    for block in manifest.get("blocks", []):
        if block.get("external_optional"):
            continue
        for pattern in block.get("python_globs", []):
            if pattern == manifest.get("app", {}).get("entrypoint"):
                continue
            prefix = pattern.split("/", 1)[0]
            if not prefix.startswith("ls_"):
                continue
            for path in APP_DIR.glob(pattern):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                relative = path.relative_to(APP_DIR).with_suffix("")
                parts = list(relative.parts)
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                if parts:
                    names.add(".".join(parts))
    return sorted(names)


def _runtime_unresolved_globals(module_names):
    failures = []
    seen = set()
    for module_name in module_names:
        module = importlib.import_module(module_name)
        candidates = []
        for name, value in vars(module).items():
            if inspect.isfunction(value) and getattr(value, "__module__", None) == module.__name__:
                candidates.append((name, value))
            elif inspect.isclass(value) and getattr(value, "__module__", None) == module.__name__:
                for method_name, method in vars(value).items():
                    if inspect.isfunction(method):
                        candidates.append((f"{name}.{method_name}", method))
        for callable_name, function in candidates:
            namespace = function.__globals__
            for instruction in dis.get_instructions(function):
                if instruction.opname not in {"LOAD_GLOBAL", "LOAD_NAME"}:
                    continue
                symbol = instruction.argval
                if symbol in namespace or hasattr(builtins, symbol):
                    continue
                key = (module.__name__, callable_name, symbol)
                if key in seen:
                    continue
                seen.add(key)
                failures.append(f"unresolved runtime global {module.__name__}.{callable_name}: {symbol}")
    return failures


def run_startup_probe():
    failures = []
    imported = []
    try:
        manifest = _manifest()
    except Exception as exc:
        manifest = {}
        failures.append(f"architecture manifest: {exc}")

    if manifest:
        app = manifest.get("app", {})
        if app.get("version") != APP_VERSION:
            failures.append(f"manifest version {app.get('version')!r} != {APP_VERSION!r}")
        if app.get("based_on") != APP_BASED_ON:
            failures.append(f"manifest based_on {app.get('based_on')!r} != {APP_BASED_ON!r}")
        if app.get("entrypoint") != Path(APP_ENTRYPOINT_PATH).name:
            failures.append("manifest entrypoint mismatch")
        module_names = _module_names_from_manifest(manifest)
        for name in module_names:
            try:
                importlib.import_module(name)
                imported.append(name)
            except Exception as exc:
                failures.append(f"import {name}: {type(exc).__name__}: {exc}")
        failures.extend(_runtime_unresolved_globals(module_names))

    required_blocks = {
        "CORE", "DATA", "SUNO", "AUDIO", "LIBRARY", "MEDIA", "PLAYER",
        "STEMS", "DOWNLOADER", "TOOLS", "WEB", "ELZA", "UPGRADE", "MAIN",
    }
    block_ids = {b.get("id") for b in manifest.get("blocks", [])}
    missing_blocks = sorted(required_blocks - block_ids)
    if missing_blocks:
        failures.append("missing architecture blocks: " + ", ".join(missing_blocks))

    return {
        "ok": not failures,
        "marker": LS_UPDATE_PROBE_MARKER,
        "app_version": APP_VERSION,
        "app_file": Path(APP_ENTRYPOINT_PATH).name,
        "app_path": str(Path(APP_ENTRYPOINT_PATH).resolve()),
        "based_on": APP_BASED_ON,
        "runtime_contract": {
            "manifest_schema": manifest.get("schema_version"),
            "block_count": len(manifest.get("blocks", [])),
            "missing_blocks": missing_blocks,
        },
        "imports": {
            "ok": not any(item.startswith("import ") for item in failures),
            "count": len(imported),
        },
        "failures": failures,
    }


def run_ls_update_safety_probe():
    return run_startup_probe()
