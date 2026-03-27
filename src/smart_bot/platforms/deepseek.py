import asyncio
import json
from typing import Any, AsyncGenerator, ClassVar, Dict, List

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, InternalServerError, RateLimitError

from smart_bot.interface import (
    ModelCapability, ThinkingEffort, LLM, PlatformConfig,
    ContentBlock, ContentType, ImageBlock, MediaType,
    Message, TextBlock, ToolCallBlock, UsageBlock,
    ResponseLengthExceedException, Memory, ToolMessage, AIMessage,
)

class DeepSeekLLM(LLM):
    default_config: ClassVar[PlatformConfig] = PlatformConfig(
        provider="deepseek",
        base_url="https://api.deepseek.com",
        timeout=60,
        max_retries=3,
        temperature=0.7,
        capability=ModelCapability(
            input_types=[ContentType.TEXT, ContentType.IMAGE],
            output_types=[ContentType.TEXT, ContentType.TOOL_CALL],
            max_tokens=131072,
            supports_stream=True,
            supports_tool_call=True,
            supports_thinking=True,
        ),
    )

    def __init__(self, config: PlatformConfig, api_key: str = "", model_name: str = "", memory: Memory = None):
        super().__init__(config, api_key=api_key, model_name=model_name, memory=memory)
        self.client = None

    async def enable(self):
        self.client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )

    async def disable(self):
        if self.client is not None:
            await self.client.close()
            self.client = None

    def transform_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        transformed_messages = []
        for message in messages:
            if isinstance(message, ToolMessage):
                call_dict = {
                    "role": "assistant",
                    "content": message.ai_think.text,
                    "tool_calls": []
                }
                if message.ai_think.thinking:
                    call_dict["reasoning_content"] = message.ai_think.thinking

                for content_block in message.content:
                    if not isinstance(content_block, ToolCallBlock):
                        continue
                    call_dict["tool_calls"].append({
                        "id": content_block.call_id,
                        "type": "function",
                        "function": {
                            "name": content_block.name,
                            "arguments": json.dumps(content_block.arguments)
                        }
                    })
                if call_dict["tool_calls"]:
                    transformed_messages.append(call_dict)

                for content_block in message.content:
                    if not isinstance(content_block, ToolCallBlock):
                        continue
                    if content_block.content is None:
                        continue
                    transformed_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": content_block.call_id,
                            "content": content_block.content,
                        }
                    )
            else:
                payload: Dict[str, Any] = {"role": message.role}
                parts: List[Dict[str, Any]] = []
                for block in message.content:
                    if isinstance(block, TextBlock):
                        parts.append({"type": "text", "text": block.text})
                        if block.thinking:
                            payload["reasoning_content"] = block.thinking

                    elif isinstance(block, ImageBlock):
                        image_url = block.source.data
                        if block.source.type == MediaType.BASE64:
                            mime_type = block.source.mimeType or "image/jpeg"
                            image_url = f"data:{mime_type};base64,{block.source.data}"
                        parts.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url},
                            }
                        )
                payload["content"] = parts
                transformed_messages.append(payload)
        return transformed_messages

    def _parse_text_block(self, payload: Any) -> ContentBlock | None:
        text = getattr(payload, "content", "")
        thinking = getattr(payload, "reasoning_content", "")

        text_value = text if isinstance(text, str) else ""
        thinking_value = thinking if isinstance(thinking, str) and thinking else None
        if not text_value and thinking_value is None:
            return None
        return TextBlock(
                text=text_value,
                thinking=thinking_value,
            )

    def _build_memory_message(self, blocks: List[ContentBlock]) -> Message | None:
        usage = next((block for block in blocks if isinstance(block, UsageBlock)), UsageBlock())
        persisted_blocks = [block for block in blocks if not isinstance(block, UsageBlock)]
        if not persisted_blocks:
            return None
        text_blocks = [block for block in persisted_blocks if isinstance(block, TextBlock)]
        tool_blocks = [block for block in persisted_blocks if isinstance(block, ToolCallBlock)]

        if tool_blocks:
            ai_think = TextBlock.combine_text_blocks(text_blocks) if text_blocks else TextBlock(text="", thinking=None)
            return ToolMessage(ai_think=ai_think, content=tool_blocks, usage=usage)
        return AIMessage(content=persisted_blocks, usage=usage)

    def _parse_tool_arguments(self, arguments: str) -> dict:
        if not arguments:
            return {}
        return json.loads(arguments)

    def _merge_tool_call_chunk(self, tool_calls: Dict[int, Dict[str, str]], tool_call_chunk: Any) -> None:
        index = getattr(tool_call_chunk, "index", None)
        if index is None:
            index = len(tool_calls)

        tool_state = tool_calls.setdefault(
            index,
            {
                "id": "",
                "name": "",
                "arguments": "",
            },
        )

        if getattr(tool_call_chunk, "id", None):
            tool_state["id"] = tool_call_chunk.id

        function = getattr(tool_call_chunk, "function", None)
        if function is None:
            return

        if getattr(function, "name", None):
            tool_state["name"] = function.name
        if getattr(function, "arguments", None):
            tool_state["arguments"] += function.arguments

    def _finalize_tool_calls(self, tool_calls: Dict[int, Dict[str, str]]) -> List[ToolCallBlock]:
        finalized_calls = []
        for index in sorted(tool_calls):
            tool_state = tool_calls[index]
            finalized_calls.append(
                ToolCallBlock(
                    call_id=tool_state["id"],
                    name=tool_state["name"],
                    arguments=self._parse_tool_arguments(tool_state["arguments"]),
                )
            )
        return finalized_calls

    async def _create_completion_with_retry(self, **request_kwargs: Any) -> Any:
        attempts = max(1, self.config.max_retries + 1)
        retryable_exceptions = (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )

        for attempt in range(1, attempts + 1):
            try:
                return await self.client.chat.completions.create(**request_kwargs)
            except retryable_exceptions:
                if attempt == attempts:
                    raise
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

    async def invoke(
        self, messages: list[Message] | None, tools: list[dict] | None = None,
    ) -> AsyncGenerator[ContentBlock, None]:
        if self.client is None:
            raise Exception("DeepSeekLLM client is not initialized. Call enable() first.")
        if self.memory is not None:
            for msg in messages or []:
                self.memory.add_message(msg)
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
            request_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            request_kwargs["reasoning_effort"] = cap.thinking_effort.value

        if cap.max_tokens is not None:
            request_kwargs["max_tokens"] = cap.max_tokens
        if cap.max_completion_tokens is not None:
            request_kwargs["max_completion_tokens"] = cap.max_completion_tokens

        if not cap.supports_stream:
            request_kwargs["stream"] = False
            response = await self._create_completion_with_retry(**request_kwargs)
            blocks: list[ContentBlock] = []
            choices = getattr(response, "choices", None) or []
            if choices:
                choice = choices[0]
                assistant_message = getattr(choice, "message", None)
                content = self._parse_text_block(assistant_message)
                if content is not None:
                    blocks.append(content)
                    yield content
                if assistant_message and getattr(assistant_message, "tool_calls", None):
                    for tc in assistant_message.tool_calls:
                        tb = ToolCallBlock(
                            call_id=tc.id,
                            name=tc.function.name,
                            arguments=self._parse_tool_arguments(tc.function.arguments),
                        )
                        blocks.append(tb)
                        yield tb
                if getattr(choice, "finish_reason", None) == "length":
                    raise ResponseLengthExceedException()
            if getattr(response, "usage", None):
                ub = UsageBlock(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    thinking_tokens=getattr(response.usage.completion_tokens_details, "reasoning_tokens", 0),
                    cached_tokens=getattr(response.usage.prompt_tokens_details, "cached_tokens", 0),
                )
                blocks.append(ub)
                yield ub
            if self.memory is not None:
                mm = self._build_memory_message(blocks)
                if mm is not None:
                    self.memory.add_message(mm)
            return

        # Streaming path
        request_kwargs["stream"] = True
        request_kwargs["stream_options"] = {"include_usage": True}
        stream = await self._create_completion_with_retry(**request_kwargs)
        text_blocks: list[TextBlock] = []
        tool_blocks: list[ToolCallBlock] = []
        tool_calls: Dict[int, Dict[str, str]] = {}
        usage = None
        async for chunk in stream:
            if getattr(chunk, "choices", None) and len(chunk.choices) > 0:
                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue
                block = self._parse_text_block(delta)
                if block is not None:
                    text_blocks.append(block)
                    yield block
                if delta.tool_calls:
                    for tcc in delta.tool_calls:
                        self._merge_tool_call_chunk(tool_calls, tcc)
                if getattr(choice, "finish_reason", None) == "length":
                    raise ResponseLengthExceedException()
            elif getattr(chunk, "usage", None):
                usage = UsageBlock(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    thinking_tokens=getattr(chunk.usage.completion_tokens_details, "reasoning_tokens", 0),
                    cached_tokens=getattr(chunk.usage.prompt_tokens_details, "cached_tokens", 0),
                )
                yield usage

        if tool_calls:
            tool_blocks = self._finalize_tool_calls(tool_calls)
            for tool_block in tool_blocks:
                yield tool_block

        if self.memory is not None:
            ai_res = TextBlock.combine_text_blocks(text_blocks)
            mm = self._build_memory_message([ai_res] + tool_blocks + ([usage] if usage else []))
            if mm is not None:
                self.memory.add_message(mm)

    async def validate_message(self, message: Message) -> bool:
        for block in message.content:
            block_type = block.type if isinstance(block.type, ContentType) else ContentType(block.type)
            if not self.config.capability.supports_input(block_type):
                return False
        return True

    async def get_available_models(self) -> List[str]:
        if self.client is None:
            raise Exception("DeepSeekLLM client is not initialized. Call enable() first.")
        models = await self.client.models.list()
        return [model.id for model in models.data]
