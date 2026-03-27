from __future__ import annotations

from pathlib import Path
from typing import Any

from .store import JsonStore
from ..event.bus import EventBus
from ..interface.platform_config import PlatformConfig


class PlatformStore:
    def __init__(self, items: dict[str, PlatformConfig] | None = None):
        self.items: dict[str, PlatformConfig] = items or {}
        self._store: JsonStore | None = None
        self._event_bus: EventBus | None = None

    def get(self, platform_id: str) -> dict[str, Any] | None:
        p = self.items.get(platform_id)
        return p.model_dump(mode="json") if p else None

    def get_obj(self, platform_id: str) -> PlatformConfig | None:
        return self.items.get(platform_id)

    def api_key(self, platform_id: str) -> str:
        p = self.items.get(platform_id)
        return p.api_key if p else ""

    async def save_platform(self, platform_id: str, data: PlatformConfig | dict[str, Any]) -> None:
        if isinstance(data, dict):
            data = PlatformConfig(**data)
        self.items[platform_id] = data
        await self._save()
        if self._event_bus:
            self._event_bus.emit("platforms_changed", {"platform_id": platform_id})

    async def delete_platform(self, platform_id: str) -> None:
        self.items.pop(platform_id, None)
        await self._save()
        if self._event_bus:
            self._event_bus.emit("platforms_changed", {"platform_id": platform_id, "deleted": True})

    async def _save(self) -> None:
        if self._store is None:
            return
        await self._store.save(
            {pid: p.model_dump(mode="json", exclude_none=True)
             for pid, p in self.items.items()}
        )

    @classmethod
    def _from_dir(cls, config_dir: Path, event_bus: EventBus) -> "PlatformStore":
        store = JsonStore(config_dir / "platforms.json")
        raw = store.load_sync()
        items = {pid: PlatformConfig(**pdata) for pid, pdata in raw.items()}
        self = cls(items=items)
        self._store = store
        self._event_bus = event_bus
        return self
