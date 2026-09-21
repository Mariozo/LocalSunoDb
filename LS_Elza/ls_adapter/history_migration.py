"""Deterministic current-LS history compatibility conversion."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from ..elza_core.model import Conversation, Message, MessageState, SourceRef, Turn, utc_now


def _stable_id(kind: str, *parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "ls-elza:" + kind + ":" + ":".join(parts)))


def _chat_items(payload: dict):
    chats = payload.get("chats") or {}
    if isinstance(chats, dict):
        return [(str(chat_id), chat) for chat_id, chat in chats.items() if isinstance(chat, dict)]
    if isinstance(chats, list):
        return [
            (str(chat.get("id") or chat.get("chat_id") or index), chat)
            for index, chat in enumerate(chats)
            if isinstance(chat, dict)
        ]
    return []


def convert_legacy_history(payload: dict) -> list[Conversation]:
    """Convert LS history schema v1/v2 without mutating the source payload."""
    result: list[Conversation] = []
    for legacy_chat_id, chat in _chat_items(payload if isinstance(payload, dict) else {}):
        conversation_id = _stable_id("conversation", legacy_chat_id)
        created = str(chat.get("created_at") or utc_now())
        conversation = Conversation(
            id=conversation_id,
            created_at=created,
            updated_at=str(chat.get("updated_at") or created),
            title=str(chat.get("title") or ""),
            metadata={
                "legacy_chat_id": legacy_chat_id,
                "legacy_schema_version": (payload or {}).get("schema_version"),
                "legacy_active": str((payload or {}).get("active_chat_id") or "") == legacy_chat_id,
            },
        )
        pending_user: Message | None = None
        for index, item in enumerate(chat.get("messages") or []):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").lower()
            content = str(item.get("content") or item.get("text") or "")
            created_at = str(item.get("created_at") or created)
            if role == "user":
                turn_id = _stable_id("turn", legacy_chat_id, str(index))
                turn = Turn(
                    id=turn_id,
                    conversation_id=conversation_id,
                    created_at=created_at,
                )
                message = Message(
                    id=_stable_id("message", legacy_chat_id, str(index), "user"),
                    conversation_id=conversation_id,
                    turn_id=turn_id,
                    role="user",
                    content=content,
                    created_at=created_at,
                    state=MessageState.COMPLETED,
                    metadata={"legacy_index": index},
                )
                turn.message_ids.append(message.id)
                conversation.turns.append(turn)
                conversation.messages.append(message)
                pending_user = message
                continue

            if role != "assistant":
                continue

            # Current LS history is a flat user/assistant list. If an orphan
            # assistant exists, give it a stable synthetic turn instead of
            # dropping text.
            if pending_user is None:
                turn_id = _stable_id("turn", legacy_chat_id, str(index), "orphan")
                turn = Turn(
                    id=turn_id,
                    conversation_id=conversation_id,
                    created_at=created_at,
                )
                conversation.turns.append(turn)
                reply_to_id = None
            else:
                turn = conversation.turns[-1]
                turn_id = pending_user.turn_id
                reply_to_id = pending_user.id

            sources = []
            for source_index, source in enumerate(item.get("sources") or []):
                if not isinstance(source, dict):
                    continue
                sources.append(SourceRef(
                    id=str(source.get("id") or f"legacy-{source_index}"),
                    kind=str(source.get("kind") or "provided"),
                    label=str(source.get("label") or "Legacy source"),
                    detail=str(source.get("detail") or ""),
                    metadata={"legacy_index": source_index},
                ))
            message = Message(
                id=_stable_id("message", legacy_chat_id, str(index), "assistant"),
                conversation_id=conversation_id,
                turn_id=turn_id,
                role="assistant",
                content=content,
                created_at=created_at,
                reply_to_id=reply_to_id,
                state=MessageState.COMPLETED,
                pinned=bool(item.get("pinned", False)),
                sources=sources,
                metadata={"legacy_index": index},
            )
            conversation.messages.append(message)
            turn.message_ids.append(message.id)
            pending_user = None

        result.append(conversation)
    return result
