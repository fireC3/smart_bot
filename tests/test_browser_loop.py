"""Tests for browser_control tool — direct and LLM-integrated."""
import pytest
from smart_bot.config import ConfigManager
from smart_bot.interface import PlatformConfig, ToolExecuteContext, ToolPermission


def _get_default_llm_config():
    cfg = ConfigManager.get()
    settings = cfg.settings.to_dict()
    platform_id = settings.get("default_platform", "")
    if not platform_id or platform_id not in cfg.platforms.items:
        available = list(cfg.platforms.items.keys())
        if not available:
            raise RuntimeError("No platforms configured")
        platform_id = available[0]
    platform_data = cfg.platforms.get(platform_id)
    config = PlatformConfig.from_platform_dict(platform_id, platform_data)
    api_key = cfg.platforms.api_key(platform_id)
    model_name = settings.get("default_model", {}).get(platform_id, "")
    return config, api_key, model_name


def test_browser_control_direct():
    """Direct test: navigate, read, screenshot without LLM."""
    import asyncio
    from smart_bot.tools.browser_control import BrowserControl
    from smart_bot.interface.tool import ToolExecuteContext

    async def run():
        tool = BrowserControl()
        ctx = ToolExecuteContext()
        try:
            nav = await tool.run({"action": "navigate", "url": "https://example.com"}, ctx)
            print("===== Navigate Result =====")
            print(nav[:500])
            assert "Example Domain" in nav, "Should find page title in response"

            read = await tool.run({"action": "read"}, ctx)
            print("\n===== Read Result =====")
            print(read[:300])
            assert "Example" in read, "Should contain page text"

            scr = await tool.run({"action": "screenshot"}, ctx)
            print(f"\n===== Screenshot: {scr} =====")
            assert "screenshots" in scr, "Should save screenshot"

            print("\nAll direct tests passed.")
        finally:
            await tool.cleanup()

    asyncio.run(run())


def test_browser_control_with_llm():
    """LLM integration test: AI operates browser to complete a task."""
    import asyncio
    from smart_bot.interface import ToolManager
    from smart_bot.platforms import DeepSeekLLM
    from smart_bot.interface.message import (
        SystemMessage, UserMessage, AIMessage, TextBlock,
        ToolMessage, ToolCallBlock, UsageBlock,
    )
    from smart_bot.interface.tool import PermissionMode, ToolExecuteContext
    from smart_bot.interface.memory import Memory

    async def run():
        tool_manager = ToolManager()
        await tool_manager.enable_tools(["browser_control"])
        tool_manager.set_permission_mode(PermissionMode.ALLOW_ALL)

        config, api_key, model_name = _get_default_llm_config()
        # if config.provider != "dashscope":
        #     print(f"Current default platform '{config.provider}' is not 'dashscope'. Please set up a Dashscope platform for this test.")
        #     return
        llm = DeepSeekLLM(config, api_key=api_key, model_name=model_name, memory=Memory("test_browser_loop_memory"))
        await llm.enable()

        task = "帮我从淘宝找一下有什么好吃的，必须要有它的配料表"

        history = [
            SystemMessage(content=[TextBlock(text=(
                "You are a helpful assistant with browser control capabilities.\n"
                "The browser window is VISIBLE — the user can see it and interact with it.\n"
                "When a page asks for login or verification, the user CAN solve it manually.\n"
                "Your job at that point is to WAIT, not to find a workaround.\n\n"
                "## RULE #1: Login or verification → WAIT, don't switch\n"
                "If scan/read shows any of these, the user needs to act:\n"
                "- Login page: links/buttons labeled '登录', 'Sign in', 'Login', '亲，请登录'\n"
                "- Captcha/verification: '验证码', captcha, slider, puzzle\n"
                "- Loading overlay with a login link behind it\n"
                "WHAT TO DO:\n"
                "1. Tell the user in Chinese what you see and ask them to act\n"
                "2. Call wait(wait_ms=10000) then scan — repeat until page shows real content\n"
                "3. Check each scan result: did it change? Is there now product/search data?\n"
                "4. Poll at least 10 times before concluding the page is non-functional\n"
                "WHAT NOT TO DO:\n"
                "- Do NOT try other sites, search engines, or alternative approaches\n"
                "- Do NOT use wait_ms shorter than 10000 — the user needs time\n"
                "- Do NOT give up after 2-3 polls — the user might be typing a password\n"
                "- A login page is NOT a blocked page — it means the user CAN help\n\n"
                "## When a site is truly blocking (not login)\n"
                "Only conclude a site is blocking after 10+ polls show:\n"
                "- NO login link or login form at all\n"
                "- NO product data, NO search results — just spinners or blank\n"
                "- The page content does NOT change between polls\n"
                "Then say '这个网站可能限制了自动访问，我换一个方式试试' and try ONE alternative.\n\n"
                "## Reading pages\n"
                "- navigate/scan/click/scroll return an ARIA accessibility tree\n"
                "- ARIA shows: link 'X' → click with a:has-text('X')\n"
                "              button 'X' → click with button:has-text('X')\n"
                "              textbox → type into it\n"
                "- If scan header says 'body has X chars but only Y ARIA lines',\n"
                "  content is in iframes — use read to get full text\n"
                "- read returns the full visible text; scan shows structure\n\n"
                "## Other notes\n"
                "- Clicks may open new tabs — the tool auto-switches, use scan to verify\n"
                "- If click/type fails, check the last ARIA snapshot for the correct selector\n"
                "- When you have enough info to answer, summarize and stop calling tools"
            ))]),
            UserMessage(content=[TextBlock(text=task)]),
        ]

        ctx = ToolExecuteContext()

        print("===== Tools Schema =====")
        for tool in tool_manager.get_enabled_tools_schema():
            name = tool["function"]["name"]
            desc = tool["function"]["description"][:100]
            print(f"  {name}: {desc}...")
        print("========================\n")

        max_loops = 30
        for i in range(max_loops):
            responses = llm.invoke(
                history,
                tools=tool_manager.get_enabled_tools_schema(),
            )
            tool_calls = []
            message_blocks = []
            is_thinking = False

            print(f"\n========== Loop {i+1} ==========")
            async for response in responses:
                if isinstance(response, TextBlock):
                    message_blocks.append(response)
                    if response.thinking:
                        if not is_thinking:
                            print("===== Thinking =====")
                            is_thinking = True
                        print(response.thinking, end="", flush=True)
                    if response.text:
                        if is_thinking:
                            print("\n===== Response =====")
                            is_thinking = False
                        print(response.text, end="", flush=True)

                if isinstance(response, ToolCallBlock):
                    print(f"\n===== Tool Call: {response.name} =====")
                    print(f"Arguments: {response.arguments}")
                    res = await tool_manager.execute_tool(response, ctx)
                    print(f"Result preview: {str(res.content)}")
                    tool_calls.append(res)

            if tool_calls:
                history.append(ToolMessage(
                    ai_think=TextBlock.combine_text_blocks(message_blocks),
                    content=tool_calls,
                    usage=UsageBlock(),
                ))
            else:
                history.append(AIMessage(
                    content=[TextBlock.combine_text_blocks(message_blocks)],
                    usage=UsageBlock(),
                ))
                print("\n\n===== Task Complete (no more tool calls) =====")
                break
        else:
            print("\n\n===== Max loops reached =====")

        # Cleanup browser
        tool = tool_manager.get_enabled_tool("browser_control")
        if tool:
            await tool.cleanup()

    asyncio.run(run())


if __name__ == "__main__":
    # test_browser_control_direct()
    test_browser_control_with_llm()
