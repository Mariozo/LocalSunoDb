"""Stable host-neutral Elza Core execution facade."""

from __future__ import annotations

from typing import Any

from .context import ElzaContext, HostRef, SurfaceRef
from .contract import (
    CONTRACT_VERSION,
    CoreRequest,
    CoreResponse,
    ErrorInfo,
    ProvenanceItem,
    ToolResult as ContractToolResult,
)
from .conversation import ConversationService
from .errors import CoreError, ErrorCategory
from .history import HistoryStore
from .model import Conversation, SourceRef, utc_now
from .operations import OperationRegistry
from .providers.base import AIProvider, AIRequest
from .routing import RouteDecision, Router
from .tools.contracts import ToolCall as RuntimeToolCall
from .tools.runtime import ToolRuntime


MAX_PROVIDER_TOOL_ROUNDS = 4
MAX_PROVIDER_TOOL_CALLS = 8


class ElzaCore:
    """Execute Contract-v1 requests without host-specific objects."""

    def __init__(
        self,
        *,
        provider: AIProvider,
        tool_runtime: ToolRuntime | None = None,
        history_store: HistoryStore | None = None,
        router: Router | None = None,
        operations: OperationRegistry | None = None,
    ):
        self.provider = provider
        self.tool_runtime = tool_runtime or ToolRuntime()
        self.history_store = history_store
        self.router = router or Router()
        self.operations = operations or OperationRegistry()
        self.conversations = ConversationService(history_store)

    def handle(self, request: CoreRequest) -> CoreResponse:
        if request.contract_version != CONTRACT_VERSION:
            raise ValueError("Unsupported Elza Core contract version")

        context = self._routing_context(request)
        route = self.router.decide(request.message, context)
        if route.decision == RouteDecision.CLARIFY:
            return CoreResponse(
                contract_version=CONTRACT_VERSION,
                conversation_id=request.conversation_id,
                text="",
                error=ErrorInfo(
                    code="clarification_required",
                    message="Request requires clarification",
                    category=ErrorCategory.INVALID_REQUEST.value,
                    retryable=False,
                ),
                metadata={"route": route.decision.value, "reason": route.reason},
            )
        if route.decision == RouteDecision.BLOCK:
            return CoreResponse(
                contract_version=CONTRACT_VERSION,
                conversation_id=request.conversation_id,
                text="",
                error=ErrorInfo(
                    code="blocked",
                    message=route.reason or "Request blocked",
                    category=ErrorCategory.INVALID_REQUEST.value,
                    retryable=False,
                ),
                metadata={"route": route.decision.value},
            )

        conversation = self._conversation(request.conversation_id)
        user_message = self.conversations.append_user_message(conversation, request.message)
        operation = self.operations.start(request.conversation_id)
        try:
            provider_result, tool_results, provider_rounds = self._run_provider_rounds(
                request,
                operation.token,
            )
            metadata: dict[str, Any] = {
                "route": route.decision.value,
                "provider_rounds": provider_rounds,
            }
            if provider_result.provider_request_id:
                metadata["provider_request_id"] = provider_result.provider_request_id
            if provider_result.usage:
                metadata["usage"] = dict(provider_result.usage)
            if provider_result.provider_metadata:
                metadata["provider_state"] = dict(provider_result.provider_metadata)
            self.conversations.append_assistant_message(
                conversation,
                user_message.id,
                provider_result.text,
            )
            return CoreResponse(
                contract_version=CONTRACT_VERSION,
                conversation_id=request.conversation_id,
                text=provider_result.text,
                tool_results=tuple(tool_results),
                metadata=metadata,
            )
        except CoreError as exc:
            return CoreResponse(
                contract_version=CONTRACT_VERSION,
                conversation_id=request.conversation_id,
                text=exc.user_message,
                error=ErrorInfo(
                    code=exc.code,
                    message=exc.user_message,
                    category=exc.category.value,
                    retryable=exc.retryable,
                ),
                metadata={"route": route.decision.value},
            )
        finally:
            self.operations.finish(operation)

    def _run_provider_rounds(self, request: CoreRequest, cancel_token: Any):
        messages: list[dict[str, Any]] = [{"role": "user", "content": request.message}]
        tools = tuple(tool.to_dict() for tool in request.tools)
        provider_state: dict[str, Any] = {}
        all_tool_results: list[ContractToolResult] = []
        total_tool_calls = 0

        for round_number in range(1, MAX_PROVIDER_TOOL_ROUNDS + 2):
            provider_result = self.provider.generate(
                AIRequest(
                    instructions="",
                    messages=tuple(messages),
                    tools=tools,
                    metadata=self._provider_metadata(request, provider_state),
                ),
                cancel_token,
            )
            raw_calls = tuple(provider_result.tool_calls or ())
            if not raw_calls:
                return provider_result, all_tool_results, round_number

            if round_number > MAX_PROVIDER_TOOL_ROUNDS:
                raise CoreError(
                    code="provider_tool_round_limit",
                    category=ErrorCategory.TOOL_ERROR,
                    user_message="Provider exceeded the safe tool-call round limit",
                )
            total_tool_calls += len(raw_calls)
            if total_tool_calls > MAX_PROVIDER_TOOL_CALLS:
                raise CoreError(
                    code="provider_tool_call_limit",
                    category=ErrorCategory.TOOL_ERROR,
                    user_message="Provider exceeded the safe tool-call limit",
                )

            runtime_calls = [self._runtime_call(raw_call) for raw_call in raw_calls]
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": call.id,
                        "tool_id": call.tool_id,
                        "arguments": dict(call.arguments),
                    }
                    for call in runtime_calls
                ],
            })
            round_results = self._execute_runtime_calls(request, runtime_calls)
            all_tool_results.extend(round_results)
            for result, call in zip(round_results, runtime_calls):
                messages.append({
                    "role": "tool",
                    "call_id": result.call_id,
                    "tool_id": call.tool_id,
                    "output": result.output,
                })
            provider_state = dict(provider_result.provider_metadata or {})

        raise AssertionError("unreachable provider loop")

    @staticmethod
    def _provider_metadata(
        request: CoreRequest,
        provider_state: dict[str, Any],
    ) -> tuple[tuple[str, Any], ...]:
        metadata: list[tuple[str, Any]] = [
            ("conversation_id", request.conversation_id),
            ("contract_version", request.contract_version),
            ("context", tuple(item.to_dict() for item in request.context)),
            ("request_metadata", dict(request.metadata)),
        ]
        if provider_state:
            metadata.append(("provider_state", dict(provider_state)))
        return tuple(metadata)

    def _routing_context(self, request: CoreRequest) -> ElzaContext:
        return ElzaContext(
            schema_version=CONTRACT_VERSION,
            host=HostRef(id="elza-core-client", version=request.contract_version),
            surface=SurfaceRef(id="core-contract", label="Core Contract"),
            attributes=(("context", tuple(item.to_dict() for item in request.context)),),
            capabilities=tuple(
                name
                for name, enabled in request.capabilities.to_dict().items()
                if enabled
            ),
            available_tools=tuple(tool.id for tool in request.tools),
        )

    def _conversation(self, conversation_id: str) -> Conversation:
        if self.history_store is not None:
            existing = self.history_store.load(conversation_id)
            if existing is not None:
                return existing
        now = utc_now()
        return Conversation(
            id=conversation_id,
            created_at=now,
            updated_at=now,
        )

    def _execute_tool_calls(
        self,
        request: CoreRequest,
        raw_calls: tuple[Any, ...],
    ) -> list[ContractToolResult]:
        return self._execute_runtime_calls(
            request,
            [self._runtime_call(raw_call) for raw_call in raw_calls],
        )

    def _execute_runtime_calls(
        self,
        request: CoreRequest,
        calls: list[RuntimeToolCall],
    ) -> list[ContractToolResult]:
        allowed = {tool.id for tool in request.tools}
        results: list[ContractToolResult] = []
        for call in calls:
            if call.tool_id not in allowed:
                raise CoreError(
                    code="undeclared_tool",
                    category=ErrorCategory.TOOL_ERROR,
                    user_message="Provider requested an undeclared tool",
                )
            runtime_result = self.tool_runtime.execute(call)
            results.append(
                ContractToolResult(
                    call_id=runtime_result.call_id,
                    output=runtime_result.output,
                    provenance=tuple(self._provenance(source) for source in runtime_result.sources),
                    metadata=dict(runtime_result.metadata),
                )
            )
        return results

    @staticmethod
    def _runtime_call(raw_call: Any) -> RuntimeToolCall:
        if isinstance(raw_call, RuntimeToolCall):
            return raw_call
        if isinstance(raw_call, dict):
            return RuntimeToolCall(
                id=str(raw_call["id"]),
                tool_id=str(raw_call["tool_id"]),
                arguments=dict(raw_call.get("arguments", {})),
            )
        raise CoreError(
            code="invalid_tool_call",
            category=ErrorCategory.TOOL_ERROR,
            user_message="Provider returned an invalid tool call",
        )

    @staticmethod
    def _provenance(source: SourceRef) -> ProvenanceItem:
        return ProvenanceItem(
            id=source.id,
            kind=source.kind,
            label=source.label,
            detail=source.detail,
            metadata=dict(source.metadata),
        )
