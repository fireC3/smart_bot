from pathlib import Path
from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class FileEdit(BaseTool):
    MAX_FILE_SIZE = 256 * 1024
    name = "file_edit"
    description = "Preferred tool for editing text files by string replacement. Relative paths are resolved from the home directory. Max file size 256KB."
    parameters = [
        ToolParameter(name="file_path", type="string", description="Path to the text file. Relative paths are resolved from the home directory.", required=True),
        ToolParameter(name="old_text", type="string", description="Text to find", required=True),
        ToolParameter(name="new_text", type="string", description="Replacement text", required=True),
        ToolParameter(name="replace_all", type="boolean", description="Replace all matches if true; first match only if false, default false", required=False),
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
        old_text = arguments.get("old_text", "")
        new_text = arguments.get("new_text", "")
        replace_all = bool(arguments.get("replace_all", False))
        if not file_path:
            raise ValueError("file_path cannot be empty")

        target = self._resolve_path(file_path)
        if not target.exists():
            return "ERROR: file not found"
        if not target.is_file():
            return "ERROR: not a file"
        if target.stat().st_size > self.MAX_FILE_SIZE:
            return "ERROR: file too large (max 256KB)"

        try:
            text = target.read_text(encoding="utf-8")
        except Exception as exc:
            return f"ERROR: read failed: {exc}"

        total_matches = text.count(old_text)
        if total_matches == 0:
            return "ERROR: old_text not found"

        if replace_all:
            updated = text.replace(old_text, new_text)
            replaced = total_matches
        else:
            updated = text.replace(old_text, new_text, 1)
            replaced = 1

        if len(updated.encode("utf-8")) > self.MAX_FILE_SIZE:
            return "ERROR: edited content too large (max 256KB)"

        try:
            target.write_text(updated, encoding="utf-8")
        except Exception as exc:
            return f"ERROR: write failed: {exc}"
        return f"SUCCESS: updated {file_path}, replacements={replaced}"
