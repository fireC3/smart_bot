from pathlib import Path
from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class FileRead(BaseTool):
    MAX_FILE_SIZE = 256 * 1024
    name = "file_read"
    description = "Preferred tool for reading text files. Relative paths are resolved from the home directory. Max file size 256KB."
    parameters = [
        ToolParameter(name="file_path", type="string", description="Path to the text file to read. Relative paths are resolved from the home directory."),
        ToolParameter(name="offset", type="integer", description="Start line number (1-based), default 1", required=False),
        ToolParameter(name="limit", type="integer", description="Number of lines to read, default 0 (read all)", required=False),
    ]
    permission = ToolPermission.ALLOW

    def change_permission(self, mode: PermissionMode):
        if mode == PermissionMode.DENY_ALL:
            self.permission = ToolPermission.DENY
        else:
            self.permission = ToolPermission.ALLOW

    @staticmethod
    def _resolve_path(file_path: str) -> Path:
        target = Path(file_path).expanduser()
        if not target.is_absolute():
            target = Path.home() / target
        return target.resolve()

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        file_path = (arguments.get("file_path", "") or "").strip()
        offset = int(arguments.get("offset", 1))
        limit = int(arguments.get("limit", 0))
        if not file_path:
            raise ValueError("file_path cannot be empty")
        if offset < 1:
            raise ValueError("offset must be 1 or greater")
        if limit < 0:
            raise ValueError("limit must be 0 or greater")

        target = self._resolve_path(file_path)
        if not target.exists():
            return "ERROR: file not found"
        if not target.is_file():
            return "ERROR: not a file"
        if target.stat().st_size > self.MAX_FILE_SIZE:
            return "ERROR: file too large (max 256KB)"

        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            return f"ERROR: read failed: {exc}"

        total = len(lines)
        start = offset - 1
        end = min(start + limit, total) if limit else total
        selected = lines[start:end]
        end_line = offset + len(selected) - 1
        output_lines = [f"=== {file_path} (lines {offset}-{end_line}) (Total {total} line) ==="]
        for index, line in enumerate(selected, start=offset):
            output_lines.append(f"{index:4} | {line}")
        return "\n".join(output_lines)
