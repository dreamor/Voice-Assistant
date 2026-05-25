"""AppLifecycle 集成测试"""

from voice_assistant.core.lifecycle import get_lifecycle, shutdown_lifecycle


class TestAppLifecycleSingleton:
    """测试全局单例行为"""

    def setup_method(self):
        shutdown_lifecycle()

    def teardown_method(self):
        shutdown_lifecycle()

    def test_get_lifecycle_returns_same_instance(self):
        lc1 = get_lifecycle()
        lc2 = get_lifecycle()
        assert lc1 is lc2

    def test_shutdown_resets_singleton(self):
        lc = get_lifecycle()
        shutdown_lifecycle()
        lc2 = get_lifecycle()
        assert lc2 is not lc

    def test_shutdown_clears_managers(self):
        lc = get_lifecycle()
        lc._mcp_manager = "fake_mcp"
        lc._skill_manager = "fake_skill"
        lc._tool_registry = "fake_registry"
        shutdown_lifecycle()
        lc2 = get_lifecycle()
        assert lc2._mcp_manager is None
        assert lc2._skill_manager is None
        assert lc2._tool_registry is None


class TestAppLifecycleBuildToolRegistry:
    """测试 build_tool_registry 行为"""

    def setup_method(self):
        shutdown_lifecycle()

    def teardown_method(self):
        shutdown_lifecycle()

    def test_build_tool_registry_returns_registry(self):
        lc = get_lifecycle()
        registry = lc.build_tool_registry()
        assert registry is not None
        assert lc.tool_registry is registry

    def test_build_tool_registry_idempotent(self):
        lc = get_lifecycle()
        registry1 = lc.build_tool_registry()
        registry2 = lc.build_tool_registry()
        assert registry1 is registry2

    def test_build_tool_registry_registers_tools(self):
        lc = get_lifecycle()
        registry = lc.build_tool_registry()
        tools = registry.list_tools()
        # 调试：如果工具列表为空，检查各个工具源
        if len(tools) == 0:
            from voice_assistant.tools.universal import get_universal_tools
            from voice_assistant.tools.platform_specific import get_platform_tools
            from voice_assistant.platform import detect_platform

            platform = detect_platform()
            universal = get_universal_tools()
            platform_tools = get_platform_tools(platform)
            assert len(universal) > 0, f"universal tools empty (platform={platform})"
            assert len(platform_tools) >= 0, f"platform tools error (platform={platform})"
        assert len(tools) > 0, f"no tools registered (platform={platform})"

    def test_shutdown_clears_tool_registry(self):
        lc = get_lifecycle()
        lc.build_tool_registry()
        assert lc.tool_registry is not None
        lc.shutdown()
        assert lc.tool_registry is None


class TestAppLifecycleSkillAddendum:
    """测试 build_skill_addendum 行为"""

    def setup_method(self):
        shutdown_lifecycle()

    def teardown_method(self):
        shutdown_lifecycle()

    def test_skill_addendum_returns_empty_without_manager(self):
        lc = get_lifecycle()
        result = lc.build_skill_addendum("hello")
        assert result == ""

    def test_skill_addendum_with_skill_manager(self, tmp_path):
        lc = get_lifecycle()
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        (skill_dir / "test_skill").mkdir()
        (skill_dir / "test_skill" / "SKILL.md").write_text(
            "---\nname: test_skill\ndescription: test\n"
            "trigger: keywords\nkeywords: [test]\n---\nTest body"
        )
        from voice_assistant.skills import SkillManager

        lc._skill_manager = SkillManager(skill_dir)
        lc._skill_manager.reload()
        result = lc.build_skill_addendum("test something")
        assert "test_skill" in result

    def test_skill_addendum_exception_returns_empty(self):
        lc = get_lifecycle()

        class BadManager:
            def build_addendum_for_message(self, text):
                raise RuntimeError("boom")

        lc._skill_manager = BadManager()
        result = lc.build_skill_addendum("hello")
        assert result == ""


class TestAppLifecycleShutdown:
    """测试 shutdown 行为"""

    def setup_method(self):
        shutdown_lifecycle()

    def teardown_method(self):
        shutdown_lifecycle()

    def test_shutdown_with_mcp_manager(self):
        lc = get_lifecycle()
        shutdown_called = []

        class FakeMcp:
            def shutdown(self):
                shutdown_called.append(True)

        lc._mcp_manager = FakeMcp()
        lc.shutdown()
        assert len(shutdown_called) == 1
        assert lc._mcp_manager is None

    def test_shutdown_mcp_error_does_not_raise(self):
        lc = get_lifecycle()

        class BadMcp:
            def shutdown(self):
                raise RuntimeError("shutdown error")

        lc._mcp_manager = BadMcp()
        lc.shutdown()  # Should not raise
        assert lc._mcp_manager is None
