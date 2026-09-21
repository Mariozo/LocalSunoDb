"""Atomic JSON HistoryStore owned by the LocalSunoDb adapter."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from ..elza_core.history import HistoryStore, validate_conversation
from ..elza_core.model import AttachmentRef, Conversation, Message, MessageState, Reaction, SourceRef, Turn


class JsonHistoryStore(HistoryStore):
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, conversation_id: str) -> Path:
        return self.root / f"{conversation_id}.json"

    def list_ids(self) -> list[str]:
        return sorted(path.stem for path in self.root.glob("*.json") if path.is_file())

    def load(self, conversation_id: str) -> Conversation | None:
        path = self._path(conversation_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        messages = []
        for item in payload.get("messages") or []:
            item = dict(item)
            item["state"] = MessageState(item.get("state", "created"))
            item["reaction"] = Reaction(item.get("reaction", "none"))
            item["sources"] = [SourceRef(**source) for source in item.get("sources") or []]
            item["attachments"] = [AttachmentRef(**attachment) for attachment in item.get("attachments") or []]
            messages.append(Message(**item))
        conversation = Conversation(
            id=payload["id"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            title=payload.get("title", ""),
            messages=messages,
            turns=[Turn(**turn) for turn in payload.get("turns") or []],
            metadata=payload.get("metadata") or {},
        )
        validate_conversation(conversation)
        return conversation

    def save(self, conversation: Conversation) -> None:
        validate_conversation(conversation)
        payload = asdict(conversation)
        destination = self._path(conversation.id)
        fd, tmp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, destination)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
