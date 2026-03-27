import asyncio
from dataclasses import dataclass
from .model import HookContent, HookEvent
from .action import BashHookAction, HttpHookAction


@dataclass
class HookResult:
    hook: "Hook"
    is_success: bool
    blocked: bool = False
    result: str | None = None


class Hook:
    def __init__(self, hook: BashHookAction | HttpHookAction, timeout: int = 30, block_on_failure: bool = True, match_tool: list[str] | None = None):
        self.hook = hook
        self.timeout = timeout
        self.block_on_failure = block_on_failure
        self.match_tool = match_tool

    def to_dict(self) -> dict:
        d = {
            "action": self.hook.to_dict(),
            "timeout": self.timeout,
            "block_on_failure": self.block_on_failure,
        }
        if self.match_tool:
            d["match_tool"] = self.match_tool
        return d

    @staticmethod
    def from_dict(data: dict) -> "Hook":
        action_data = data["action"]
        action_cls = globals().get(action_data["type"])
        if action_cls is None:
            raise ValueError(f"Unknown hook action type: {action_data['type']}")
        action = action_cls.from_dict(action_data)
        return Hook(
            hook=action,
            timeout=data.get("timeout", 30),
            block_on_failure=data.get("block_on_failure", True),
            match_tool=data.get("match_tool"),
        )

    async def run(self, event: HookEvent, arguments: dict, hook_content: HookContent) -> HookResult:
        try:
            async with asyncio.timeout(self.timeout):
                is_success, reason = await self.hook.run(event, arguments, hook_content)
                blocked = (not is_success) and self.block_on_failure
                res = HookResult(hook=self, is_success=is_success, blocked=blocked, result=reason)
        except Exception as e:
            res = HookResult(
                hook=self,
                is_success=False,
                blocked=self.block_on_failure,
                result=f"Runtime Error: {str(e)}"
            )
        finally:
            if not res.is_success:
                await self.hook.stop()
        return res
