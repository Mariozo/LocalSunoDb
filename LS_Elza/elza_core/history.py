"""History store contract and validation."""

from __future__ import annotations

from typing import Protocol

from .model import Conversation

HISTORY_SCHEMA_VERSION = "1"


class HistoryStore(Protocol):
    def load(self, conversation_id: str) -> Conversation | None: ...
    def save(self, conversation: Conversation) -> None: ...
    def list_ids(self) -> list[str]: ...


def validate_conversation(conversation: Conversation) -> None:
    message_ids: set[str] = set()
    turn_ids = {turn.id for turn in conversation.turns}
    for message in conversation.messages:
        if message.id in message_ids:
            raise ValueError("Duplicate message id")
        message_ids.add(message.id)
        if message.turn_id not in turn_ids:
            raise ValueError("Message references an unknown turn")
        if message.reply_to_id and message.reply_to_id not in message_ids:
            raise ValueError("Message reply target is missing or ordered after the reply")
