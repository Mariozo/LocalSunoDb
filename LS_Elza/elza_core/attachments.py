"""Attachment validation policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentPolicy:
    allowed_mime_types: frozenset[str]
    max_items: int
    max_item_bytes: int
    max_total_bytes: int

    def validate(self, mime_types: list[str], sizes: list[int]) -> None:
        if len(mime_types) != len(sizes):
            raise ValueError("Attachment metadata length mismatch")
        if len(mime_types) > self.max_items:
            raise ValueError("Too many attachments")
        total = 0
        for mime_type, size in zip(mime_types, sizes):
            if mime_type not in self.allowed_mime_types:
                raise ValueError("Unsupported attachment type")
            if size < 0 or size > self.max_item_bytes:
                raise ValueError("Attachment size is outside policy")
            total += size
        if total > self.max_total_bytes:
            raise ValueError("Attachment total exceeds policy")
