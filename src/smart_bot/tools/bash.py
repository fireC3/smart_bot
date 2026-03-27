import asyncio
import locale
from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager

@ToolManager.register_tool
class BashTool(BaseTool):
    name = "bash"
    description = (
        "Execute bash commands. "
        "Keep this tool as a fallback when shell execution is actually required or the dedicated file tools are not enough. "
        "When running Python, use `python3 - <<'PY' ... PY`."
    )
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="The bash command to execute.",
        ),
    ]
    permission = ToolPermission.CONFIRM

    def change_permission(self, mode: PermissionMode):
        match mode:
            case PermissionMode.DENY_ALL | PermissionMode.STRICT:
                self.permission = ToolPermission.DENY
            case PermissionMode.ALLOW_BASH | PermissionMode.ALLOW_ALL:
                self.permission = ToolPermission.ALLOW
            case _:
                self.permission = ToolPermission.CONFIRM

    def _build_error_message(self, command: str, stderr: str) -> str:
        message = f"error: {stderr}"
        if "SyntaxError: invalid syntax" not in stderr:
            return message

        hints = []
        if "python -c" in command or "python3 -c" in command:
            hints.append(
                "This looks like Python code passed with -c. If the script needs loops, conditionals, try/except, or multiple statements, switch to a bash heredoc: python3 - <<'PY' ... PY"
            )
        if any(token in command for token in ("; for ", "; if ", "; while ", "; try:", "; def ", "; class ")):
            hints.append(
                "Do not place Python compound statements after semicolons. `for/if/while/try/def/class` should be written on normal lines inside a heredoc script."
            )
        if hints:
            message += "\nHINT: " + " ".join(hints)
        return message

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        command = arguments["command"]
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(context.cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode() if stdout else ""
        stderr_text = stderr.decode() if stderr else ""

        if process.returncode == 0:
            return f"success: {stdout_text}"
        if stdout_text and stderr_text:
            return f"{self._build_error_message(command, stderr_text)}\nstdout: {stdout_text}"
        return self._build_error_message(command, stderr_text or stdout_text)
