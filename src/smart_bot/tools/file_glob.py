import glob as glob_mod
from pathlib import Path
from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class FileGlob(BaseTool):
    name = "file_glob"
    description = "Preferred tool for finding files or directories by glob pattern. Relative patterns are resolved from the home directory."
    parameters = [
        ToolParameter(name="pattern", type="string", description="Glob pattern. Relative patterns are resolved from the home directory."),
        ToolParameter(name="limit", type="integer", description="Max number of results, default 200", required=False),
        ToolParameter(name="ignore_dots_dirs", type="boolean", description="Ignore files/directories whose path contains a dot-prefixed component, default True", required=False),
    ]
    permission = ToolPermission.ALLOW

    def change_permission(self, mode: PermissionMode):
        if mode == PermissionMode.DENY_ALL:
            self.permission = ToolPermission.DENY
        else:
            self.permission = ToolPermission.ALLOW

    @staticmethod
    def _resolve_pattern(pattern: str) -> str:
        expanded = Path(pattern).expanduser()
        if expanded.is_absolute():
            return str(expanded)
        return str((Path.home() / expanded).resolve())

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        pattern = (arguments.get("pattern", "") or "").strip()
        limit = int(arguments.get("limit", 200))
        ignore_dots_dirs = bool(arguments.get("ignore_dots_dirs", True))
        if not pattern:
            raise ValueError("pattern cannot be empty")
        if limit < 1:
            raise ValueError("limit must be 1 or greater")
        if limit > 2000:
            raise ValueError("limit must be 2000 or less")

        resolved_pattern = self._resolve_pattern(pattern)
        try:
            matched: list[tuple[str, Path]] = []
            for path_str in glob_mod.glob(resolved_pattern, recursive=True):
                path = Path(path_str).expanduser().resolve()
                if ignore_dots_dirs and any(
                    part.startswith(".") and part not in (".", "..")
                    for part in path.parts
                ):
                    continue
                matched.append((str(path), path))
        except Exception as exc:
            return f"ERROR: glob failed: {exc}"

        matched.sort(key=lambda item: item[0])
        shown = matched[:limit]
        if not shown:
            return f"=== glob: {pattern} ===\n(no matches)"
        output_lines = [f"=== glob: {pattern} (showing {len(shown)}/{len(matched)}) ==="]
        for index, (rel, path) in enumerate(shown, start=1):
            if path.is_dir():
                output_lines.append(f"{index:4} | [DIR ] {rel}/")
            else:
                size = path.stat().st_size if path.exists() else 0
                output_lines.append(f"{index:4} | [FILE] {rel} ({size} bytes)")
        return "\n".join(output_lines)
