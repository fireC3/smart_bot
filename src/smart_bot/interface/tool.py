import asyncio
import importlib
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from uuid_backport import uuid7

from ..hook import HookManager, HookEvent
from ..skill.skill_manager import SkillManager

class PermissionMode(Enum):
    DENY_ALL = "deny_all"
    STRICT = "strict"
    DEFAULT = "default"
    ALLOW_WRITE = "allow_write"
    ALLOW_BASH = "allow_bash"
    ALLOW_ALL = "allow_all"


class ToolPermission(Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True


@dataclass
class ToolExecuteContext:
    cwd: Path = Path.home()
    skill_manager: SkillManager | None = None
    hook_manager: HookManager | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)



class BaseTool(ABC):
    """工具基类，所有工具都需要继承此类"""
    
    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = []
    permission: ToolPermission = ToolPermission.CONFIRM
    
    def __init__(self):
        self.name = self.name or self.__class__.__name__
        self.description = self.description or 'No description provided'
        self.parameters = self.parameters or []

    async def confirm_permissions(self, arguments: Dict[str, Any]) -> bool:
        """可选的权限确认方法，返回 False 将阻止工具执行"""
        return True
    async def setup(self) -> None:
        """可选的初始化方法，在工具被加载时调用"""
        pass
    
    @abstractmethod
    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        """执行工具的主要方法"""
        raise NotImplementedError
    
    def to_dict(self) -> Dict:
        """转换为字典格式，用于传递给AI模型"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        param.name: {
                            "type": param.type,
                            "description": param.description,
                        }
                        for param in self.parameters
                    },
                    "required": [
                        param.name
                        for param in self.parameters
                        if param.required
                    ]
                }
            }
        }


class ToolManager:
    _tools: dict[str, type[BaseTool]] = {}

    def __init__(self):
        from smart_bot.config import ConfigManager, get_tmp_path
        self._cfg = ConfigManager.get()
        self._tmp_path = get_tmp_path()
        self._enabled_tools: Dict[str, BaseTool] = {}
        self._auto_discover_tools()

    @classmethod
    def register_tool(cls, tool_class: Type[BaseTool]):
        name = getattr(tool_class, 'name', None) or tool_class.__name__
        cls._tools[name] = tool_class
        return tool_class

    def _auto_discover_tools(self):
        from smart_bot import PACKAGE_PATH
        tools_dir = PACKAGE_PATH / "tools"

        for file_path in tools_dir.glob("*.py"):
            module_name = f"smart_bot.tools.{file_path.stem}"

            try:
                module = importlib.import_module(module_name)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    if (isinstance(attr, type) and
                        issubclass(attr, BaseTool) and
                        attr != BaseTool):

                        name = getattr(attr, 'name', None) or attr.__name__
                        if name not in self._tools:
                            self._tools[name] = attr
                            print(f"Auto-discovered tool: {name}")

            except Exception as e:
                print(f"Error importing module {module_name}: {e}")

    async def enable_tools(self, names: list[str]):
        new_tools: Dict[str, BaseTool] = {}

        for name in names:
            if name in self._enabled_tools:
                print(f"Tool '{name}' is already enabled")
                continue

            tool_class = self._tools.get(name)
            if not tool_class:
                raise ValueError(f"Tool '{name}' not found")

            tool_instance = tool_class()
            new_tools[name] = tool_instance

        self._enabled_tools.update(new_tools)

        if new_tools:
            results = await asyncio.gather(
                *(tool.setup() for tool in new_tools.values()),
                return_exceptions=True
            )
            for name, result in zip(new_tools.keys(), results):
                if isinstance(result, Exception):
                    print(f"Tool '{name}' setup failed: {result}")

    def get_enabled_tool(self, name: str) -> BaseTool | None:
        return self._enabled_tools.get(name)

    def get_all_tools_name(self) -> List[str]:
        return list(self._tools.keys())

    def get_enabled_tools_schema(self) -> List[Dict]:
        return [tool.to_dict() for tool in self._enabled_tools.values()]

    def set_permission_mode(self, mode: PermissionMode):
        for tool in self._enabled_tools.values():
            tool.change_permission(mode)

    def get_tool_permission(self, name: str) -> str:
        tool = self.get_enabled_tool(name)
        if tool:
            return tool.permission
        return ToolPermission.CONFIRM

    def _truncate_if_needed(self, result: str, tool_name: str, tool_call_id: str) -> str:
        max_len = self._cfg.settings.tool_inline_limit or 8000
        if len(result) <= max_len:
            return result
        artifact_dir = self._tmp_path / "tool_artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        uid = str(uuid7())[:8]
        artifact_path = artifact_dir / f"{ts}-{tool_name}-{uid}.txt"
        artifact_path.write_text(result, encoding="utf-8")
        preview_chars = self._cfg.settings.tool_preview_chars or 8000
        preview = result[:preview_chars]
        return (
            f"[Tool output truncated]\n"
            f"Tool call id: {tool_call_id}\n"
            f"Original size: {len(result)} chars\n"
            f"Full output saved to: {artifact_path}\n"
            f"Preview:\n{preview}"
        )

    async def execute_tool(self, tool_call: "ToolCallBlock", context: ToolExecuteContext) -> "ToolCallBlock":
        from .message import ToolCallBlock

        tool = self.get_enabled_tool(tool_call.name)
        if not tool:
            tool_call.content = f"调用失败: Tool '{tool_call.name}' not found or not enabled"
            return tool_call

        try:
            args = dict(tool_call.arguments)

            hm = context.hook_manager
            if hm:
                blocked, _ = await hm.run_hooks(
                    HookEvent.TOOL_CALL_BEFORE,
                    {"tool_name": tool_call.name, "tool_arguments": args}
                )
                if blocked:
                    tool_call.content = f"调用失败: Tool '{tool_call.name}' blocked by before-hook"
                    return tool_call

            result = await tool.run(args, context)

            if hm:
                await hm.run_hooks(
                    HookEvent.TOOL_CALL_AFTER,
                    {"tool_name": tool_call.name, "tool_arguments": args, "is_success": True, "tool_result": result, "tool_call_id": tool_call.call_id}
                )

            tool_call.content = self._truncate_if_needed(result, tool_call.name, tool_call.call_id)

        except Exception as e:
            import traceback
            tool_call.content = f"调用失败: {str(e)}\n{traceback.format_exc()}"

            if hm:
                await hm.run_hooks(
                    HookEvent.TOOL_CALL_FAILED,
                    {"tool_name": tool_call.name, "tool_arguments": tool_call.arguments, "is_success": False, "tool_result": tool_call.content, "tool_call_id": tool_call.call_id}
                )

        return tool_call