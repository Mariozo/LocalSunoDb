"""Provenance helpers."""

from __future__ import annotations

from typing import Iterable

from .model import SourceRef


def dedupe_sources(sources: Iterable[SourceRef]) -> list[SourceRef]:
    result: list[SourceRef] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        key = (source.id, source.kind)
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result
