"""Shared semantic Search/Filter intent contract for LS Elza and LS Main.

This module contains no database access and no UI side effects. It only
normalizes a bounded semantic intent and maps it onto the existing deterministic
LocalSunoDb filter arguments.
"""

SCHEMA_VERSION = 1

_ALLOWED_FIELDS = {
    "schema_version",
    "source",
    "text_query",
    "search_fields",
    "workspace",
    "category",
    "local_family",
    "local_family_assigned",
    "kind",
    "local_audio",
    "flags",
    "exact_flags",
    "tags",
    "exact_stem_count",
}
_ALLOWED_SOURCES = {"elza", "smart_search", "flags_tags", "library"}
_ALLOWED_SEARCH_FIELDS = {"name", "lyrics", "prompt"}
_ALLOWED_CATEGORIES = {"Song", "Instrumental"}
_ALLOWED_KINDS = {"", "liked", "has_stems"}
_ALLOWED_LOCAL_AUDIO = {"any", "with", "without"}


def _clean_text(value):
    return " ".join(str(value or "").strip().split())


def _unique_text_list(value):
    if value in (None, ""):
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ValueError("Expected a list of strings.")
    result = []
    seen = set()
    for item in value:
        text = _clean_text(item)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def _normalize_tags(value):
    result = []
    seen = set()
    for item in _unique_text_list(value):
        tag = item if item.startswith("#") else "#" + item
        key = tag.casefold()
        if key not in seen:
            result.append(tag)
            seen.add(key)
    return result


def normalize_search_filter_intent(payload):
    if not isinstance(payload, dict):
        raise ValueError("Search/Filter intent must be an object.")

    unknown = sorted(set(payload) - _ALLOWED_FIELDS)
    if unknown:
        raise ValueError("Unsupported Search/Filter intent fields: " + ", ".join(unknown))

    version = payload.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError("Unsupported Search/Filter intent schema version.")

    source = _clean_text(payload.get("source") or "elza").lower()
    if source not in _ALLOWED_SOURCES:
        raise ValueError("Unsupported Search/Filter intent source.")

    search_fields = [item.lower() for item in _unique_text_list(payload.get("search_fields"))]
    if any(item not in _ALLOWED_SEARCH_FIELDS for item in search_fields):
        raise ValueError("Unsupported Search/Filter search field.")

    categories = _unique_text_list(payload.get("category"))
    if any(item not in _ALLOWED_CATEGORIES for item in categories):
        raise ValueError("Unsupported Search/Filter category.")

    local_family = _unique_text_list(payload.get("local_family"))
    local_family_assigned = payload.get("local_family_assigned")
    if local_family_assigned is not None and not isinstance(local_family_assigned, bool):
        raise ValueError("local_family_assigned must be true, false, or null.")
    if local_family and local_family_assigned is False:
        raise ValueError("Local family cannot be combined with assigned=false.")

    raw_flags = payload.get("flags") or []
    if isinstance(raw_flags, int):
        raw_flags = [raw_flags]
    if not isinstance(raw_flags, (list, tuple)):
        raise ValueError("Search/Filter flags must be a list.")
    flags = []
    for item in raw_flags:
        try:
            number = int(item)
        except (TypeError, ValueError) as error:
            raise ValueError("Search/Filter flag must be an integer 1..5.") from error
        if number < 1 or number > 5:
            raise ValueError("Search/Filter flag must be in range 1..5.")
        if number not in flags:
            flags.append(number)
    flags.sort()

    exact_flags = bool(payload.get("exact_flags", False))
    if exact_flags and not flags:
        raise ValueError("exact_flags requires at least one flag.")

    kind = _clean_text(payload.get("kind"))
    if kind not in _ALLOWED_KINDS:
        raise ValueError("Unsupported Search/Filter kind.")

    local_audio = _clean_text(payload.get("local_audio") or "any").lower()
    if local_audio not in _ALLOWED_LOCAL_AUDIO:
        raise ValueError("Unsupported Search/Filter local_audio value.")

    exact_stem_count = payload.get("exact_stem_count")
    if exact_stem_count in (None, ""):
        exact_stem_count = None
    else:
        try:
            exact_stem_count = int(exact_stem_count)
        except (TypeError, ValueError) as error:
            raise ValueError("exact_stem_count must be a non-negative integer.") from error
        if exact_stem_count < 0:
            raise ValueError("exact_stem_count must be a non-negative integer.")

    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "text_query": _clean_text(payload.get("text_query")),
        "search_fields": search_fields,
        "workspace": _unique_text_list(payload.get("workspace")),
        "category": categories,
        "local_family": local_family,
        "local_family_assigned": local_family_assigned,
        "kind": kind,
        "local_audio": local_audio,
        "flags": flags,
        "exact_flags": exact_flags,
        "tags": _normalize_tags(payload.get("tags")),
        "exact_stem_count": exact_stem_count,
    }


def intent_to_ls_filters(intent):
    intent = normalize_search_filter_intent(intent)
    filters = {}
    meta = {}

    if intent["text_query"]:
        filters["query"] = intent["text_query"]
        for field in intent["search_fields"] or ["name"]:
            filters["search_" + field] = True

    if intent["workspace"]:
        filters["workspace"] = intent["workspace"] if len(intent["workspace"]) > 1 else intent["workspace"][0]
    if intent["category"]:
        filters["category_filter"] = intent["category"] if len(intent["category"]) > 1 else intent["category"][0]
    if intent["local_family"]:
        filters["local_family_filter"] = intent["local_family"] if len(intent["local_family"]) > 1 else intent["local_family"][0]
    if intent["local_family_assigned"] is not None:
        meta["local_family_assigned"] = intent["local_family_assigned"]

    if intent["kind"] == "liked":
        filters["kind_filter"] = "__liked__"
    elif intent["kind"] == "has_stems":
        filters["kind_filter"] = "__has_stems__"

    if intent["local_audio"] in {"with", "without"}:
        filters["local_audio_filter"] = intent["local_audio"]

    if intent["flags"]:
        masks = [1 << (number - 1) for number in intent["flags"]]
        filters["flag_filter"] = ",".join(str(mask) for mask in masks)
        if intent["exact_flags"]:
            exact_mask = 0
            for mask in masks:
                exact_mask |= mask
            meta["exact_flag_mask"] = exact_mask

    if intent["tags"]:
        filters["tag_filter"] = ",".join(intent["tags"])

    if intent["exact_stem_count"] is not None:
        meta["exact_stem_count"] = intent["exact_stem_count"]

    return filters, meta
