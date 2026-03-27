import io
from typing import Any, Dict

import httpx

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class WebFetchTool(BaseTool):
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    name = "web_fetch"
    description = "Fetch and convert a webpage to readable plain text."
    parameters = [
        ToolParameter(name="url", type="string", description="The URL to fetch (must start with http:// or https://)", required=True),
    ]
    permission = ToolPermission.ALLOW

    def change_permission(self, mode: PermissionMode):
        if mode == PermissionMode.DENY_ALL:
            self.permission = ToolPermission.DENY
        else:
            self.permission = ToolPermission.ALLOW

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        url = (arguments.get("url", "") or "").strip()
        if not url:
            raise ValueError("URL cannot be empty")
        if not url.startswith("http://") and not url.startswith("https://"):
            raise ValueError("URL must start with http:// or https://")

        try:
            import importlib
            MarkItDown = importlib.import_module("markitdown").MarkItDown
        except ImportError as exc:
            return f"Browse failed: markitdown is not installed: {exc}"

        headers = {"User-Agent": self.USER_AGENT}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            html_content = response.text

        stream = io.BytesIO(html_content.encode("utf-8"))
        md = MarkItDown()
        result = md.convert_stream(stream, input_type="html")
        text = result.text_content
        if text == "":
            return f"Browse failed: no readable content found at {url}"
        return f"URL: {url} (total {len(text)} chars)\n\n{text}"
