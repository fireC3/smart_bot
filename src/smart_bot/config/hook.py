from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .store import JsonStore
from ..event.bus import EventBus


class HookConfigData(BaseModel):
    session_start: list[dict[str, Any]] = Field(default_factory=list)
    session_end: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_before: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_after: list[dict[str, Any]] = Field(default_factory=list)


class HookStore:
    def __init__(self) -> None:
        self._data = HookConfigData()
        self._store: JsonStore | None = None
        self._event_bus: EventBus | None = None

    @property
    def data(self) -> dict[str, Any]:
        return self._data.model_dump(mode="json")

    async def update(self, data: dict[str, Any]) -> None:
        self._data = HookConfigData(**data)
        await self._save()
        if self._event_bus:
            self._event_bus.emit("hooks_changed", {"hooks": self.data})

    async def _save(self) -> None:
        if self._store is None:
            return
        await self._store.save(self._data.model_dump(mode="json"))

    @classmethod
    def _from_dir(cls, config_dir: Path, event_bus: EventBus) -> "HookStore":
        store = JsonStore(config_dir / "hooks.json")
        raw = store.load_sync()
        self = cls()
        self._data = HookConfigData(**raw)
        self._store = store
        self._event_bus = event_bus
        return self
