from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict
from .message import Message, ContentBlock
from .capability import ModelCapability
from .platform_config import PlatformConfig
from .memory import Memory

class LLM(ABC):
    def __init__(self, config: PlatformConfig, api_key: str = "", model_name: str = "", memory: Memory = None):
        self.config = config
        self._api_key = api_key
        self._model_name = model_name
        self.memory = memory

    def get_capability(self) -> ModelCapability:
        return self.config.capability
    @abstractmethod
    async def enable(self):
        """启用模型，进行必要的初始化"""
        pass
    @abstractmethod
    async def disable(self):
        """禁用模型，进行必要的清理"""
        pass

    @abstractmethod
    async def invoke(
        self,
        messages: list[Message] | None,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[ContentBlock, None]:
        """生成回复，根据 capability 自动决定流式/工具调用/思考模式。"""
        yield  # pragma: no cover — abstract, never called

    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        pass


class STT(ABC):
    @abstractmethod
    async def get_capability(self) -> ModelCapability: pass

    @abstractmethod
    async def transcribe(self, audio_data: bytes, **kwargs) -> str: pass

    @abstractmethod
    async def stream_transcribe(self, audio_stream: AsyncGenerator[bytes, None], **kwargs) -> AsyncGenerator[Dict, None]:
        """yield {"text": str, "is_final": bool, ...}"""
        pass


class TTS(ABC):
    @abstractmethod
    async def get_capability(self) -> ModelCapability: pass

    @abstractmethod
    def list_voices(self) -> List[Dict]: pass

    @abstractmethod
    async def stream_speak(self, text: str, voice_id: str, **kwargs) -> AsyncGenerator[bytes, None]:
        """yield 音频二进制块"""
        pass