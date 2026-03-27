from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class AskUserTool(BaseTool):
    name = "ask_user"
    description = "Ask the user a question and get their response. Use this when you need user input, confirmation on a plan, or to alert the user about something (e.g., a captcha on a webpage)."
    parameters = [
        ToolParameter(name="question", type="string", description="The question to ask the user", required=True),
    ]
    permission = ToolPermission.ALLOW

    def change_permission(self, mode: PermissionMode):
        if mode == PermissionMode.DENY_ALL:
            self.permission = ToolPermission.DENY
        else:
            self.permission = ToolPermission.ALLOW

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        question = (arguments.get("question", "") or "").strip()
        if not question:
            raise ValueError("Question cannot be empty")

        ask_user_func = context.metadata.get("ask_user_func")
        if ask_user_func is None:
            return "Error: ask_user tool requires an interactive session (no user available)."

        try:
            answer = await ask_user_func(question)
            return answer if answer else "(user provided no response)"
        except Exception as e:
            return f"Error asking user: {e}"
