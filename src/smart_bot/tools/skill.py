from typing import Any, Dict

from smart_bot.interface import BaseTool, ToolExecuteContext, ToolParameter, ToolPermission, PermissionMode
from smart_bot.interface import ToolManager


@ToolManager.register_tool
class SkillTool(BaseTool):
    name = "skill"
    description = "Execute a skill by name to get detailed task instructions."
    parameters = [
        ToolParameter(name="skill_name", type="string", description="The name of the skill to execute", required=True),
    ]
    permission = ToolPermission.ALLOW

    def change_permission(self, mode: PermissionMode):
        if mode == PermissionMode.DENY_ALL:
            self.permission = ToolPermission.DENY
        else:
            self.permission = ToolPermission.ALLOW

    async def run(self, arguments: Dict[str, Any], context: ToolExecuteContext) -> str:
        skill_name = arguments["skill_name"]
        if context.skill_manager is None:
            return "Skill manager not available."
        if skill_name not in context.skill_manager:
            return f"Skill '{skill_name}' not found."
        instruction = context.skill_manager.get_skill_instructions(skill_name)
        return f"Executing skill '{skill_name}':\n{instruction}"
