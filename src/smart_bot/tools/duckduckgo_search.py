from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class DuckDuckGoSearch(BaseTool):
    name = "duckduckgo_search"
    description = "Stable web search using DuckDuckGo. Returns title, URL, summary."
    parameters = [
        ToolParameter(name="query", type="string", description="Search keywords or question to look up"),
        ToolParameter(name="num_results", type="integer", description="Number of results, default 5, max is 10", required=False),
    ]
    permission = ToolPermission.ALLOW

    def change_permission(self, mode: PermissionMode):
        if mode == PermissionMode.DENY_ALL:
            self.permission = ToolPermission.DENY
        else:
            self.permission = ToolPermission.ALLOW

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        query = arguments.get("query", "").strip()
        num_results = int(arguments.get("num_results", 5))
        if not query:
            raise ValueError("Query cannot be empty")
        if num_results < 1:
            raise ValueError("num_results must be at least 1")
        num_results = max(min(num_results, 10), 1)

        headers = {"User-Agent": "Lynx/2.8.9rel.1"}
        url = "https://lite.duckduckgo.com/lite/"
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, params={"q": query}, headers=headers)
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for a in soup.select("a.result-link"):
            title = a.get_text(strip=True)
            try:
                qs = parse_qs(urlparse(a["href"]).query)
                real_url = qs.get("uddg", [None])[0]
            except Exception:
                real_url = a["href"]
            snippet = ""
            snippet_td = a.find_parent("tr").find_next_sibling("tr").find("td", class_="result-snippet")
            if snippet_td:
                snippet = snippet_td.get_text(strip=True)
            if title and real_url:
                results.append({"title": title, "url": real_url, "snippet": snippet})
            if len(results) >= num_results:
                break
        return f"{results}"
