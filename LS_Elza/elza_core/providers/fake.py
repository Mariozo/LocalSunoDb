"""Deterministic provider for Core tests."""

from __future__ import annotations

from .base import AIRequest, AIResult, ProviderCapabilities
from ..errors import CoreError, ErrorCategory
from ..operations import CancellationToken


class FakeAIProvider:
    def __init__(self, mode: str = "text", text: str = "fake response"):
        self.mode = mode
        self.text = text

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(text=True, vision=True, tools=True, cancellation=True, usage=True)

    def generate(self, request: AIRequest, cancel_token: CancellationToken) -> AIResult:
        if cancel_token.cancelled or self.mode == "cancelled":
            raise CoreError("cancelled", ErrorCategory.CANCELLED, "Request cancelled")
        if self.mode == "timeout":
            raise CoreError("timeout", ErrorCategory.TIMEOUT, "Provider timeout", retryable=True)
        if self.mode == "network":
            raise CoreError("network", ErrorCategory.NETWORK, "Provider network error", retryable=True)
        if self.mode == "auth":
            raise CoreError("auth", ErrorCategory.AUTH, "Provider authentication failed")
        if self.mode == "rate_limit":
            raise CoreError("rate_limit", ErrorCategory.RATE_LIMIT, "Provider rate limit", retryable=True)
        if self.mode == "malformed":
            raise CoreError("malformed", ErrorCategory.PROVIDER_ERROR, "Malformed provider response")
        return AIResult(text=self.text, usage={"input": 0, "output": 0}, provider_request_id="fake-1")
