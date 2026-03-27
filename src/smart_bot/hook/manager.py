from .model import HookContent, HookEvent
from .hook import Hook, HookResult


class HookManager:
    def __init__(self, context: HookContent):
        self.hooks = {event: [] for event in HookEvent}
        self._hook_content = context

    def register_hook(self, event: HookEvent, hook: Hook) -> None:
        self.hooks[event].append(hook)

    def to_dict(self) -> dict:
        return {event.value: [h.to_dict() for h in hooks] for event, hooks in self.hooks.items()}

    @staticmethod
    def from_dict(data: dict, context: HookContent) -> "HookManager":
        manager = HookManager(context)
        for event in HookEvent:
            for hook_dict in data.get(event.value, []):
                manager.register_hook(event, Hook.from_dict(hook_dict))
        return manager

    async def run_hooks(self, event: HookEvent, arguments: dict) -> tuple[bool, list[HookResult]]:
        hook_results: list[HookResult] = []
        blocked: bool = False
        for hook in self.hooks[event]:
            if event in (HookEvent.TOOL_CALL_BEFORE, HookEvent.TOOL_CALL_AFTER):
                if hook.match_tool and arguments.get("tool_name") not in hook.match_tool:
                    continue
            hook_result = await hook.run(event, arguments, self._hook_content)
            hook_results.append(hook_result)
            if hook_result.blocked:
                blocked = True
                break
        return blocked, hook_results
