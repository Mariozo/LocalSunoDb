"""Semantic settings contract."""

from typing import Any, Protocol


class SettingsStore(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
