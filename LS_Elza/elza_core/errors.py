"""Structured Elza Core errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    INVALID_REQUEST = "INVALID_REQUEST"
    CANCELLED = "CANCELLED"
    UNSUPPORTED = "UNSUPPORTED"
    TOOL_ERROR = "TOOL_ERROR"
    HOST_ERROR = "HOST_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL = "INTERNAL"


@dataclass
class CoreError(Exception):
    code: str
    category: ErrorCategory
    user_message: str
    retryable: bool = False
    diagnostic: str = ""
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.user_message
