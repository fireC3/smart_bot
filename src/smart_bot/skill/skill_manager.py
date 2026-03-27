import asyncio
from pathlib import Path
import aiofiles
from typing import Dict
from pydantic import BaseModel
import yaml


class SkillData(BaseModel):
    name: str
    description: str
    instructions: str = ""
    path: str = ""


class SkillManager:
    def __init__(self, paths: list[Path]):
        self._paths = [Path(p) for p in paths]
        self._skills: Dict[str, SkillData] = {}

    def __contains__(self, skill_name: str) -> bool:
        return skill_name in self._skills

    def list_skills(self) -> list[SkillData]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    async def load(self) -> None:
        """Load all skills from configured paths."""
        for path in self._paths:
            if path.is_dir():
                skills = await self._load_skills_path(path)
                self._skills.update({skill.name: skill for skill in skills})

    async def _load_skills_path(self, path: Path, skip_hidden: bool = True, skip_patterns: tuple = ('.', '_')) -> list[SkillData]:
        if not path.exists():
            print(f"Path does not exist: {path}")
            return []

        if not path.is_dir():
            print(f"Path is not a directory: {path}")
            return []

        tasks = []
        for item in path.iterdir():
            if not item.is_dir():
                continue
            if skip_hidden:
                if any(item.name.startswith(pattern) for pattern in skip_patterns):
                    continue
            tasks.append(self._load_single_skill(item))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_skills = []
        for result in results:
            if isinstance(result, Exception):
                print(f"Error loading skill: {result}")
            elif isinstance(result, SkillData):
                valid_skills.append(result)

        return valid_skills

    async def _load_single_skill(self, path: Path) -> SkillData | None:
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            return None
        async with aiofiles.open(skill_md, mode='r', encoding='utf-8') as f:
            content = await f.read()

        metadata, instructions = self._parse_skill_markdown(content)
        if not metadata:
            return None

        return SkillData(
            name=metadata['name'],
            description=metadata['description'],
            instructions=instructions,
            path=str(path.resolve())
        )

    def _parse_skill_markdown(self, content: str) -> tuple[dict[str, str], str]:
        if not content or not isinstance(content, str):
            return {}, ""

        content = content.strip()
        if not content:
            return {}, ""

        lines = content.splitlines()

        first_content_line = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                first_content_line = i
                break

        if first_content_line < len(lines) and lines[first_content_line].strip() == '---':
            start_idx = 3
            end_idx = content.find('\n---\n', start_idx)

            if end_idx == -1:
                end_idx = content.find('\n---', start_idx)

            if end_idx != -1:
                try:
                    yaml_content = content[3:end_idx].strip()
                    metadata = yaml.safe_load(yaml_content) or {}

                    if not isinstance(metadata, dict):
                        metadata = {}

                    second_sep_end = end_idx + 4
                    if content[end_idx:end_idx+4] == '\n---':
                        second_sep_end = end_idx + 4
                    elif content[end_idx:end_idx+3] == '---':
                        second_sep_end = end_idx + 3

                    instructions = content[second_sep_end:].strip()
                    return metadata, instructions

                except yaml.YAMLError as e:
                    print(f"Warning: Failed to parse YAML frontmatter: {e}")
                    return {}, content

        return {}, content.strip()

    def get_skill_instructions(self, skill_name: str) -> str:
        skill = self._skills.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found."
        return skill.instructions

    def build_skill_prompt(self) -> str:
        lines = [
            "# Available Skills",
            "",
            "The Following is a list of available skills that can be invoked using the skill tool.",
            "When the user's request involves a specific skill, use the `skill(name='<skill_name>')` tool to invoke the corresponding skill for detailed instructions, and then follow those instructions to respond or perform tasks.",
            "",
        ]
        for skill in self.list_skills():
            lines.append(f"- **{skill.name}**: {skill.description}")
        return "\n".join(lines)


if __name__ == "__main__":
    async def main():
        from smart_bot import PACKAGE_PATH
        skill_path = PACKAGE_PATH / "skill" / "embed"
        manager = SkillManager([skill_path])
        await manager.load()
        print(f"skill prompt size: {len(manager.build_skill_prompt())} chars")
        print(manager.build_skill_prompt())

    asyncio.run(main())
