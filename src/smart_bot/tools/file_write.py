from pathlib import Path
from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class FileWrite(BaseTool):
    MAX_FILE_SIZE = 256 * 1024
    name = "file_write"
    description = "Preferred tool for writing text files. Relative paths are resolved from the home directory. Supports overwrite/append. Max file size 256KB."
    parameters = [
        ToolParameter(name="file_path", type="string", description="Path to the text file. Relative paths are resolved from the home directory.", required=True),
        ToolParameter(name="content", type="string", description="Text content to write", required=True),
        ToolParameter(name="append", type="boolean", description="Append to file if true; overwrite if false, default False", required=False),
        ToolParameter(name="create_dirs", type="boolean", description="Create parent directories if missing, default False", required=False),
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

    @staticmethod
    def _resolve_path(file_path: str) -> Path:
        target = Path(file_path).expanduser()
        if not target.is_absolute():
            target = Path.home() / target
        return target.resolve()

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        file_path = (arguments.get("file_path", "") or "").strip()
        content = arguments.get("content", "")
        append = bool(arguments.get("append", False))
        create_dirs = bool(arguments.get("create_dirs", False))
        if not file_path:
            raise ValueError("file_path cannot be empty")
        if content is None:
            raise ValueError("content cannot be null")

        target = self._resolve_path(file_path)
        new_bytes = content.encode("utf-8")
        if len(new_bytes) > self.MAX_FILE_SIZE:
            return "ERROR: content too large (max 256KB)"

        if create_dirs:
            target.parent.mkdir(parents=True, exist_ok=True)
        elif not target.parent.exists():
            return "ERROR: parent directory does not exist"

        old_size = target.stat().st_size if target.exists() else 0
        final_size = old_size + len(new_bytes) if append else len(new_bytes)
        if final_size > self.MAX_FILE_SIZE:
            return "ERROR: file too large after write (max 256KB)"

        try:
            if append:
                with target.open("a", encoding="utf-8") as handle:
                    handle.write(content)
                return f"SUCCESS: appended {len(new_bytes)} bytes to {file_path}"
            target.write_text(content, encoding="utf-8")
            return f"SUCCESS: wrote {len(new_bytes)} bytes to {file_path}"
        except Exception as exc:
            return f"ERROR: write failed: {exc}"
