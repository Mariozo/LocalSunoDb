"""Compatibility bridge from current LS payloads into Elza Core contracts."""

from __future__ import annotations

import json
from typing import Any, Callable

from ..elza_core.context import ElzaContext
from ..elza_core.contract import Capabilities, CoreRequest, ToolDeclaration
from ..elza_core.providers import AIRequest, AIResult, ProviderCapabilities
from ..elza_core.tools import SideEffectLevel, ToolCall, ToolResult, ToolSpec
from .context_adapter import build_core_context_items, build_elza_context


INVALID_TOOL_ARGUMENTS_KEY = "__ls_invalid_tool_arguments__"


def _selected_track(source: dict[str, Any]) -> dict[str, Any]:
    selected_track_id = str(source.get("selected_track_id") or "").strip()
    if not selected_track_id:
        return {}
    return {
        "track_id": selected_track_id,
        "title": source.get("title"),
        "workspace": source.get("workspace"),
        "category": source.get("main_category"),
        "local_family_title": source.get("local_family_title"),
    }


def build_core_request(
    *,
    conversation_id: str,
    message: str,
    context: dict[str, Any],
    tool_definitions: list[dict[str, Any]] | None = None,
    provider_input: list[dict[str, Any]] | None = None,
    instructions: str = "",
) -> CoreRequest:
    """Translate current LS host payloads into the public Contract-v1 request."""
    source = context if isinstance(context, dict) else {}
    validate_openai_tool_definitions(tool_definitions or [])
    tools: list[ToolDeclaration] = []
    for item in tool_definitions or []:
        if not isinstance(item, dict) or item.get("type") != "function":
            continue
        tools.append(
            ToolDeclaration(
                id=str(item.get("name") or "").strip(),
                description=str(item.get("description") or ""),
                input_schema=dict(item.get("parameters") or {}),
                side_effect="READ",
            )
        )
    metadata: dict[str, Any] = {
        "host": "localsunodb",
        "app_version": str(source.get("app_version") or ""),
        "surface": str(source.get("active_tab") or "unknown"),
        "current_url": str(source.get("current_url") or ""),
    }
    if provider_input is not None:
        metadata["provider_input"] = list(provider_input)
    if instructions:
        metadata["instructions"] = str(instructions)
    return CoreRequest(
        contract_version="1",
        conversation_id=str(conversation_id),
        message=str(message),
        context=build_core_context_items({"selected_track": _selected_track(source)}),
        tools=tuple(tools),
        capabilities=Capabilities(text=True, tools=bool(tools)),
        metadata=metadata,
    )


def _response_item_for_input(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return dict(item)
    model_dump = getattr(item, "model_dump", None)
    if callable(model_dump):
        return model_dump(exclude_none=True)
    raise TypeError("Unsupported OpenAI Responses output item")


def _contract_tools_for_openai(tools: tuple[Any, ...]) -> list[dict[str, Any]]:
    result = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_id = str(tool.get("id") or "").strip()
        if not tool_id:
            continue
        result.append({
            "type": "function",
            "name": tool_id,
            "description": str(tool.get("description") or ""),
            "parameters": dict(tool.get("input_schema") or {}),
        })
    return result


def _usage_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(exclude_none=True)
        return dict(dumped) if isinstance(dumped, dict) else {}
    return {}


class OpenAIResponsesProvider:
    """Adapt the OpenAI Responses host client to Elza Core's AIProvider contract."""

    def __init__(
        self,
        *,
        create_response: Callable[[list[dict[str, Any]], str, list[dict[str, Any]]], Any],
    ):
        self._create_response = create_response

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(text=True, vision=True, tools=True, usage=True)

    def generate(self, request: AIRequest, cancel_token: Any) -> AIResult:
        if getattr(cancel_token, "cancelled", False):
            raise RuntimeError("Elza Core operation was cancelled")

        metadata = dict(request.metadata)
        request_metadata = metadata.get("request_metadata")
        if not isinstance(request_metadata, dict):
            request_metadata = {}
        provider_state = metadata.get("provider_state")
        if not isinstance(provider_state, dict):
            provider_state = {}

        state_input = provider_state.get("model_input")
        if isinstance(state_input, list):
            model_input = [
                dict(item) if isinstance(item, dict) else item
                for item in state_input
            ]
        else:
            initial = request_metadata.get("provider_input")
            if isinstance(initial, list):
                model_input = [
                    dict(item) if isinstance(item, dict) else item
                    for item in initial
                ]
            else:
                model_input = [dict(item) for item in request.messages]

        handled_call_ids = {
            str(item)
            for item in (provider_state.get("handled_tool_call_ids") or [])
            if str(item)
        }
        for item in request.messages:
            if not isinstance(item, dict) or item.get("role") != "tool":
                continue
            call_id = str(item.get("call_id") or "").strip()
            if not call_id or call_id in handled_call_ids:
                continue
            model_input.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": str(item.get("output") or ""),
            })
            handled_call_ids.add(call_id)

        instructions = str(
            request_metadata.get("instructions") or request.instructions or ""
        )
        tools = _contract_tools_for_openai(request.tools)
        response = self._create_response(model_input, instructions, tools)

        response_items = [
            _response_item_for_input(item)
            for item in (getattr(response, "output", None) or [])
        ]
        tool_calls = []
        for item in response_items:
            if item.get("type") != "function_call":
                continue
            raw_arguments = item.get("arguments", "{}")
            try:
                arguments = json.loads(str(raw_arguments or "{}"))
                if not isinstance(arguments, dict):
                    raise ValueError("tool arguments must be an object")
            except (TypeError, ValueError, json.JSONDecodeError):
                arguments = {
                    INVALID_TOOL_ARGUMENTS_KEY: str(raw_arguments or "")
                }
            tool_calls.append({
                "id": str(item.get("call_id") or item.get("id") or ""),
                "tool_id": str(item.get("name") or ""),
                "arguments": arguments,
            })

        provider_metadata: dict[str, Any] = {}
        if tool_calls:
            provider_metadata = {
                "model_input": model_input + response_items,
                "handled_tool_call_ids": sorted(handled_call_ids),
            }

        return AIResult(
            text=str(getattr(response, "output_text", "") or ""),
            tool_calls=tuple(tool_calls),
            usage=_usage_dict(getattr(response, "usage", None)),
            provider_request_id=str(getattr(response, "id", "") or ""),
            provider_metadata=provider_metadata,
        )


class LSReadOnlyToolRuntime:
    """Delegate Core tool calls to the existing LS read-only host executor."""

    def __init__(self, *, handler: Callable[[ToolCall], ToolResult]):
        self._handler = handler

    def execute(self, call: ToolCall) -> ToolResult:
        result = self._handler(call)
        if not isinstance(result, ToolResult):
            raise TypeError("LS read-only Core tool handler must return ToolResult")
        return result


def build_core_context_snapshot(context: dict[str, Any]) -> ElzaContext:
    """Legacy internal context mapping retained during the Contract-v1 cutover."""
    source = context if isinstance(context, dict) else {}
    selected_ids = [
        str(item).strip()
        for item in (source.get("selected_track_ids") or [])
        if str(item).strip()
    ]
    selected = _selected_track(source)
    selection = [
        {"track_id": track_id, "title": ""}
        for track_id in selected_ids
    ]
    view = source.get("view") if isinstance(source.get("view"), dict) else {}
    return build_elza_context({
        "host": {
            "id": "localsunodb",
            "version": str(source.get("app_version") or ""),
        },
        "surface": {
            "id": str(source.get("active_tab") or "unknown"),
            "label": str(source.get("active_tab") or "unknown"),
            "uri": str(source.get("current_url") or "") or None,
        },
        "selected_track": selected,
        "selection": selection,
        "selection_summary": (
            f"{len(selection)} selected track(s)" if selection else ""
        ),
        "current_url": source.get("current_url"),
        "capabilities": ("read_only",),
        "help_context": ("ls_help",),
        "code_context": {
            "available": True,
            "reference": "current_accepted_source",
        },
        "request_hints": {
            "language": "lv",
            "selected_mode": str(view.get("selected_mode") or ""),
        },
    })


def validate_openai_tool_definitions(tool_definitions: list[dict[str, Any]]) -> None:
    """Validate current host tool schemas against Core's default-deny contract."""
    for item in tool_definitions or []:
        if not isinstance(item, dict) or item.get("type") != "function":
            continue
        name = str(item.get("name") or "").strip()
        schema = item.get("parameters") or {}
        if not name or not isinstance(schema, dict):
            raise ValueError("Invalid LS Elza read-only tool contract.")
        spec = ToolSpec(
            id=name,
            description=str(item.get("description") or ""),
            side_effect=SideEffectLevel.READ,
            input_schema=dict(schema),
        )
        spec.validate_schema_policy()
