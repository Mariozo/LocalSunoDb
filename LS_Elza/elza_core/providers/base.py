"""Provider-neutral AI contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..operations import CancellationToken


@dataclass(frozen=True)
class ProviderCapabilities:
    text: bool = True
    vision: bool = False
    tools: bool = False
    streaming: bool = False
    cancellation: bool = False
    usage: bool = False


@dataclass(frozen=True)
class AIRequest:
    instructions: str
    messages: tuple[dict[str, Any], ...]
    attachments: tuple[Any, ...] = ()
    tools: tuple[Any, ...] = ()
    limits: tuple[tuple[str, Any], ...] = ()
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class AIResult:
    text: str
    tool_calls: tuple[Any, ...] = ()
    usage: dict[str, Any] = field(default_factory=dict)
    provider_request_id: str = ""
    provider_metadata: dict[str, Any] = field(default_factory=dict)


class AIProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...
    def generate(self, request: AIRequest, cancel_token: CancellationToken) -> AIResult: ...
