from typing import Protocol, runtime_checkable

from ..interface import ToolCallBlock


@runtime_checkable
class ChatFrontend(Protocol):
    """I/O abstraction for chat frontends (CLI, WebSocket, etc.)."""

    async def on_turn_start(self) -> None:
        """Called at the beginning of each chat turn."""
        ...

    async def output_text(self, text: str) -> None:
        """Emit a text delta from the model."""
        ...

    async def output_thinking(self, text: str) -> None:
        """Emit a thinking/scratchpad delta from the model."""
        ...

    async def output_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        thinking_tokens: int,
        cached_tokens: int,
    ) -> None:
        """Emit token usage information."""
        ...

    async def output_tool_call(
        self, call_id: str, name: str, arguments: dict
    ) -> None:
        """Emit a tool call that the model decided to invoke."""
        ...

    async def output_tool_result(
        self, call_id: str, name: str, result: str
    ) -> None:
        """Emit the result of a tool execution."""
        ...

    async def output_error(self, message: str) -> None:
        """Emit an error message."""
        ...

    async def request_tool_confirmation(
        self, tool_block: ToolCallBlock
    ) -> bool:
        """Ask the user to confirm a tool call. Return True if allowed."""
        ...

    async def request_user_input(self, question: str) -> str:
        """Ask the user a question and return their response."""
        ...

    async def on_turn_end(self) -> None:
        """Called when a chat turn finishes (no more tool calls)."""
        ...
