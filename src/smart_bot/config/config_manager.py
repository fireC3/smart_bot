from __future__ import annotations

from .path import get_config_path
from .platform import PlatformStore
from .settings import SettingsStore
from .hook import HookStore
from ..event.bus import EventBus


class ConfigManager:
    _instance: ConfigManager | None = None

    def __init__(self) -> None:
        self.event_bus = EventBus()
        config_dir = get_config_path()
        self.platforms = PlatformStore._from_dir(config_dir, event_bus=self.event_bus)
        self.settings = SettingsStore._from_dir(config_dir, event_bus=self.event_bus)
        self.hooks = HookStore._from_dir(config_dir, event_bus=self.event_bus)

    @classmethod
    def get(cls) -> "ConfigManager":
        if cls._instance is None:
            get_config_path().mkdir(parents=True, exist_ok=True)
            cls._instance = cls()
        return cls._instance
