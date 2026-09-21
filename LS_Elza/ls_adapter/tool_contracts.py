"""Read-only LocalSunoDb tool contract factories."""

from __future__ import annotations

from ..elza_core.contract import ToolDeclaration
from ..elza_core.tools import SideEffectLevel, ToolSpec


def _closed_schema(properties: dict) -> dict:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": [],
        "additionalProperties": False,
    }


def readonly_tool_declaration(tool_id: str, description: str, properties: dict) -> ToolDeclaration:
    return ToolDeclaration(
        id=tool_id,
        description=description,
        side_effect="READ",
        input_schema=_closed_schema(properties),
    )


def readonly_tool_spec(tool_id: str, description: str, properties: dict) -> ToolSpec:
    """Legacy runtime ToolSpec retained during the Contract-v1 cutover."""
    return ToolSpec(
        id=tool_id,
        description=description,
        side_effect=SideEffectLevel.READ,
        input_schema=_closed_schema(properties),
    )
