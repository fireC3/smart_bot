import asyncio
from typing import Any, Dict, Optional

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager

DEFAULT_NAVIGATE_TIMEOUT = 30000
DEFAULT_ACTION_TIMEOUT = 5000


@ToolManager.register_tool
class BrowserControl(BaseTool):
    name = "browser_control"
    description = (
        "Through playwright control a web browser to navigate pages, click elements, type text, "
        "read page content, scan page structure, take screenshots, scroll, wait, "
        "and execute JavaScript."
    )
    parameters = [
        ToolParameter(name="action", type="string", description="Browser action: navigate, click, type, read, scan, screenshot, scroll, wait, evaluate", required=True),
        ToolParameter(name="url", type="string", description="URL for navigate (must include http:// or https://)", required=False),
        ToolParameter(name="selector", type="string", description="CSS selector for click, type, or wait", required=False),
        ToolParameter(name="text", type="string", description="Text to type into an input element", required=False),
        ToolParameter(name="script", type="string", description="JavaScript code to execute in the page for evaluate", required=False),
        ToolParameter(name="timeout", type="integer", description="Timeout in milliseconds (default: 30000 for navigate/wait, 5000 for click/type)", required=False),
        ToolParameter(name="wait_until", type="string", description="Page load strategy: 'load' (default), 'domcontentloaded', 'networkidle'", required=False),
        ToolParameter(name="wait_ms", type="integer", description="Extra milliseconds to wait after the action completes", required=False),
    ]
    permission = ToolPermission.CONFIRM

    def change_permission(self, mode: PermissionMode):
        match mode:
            case PermissionMode.DENY_ALL:
                self.permission = ToolPermission.DENY
            case PermissionMode.STRICT | PermissionMode.DEFAULT:
                self.permission = ToolPermission.CONFIRM
            case _:
                self.permission = ToolPermission.ALLOW

    _playwright: Optional[object] = None
    _browser: Optional[object] = None
    _context: Optional[object] = None
    _page: Optional[object] = None

    async def _get_browser(self):
        if BrowserControl._browser and BrowserControl._browser.is_connected():
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError("playwright not installed.")
        BrowserControl._playwright = await async_playwright().start()
        BrowserControl._browser = await BrowserControl._playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        BrowserControl._context = await BrowserControl._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        )
        BrowserControl._page = await BrowserControl._context.new_page()
        init_script = """
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """
        await BrowserControl._page.add_init_script(init_script)

        async def _on_new_page(page):
            await page.add_init_script(init_script)
            BrowserControl._page = page
        BrowserControl._context.on("page", _on_new_page)

    async def _ensure_page(self):
        await self._get_browser()
        pages = BrowserControl._context.pages
        if pages:
            latest = pages[-1]
            if BrowserControl._page is None or BrowserControl._page.is_closed():
                BrowserControl._page = latest
            elif latest != BrowserControl._page and not latest.is_closed():
                BrowserControl._page = latest
        if BrowserControl._page is None or BrowserControl._page.is_closed():
            BrowserControl._page = await BrowserControl._context.new_page()

    async def _build_aria_snapshot(self) -> str:
        page = BrowserControl._page
        snapshot = await page.locator("body").aria_snapshot()
        frames = page.frames
        if len(frames) > 1:
            for i, frame in enumerate(frames[1:], 1):
                try:
                    frame_snap = await frame.locator("body").aria_snapshot()
                    if frame_snap:
                        snapshot += f"\n\n# --- iframe #{i} ({frame.url[:80]}) ---\n{frame_snap}"
                except Exception:
                    pass
        body_text = (await page.evaluate("() => document.body?.innerText || ''")).strip()
        text_len = len(body_text)
        lines = snapshot.split("\n")
        total_lines = len(lines)
        parts = [
            f"# URL: {page.url}",
            f"# Title: {await page.title()}",
            f"# ARIA lines: {total_lines}, body text: {text_len} chars",
        ]
        return "\n".join(parts) + "\n" + snapshot

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        action = arguments.get("action", "")
        url = arguments.get("url", "")
        selector = arguments.get("selector", "")
        text = arguments.get("text", "")
        script = arguments.get("script", "")
        timeout = int(arguments.get("timeout", 0))
        wait_until = arguments.get("wait_until", "load")
        wait_ms = int(arguments.get("wait_ms", 0))

        valid_actions = {"navigate", "click", "type", "read", "scan", "screenshot", "scroll", "wait", "evaluate"}
        if action not in valid_actions:
            return f"Invalid action '{action}'. Valid: {', '.join(sorted(valid_actions))}"

        await self._ensure_page()
        page = BrowserControl._page

        if action == "navigate":
            if not url.startswith(("http://", "https://")):
                return "Error: url must start with http:// or https://"
            t = timeout or DEFAULT_NAVIGATE_TIMEOUT
            try:
                await page.goto(url, timeout=t, wait_until=wait_until)
            except Exception as e:
                return f"Navigate failed: {e}"
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000.0)
            else:
                await asyncio.sleep(1.0)
            return await self._build_aria_snapshot()

        elif action == "click":
            if not selector:
                return "Error: selector is required for click"
            t = timeout or DEFAULT_ACTION_TIMEOUT
            try:
                await page.click(selector, timeout=t)
            except Exception as e:
                return f"Click failed ({selector}): {e}"
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000.0)
            return f"Clicked: {selector}\n\n{await self._build_aria_snapshot()}"

        elif action == "type":
            if not selector:
                return "Error: selector is required for type"
            t = timeout or DEFAULT_ACTION_TIMEOUT
            try:
                await page.fill(selector, text, timeout=t)
            except Exception as e:
                return f"Type failed ({selector}): {e}"
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000.0)
            return f"Typed '{text}' into: {selector}"

        elif action == "read":
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000.0)
            content = await page.evaluate("() => document.body?.innerText || ''")
            return f"# URL: {page.url}\n# Content length: {len(content)} chars\n\n{content}"

        elif action == "scan":
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000.0)
            return await self._build_aria_snapshot()

        elif action == "screenshot":
            from smart_bot import PACKAGE_PATH
            screenshot_dir = PACKAGE_PATH.parent / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            path = screenshot_dir / f"screenshot_{asyncio.get_event_loop().time():.0f}.png"
            await page.screenshot(path=str(path), full_page=False, timeout=timeout or DEFAULT_NAVIGATE_TIMEOUT)
            return f"Screenshot saved to: {path}"

        elif action == "scroll":
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            if wait_ms:
                await asyncio.sleep(wait_ms / 1000.0)
            else:
                await asyncio.sleep(0.5)
            return f"Scrolled down\n\n{await self._build_aria_snapshot()}"

        elif action == "wait":
            if selector:
                try:
                    await page.wait_for_selector(selector, timeout=timeout or DEFAULT_NAVIGATE_TIMEOUT, state="visible")
                    return f"Element visible: {selector}"
                except Exception as e:
                    return f"Wait for selector failed: {e}"
            else:
                sleep_ms = wait_ms if wait_ms > 0 else (timeout or DEFAULT_NAVIGATE_TIMEOUT)
                await asyncio.sleep(sleep_ms / 1000.0)
                return f"Waited {sleep_ms}ms"

        elif action == "evaluate":
            if not script:
                return "Error: script is required for evaluate"
            try:
                result = await page.evaluate(script)
            except Exception as e:
                return f"Evaluate failed: {e}"
            return str(result)

        return "Unknown action"

    async def cleanup(self):
        if BrowserControl._browser:
            await BrowserControl._browser.close()
            BrowserControl._browser = None
            BrowserControl._context = None
            BrowserControl._page = None
        if BrowserControl._playwright:
            await BrowserControl._playwright.stop()
            BrowserControl._playwright = None
