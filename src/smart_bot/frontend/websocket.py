import asyncio
from fastapi import WebSocket

from ..interface import ToolCallBlock


class WebSocketFrontend:
    """WebSocket frontend: sends/receives JSON via FastAPI WebSocket."""

    def __init__(self, websocket: WebSocket) -> None:
        self._ws = websocket
        self._pending_confirm: asyncio.Future[dict] | None = None

    async def on_turn_start(self) -> None:
        pass

    async def output_text(self, text: str) -> None:
        await self._ws.send_json({"type": "text", "text": text})

    async def output_thinking(self, text: str) -> None:
        await self._ws.send_json({"type": "thinking", "text": text})

    async def output_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        thinking_tokens: int,
        cached_tokens: int,
    ) -> None:
        await self._ws.send_json({
            "type": "usage",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "thinking_tokens": thinking_tokens,
            "cached_tokens": cached_tokens,
        })

    async def output_tool_call(self, call_id: str, name: str, arguments: dict) -> None:
        await self._ws.send_json({
            "type": "tool_call",
            "call_id": call_id,
            "name": name,
            "arguments": arguments,
        })

    async def output_tool_result(self, call_id: str, name: str, result: str) -> None:
        await self._ws.send_json({
            "type": "tool_result",
            "call_id": call_id,
            "name": name,
            "result": result,
        })

    async def output_error(self, message: str) -> None:
        await self._ws.send_json({"type": "error", "message": message})

    def handle_ws_message(self, data: dict) -> bool:
        """Forward incoming messages to the pending confirmation future, if any.
        Called from the main ws loop for messages that arrive outside of
        a confirmation dialog (should not normally happen).
        """
        if data.get("type") == "tool_confirm" and self._pending_confirm and not self._pending_confirm.done():
            self._pending_confirm.set_result(data)
            return True
        return False

    async def request_tool_confirmation(self, tool_block: ToolCallBlock) -> bool:
        await self._ws.send_json({
            "type": "tool_confirm_request",
            "call_id": tool_block.call_id,
            "name": tool_block.name,
            "arguments": tool_block.arguments,
        })
        confirm_data = await self._ws.receive_json()
        return (
            confirm_data.get("type") == "tool_confirm"
            and confirm_data.get("confirmed", False)
        )

    async def request_user_input(self, question: str) -> str:
        await self._ws.send_json({"type": "ask_user", "question": question})
        response_data = await self._ws.receive_json()
        return response_data.get("text", "")

    async def on_turn_end(self) -> None:
        await self._ws.send_json({"type": "done"})
