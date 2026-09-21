"""Single routing authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .context import ElzaContext


class RouteDecision(str, Enum):
    LOCAL = "LOCAL"
    AI = "AI"
    TOOL_ASSISTED = "TOOL_ASSISTED"
    CLARIFY = "CLARIFY"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RouteResult:
    decision: RouteDecision
    reason: str = ""


LocalRoute = Callable[[str, ElzaContext], RouteResult | None]


class Router:
    def __init__(self, local_routes: list[LocalRoute] | None = None):
        self.local_routes = list(local_routes or [])

    def decide(self, text: str, context: ElzaContext) -> RouteResult:
        clean_text = str(text or "").strip()
        if not clean_text:
            return RouteResult(RouteDecision.CLARIFY, "empty request")
        for local_route in self.local_routes:
            result = local_route(clean_text, context)
            if result is not None:
                return result
        if context.available_tools:
            return RouteResult(RouteDecision.TOOL_ASSISTED, "read capabilities available")
        return RouteResult(RouteDecision.AI, "provider response required")
