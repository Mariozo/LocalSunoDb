# LS Elza semantic selection contract
# Created: 15.aug.2026   22:35
# Actual base: v5.425
# Purpose: Validate model-produced structured LS selections
# ver. 1.1

"""Semantic LS selection tool contract and validation."""

SELECTION_TOOL_NAME = "ls_prepare_selection"

_ALLOWED_CATEGORY = {"", "Song", "Instrumental"}
_ALLOWED_KIND_FILTER = {"", "liked", "has_stems"}
_ALLOWED_LOCAL_AUDIO = {"", "with", "without"}
_ALLOWED_LOCAL_AUDIO_EXTENSIONS = {"wav", "mp3", "flac", "m4a", "aac", "ogg"}
_REQUIRED_FIELDS = {
    "safe_to_execute",
    "reason",
    "category",
    "flags",
    "exact_flags",
    "any_flag",
    "kind_filter",
    "local_audio",
    "tags",
    "workspace",
    "local_family",
    "local_family_assigned",
    "title_query",
    "exact_stem_count",
}
_OPTIONAL_FIELDS = {
    "exclude_ui_types",
    "local_audio_extensions",
}
_ALLOWED_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS


def get_selection_tool_definition():
    return {
        "type": "function",
        "name": SELECTION_TOOL_NAME,
        "description": (
            "Interpret a user request to select, filter, show, find, or list LocalSunoDb tracks. "
            "Use semantic meaning rather than exact spelling, including ordinary typing and "
            "speech-to-text errors. Preserve every stated condition. This tool does not change "
            "the database; it only returns a structured read-only selection request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "safe_to_execute": {
                    "type": "boolean",
                    "description": "True only when every requested condition is understood safely.",
                },
                "reason": {
                    "type": "string",
                    "description": "Short reason when safe_to_execute is false; otherwise empty.",
                },
                "category": {
                    "type": "string",
                    "enum": ["", "Song", "Instrumental"],
                    "description": "Canonical LS category inferred from meaning, including misspellings.",
                },
                "flags": {
                    "type": "array",
                    "items": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                    "maxItems": 5,
                    "description": "Requested LS user Flags, called flags, karodzini, or zvaigznites.",
                },
                "exact_flags": {
                    "type": "boolean",
                    "description": (
                        "True when the user means only/exactly the listed Flags and no other "
                        "Flags may be present; false when listed Flags are merely required."
                    ),
                },
                "any_flag": {
                    "type": "boolean",
                    "description": "True only when any nonzero LS Flag is requested without specific Flags.",
                },
                "kind_filter": {
                    "type": "string",
                    "enum": ["", "liked", "has_stems"],
                    "description": "Optional canonical LS kind filter.",
                },
                "local_audio": {
                    "type": "string",
                    "enum": ["", "with", "without"],
                    "description": "Whether local audio must exist, must not exist, or is unspecified.",
                },
                "local_audio_extensions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["wav", "mp3", "flac", "m4a", "aac", "ogg"],
                    },
                    "maxItems": 6,
                    "description": (
                        "Explicit local audio formats requested by the user. "
                        "For example, 'local WAV' means ['wav']. Leave empty "
                        "when no local file format was requested."
                    ),
                },
                "exclude_ui_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 20,
                    "description": (
                        "Exact LocalSunoDb Type badges to exclude from the selection. "
                        "For example, 'bez Upload', '- Upload', or 'izņem Upload' "
                        "means ['Upload']. Preserve the visible LS Type name."
                    ),
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 20,
                    "description": "Requested LS tags, preserving # prefix when the user supplied it.",
                },
                "workspace": {
                    "type": "string",
                    "description": "Explicitly requested Workspace name, otherwise empty.",
                },
                "local_family": {
                    "type": "string",
                    "description": "Explicitly requested Local family title, otherwise empty.",
                },
                "local_family_assigned": {
                    "type": ["boolean", "null"],
                    "description": (
                        "True when any confirmed Local Family assignment is required; false when "
                        "no confirmed assignment is required; null when unspecified."
                    ),
                },
                "title_query": {
                    "type": "string",
                    "description": "Explicit title/name search text, otherwise empty.",
                },
                "exact_stem_count": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Exact requested Stems count; use 0 when not requested.",
                },
            },
            "required": sorted(_REQUIRED_FIELDS),
            "additionalProperties": False,
        },
    }


def _clean_text(value, max_chars):
    text = str(value or "").strip()
    if len(text) > int(max_chars):
        text = text[: int(max_chars)].rstrip()
    return text


def _normalize_optional_text_list(value, max_items=20, max_chars=120):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("Expected a list of strings.")
    result = []
    seen = set()
    for item in value[:max_items]:
        text = _clean_text(item, max_chars)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def normalize_selection_request(arguments):
    if not isinstance(arguments, dict):
        raise ValueError("Selection arguments must be an object.")

    unexpected = sorted(set(arguments) - _ALLOWED_FIELDS)
    missing = sorted(_REQUIRED_FIELDS - set(arguments))
    if unexpected:
        raise ValueError("Unsupported selection arguments: " + ", ".join(unexpected))
    if missing:
        raise ValueError("Missing selection arguments: " + ", ".join(missing))

    category = _clean_text(arguments.get("category"), 40)
    kind_filter = _clean_text(arguments.get("kind_filter"), 40)
    local_audio = _clean_text(arguments.get("local_audio"), 40)
    if category not in _ALLOWED_CATEGORY:
        raise ValueError("Unsupported category.")
    if kind_filter not in _ALLOWED_KIND_FILTER:
        raise ValueError("Unsupported kind filter.")
    if local_audio not in _ALLOWED_LOCAL_AUDIO:
        raise ValueError("Unsupported local audio filter.")

    raw_flags = arguments.get("flags")
    if not isinstance(raw_flags, list):
        raise ValueError("Flags must be a list.")
    flags = []
    for item in raw_flags:
        try:
            number = int(item)
        except (TypeError, ValueError) as error:
            raise ValueError("Flag values must be integers.") from error
        if number not in {1, 2, 3, 4, 5}:
            raise ValueError("Flag values must be between 1 and 5.")
        if number not in flags:
            flags.append(number)
    flags.sort()

    local_audio_extensions = []
    for item in _normalize_optional_text_list(
        arguments.get("local_audio_extensions"), max_items=6, max_chars=20
    ):
        extension = item.lower().lstrip(".")
        if extension not in _ALLOWED_LOCAL_AUDIO_EXTENSIONS:
            raise ValueError("Unsupported local audio extension.")
        if extension not in local_audio_extensions:
            local_audio_extensions.append(extension)

    exclude_ui_types = _normalize_optional_text_list(
        arguments.get("exclude_ui_types"), max_items=20, max_chars=120
    )

    raw_tags = arguments.get("tags")
    if not isinstance(raw_tags, list):
        raise ValueError("Tags must be a list.")
    tags = []
    for item in raw_tags[:20]:
        tag = _clean_text(item, 120)
        if tag and tag not in tags:
            tags.append(tag)

    try:
        exact_stem_count = int(arguments.get("exact_stem_count") or 0)
    except (TypeError, ValueError) as error:
        raise ValueError("Exact stem count must be an integer.") from error
    if exact_stem_count < 0 or exact_stem_count > 100:
        raise ValueError("Exact stem count is out of range.")

    for field in ("safe_to_execute", "exact_flags", "any_flag"):
        if not isinstance(arguments.get(field), bool):
            raise ValueError(f"{field} must be a boolean.")

    local_family_assigned = arguments.get("local_family_assigned")
    if local_family_assigned is not None and not isinstance(local_family_assigned, bool):
        raise ValueError("local_family_assigned must be true, false, or null.")

    safe_to_execute = arguments["safe_to_execute"]
    reason = _clean_text(arguments.get("reason"), 600)
    exact_flags = arguments["exact_flags"]
    any_flag = arguments["any_flag"]
    local_family = _clean_text(arguments.get("local_family"), 300)
    if exact_flags and not flags:
        raise ValueError("Exact flags requires at least one flag.")
    if any_flag and flags:
        raise ValueError("Any flag cannot be combined with specific flags.")
    if local_family and local_family_assigned is False:
        raise ValueError("Local family cannot be combined with assigned=false.")

    return {
        "safe_to_execute": safe_to_execute,
        "reason": reason,
        "category": category,
        "flags": flags,
        "exact_flags": exact_flags,
        "any_flag": any_flag,
        "kind_filter": kind_filter,
        "local_audio": local_audio,
        "local_audio_extensions": local_audio_extensions,
        "exclude_ui_types": exclude_ui_types,
        "tags": tags,
        "workspace": _clean_text(arguments.get("workspace"), 300),
        "local_family": local_family,
        "local_family_assigned": local_family_assigned,
        "title_query": _clean_text(arguments.get("title_query"), 300),
        "exact_stem_count": exact_stem_count,
    }


def extract_selection_request(source_trace):
    if not isinstance(source_trace, list):
        return None
    for item in reversed(source_trace):
        if not isinstance(item, dict):
            continue
        if item.get("source_id") != "selection":
            continue
        if item.get("action") != SELECTION_TOOL_NAME:
            continue
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        return normalize_selection_request(data)
    return None
