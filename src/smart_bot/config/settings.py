from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .path import get_config_path
from .store import JsonStore
from ..event.bus import EventBus


class SettingsStoreData(BaseModel):
    default_platform: str = ""
    default_model: dict[str, str] = Field(default_factory=dict)
    data_dir: str = ""
    extra_skill_paths: list[str] = Field(default_factory=list)
    tool_inline_limit: int = 8000
    tool_preview_chars: int = 8000


class SettingsStore:
    def __init__(self) -> None:
        self._data = SettingsStoreData()
        self._store: JsonStore | None = None
        self._event_bus: EventBus | None = None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if hasattr(self._data, name):
            return getattr(self._data, name)
        raise AttributeError(name)

    def to_dict(self) -> dict[str, Any]:
        return self._data.model_dump(mode="json")

    def data_dir_path(self) -> Path:
        d = self._data.data_dir
        if not d:
            d = str(get_config_path() / "data")
        return Path(d)

    async def update(self, data: dict[str, Any]) -> None:
        old = self.to_dict()
        for k, v in data.items():
            if hasattr(self._data, k) and v is not None:
                setattr(self._data, k, v)
        await self._save()
        if self._event_bus:
            self._event_bus.emit("settings_changed", {"old": old, "new": self.to_dict()})

    async def _save(self) -> None:
        if self._store is None:
            return
        await self._store.save(self._data.model_dump(mode="json"))

    @classmethod
    def _from_dir(cls, config_dir: Path, event_bus: EventBus) -> "SettingsStore":
        store = JsonStore(config_dir / "settings.json")
        raw = store.load_sync()
        self = cls()
        self._data = SettingsStoreData(**raw)
        self._store = store
        self._event_bus = event_bus
        return self
