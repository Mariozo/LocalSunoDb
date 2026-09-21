"""Runtime composition with explicit one-way block boundaries.

The legacy monolith referenced top-level functions by name.  The architecture
reform preserves those call contracts without circular imports by wiring only
symbols from dependencies explicitly allowed for each block.  Private names
(`_name`) never cross a block boundary.
"""
from collections import defaultdict

_RUNTIME_MODULES = []
_EXTERNAL_SYMBOLS = {}

_BLOCK_BY_PACKAGE = {
    "ls_core": "CORE",
    "ls_data": "DATA",
    "ls_suno": "SUNO",
    "ls_audio": "AUDIO",
    "ls_library": "LIBRARY",
    "ls_player": "PLAYER",
    "ls_stems": "STEMS",
    "ls_downloader": "DOWNLOADER",
    "ls_tools": "TOOLS",
    "ls_web": "WEB",
}

_ALLOWED_BLOCKS = {
    "CORE": {"CORE"},
    "DATA": {"CORE", "DATA"},
    "SUNO": {"CORE", "DATA", "SUNO"},
    "AUDIO": {"CORE", "DATA", "AUDIO"},
    "LIBRARY": {"CORE", "DATA", "LIBRARY"},
    "PLAYER": {"CORE", "DATA", "AUDIO", "PLAYER"},
    "STEMS": {"CORE", "DATA", "AUDIO", "STEMS"},
    "DOWNLOADER": {"CORE", "DATA", "SUNO", "AUDIO", "DOWNLOADER"},
    "TOOLS": {"CORE", "DATA", "SUNO", "AUDIO", "TOOLS"},
    "WEB": {"CORE", "DATA", "SUNO", "AUDIO", "LIBRARY", "PLAYER", "STEMS", "DOWNLOADER", "TOOLS", "WEB"},
}

_IGNORED_EXPORTS = {
    "base64", "difflib", "hashlib", "importlib", "socket", "threading",
    "html", "json", "os", "shutil", "mimetypes", "re", "sqlite3",
    "subprocess", "sys", "tempfile", "time", "traceback", "urllib",
    "unicodedata", "warnings", "webbrowser", "zipfile", "datetime",
    "timezone", "BaseHTTPRequestHandler", "ThreadingHTTPServer", "Path",
    "PurePosixPath", "types", "defaultdict",
}


def module_block(module):
    package = str(getattr(module, "__name__", "")).split(".", 1)[0]
    return _BLOCK_BY_PACKAGE.get(package, "WEB")


def _exports(module):
    result = {}
    for name, value in vars(module).items():
        if name.startswith("__") or name in _IGNORED_EXPORTS:
            continue
        result[name] = value
    return result


def wire_runtime(modules, external_symbols=None):
    """Wire only dependency-approved public interfaces into each module."""
    global _RUNTIME_MODULES, _EXTERNAL_SYMBOLS
    _RUNTIME_MODULES = list(modules)
    _EXTERNAL_SYMBOLS = dict(external_symbols or {})

    exports_by_block = defaultdict(dict)
    flat_registry = {}
    duplicates = set()
    for module in modules:
        block = module_block(module)
        for name, value in _exports(module).items():
            exports_by_block[block].setdefault(name, value)
            if name in flat_registry and flat_registry[name] is not value:
                duplicates.add(name)
            else:
                flat_registry.setdefault(name, value)

    for module in modules:
        target_block = module_block(module)
        namespace = vars(module)
        for source_block in _ALLOWED_BLOCKS.get(target_block, {target_block}):
            for name, value in exports_by_block.get(source_block, {}).items():
                if name.startswith("_") and source_block != target_block:
                    continue
                # Never guess between same-named APIs from different blocks.
                if name in duplicates and name not in namespace:
                    continue
                namespace.setdefault(name, value)
        if target_block == "WEB":
            for name, value in _EXTERNAL_SYMBOLS.items():
                namespace[name] = value

    flat_registry.update(_EXTERNAL_SYMBOLS)
    return flat_registry


def refresh_symbol(name, value):
    """Refresh a public external adapter only where external adapters are legal."""
    _EXTERNAL_SYMBOLS[name] = value
    for module in _RUNTIME_MODULES:
        if module_block(module) == "WEB":
            vars(module)[name] = value
