"""Deterministic safety reconciliation for LS Elza selection tool arguments."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _fold_selection_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _latest_user_question_text(model_input: list[Any]) -> str:
    for item in reversed(model_input or []):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        content = item.get("content")
        texts: list[str] = []
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in {"input_text", "text"}:
                    texts.append(str(part.get("text") or ""))
        combined = "\n".join(texts).strip()
        marker = "\n\nUser question:\n"
        if marker in combined:
            return combined.rsplit(marker, 1)[-1].strip()
        if combined:
            return combined
    return ""


def reconcile_selection_tool_arguments(
    tool_id: Any,
    arguments: dict[str, Any],
    model_input: list[Any],
) -> dict[str, Any]:
    if str(tool_id or "").strip() != "ls_prepare_selection":
        return arguments
    if not isinstance(arguments, dict):
        return arguments

    result = dict(arguments)
    user_text = _latest_user_question_text(model_input)
    plain = _fold_selection_text(user_text)
    if not plain:
        return result

    explicit_locf = bool(
        re.search(r"\blocf\b", plain)
        or re.search(r"\blocal\s+family\b", plain)
    )
    if not explicit_locf:
        result["local_family"] = ""
        result["local_family_assigned"] = None

    local_wording = bool(
        re.search(r"\b(?:vietej\w*|lokal\w*)\b", plain)
        and re.search(
            r"\b(?:dziesm\w*|ierakst\w*|audio\w*|wav\w*|fail\w*|track\w*)\b",
            plain,
        )
        and not re.search(r"\blocal\s+family\b", plain)
    )
    if local_wording:
        result["local_audio"] = "with"

    anywhere_scope = bool(
        re.search(r"\b(?:jebkur|citur|elsewhere|anywhere)\b", plain)
        or re.search(r"\bkaut\s+kur\b", plain)
        or (
            re.search(r"\bnosaukum\w*\b", plain)
            and re.search(r"\b(?:vai|or)\b", plain)
            and re.search(r"\b(?:citur|tekst\w*|lyrics?|tag\w*)\b", plain)
        )
        or (
            re.search(r"\b(?:tekst\w*|lyrics?|tag\w*)\b", plain)
            and re.search(r"\b(?:vai|or)\b", plain)
        )
    )

    query = ""
    if anywhere_scope:
        quoted = re.search(r'["“”]([^"“”]{1,160})["“”]', user_text)
        if quoted:
            query = re.sub(r"\s+", " ", quoted.group(1).strip())
        if not query:
            named = re.search(
                r"\b(?:vārds?|vārdu|frāze|fraze|word)\s+"
                r'["“”]?([^\s,;:.!?"“”]{1,120})',
                user_text,
                flags=re.IGNORECASE,
            )
            if named:
                query = named.group(1).strip()
        if not query:
            query = str(
                result.get("anywhere_query")
                or result.get("title_query")
                or ""
            ).strip()
        if query:
            result["anywhere_query"] = query
            result["title_query"] = ""

    if str(result.get("category") or "") == "Song":
        explicit_song_category = bool(
            re.search(r"\bsong\b", plain)
            or re.search(r"\bkategorij\w*\s+song\b", plain)
        )
        if not explicit_song_category:
            result["category"] = ""

    return result


__all__ = ["reconcile_selection_tool_arguments"]
