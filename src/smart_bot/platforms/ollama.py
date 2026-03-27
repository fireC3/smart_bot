import asyncio
from contextlib import suppress
from typing import Any, AsyncGenerator, ClassVar, Dict, List

from ollama import AsyncClient

from smart_bot.interface import (
    ModelCapability, LLM, PlatformConfig,
    ContentBlock, ContentType, ImageBlock,
    Message, TextBlock, ToolCallBlock, UsageBlock,
    Memory, AIMessage, ToolMessage,
)


class OllamaLLM(LLM):
    default_config: ClassVar[PlatformConfig] = PlatformConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        timeout=120,
        max_retries=3,
        temperature=0.7,
        capability=ModelCapability(
            input_types=[ContentType.TEXT],
            output_types=[ContentType.TEXT, ContentType.TOOL_CALL],
            supports_stream=True,
            supports_tool_call=True,
            supports_thinking=True,
        ),
    )

    def __init__(self, config: PlatformConfig, api_key: str = "", model_name: str = "", memory: Memory = None):
        super().__init__(config, api_key=api_key, model_name=model_name, memory=memory)
        self.client = None

    async def enable(self):
        self.client = AsyncClient(
            host=self.config.base_url,
            timeout=self.config.timeout,
        )

    async def disable(self):
        if self.client is None:
            return
        self.client = None

    def transform_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        transformed_messages = []
        for message in messages:
            if isinstance(message, ToolMessage):
                tool_call_message = {
                    "role": "assistant",
                    "content": message.ai_think.text,
                    "tool_calls": []
                }
                for content_block in message.content:
                    if not isinstance(content_block, ToolCallBlock):
                        continue
                    tool_call_message["tool_calls"].append(
                        {
                            "type": "function",
                            "function": {
                                "name": content_block.name,
                                "arguments": content_block.arguments
                            }
                        }
                    )
                transformed_messages.append(tool_call_message)

                for content_block in message.content:
                    transformed_messages.append(
                        {
                            "role": "tool",
                            "tool_name": content_block.name,
                            "content": content_block.content
                        }
                    )
            else:
                payload: Dict[str, Any] = {"role": message.role}
                payload["images"] = []
                for block in message.content:
                    if isinstance(block, TextBlock):
                        payload["content"] = block.text

                    elif isinstance(block, ImageBlock):
                        payload["images"].append(block.source.data)

                transformed_messages.append(payload)

        return transformed_messages

    def _parse_text_block(self, payload: Any) -> TextBlock:
        text = getattr(payload, "content", "")
        thinking = getattr(payload, "thinking", "")

        text_value = text if isinstance(text, str) else ""
        thinking_value = thinking if isinstance(thinking, str) and thinking else None
        return TextBlock(
            text=text_value,
            thinking=thinking_value,
        )

    def _build_memory_message(self, blocks: List[ContentBlock]) -> Message | None:
        usage = UsageBlock()
        text_blocks = []
        tool_blocks = []
        for block in blocks:
            if isinstance(block, ToolCallBlock):
                tool_blocks.append(block)
            if isinstance(block, TextBlock) and (block.text or block.thinking):
                text_blocks.append(block)

        ai_think = TextBlock.combine_text_blocks(text_blocks) if text_blocks else TextBlock(text="", thinking=None)
        if tool_blocks:
            return ToolMessage(ai_think=ai_think, content=tool_blocks, usage=usage)
        return AIMessage(content=[ai_think], usage=usage)
    async def _create_completion_with_retry(self, **request_kwargs: Any) -> Any:
        attempts = max(1, self.config.max_retries + 1)

        for attempt in range(1, attempts + 1):
            try:
                return await self.client.chat(**request_kwargs)
            except Exception as e:
                if attempt == attempts:
                    raise
                await asyncio.sleep(min(2 ** (attempt - 1), 8))
    async def invoke(
        self, messages: list[Message] | None, tools: list[dict] | None = None,
    ) -> AsyncGenerator[ContentBlock, None]:
        if self.client is None:
            raise Exception("OllamaLLM client is not initialized. Call enable() first.")

        if self.memory is not None:
            for message in messages or []:
                self.memory.add_message(message)
            history = self.memory.get_history()
        else:
            history = messages or []
        if not history:
            raise ValueError("Messages cannot be empty")

        cap = self.config.capability

        request_kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": self.transform_messages(history),
        }

        if cap.supports_tool_call and tools:
            request_kwargs["tools"] = tools

        if cap.supports_thinking:
            request_kwargs["think"] = True

        if not cap.supports_stream:
            request_kwargs["stream"] = False
            response = await self._create_completion_with_retry(**request_kwargs)
            blocks: list[ContentBlock] = []
            text_block = self._parse_text_block(response.message)
            if text_block.text or text_block.thinking:
                blocks.append(text_block)
                yield text_block
            message_tool_calls = getattr(response.message, "tool_calls", None) or []
            for tc in message_tool_calls:
                tb = ToolCallBlock(call_id="", name=tc.function.name, arguments=tc.function.arguments)
                blocks.append(tb)
                yield tb
            if self.memory is not None:
                mm = self._build_memory_message(blocks)
                if mm is not None:
                    self.memory.add_message(mm)
            return

        # Streaming path
        request_kwargs["stream"] = True
        stream = await self._create_completion_with_retry(**request_kwargs)
        text_blocks: list[TextBlock] = []
        tool_blocks: list[ToolCallBlock] = []
        try:
            async for chunk in stream:
                message = chunk.message
                if message.content != "" or message.thinking is not None:
                    text_block = self._parse_text_block(message)
                    text_blocks.append(text_block)
                    yield text_block
                if message.tool_calls:
                    for tc in message.tool_calls:
                        tb = ToolCallBlock(call_id="", name=tc.function.name, arguments=tc.function.arguments)
                        tool_blocks.append(tb)
                        yield tb
        except RuntimeError as e:
            if "asynchronous generator is already running" not in str(e):
                raise
        finally:
            if hasattr(stream, "aclose"):
                with suppress(RuntimeError):
                    await stream.aclose()

        if self.memory is not None:
            blocks_to_persist: list[ContentBlock] = []
            if text_blocks:
                combined_block = TextBlock.combine_text_blocks(text_blocks)
                if combined_block.text or combined_block.thinking:
                    blocks_to_persist.append(combined_block)
            blocks_to_persist.extend(tool_blocks)
            mm = self._build_memory_message(blocks_to_persist)
            if mm is not None:
                self.memory.add_message(mm)


    async def validate_message(self, message: Message) -> bool:
        for block in message.content:
            block_type = block.type if isinstance(block.type, ContentType) else ContentType(block.type)
            if not self.config.capability.supports_input(block_type):
                return False
        return True

    async def validate_messages(self, messages: List[Message]) -> bool:
        for msg in messages:
            for block in msg.content:
                block_type = block.type if isinstance(block.type, ContentType) else ContentType(block.type)
                if not self.config.capability.supports_input(block_type):
                    return False
        return True

    async def get_available_models(self) -> List[str]:
        if self.client is None:
            raise Exception("OllamaLLM client is not initialized. Call enable() first.")

        models_response = await self.client.list()
        models = getattr(models_response, "models", None)
        if models is None and isinstance(models_response, dict):
            models = models_response.get("models", [])

        available_models = []
        for model in models or []:
            if isinstance(model, dict):
                model_name = model.get("model") or model.get("name")
            else:
                model_name = getattr(model, "model", None) or getattr(model, "name", None)
            if model_name:
                available_models.append(model_name)
        return available_models