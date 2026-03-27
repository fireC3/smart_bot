from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .message import ContentType

class ThinkingEffort(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


@dataclass
class ModelCapability:
    """Flat capability declaration for a model.

    Provider example::

        ModelCapability(
            input_types=[ContentType.TEXT, ContentType.IMAGE],
            output_types=[ContentType.TEXT, ContentType.TOOL_CALL],
            max_tokens=131072,
        )
    """

    input_types: list[ContentType] = field(default_factory=lambda: [ContentType.TEXT])
    output_types: list[ContentType] = field(default_factory=lambda: [ContentType.TEXT])
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    supports_stream: bool = True
    supports_tool_call: bool = True
    supports_thinking: bool = True
    thinking_effort: ThinkingEffort = ThinkingEffort.HIGH
    extra_capability: dict[str, Any] = field(default_factory=dict)

    def supports_input(self, content_type: ContentType) -> bool:
        return content_type in self.input_types

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_types": [ct.value for ct in self.input_types],
            "output_types": [ct.value for ct in self.output_types],
            "max_tokens": self.max_tokens,
            "max_completion_tokens": self.max_completion_tokens,
            "supports_stream": self.supports_stream,
            "supports_tool_call": self.supports_tool_call,
            "supports_thinking": self.supports_thinking,
            "thinking_effort": self.thinking_effort,
            "extra_capability": self.extra_capability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelCapability":
        return cls(
            input_types=[ContentType(v) for v in data.get("input_types", ["text"])],
            output_types=[ContentType(v) for v in data.get("output_types", ["text"])],
            max_tokens=data.get("max_tokens"),
            max_completion_tokens=data.get("max_completion_tokens"),
            supports_stream=data.get("supports_stream", True),
            supports_tool_call=data.get("supports_tool_call", False),
            supports_thinking=data.get("supports_thinking", False),
            thinking_effort=ThinkingEffort(data.get("thinking_effort", "high")),
            extra_capability=data.get("extra_capability", {}),
        )

    @classmethod
    def from_defaults_and_overrides(
        cls,
        defaults: "ModelCapability",
        overrides: dict[str, Any] | None,
    ) -> "ModelCapability":
        """Create a ModelCapability by merging provider defaults with user overrides."""
        if not overrides:
            return defaults
        merged = defaults.to_dict()
        merged.update(overrides)
        return cls.from_dict(merged)
