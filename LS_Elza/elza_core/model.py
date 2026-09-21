"""Stable conversation data model for Elza Core."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MessageState(str, Enum):
    CREATED = "created"
    GENERATING = "generating"
    COMPLETED = "completed"
    REJECTED = "rejected"
    DELETED = "deleted"
    ERROR = "error"


class Reaction(str, Enum):
    NONE = "none"
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclass(frozen=True)
class SourceRef:
    id: str
    kind: str
    label: str
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AttachmentRef:
    id: str
    kind: str
    mime_type: str
    size_bytes: int
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    id: str
    conversation_id: str
    turn_id: str
    role: str
    content: str
    created_at: str
    reply_to_id: str | None = None
    state: MessageState = MessageState.CREATED
    reaction: Reaction = Reaction.NONE
    pinned: bool = False
    attachments: list[AttachmentRef] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Turn:
    id: str
    conversation_id: str
    created_at: str
    message_ids: list[str] = field(default_factory=list)


@dataclass
class Conversation:
    id: str
    created_at: str
    updated_at: str
    title: str = ""
    messages: list[Message] = field(default_factory=list)
    turns: list[Turn] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, title: str = "") -> "Conversation":
        now = utc_now()
        return cls(id=new_id(), created_at=now, updated_at=now, title=title)

    def get_message(self, message_id: str) -> Message | None:
        for message in self.messages:
            if message.id == message_id:
                return message
        return None
