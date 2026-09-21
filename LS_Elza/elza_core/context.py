"""Immutable per-request context snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EntityRef:
    id: str
    label: str = ""
    kind: str = "entity"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HostRef:
    id: str
    version: str
    instance_id: str | None = None


@dataclass(frozen=True)
class SurfaceRef:
    id: str
    label: str
    uri: str | None = None


@dataclass(frozen=True)
class SelectionRef:
    items: tuple[EntityRef, ...] = ()
    count: int = 0
    summary: str = ""


@dataclass(frozen=True)
class RequestHints:
    language: str = "lv"
    selected_mode: str = ""
    route_hint: str = ""


@dataclass(frozen=True)
class ElzaContext:
    schema_version: str
    host: HostRef
    surface: SurfaceRef
    active_document: EntityRef | None = None
    active_item: EntityRef | None = None
    selection: SelectionRef = SelectionRef()
    attributes: tuple[tuple[str, Any], ...] = ()
    capabilities: tuple[str, ...] = ()
    help_context: tuple[str, ...] = ()
    code_context: tuple[tuple[str, Any], ...] = ()
    audio_context: tuple[tuple[str, Any], ...] = ()
    available_tools: tuple[str, ...] = ()
    request_hints: RequestHints = RequestHints()
