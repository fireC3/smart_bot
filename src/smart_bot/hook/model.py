from enum import Enum
from typing import Any
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class HookContent:
    cwd: Path
    metadata: dict[str, Any] = field(default_factory=dict)


class HookEvent(Enum):
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    TOOL_CALL_BEFORE = "tool_call_before"
    TOOL_CALL_AFTER = "tool_call_after"
    TOOL_CALL_FAILED = "tool_call_failed"
