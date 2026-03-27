from __future__ import annotations
from dataclasses import dataclass, field

from smart_bot.config import ConfigManager
from smart_bot.interface import PermissionMode



@dataclass
class AppState:
    """Top-level application state. Created once per process."""

    config: ConfigManager = field(default_factory=ConfigManager.get)
    permission_mode: PermissionMode = PermissionMode.DEFAULT
