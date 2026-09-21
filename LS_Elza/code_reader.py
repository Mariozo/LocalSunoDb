# LS Elza - read-only LocalSunoDb modular source inspector
# Created: 13.jul.2026 15:26
# Modified: 11.aug.2026
# Purpose: Inspect the currently running modular LocalSunoDb source safely
# ver. 2.0

from __future__ import annotations

import ast
import re
import threading
from pathlib import Path

from .host_paths import APP_ROOT, HOST_ROOT

BASE_DIR = APP_ROOT
APP_FILENAME_PATTERN = re.compile(r"^LocalSunoDb\.py$", re.IGNORECASE)
ALLOWED_SOURCE_SUFFIXES = {".py", ".html", ".htm", ".css", ".js", ".json", ".md", ".txt"}
EXCLUDED_PARTS = {
    "__pycache__", ".git", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".ls_update_transaction", "Backup", "Backups", "Logs", "Data", "Reports",
    "exports", "edit_cache",
}
MAX_SOURCE_BYTES = 3_000_000
MAX_TOTAL_SEARCH_BYTES = 14_000_000
MAX_SEARCH_FILES = 300
MAX_QUERY_CHARS = 160
MAX_SEARCH_RESULTS = 20
MAX_SEARCH_CONTEXT_LINES = 6
MAX_READ_LINES = 180
MAX_FUNCTION_LINES = 240
MAX_STRUCTURE_ITEMS = 240

_SOURCE_LOCK = threading.RLock()
_APP_SOURCE_PATH = None


class LSElzaCodeReadOnlyError(RuntimeError):
    def __init__(self, message, code="code_readonly_error"):
        super().__init__(message)
        self.code = str(code or "code_readonly_error")


def _clean_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) > int(max_chars):
        text = text[: int(max_chars)].rstrip()
    return text


def _bounded_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(int(minimum), min(number, int(maximum)))


def _require_arguments(arguments, allowed):
    if arguments is None:
        return {}
    if not isinstance(arguments, dict):
        raise LSElzaCodeReadOnlyError(
            "Code-reader arguments must be a JSON object.",
            code="invalid_arguments",
        )
    unexpected = sorted(set(arguments) - set(allowed))
    if unexpected:
        raise LSElzaCodeReadOnlyError(
            "Unsupported code-reader arguments: " + ", ".join(unexpected),
            code="unsupported_arguments",
        )
    return arguments


def configure_app_source(path):
    """Bind the inspector to one exact running LS entrypoint."""
    candidate = Path(path).expanduser().resolve()
    if candidate.parent != APP_ROOT.resolve():
        raise LSElzaCodeReadOnlyError(
            "The app source must be in the LocalSunoDb installation folder.",
            code="source_outside_app_folder",
        )
    if not APP_FILENAME_PATTERN.fullmatch(candidate.name):
        raise LSElzaCodeReadOnlyError(
            "The app source filename is not an allowed LocalSunoDb version file.",
            code="source_filename_not_allowed",
        )
    _validate_file(candidate)
    global _APP_SOURCE_PATH
    with _SOURCE_LOCK:
        _APP_SOURCE_PATH = candidate
    return {
        "configured": True,
        "file_name": candidate.name,
        "source_root": str(APP_ROOT),
        "modular_source": True,
        "read_only": True,
    }


def _configured_source_path():
    with _SOURCE_LOCK:
        path = _APP_SOURCE_PATH
    if path is None:
        raise LSElzaCodeReadOnlyError(
            "The running LocalSunoDb source has not been configured.",
            code="source_not_configured",
        )
    candidate = Path(path).resolve()
    if candidate.parent != APP_ROOT.resolve() or not APP_FILENAME_PATTERN.fullmatch(candidate.name):
        raise LSElzaCodeReadOnlyError(
            "The configured source is no longer allowed.",
            code="source_not_allowed",
        )
    _validate_file(candidate)
    return candidate


def _validate_file(path: Path):
    if not path.is_file():
        raise LSElzaCodeReadOnlyError(
            "The requested LocalSunoDb source file was not found.",
            code="source_not_found",
        )
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise LSElzaCodeReadOnlyError(
            "The requested source file exceeds the safe read limit.",
            code="source_too_large",
        )


def _is_allowed_source_path(path: Path) -> bool:
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(APP_ROOT.resolve())
    except Exception:
        return False
    if not resolved.is_file() or resolved.suffix.lower() not in ALLOWED_SOURCE_SUFFIXES:
        return False
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if resolved.stat().st_size > MAX_SOURCE_BYTES:
        return False
    parts = relative.parts
    if len(parts) == 1:
        return (
            APP_FILENAME_PATTERN.fullmatch(resolved.name) is not None
            or resolved.name.startswith("ls_")
        )
    first = parts[0]
    return first.startswith("ls_") or first == "LS_Elza"


def _source_files(python_only=False):
    configured = _configured_source_path()
    result = [configured]
    seen = {configured.resolve()}
    total_bytes = configured.stat().st_size
    for path in sorted(APP_ROOT.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if len(result) >= MAX_SEARCH_FILES or total_bytes >= MAX_TOTAL_SEARCH_BYTES:
            break
        if not _is_allowed_source_path(path):
            continue
        if python_only and path.suffix.lower() != ".py":
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        size = resolved.stat().st_size
        if total_bytes + size > MAX_TOTAL_SEARCH_BYTES:
            continue
        result.append(resolved)
        seen.add(resolved)
        total_bytes += size
    return result


def _relative_name(path: Path) -> str:
    return path.resolve().relative_to(APP_ROOT.resolve()).as_posix()


def _resolve_requested_file(file_name="") -> Path:
    clean = _clean_text(file_name, 300).replace("\\", "/").lstrip("/")
    if not clean:
        return _configured_source_path()
    candidate = (APP_ROOT / clean).resolve()
    if not _is_allowed_source_path(candidate):
        raise LSElzaCodeReadOnlyError(
            "The requested source file is outside the LS read-only source allowlist.",
            code="source_not_allowed",
        )
    return candidate


_SECRET_PATTERNS = [
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)(Authorization\s*[:=]\s*Bearer\s+)[^\s\"']+"),
    re.compile(r"(?i)(api_key\s*=\s*[\"'])[^\"']+([\"'])"),
    re.compile(r"(?i)(OPENAI_API_KEY\s*[:=]\s*)[^\s,;\"']+"),
]


def _redact_line(value):
    text = str(value or "")
    text = _SECRET_PATTERNS[0].sub("[REDACTED_OPENAI_KEY]", text)
    text = _SECRET_PATTERNS[1].sub(r"\1[REDACTED_TOKEN]", text)
    text = _SECRET_PATTERNS[2].sub(r"\1[REDACTED]\2", text)
    text = _SECRET_PATTERNS[3].sub(r"\1[REDACTED]", text)
    return text


def _read_source(file_name=""):
    path = _resolve_requested_file(file_name)
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise LSElzaCodeReadOnlyError(
            "The LocalSunoDb source could not be read.",
            code="source_read_failed",
        ) from error
    return path, source, source.splitlines()


def _line_block(lines, start_line, end_line):
    start = max(1, int(start_line))
    end = min(len(lines), int(end_line))
    return [
        {"line": number, "text": _redact_line(lines[number - 1])}
        for number in range(start, end + 1)
    ]


def code_search(query, match_mode="literal", context_lines=3, limit=12):
    query = _clean_text(query, MAX_QUERY_CHARS)
    if not query:
        raise LSElzaCodeReadOnlyError(
            "A non-empty code search query is required.",
            code="missing_query",
        )
    mode = _clean_text(match_mode, 40).lower() or "literal"
    if mode not in {"literal", "all_terms", "any_term"}:
        raise LSElzaCodeReadOnlyError(
            "Unsupported code search mode.",
            code="unsupported_match_mode",
        )
    context = _bounded_int(context_lines, 3, 0, MAX_SEARCH_CONTEXT_LINES)
    result_limit = _bounded_int(limit, 12, 1, MAX_SEARCH_RESULTS)
    query_folded = query.casefold()
    terms = [item.casefold() for item in re.findall(r"\S+", query)]

    def matches(line):
        folded = line.casefold()
        if mode == "literal":
            return query_folded in folded
        if mode == "all_terms":
            return bool(terms) and all(term in folded for term in terms)
        return bool(terms) and any(term in folded for term in terms)

    snippets = []
    matching_line_count = 0
    files_searched = 0
    matched_files = []
    for path in _source_files():
        files_searched += 1
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        matching_lines = [
            index for index, line in enumerate(lines, start=1) if matches(line)
        ]
        if not matching_lines:
            continue
        matching_line_count += len(matching_lines)
        file_name = _relative_name(path)
        matched_files.append(file_name)
        covered_until = 0
        for line_number in matching_lines:
            start = max(1, line_number - context)
            end = min(len(lines), line_number + context)
            if start <= covered_until and snippets and snippets[-1].get("file_name") == file_name:
                snippets[-1]["end_line"] = max(snippets[-1]["end_line"], end)
                snippets[-1]["lines"] = _line_block(
                    lines, snippets[-1]["start_line"], snippets[-1]["end_line"]
                )
                covered_until = snippets[-1]["end_line"]
                continue
            snippets.append({
                "file_name": file_name,
                "start_line": start,
                "end_line": end,
                "lines": _line_block(lines, start, end),
            })
            covered_until = end
            if len(snippets) >= result_limit:
                break
        if len(snippets) >= result_limit:
            break

    unique_files = list(dict.fromkeys(matched_files))
    return {
        "file_name": unique_files[0] if len(unique_files) == 1 else "",
        "read_only": True,
        "modular_source": True,
        "query": query,
        "match_mode": mode,
        "files_searched": files_searched,
        "matching_file_count": len(unique_files),
        "matching_line_count": matching_line_count,
        "returned_snippet_count": len(snippets),
        "truncated": len(snippets) >= result_limit,
        "snippets": snippets,
    }


def read_code_lines(start_line, end_line, file_name=""):
    path, source, lines = _read_source(file_name)
    start = _bounded_int(start_line, 1, 1, max(1, len(lines)))
    end = _bounded_int(end_line, start, start, max(start, len(lines)))
    requested_end = end
    end = min(end, start + MAX_READ_LINES - 1)
    return {
        "file_name": _relative_name(path),
        "read_only": True,
        "start_line": start,
        "end_line": end,
        "total_lines": len(lines),
        "truncated": requested_end > end,
        "lines": _line_block(lines, start, end),
    }


def _iter_named_nodes(tree):
    result = []

    def visit(node, parents):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualified = ".".join(parents + [child.name])
                result.append((qualified, "class", child))
                visit(child, parents + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = ".".join(parents + [child.name])
                result.append((qualified, "function", child))
                visit(child, parents + [child.name])
            else:
                visit(child, parents)

    visit(tree, [])
    return result


def _parsed_python(path):
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        return source, source.splitlines(), ast.parse(source, filename=_relative_name(path))
    except SyntaxError:
        return None, None, None
    except OSError:
        return None, None, None


def read_function(symbol, file_name=""):
    symbol = _clean_text(symbol, 200)
    if not symbol:
        raise LSElzaCodeReadOnlyError(
            "A Python function, method or class name is required.",
            code="missing_symbol",
        )
    paths = [_resolve_requested_file(file_name)] if file_name else _source_files(python_only=True)
    symbol_folded = symbol.casefold()
    candidates = []
    for path in paths:
        source, lines, tree = _parsed_python(path)
        if tree is None:
            continue
        for qualified, kind, node in _iter_named_nodes(tree):
            if qualified.casefold() == symbol_folded or node.name.casefold() == symbol_folded:
                candidates.append((path, lines, qualified, kind, node))
        if candidates and file_name:
            break
    if not candidates:
        return {
            "file_name": _clean_text(file_name, 300),
            "read_only": True,
            "found": False,
            "symbol": symbol,
        }

    path, lines, qualified, kind, node = candidates[0]
    decorator_lines = [
        int(item.lineno)
        for item in getattr(node, "decorator_list", [])
        if getattr(item, "lineno", None)
    ]
    start = min(decorator_lines + [int(node.lineno)])
    actual_end = int(getattr(node, "end_lineno", node.lineno))
    end = min(actual_end, start + MAX_FUNCTION_LINES - 1)
    return {
        "file_name": _relative_name(path),
        "read_only": True,
        "found": True,
        "symbol": qualified,
        "kind": kind,
        "start_line": start,
        "end_line": end,
        "actual_end_line": actual_end,
        "truncated": actual_end > end,
        "ambiguous_match_count": len(candidates),
        "lines": _line_block(lines, start, end),
    }


def app_structure(query="", limit=120, file_name=""):
    query = _clean_text(query, MAX_QUERY_CHARS)
    query_folded = query.casefold()
    result_limit = _bounded_int(limit, 120, 1, MAX_STRUCTURE_ITEMS)
    paths = [_resolve_requested_file(file_name)] if file_name else _source_files(python_only=True)
    items = []
    for path in paths:
        source, lines, tree = _parsed_python(path)
        if tree is None:
            continue
        for qualified, kind, node in _iter_named_nodes(tree):
            display_name = f"{_relative_name(path)}:{qualified}"
            if query_folded and query_folded not in display_name.casefold():
                continue
            items.append({
                "file_name": _relative_name(path),
                "name": qualified,
                "kind": kind,
                "line": int(node.lineno),
                "end_line": int(getattr(node, "end_lineno", node.lineno)),
            })
            if len(items) >= result_limit:
                break
        if len(items) >= result_limit:
            break
    return {
        "file_name": _clean_text(file_name, 300),
        "read_only": True,
        "modular_source": True,
        "query": query or None,
        "matching_item_count": len(items),
        "truncated": len(items) >= result_limit,
        "items": items,
    }


def get_code_tool_definitions():
    file_property = {
        "type": "string",
        "description": (
            "Optional source path returned by ls_code_search, for example "
            "ls_library/render.py. Omit to use the active entrypoint or search all modules."
        ),
    }
    return [
        {
            "type": "function",
            "name": "ls_code_search",
            "description": (
                "Search the current modular LocalSunoDb source tree read-only. "
                "Use this first for questions about actual LS UI behavior, labels, "
                "element IDs, endpoints, Python handlers or JavaScript."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "match_mode": {
                        "type": "string",
                        "enum": ["literal", "all_terms", "any_term"],
                    },
                    "context_lines": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_SEARCH_CONTEXT_LINES,
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_SEARCH_RESULTS,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ls_read_function",
            "description": (
                "Read one bounded Python function, method or class from the current "
                "modular LocalSunoDb source. Use file_name from search when known."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "file_name": file_property,
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ls_read_code_lines",
            "description": (
                "Read a bounded line range from one current LocalSunoDb source file. "
                "Use file_name returned by ls_code_search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": file_property,
                    "start_line": {"type": "integer", "minimum": 1},
                    "end_line": {"type": "integer", "minimum": 1},
                },
                "required": ["start_line", "end_line"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ls_app_structure",
            "description": (
                "List bounded Python class/function structure from the current modular "
                "LocalSunoDb source, optionally filtered by source path or symbol name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "file_name": file_property,
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_STRUCTURE_ITEMS,
                    },
                },
                "additionalProperties": False,
            },
        },
    ]


def run_code_action(action, arguments=None):
    action = _clean_text(action, 100)
    if action == "ls_code_search":
        args = _require_arguments(
            arguments, {"query", "match_mode", "context_lines", "limit"}
        )
        return code_search(
            query=args.get("query"),
            match_mode=args.get("match_mode", "literal"),
            context_lines=args.get("context_lines", 3),
            limit=args.get("limit", 12),
        )
    if action == "ls_read_function":
        args = _require_arguments(arguments, {"symbol", "file_name"})
        return read_function(args.get("symbol"), args.get("file_name", ""))
    if action == "ls_read_code_lines":
        args = _require_arguments(
            arguments, {"file_name", "start_line", "end_line"}
        )
        return read_code_lines(
            args.get("start_line"),
            args.get("end_line"),
            args.get("file_name", ""),
        )
    if action == "ls_app_structure":
        args = _require_arguments(arguments, {"query", "file_name", "limit"})
        return app_structure(
            query=args.get("query", ""),
            limit=args.get("limit", 120),
            file_name=args.get("file_name", ""),
        )
    raise LSElzaCodeReadOnlyError(
        "Unknown LS Elza code-reader action.",
        code="unknown_code_action",
    )
