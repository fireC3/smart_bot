from __future__ import annotations
from enum import Enum
import time
from typing import Optional, Union, List, Dict, Any
from uuid import UUID
from uuid_backport import uuid7
from dataclasses import dataclass, field


# ========== 枚举定义 ==========

class MediaType(str, Enum):
    URL = "url"
    BASE64 = "base64"

class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TOOL_CALL = "tool_call"
    USAGE = "usage"

# ========== 媒体源 ==========
@dataclass
class MediaSource:
    type: MediaType
    data: str
    mimeType: Optional[str] = None  # ✅ 修复：这里应该是 str，不是 MediaType

    def __post_init__(self):
        if self.type == MediaType.BASE64 and not self.mimeType:
            raise ValueError("Base64 类型必须提供 mimeType")

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": self.data,
            "mimeType": self.mimeType
        }

@dataclass
class TextBlock:
    text: str
    thinking: Optional[str] = None
    type: ContentType = ContentType.TEXT

    @staticmethod
    def combine_text_blocks(blocks: List["TextBlock"]) -> "TextBlock":
        combined_text = "".join(block.text for block in blocks)
        combined_thinking = "".join(
            block.thinking for block in blocks if block.thinking
        )
        return TextBlock(
            text=combined_text,
            thinking=combined_thinking or None
        )

@dataclass
class ImageBlock:
    source: MediaSource
    size: tuple[int, int]
    type: ContentType = ContentType.IMAGE

@dataclass
class VideoBlock:
    source: MediaSource
    size: tuple[int, int]
    type: ContentType = ContentType.VIDEO

@dataclass
class AudioBlock:
    source: MediaSource
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    transcript: Optional[str] = None
    type: ContentType = ContentType.AUDIO

@dataclass
class ToolCallBlock:
    call_id: str
    name: str
    arguments: dict
    content: Optional[str] = None
    type: ContentType = ContentType.TOOL_CALL

@dataclass
class UsageBlock:
    prompt_tokens: int = 0
    cached_tokens: int = 0
    thinking_tokens: int = 0
    completion_tokens: int = 0
    type: ContentType = ContentType.USAGE

ContentBlock = Union[TextBlock, ImageBlock, VideoBlock, AudioBlock, ToolCallBlock, UsageBlock]

# ========== 消息主结构 ==========
@dataclass
class Message:
    role: str
    id: UUID = field(default_factory=uuid7)
    content: List[ContentBlock] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Optional[Dict[str, Any]] = None

# ========== 角色消息子类 ==========
@dataclass
class UserMessage(Message):
    role: str = "user"

@dataclass
class SystemMessage(Message):
    role: str = "system"

@dataclass
class AIMessage(Message):
    role: str = "assistant"
    usage: Optional[UsageBlock] = None

    def __post_init__(self):
        if any(isinstance(b, ToolCallBlock) for b in self.content):
            raise ValueError("AIMessage content cannot contain ToolCallBlock; use ToolMessage instead")

@dataclass
class ToolMessage(Message):
    role: str = "tool"
    ai_think: Optional[TextBlock] = None
    usage: Optional[UsageBlock] = None

    def __post_init__(self):
        if any(not isinstance(b, ToolCallBlock) for b in self.content):
            raise ValueError("ToolMessage content must contain only ToolCallBlock entries")
        if self.ai_think is None:
            raise ValueError("ToolMessage must contain an ai_think block")