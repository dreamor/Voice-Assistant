"""工具分组与按需加载测试"""
import pytest

from voice_assistant.tools.tool_groups import (
    TOOL_GROUPS,
    GROUP_DESCRIPTIONS,
    get_all_group_names,
    get_group_summary,
    get_tool_group,
    get_tools_for_groups,
)


class TestToolGroups:
    def test_all_groups_have_descriptions(self):
        for group in TOOL_GROUPS:
            assert group in GROUP_DESCRIPTIONS, f"分组 {group} 缺少描述"

    def test_descriptions_match_groups(self):
        for group in GROUP_DESCRIPTIONS:
            assert group in TOOL_GROUPS, f"描述 {group} 缺少对应分组"

    def test_core_group_not_empty(self):
        assert len(TOOL_GROUPS["core"]) > 0

    def test_no_duplicate_tools_across_groups(self):
        all_tools: list[str] = []
        for tools in TOOL_GROUPS.values():
            all_tools.extend(tools)
        duplicates = [t for t in set(all_tools) if all_tools.count(t) > 1]
        assert not duplicates, f"工具重复出现在多个分组: {duplicates}"

    def test_group_names_are_valid(self):
        for name in TOOL_GROUPS:
            assert name.isidentifier(), f"分组名 {name} 不是有效标识符"


class TestGetToolGroup:
    def test_known_tool(self):
        assert get_tool_group("calculate") == "core"

    def test_file_ops_tool(self):
        assert get_tool_group("open_file") == "file_ops"

    def test_system_ops_tool(self):
        assert get_tool_group("launch_application") == "system_ops"

    def test_unknown_tool_returns_core(self):
        assert get_tool_group("nonexistent_tool") == "core"


class TestGetToolsForGroups:
    def test_none_returns_none(self):
        assert get_tools_for_groups(None) is None

    def test_single_group(self):
        tools = get_tools_for_groups(["media_ops"])
        assert "media_play_pause" in tools
        assert "calculate" not in tools

    def test_multiple_groups(self):
        tools = get_tools_for_groups(["core", "media_ops"])
        assert "calculate" in tools
        assert "media_play_pause" in tools

    def test_empty_list(self):
        tools = get_tools_for_groups([])
        assert tools == []

    def test_unknown_group(self):
        tools = get_tools_for_groups(["nonexistent"])
        assert tools == []


class TestGetAllGroupNames:
    def test_returns_all_groups(self):
        names = get_all_group_names()
        assert "core" in names
        assert "file_ops" in names
        assert len(names) == len(TOOL_GROUPS)


class TestGetGroupSummary:
    def test_summary_contains_all_groups(self):
        summary = get_group_summary()
        for group in TOOL_GROUPS:
            assert group in summary

    def test_summary_contains_tool_count(self):
        summary = get_group_summary()
        core_count = len(TOOL_GROUPS["core"])
        assert f"{core_count} 个工具" in summary

    def test_summary_is_multiline(self):
        summary = get_group_summary()
        lines = summary.strip().split("\n")
        assert len(lines) >= len(TOOL_GROUPS) + 1  # header + each group
