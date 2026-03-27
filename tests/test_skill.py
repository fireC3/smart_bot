"""Tests for skill.skill_manager.SkillManager and tools.skill.SkillTool."""

import pytest
from pathlib import Path
from smart_bot import PACKAGE_PATH

EMBED_SKILL_PATH = PACKAGE_PATH / "skill" / "embed"

# Lazy-loaded shared manager — created once with load() awaited.
_MGR = None


async def _get_manager():
    global _MGR
    if _MGR is None:
        from smart_bot.skill.skill_manager import SkillManager
        _MGR = SkillManager([EMBED_SKILL_PATH])
        await _MGR.load()
    return _MGR


# ============================================================================
# SkillData
# ============================================================================


def test_skill_data_model():
    from smart_bot.skill.skill_manager import SkillData

    s = SkillData(name="test", description="desc", instructions="do stuff", path="/tmp")
    assert s.name == "test"
    assert s.description == "desc"
    assert s.instructions == "do stuff"
    assert s.path == "/tmp"


def test_skill_data_defaults():
    from smart_bot.skill.skill_manager import SkillData

    s = SkillData(name="test", description="desc")
    assert s.instructions == ""
    assert s.path == ""


# ============================================================================
# SkillManager — init (no load)
# ============================================================================


def test_skill_manager_empty_before_load():
    from smart_bot.skill.skill_manager import SkillManager

    manager = SkillManager([EMBED_SKILL_PATH])
    assert manager.list_skills() == []


# ============================================================================
# SkillManager — loaded
# ============================================================================


@pytest.mark.asyncio
async def test_skill_manager_loads_embedded_skills():
    manager = await _get_manager()
    assert len(manager.list_skills()) >= 1


@pytest.mark.asyncio
async def test_skill_manager_list_skills_returns_sorted():
    manager = await _get_manager()
    names = [s.name for s in manager.list_skills()]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_skill_manager_contains():
    manager = await _get_manager()
    assert "say-hi" in manager
    assert "nonexistent-skill" not in manager


@pytest.mark.asyncio
async def test_skill_manager_get_skill_instructions():
    manager = await _get_manager()
    instructions = manager.get_skill_instructions("say-hi")
    assert len(instructions) > 0
    assert "good morning" in instructions.lower()

    result = manager.get_skill_instructions("nonexistent")
    assert "not found" in result


@pytest.mark.asyncio
async def test_skill_manager_build_skill_prompt():
    manager = await _get_manager()
    prompt = manager.build_skill_prompt()
    assert "# Available Skills" in prompt
    assert "say-hi" in prompt
    assert "python-script" in prompt


# ============================================================================
# SkillManager — invalid / empty paths
# ============================================================================


@pytest.mark.asyncio
async def test_skill_manager_nonexistent_path():
    from smart_bot.skill.skill_manager import SkillManager

    manager = SkillManager([Path("/nonexistent/path/12345")])
    await manager.load()
    assert manager.list_skills() == []


@pytest.mark.asyncio
async def test_skill_manager_file_path():
    from smart_bot.skill.skill_manager import SkillManager

    manager = SkillManager([Path(__file__)])
    await manager.load()
    assert manager.list_skills() == []


@pytest.mark.asyncio
async def test_skill_manager_empty_paths():
    from smart_bot.skill.skill_manager import SkillManager

    manager = SkillManager([])
    await manager.load()
    assert manager.list_skills() == []


@pytest.mark.asyncio
async def test_skill_manager_accepts_string_paths():
    from smart_bot.skill.skill_manager import SkillManager

    manager = SkillManager([str(EMBED_SKILL_PATH)])
    await manager.load()
    assert len(manager.list_skills()) >= 1


# ============================================================================
# _parse_skill_markdown
# ============================================================================


def _empty_manager():
    from smart_bot.skill.skill_manager import SkillManager
    return SkillManager([])


def test_parse_valid_frontmatter():
    manager = _empty_manager()
    content = """---
name: test-skill
description: A test skill
---
# Instructions
Do this thing."""

    meta, instructions = manager._parse_skill_markdown(content)
    assert meta["name"] == "test-skill"
    assert meta["description"] == "A test skill"
    assert "Do this thing" in instructions


def test_parse_no_frontmatter():
    manager = _empty_manager()
    meta, instructions = manager._parse_skill_markdown("# Just a heading\nSome content")
    assert meta == {}
    assert "Some content" in instructions


def test_parse_empty_string():
    manager = _empty_manager()
    meta, instructions = manager._parse_skill_markdown("")
    assert meta == {}
    assert instructions == ""


def test_parse_none():
    manager = _empty_manager()
    meta, instructions = manager._parse_skill_markdown(None)
    assert meta == {}
    assert instructions == ""


def test_parse_only_comments_then_content():
    manager = _empty_manager()
    content = """# Skill Title
Some description here.
---
name: not-parsed
description: should not be parsed
---
Actual content."""
    meta, instructions = manager._parse_skill_markdown(content)
    assert "Actual content" in instructions


# ============================================================================
# SkillTool
# ============================================================================


@pytest.mark.asyncio
async def test_skill_tool_run_with_context():
    from smart_bot.tools.skill import SkillTool
    from smart_bot.interface.tool import ToolExecuteContext

    ctx = ToolExecuteContext(skill_manager=await _get_manager())
    tool = SkillTool()

    result = await tool.run({"skill_name": "say-hi"}, ctx)
    assert "Executing skill" in result
    assert "good morning" in result


@pytest.mark.asyncio
async def test_skill_tool_run_unknown_skill():
    from smart_bot.tools.skill import SkillTool
    from smart_bot.interface.tool import ToolExecuteContext

    ctx = ToolExecuteContext(skill_manager=await _get_manager())
    tool = SkillTool()

    result = await tool.run({"skill_name": "no-such-skill"}, ctx)
    assert "not found" in result


@pytest.mark.asyncio
async def test_skill_tool_run_no_skill_manager():
    from smart_bot.tools.skill import SkillTool
    from smart_bot.interface.tool import ToolExecuteContext

    ctx = ToolExecuteContext(skill_manager=None)
    tool = SkillTool()

    result = await tool.run({"skill_name": "say-hi"}, ctx)
    assert "not available" in result


# ============================================================================
# SkillTool in ToolManager
# ============================================================================


@pytest.mark.asyncio
async def test_skill_tool_registered_and_executed():
    from smart_bot.interface import ToolManager
    from smart_bot.interface.tool import ToolExecuteContext
    from smart_bot.interface.message import ToolCallBlock

    tm = ToolManager()
    await tm.enable_tools(["skill"])

    ctx = ToolExecuteContext(skill_manager=await _get_manager())
    tc = ToolCallBlock(name="skill", call_id="1", arguments={"skill_name": "say-hi"}, content="")
    result = await tm.execute_tool(tc, ctx)
    assert "good morning" in result.content
