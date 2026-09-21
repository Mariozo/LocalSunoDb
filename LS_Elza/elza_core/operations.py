"""Operation identity, cancellation, and late-result suppression."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from .model import new_id


@dataclass
class CancellationToken:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class Operation:
    id: str
    conversation_id: str
    token: CancellationToken = field(default_factory=CancellationToken)


class OperationRegistry:
    def __init__(self):
        self._lock = RLock()
        self._active: dict[str, Operation] = {}

    def start(self, conversation_id: str) -> Operation:
        with self._lock:
            previous = self._active.get(conversation_id)
            if previous is not None:
                previous.token.cancel()
            operation = Operation(id=new_id(), conversation_id=conversation_id)
            self._active[conversation_id] = operation
            return operation

    def cancel(self, conversation_id: str) -> None:
        with self._lock:
            operation = self._active.get(conversation_id)
            if operation is not None:
                operation.token.cancel()

    def is_current(self, operation: Operation) -> bool:
        with self._lock:
            current = self._active.get(operation.conversation_id)
            return current is operation and not operation.token.cancelled

    def finish(self, operation: Operation) -> None:
        with self._lock:
            if self._active.get(operation.conversation_id) is operation:
                self._active.pop(operation.conversation_id, None)
