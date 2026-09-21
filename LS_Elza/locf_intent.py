"""Narrow deterministic recognition for simple LocF assignment selections."""

import re
import unicodedata

from .selection_intent import normalize_selection_request


def _fold(value):
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _base_selection(assigned):
    return normalize_selection_request({
        "safe_to_execute": True,
        "reason": "",
        "category": "",
        "flags": [],
        "exact_flags": False,
        "any_flag": False,
        "kind_filter": "",
        "local_audio": "",
        "tags": [],
        "workspace": "",
        "local_family": "",
        "local_family_assigned": assigned,
        "title_query": "",
        "exact_stem_count": 0,
    })


def recognize_locf_selection(text):
    """Return a complete selection request only for unambiguous simple LocF commands."""
    plain = _fold(text)
    if not plain or not re.search(r"\blocf\b", plain):
        return None
    if not re.search(r"\b(paradi|atlasi|atrodi|uzskaiti|show|list|find)\b", plain):
        return None

    # Fast-path is intentionally narrow. Any additional known LS filter
    # dimension is left to the existing semantic/model path so no condition is
    # silently discarded.
    if re.search(
        r"\b(instrumental\w*|song\b|karodz\w*|flags?\b|zvaigzn\w*|"
        r"workspace\b|darbviet\w*|stems?\b|stemiem\b|liked\b|"
        r"lokal\w*\s+audio\b|local\s+audio\b|tag\w*\b)"
        r"|#[\w-]+",
        plain,
    ):
        return None

    unassigned = bool(
        re.search(r"\bbez\s+(?:atzim\w*\s+)?locf\b", plain)
        or re.search(r"\b(?:nav|no|without)\s+(?:assigned\s+)?locf\b", plain)
        or re.search(r"\blocf\b.{0,24}\bnav\b", plain)
    )
    assigned = bool(
        not unassigned
        and (
            re.search(r"\bar\s+(?:atzim\w*\s+)?locf\b", plain)
            or re.search(r"\b(?:ir|with|has)\s+(?:assigned\s+)?locf\b", plain)
            or re.search(r"\b(?:pieskirt\w*|assigned)\s+locf\b", plain)
        )
    )

    if unassigned == assigned:
        return None
    return _base_selection(assigned)


__all__ = ["recognize_locf_selection"]
