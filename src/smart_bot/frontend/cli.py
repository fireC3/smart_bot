import asyncio

from ..interface import ToolCallBlock


class CLIFrontend:
    """CLI frontend: prints to stdout, reads from stdin."""

    def __init__(self) -> None:
        self._first_thinking = True
        self._first_answer = True

    async def on_turn_start(self) -> None:
        self._first_thinking = True
        self._first_answer = True

    async def output_text(self, text: str) -> None:
        if self._first_answer:
            self._first_answer = False
            print("\n========== Answer ==========\n", flush=True)
        print(text, end="", flush=True)

    async def output_thinking(self, text: str) -> None:
        if self._first_thinking:
            self._first_thinking = False
            print("\n========== Thinking ==========\n", flush=True)
        print(text, end="", flush=True)

    async def output_usage(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        thinking_tokens: int,
        cached_tokens: int,
    ) -> None:
        print(
            f"\n========== Usage ==========\n"
            f"Prompt tokens: {prompt_tokens}, Cached tokens: {cached_tokens}, "
            f"Completion tokens: {completion_tokens}, "
            f"Thinking tokens: {thinking_tokens}",
            flush=True,
        )

    async def output_tool_call(self, call_id: str, name: str, arguments: dict) -> None:
        print(f"\n===== Tool Call: {name} =====\nArguments: {arguments}", flush=True)

    async def output_tool_result(self, call_id: str, name: str, result: str) -> None:
        print(f"\n===== Tool {name} =====\nResult: {result}\n", flush=True)

    async def output_error(self, message: str) -> None:
        print(f"\nError: {message}", flush=True)

    async def request_tool_confirmation(self, tool_block: ToolCallBlock) -> bool:
        user_input = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: input(
                f"\n工具调用 '{tool_block.name}'\n"
                f"工具参数: {tool_block.arguments}\n"
                f"需要用户确认(y/n)，按回车确认执行...(y):"
            ),
        )
        user_input = user_input.strip().lower()
        return user_input in ("", "y")

    async def request_user_input(self, question: str) -> str:
        user_input = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: input(f"\n[AI 提问] {question}\n你的回答: "),
        )
        return user_input.strip()

    async def on_turn_end(self) -> None:
        pass
