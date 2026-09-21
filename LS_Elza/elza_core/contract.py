"""Language-neutral Elza Core Contract v1 Python representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


CONTRACT_VERSION = "1"


def _require_v1(data: Mapping[str, Any]) -> None:
    if str(data.get("contract_version", "")) != CONTRACT_VERSION:
        raise ValueError("Unsupported Elza Core contract version")


@dataclass(frozen=True)
class ContextItem:
    id: str
    kind: str
    data: dict[str, Any]
    label: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContextItem":
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            label=str(data.get("label", "")),
            data=dict(data.get("data", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "kind": self.kind}
        if self.label:
            result["label"] = self.label
        result["data"] = dict(self.data)
        return result


@dataclass(frozen=True)
class ToolDeclaration:
    id: str
    description: str
    input_schema: dict[str, Any]
    side_effect: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ToolDeclaration":
        return cls(
            id=str(data["id"]),
            description=str(data.get("description", "")),
            input_schema=dict(data.get("input_schema", {})),
            side_effect=str(data.get("side_effect", "READ")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "side_effect": self.side_effect,
        }


@dataclass(frozen=True)
class ProvenanceItem:
    id: str
    kind: str
    label: str
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProvenanceItem":
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            label=str(data.get("label", "")),
            detail=str(data.get("detail", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"id": self.id, "kind": self.kind, "label": self.label}
        if self.detail:
            result["detail"] = self.detail
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


@dataclass(frozen=True)
class Capabilities:
    text: bool = True
    vision: bool = False
    tools: bool = False
    streaming: bool = False
    voice: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Capabilities":
        return cls(
            text=bool(data.get("text", True)),
            vision=bool(data.get("vision", False)),
            tools=bool(data.get("tools", False)),
            streaming=bool(data.get("streaming", False)),
            voice=bool(data.get("voice", False)),
        )

    def to_dict(self) -> dict[str, bool]:
        return {
            "text": self.text,
            "vision": self.vision,
            "tools": self.tools,
            "streaming": self.streaming,
            "voice": self.voice,
        }


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    output: Any
    provenance: tuple[ProvenanceItem, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ToolResult":
        return cls(
            call_id=str(data["call_id"]),
            output=data.get("output"),
            provenance=tuple(ProvenanceItem.from_dict(item) for item in data.get("provenance", ())),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "output": self.output,
            "provenance": [item.to_dict() for item in self.provenance],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ErrorInfo:
    code: str
    message: str
    category: str = ""
    retryable: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ErrorInfo":
        return cls(
            code=str(data["code"]),
            message=str(data.get("message", "")),
            category=str(data.get("category", "")),
            retryable=bool(data.get("retryable", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "category": self.category,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class CoreRequest:
    contract_version: str
    conversation_id: str
    message: str
    context: tuple[ContextItem, ...] = ()
    tools: tuple[ToolDeclaration, ...] = ()
    capabilities: Capabilities = Capabilities()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CoreRequest":
        _require_v1(data)
        return cls(
            contract_version=CONTRACT_VERSION,
            conversation_id=str(data["conversation_id"]),
            message=str(data.get("message", "")),
            context=tuple(ContextItem.from_dict(item) for item in data.get("context", ())),
            tools=tuple(ToolDeclaration.from_dict(item) for item in data.get("tools", ())),
            capabilities=Capabilities.from_dict(data.get("capabilities", {})),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "contract_version": self.contract_version,
            "conversation_id": self.conversation_id,
            "message": self.message,
            "context": [item.to_dict() for item in self.context],
            "tools": [tool.to_dict() for tool in self.tools],
            "capabilities": self.capabilities.to_dict(),
        }
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


@dataclass(frozen=True)
class CoreResponse:
    contract_version: str
    conversation_id: str
    text: str
    tool_results: tuple[ToolResult, ...] = ()
    provenance: tuple[ProvenanceItem, ...] = ()
    error: ErrorInfo | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CoreResponse":
        _require_v1(data)
        raw_error = data.get("error")
        return cls(
            contract_version=CONTRACT_VERSION,
            conversation_id=str(data["conversation_id"]),
            text=str(data.get("text", "")),
            tool_results=tuple(ToolResult.from_dict(item) for item in data.get("tool_results", ())),
            provenance=tuple(ProvenanceItem.from_dict(item) for item in data.get("provenance", ())),
            error=ErrorInfo.from_dict(raw_error) if isinstance(raw_error, Mapping) else None,
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "contract_version": self.contract_version,
            "conversation_id": self.conversation_id,
            "text": self.text,
            "tool_results": [item.to_dict() for item in self.tool_results],
            "provenance": [item.to_dict() for item in self.provenance],
            "metadata": dict(self.metadata),
        }
        if self.error is not None:
            result["error"] = self.error.to_dict()
        return result
