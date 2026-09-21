"""Single authority for conversation mutations."""

from __future__ import annotations

from .history import HistoryStore, validate_conversation
from .model import Conversation, Message, MessageState, Reaction, Turn, new_id, utc_now
from .provenance import dedupe_sources


class ConversationService:
    def __init__(self, store: HistoryStore | None = None):
        self.store = store

    def create(self, title: str = "") -> Conversation:
        conversation = Conversation.create(title=title)
        self._save(conversation)
        return conversation

    def append_user_message(self, conversation: Conversation, content: str) -> Message:
        turn = Turn(id=new_id(), conversation_id=conversation.id, created_at=utc_now())
        message = Message(
            id=new_id(),
            conversation_id=conversation.id,
            turn_id=turn.id,
            role="user",
            content=str(content),
            created_at=utc_now(),
            state=MessageState.COMPLETED,
        )
        turn.message_ids.append(message.id)
        conversation.turns.append(turn)
        conversation.messages.append(message)
        conversation.updated_at = utc_now()
        self._save(conversation)
        return message

    def append_assistant_message(
        self,
        conversation: Conversation,
        user_message_id: str,
        content: str,
        *,
        state: MessageState = MessageState.COMPLETED,
        sources=None,
        attachments=None,
        metadata=None,
    ) -> Message:
        user_message = conversation.get_message(user_message_id)
        if user_message is None or user_message.role != "user":
            raise ValueError("Assistant reply target must be an existing user message")
        message = Message(
            id=new_id(),
            conversation_id=conversation.id,
            turn_id=user_message.turn_id,
            role="assistant",
            content=str(content),
            created_at=utc_now(),
            reply_to_id=user_message.id,
            state=state,
            sources=dedupe_sources(sources or []),
            attachments=list(attachments or []),
            metadata=dict(metadata or {}),
        )
        conversation.messages.append(message)
        for turn in conversation.turns:
            if turn.id == user_message.turn_id:
                turn.message_ids.append(message.id)
                break
        conversation.updated_at = utc_now()
        self._save(conversation)
        return message

    def set_pinned(self, conversation: Conversation, message_id: str, value: bool) -> None:
        message = self._assistant_message(conversation, message_id)
        message.pinned = bool(value)
        self._save(conversation)

    def set_reaction(self, conversation: Conversation, message_id: str, reaction: Reaction) -> None:
        message = self._assistant_message(conversation, message_id)
        message.reaction = Reaction(reaction)
        self._save(conversation)

    def reject(self, conversation: Conversation, message_id: str) -> None:
        message = self._assistant_message(conversation, message_id)
        message.state = MessageState.REJECTED
        self._save(conversation)

    def delete(self, conversation: Conversation, message_id: str) -> None:
        message = self._assistant_message(conversation, message_id)
        message.state = MessageState.DELETED
        self._save(conversation)

    def _assistant_message(self, conversation: Conversation, message_id: str) -> Message:
        message = conversation.get_message(message_id)
        if message is None or message.role != "assistant":
            raise ValueError("Expected an existing assistant message")
        return message

    def _save(self, conversation: Conversation) -> None:
        validate_conversation(conversation)
        if self.store is not None:
            self.store.save(conversation)
