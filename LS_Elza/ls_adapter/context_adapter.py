"""Translate bounded LocalSunoDb state into host-neutral Elza contracts."""

from __future__ import annotations

from typing import Any

from ..elza_core.context import ElzaContext, EntityRef, HostRef, RequestHints, SelectionRef, SurfaceRef
from ..elza_core.contract import ContextItem


def _pairs(values: dict[str, Any], allowed: tuple[str, ...]) -> tuple[tuple[str, Any], ...]:
    return tuple((key, values[key]) for key in allowed if key in values)


def build_core_context_items(snapshot: dict[str, Any]) -> tuple[ContextItem, ...]:
    """Translate LS selection state into Contract-v1 context items."""
    source = snapshot if isinstance(snapshot, dict) else {}
    selected = source.get("selected_track") if isinstance(source.get("selected_track"), dict) else {}
    track_id = str(selected.get("track_id") or "").strip()
    if not track_id:
        return ()
    return (
        ContextItem(
            id=track_id,
            kind="track",
            label=str(selected.get("title") or ""),
            data={
                "workspace": selected.get("workspace"),
                "category": selected.get("category"),
                "local_family_title": selected.get("local_family_title"),
            },
        ),
    )


def build_elza_context(snapshot: dict[str, Any]) -> ElzaContext:
    """Legacy internal context mapping retained for compatibility during cutover."""
    host = snapshot.get("host") or {}
    surface = snapshot.get("surface") or {}
    selected = snapshot.get("selected_track") or {}
    selection_rows = snapshot.get("selection") or []
    selected_item = None
    if selected.get("track_id"):
        selected_item = EntityRef(
            id=str(selected["track_id"]),
            label=str(selected.get("title") or ""),
            kind="track",
            metadata={
                "workspace": selected.get("workspace"),
                "category": selected.get("category"),
                "local_family_title": selected.get("local_family_title"),
            },
        )
    items = tuple(
        EntityRef(id=str(row.get("track_id") or ""), label=str(row.get("title") or ""), kind="track")
        for row in selection_rows
        if row.get("track_id")
    )
    attributes = _pairs(
        snapshot,
        (
            "current_url",
            "local_wav_exists",
            "stem_count",
            "compare_available",
            "last_refresh_result",
        ),
    )
    hints = snapshot.get("request_hints") or {}
    return ElzaContext(
        schema_version="1",
        host=HostRef(id=str(host.get("id") or "localsunodb"), version=str(host.get("version") or ""), instance_id=host.get("instance_id")),
        surface=SurfaceRef(id=str(surface.get("id") or "unknown"), label=str(surface.get("label") or surface.get("id") or "unknown"), uri=surface.get("uri")),
        active_item=selected_item,
        selection=SelectionRef(items=items, count=len(items), summary=str(snapshot.get("selection_summary") or "")),
        attributes=attributes,
        capabilities=tuple(str(item) for item in (snapshot.get("capabilities") or [])),
        help_context=tuple(str(item) for item in (snapshot.get("help_context") or [])),
        code_context=_pairs(snapshot.get("code_context") or {}, ("available", "reference")),
        available_tools=tuple(str(item) for item in (snapshot.get("available_tools") or [])),
        request_hints=RequestHints(
            language=str(hints.get("language") or "lv"),
            selected_mode=str(hints.get("selected_mode") or ""),
            route_hint=str(hints.get("route_hint") or ""),
        ),
    )
