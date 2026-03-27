from __future__ import annotations

import asyncio
import importlib
import logging
from dataclasses import dataclass
from pathlib import Path

from uuid_backport import uuid7

from smart_bot import PACKAGE_PATH
from smart_bot.frontend import ChatFrontend
from smart_bot.hook import HookContent, HookEvent, HookManager
from smart_bot.interface import (
    Memory, SystemMessage, TextBlock, ToolCallBlock, UsageBlock, UserMessage,
    LLM, PlatformConfig, ToolExecuteContext, ToolPermission,
)
from smart_bot.platforms import PROVIDER_MODULE, PROVIDER_CLASS
from smart_bot.prompts import build_base_system_prompt, EnvironmentData, get_environment_info, build_environment_prompt
from smart_bot.state import AppState
from smart_bot.config import get_data_path
from smart_bot.skill import SkillManager
from smart_bot.interface import ToolManager

logger = logging.getLogger(__name__)


# ============================================================================
# MainChatState — per-session chat state with unified build/destroy
# ============================================================================


@dataclass
class MainChatState:
    llm: LLM
    memory: Memory
    tool_manager: ToolManager
    hook_manager: HookManager
    skill_manager: SkillManager
    platform_id: str
    model_name: str
    app_state: AppState

    @classmethod
    async def build(
        cls,
        app_state: AppState,
        session_id: str | None = None,
        platform_id: str | None = None,
        model_name: str | None = None,
    ) -> MainChatState:
        """Build a fully-initialized chat session state.

        Consolidates the setup logic from main.py and web.py into a single
        entry point.
        """
        cfg = app_state.config
        settings = cfg.settings.to_dict()
        platforms = cfg.platforms.items

        # ----- resolve platform -----
        if platform_id is None:
            platform_id = settings.get("default_platform", "")
        if not platform_id or platform_id not in platforms:
            available = list(platforms.keys())
            if not available:
                raise ValueError("No platforms configured")
            platform_id = available[0]

        # ----- resolve model -----
        if model_name is None:
            model_name = settings.get("default_model", {})[platform_id]

        # ----- build PlatformConfig with provider defaults merged -----
        platform_data = cfg.platforms.get(platform_id)
        platform_config = PlatformConfig.from_platform_dict(platform_id, platform_data)

        # ----- memory -----
        if session_id is None:
            session_id = str(uuid7())
        memory = Memory(f"memory_{session_id}")

        # ----- LLM -----
        mod = importlib.import_module(PROVIDER_MODULE[platform_config.provider])
        cls_ = getattr(mod, PROVIDER_CLASS[platform_config.provider])
        api_key = cfg.platforms.api_key(platform_id)
        llm = cls_(platform_config, api_key=api_key, model_name=model_name, memory=memory)

        # ----- hooks -----
        hook_manager = HookManager.from_dict(
            cfg.hooks.data,
            HookContent(cwd=Path.cwd(), metadata={"session_id": session_id}),
        )
        # ----- skills -----
        skill_paths: list[Path] = [
            PACKAGE_PATH / "skill" / "embed",
            get_data_path() / "skills",
        ]
        for p in cfg.settings.extra_skill_paths:
            skill_paths.append(Path(p))
        skill_manager = SkillManager(skill_paths)
        await skill_manager.load()

        # ----- tools -----
        tool_manager = ToolManager()
        await tool_manager.enable_tools(tool_manager.get_all_tools_name())
        tool_manager.set_permission_mode(app_state.permission_mode)

        # ----- system prompt -----
        base_system_prompt = build_base_system_prompt()
        environment_data = get_environment_info()
        environment_prompt = build_environment_prompt(environment_data)
        skills_prompt = skill_manager.build_skill_prompt()
        sys_msg = SystemMessage(content=[TextBlock(text=base_system_prompt + "\n\n" + environment_prompt + "\n\n" + skills_prompt)])
        memory.add_message(sys_msg)

        # ----- start -----
        await hook_manager.run_hooks(HookEvent.SESSION_START, {"session_id": session_id})
        await llm.enable()

        return cls(
            llm=llm,
            memory=memory,
            tool_manager=tool_manager,
            hook_manager=hook_manager,
            skill_manager=skill_manager,
            platform_id=platform_id,
            model_name=model_name,
            app_state=app_state,
        )

    async def destroy(self) -> None:
        """Clean up session resources."""
        if self.llm is not None:
            await self.hook_manager.run_hooks(
                HookEvent.SESSION_END, {"session_id": self.memory.session_id}
            )
            await self.llm.disable()

    async def switch_llm(self, platform_id: str, model_name: str) -> None:
        """Replace the LLM in-place while keeping the same memory/session.

        The new LLM is fully created and enabled before the old one is
        disabled, so a failed switch leaves the session intact.
        """
        cfg = self.app_state.config

        platform_data = cfg.platforms.get(platform_id)
        if not platform_data:
            raise ValueError(f"Platform '{platform_id}' not found")

        platform_config = PlatformConfig.from_platform_dict(platform_id, platform_data)

        api_key = cfg.platforms.api_key(platform_id)
        mod = importlib.import_module(PROVIDER_MODULE[provider])
        cls_ = getattr(mod, PROVIDER_CLASS[provider])
        new_llm = cls_(platform_config, api_key=api_key, model_name=model_name, memory=self.memory)
        await new_llm.enable()

        old_llm = self.llm
        self.llm = new_llm
        self.platform_id = platform_id
        self.model_name = model_name

        if old_llm is not None:
            await old_llm.disable()


# ============================================================================
# MainChatPipeline — unified chat turn orchestrator
# ============================================================================


class MainChatPipeline:
    """Orchestrates a single chat turn: invoke LLM, stream deltas, run tools.

    All I/O goes through the ChatFrontend protocol, making this class
    independent of CLI vs WebSocket transport.
    """

    def __init__(self, frontend: ChatFrontend) -> None:
        self.frontend = frontend

    async def run_chat_turn(
        self,
        chat_state: MainChatState,
        user_text: str,
        max_iterations: int = 20,
    ) -> None:
        user_message = [UserMessage(content=[TextBlock(text=user_text)])]

        for iteration in range(max_iterations):
            await self.frontend.on_turn_start()

            response = chat_state.llm.invoke(
                user_message if iteration == 0 else None,
                tools=chat_state.tool_manager.get_enabled_tools_schema(),
            )
            user_message = None

            allow_tools: list[ToolCallBlock] = []
            pending_confirms: list[ToolCallBlock] = []

            async for delta in response:
                if isinstance(delta, TextBlock):
                    if delta.thinking:
                        await self.frontend.output_thinking(delta.thinking)
                    if delta.text:
                        await self.frontend.output_text(delta.text)

                elif isinstance(delta, ToolCallBlock):
                    await self.frontend.output_tool_call(
                        delta.call_id, delta.name, dict(delta.arguments)
                    )
                    permission = chat_state.tool_manager.get_tool_permission(delta.name)
                    if permission == ToolPermission.ALLOW:
                        allow_tools.append(delta)
                    elif permission == ToolPermission.CONFIRM:
                        pending_confirms.append(delta)
                    elif permission == ToolPermission.DENY:
                        delta.content = f"调用失败: Tool '{delta.name}' permission denied"
                        await self.frontend.output_tool_result(
                            delta.call_id, delta.name, delta.content
                        )

                elif isinstance(delta, UsageBlock):
                    await self.frontend.output_usage(
                        prompt_tokens=delta.prompt_tokens,
                        completion_tokens=delta.completion_tokens,
                        thinking_tokens=delta.thinking_tokens,
                        cached_tokens=delta.cached_tokens,
                    )

                else:
                    logger.warning("Unknown delta type: %s", type(delta).__name__)

            # ----- tool confirmation -----
            for tc in pending_confirms:
                confirmed = await self.frontend.request_tool_confirmation(tc)
                if confirmed:
                    allow_tools.append(tc)
                else:
                    tc.content = f"用户拒绝执行工具 '{tc.name}'"
                    await self.frontend.output_tool_result(
                        tc.call_id, tc.name, tc.content
                    )

            # ----- execute tools -----
            if allow_tools:
                ctx = ToolExecuteContext(
                    hook_manager=chat_state.hook_manager,
                    skill_manager=chat_state.skill_manager,
                    metadata={"ask_user_func": self.frontend.request_user_input},
                )
                coroutines = [
                    chat_state.tool_manager.execute_tool(tc, ctx) for tc in allow_tools
                ]
                results = await asyncio.gather(*coroutines, return_exceptions=True)
                for result in results:
                    if isinstance(result, ToolCallBlock):
                        await self.frontend.output_tool_result(
                            result.call_id, result.name,
                            str(result.content) if result.content else "",
                        )
                    elif isinstance(result, Exception):
                        await self.frontend.output_error(
                            f"Tool execution error: {result}"
                        )
            else:
                break

        await self.frontend.on_turn_end()
