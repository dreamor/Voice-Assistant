"""
依赖管理模块测试
"""
import pytest
from unittest.mock import MagicMock, patch

from voice_assistant.core.dependencies import (
    Dependency,
    DependencyStatus,
    DependencyCheckResult,
    DependencyManager,
    check_dependency,
    parse_version,
    compare_versions,
    get_installed_version,
    CORE_DEPENDENCIES,
    LOCAL_ASR_DEPENDENCIES,
    INTERPRETER_DEPENDENCIES,
)


class TestVersionParsing:
    """版本解析测试"""

    def test_parse_version_simple(self):
        """测试简单版本解析"""
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("2.0.0") == (2, 0, 0)
        assert parse_version("0.10.0") == (0, 10, 0)

    def test_parse_version_with_suffix(self):
        """测试带后缀的版本解析"""
        assert parse_version("1.2.3.dev0") == (1, 2, 3)
        assert parse_version("7.2.0a1") == (7, 2, 0)

    def test_compare_versions_equal(self):
        """测试版本相等比较"""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("2.5.3", "2.5.3") == 0

    def test_compare_versions_less(self):
        """测试版本小于比较"""
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "1.0.1") == -1

    def test_compare_versions_greater(self):
        """测试版本大于比较"""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.1.0", "1.0.0") == 1
        assert compare_versions("1.0.1", "1.0.0") == 1


class TestDependency:
    """依赖项测试"""

    def test_dependency_creation(self):
        """测试依赖项创建"""
        dep = Dependency(
            name="Test",
            package_name="test_pkg",
            min_version="1.0.0",
            required=True,
        )
        assert dep.name == "Test"
        assert dep.package_name == "test_pkg"
        assert dep.min_version == "1.0.0"
        assert dep.required is True
        assert dep.config_flag is None

    def test_get_install_command_simple(self):
        """测试简单安装命令"""
        dep = Dependency(
            name="Test",
            package_name="test_pkg",
            min_version="1.0.0",
            required=True,
        )
        cmd = dep.get_install_command()
        assert "test-pkg" in cmd
        assert ">=1.0.0" in cmd

    def test_get_install_command_with_max(self):
        """测试带最大版本的安装命令"""
        dep = Dependency(
            name="Test",
            package_name="test_pkg",
            min_version="1.0.0",
            max_version="2.0.0",
            required=True,
        )
        cmd = dep.get_install_command()
        assert ">=1.0.0" in cmd
        assert "<2.0.0" in cmd

    def test_get_install_command_custom_hint(self):
        """测试自定义安装提示"""
        dep = Dependency(
            name="Test",
            package_name="test_pkg",
            min_version="1.0.0",
            required=True,
            install_hint="pip install test-pkg-nightly",
        )
        cmd = dep.get_install_command()
        assert cmd == "pip install test-pkg-nightly"


class TestDependencyCheckResult:
    """依赖检查结果测试"""

    def test_result_is_ok_available(self):
        """测试可用状态"""
        dep = Dependency(name="Test", package_name="test", min_version="1.0.0")
        result = DependencyCheckResult(
            status=DependencyStatus.AVAILABLE,
            dependency=dep,
            installed_version="1.0.0",
        )
        assert result.is_ok is True
        assert result.should_fail is False

    def test_result_is_ok_not_required(self):
        """测试不需要状态"""
        dep = Dependency(name="Test", package_name="test", min_version="1.0.0")
        result = DependencyCheckResult(
            status=DependencyStatus.NOT_REQUIRED,
            dependency=dep,
        )
        assert result.is_ok is True
        assert result.should_fail is False

    def test_result_should_fail_missing_required(self):
        """测试缺失必需依赖"""
        dep = Dependency(name="Test", package_name="test", min_version="1.0.0", required=True)
        result = DependencyCheckResult(
            status=DependencyStatus.MISSING,
            dependency=dep,
        )
        assert result.is_ok is False
        assert result.should_fail is True

    def test_result_should_not_fail_missing_optional(self):
        """测试缺失可选依赖"""
        dep = Dependency(name="Test", package_name="test", min_version="1.0.0", required=False)
        result = DependencyCheckResult(
            status=DependencyStatus.MISSING,
            dependency=dep,
        )
        assert result.is_ok is False
        assert result.should_fail is False


class TestCheckDependency:
    """依赖检查测试"""

    def test_check_available_dependency(self):
        """测试检查可用依赖"""
        # 使用已知存在的包
        dep = Dependency(
            name="Pytest",
            package_name="pytest",
            min_version="7.0.0",
            required=True,
        )
        result = check_dependency(dep)
        assert result.status == DependencyStatus.AVAILABLE
        assert result.installed_version is not None

    def test_check_missing_dependency(self):
        """测试检查缺失依赖"""
        dep = Dependency(
            name="NonExistent",
            package_name="nonexistent_package_xyz",
            min_version="1.0.0",
            required=True,
        )
        result = check_dependency(dep)
        assert result.status == DependencyStatus.MISSING
        assert result.installed_version is None


class TestDependencyManager:
    """依赖管理器测试"""

    def test_manager_creation(self):
        """测试管理器创建"""
        manager = DependencyManager()
        assert manager.results == []

    def test_check_all_returns_results(self):
        """测试检查所有依赖返回结果"""
        manager = DependencyManager()
        results = manager.check_all(verbose=False)

        assert len(results) > 0
        # 应该有核心依赖
        core_names = [r.dependency.name for r in results]
        assert "NumPy" in core_names
        assert "Pygame" in core_names

    def test_check_all_with_config_skip_local_asr(self):
        """测试配置禁用本地 ASR 时跳过检查"""
        manager = DependencyManager()

        # 模拟配置对象
        mock_config = MagicMock()
        mock_config.asr = MagicMock()
        mock_config.asr.use_local = False

        results = manager.check_all(config=mock_config, verbose=False)

        # 应该有 NOT_REQUIRED 状态
        funasr_results = [r for r in results if r.dependency.name == "FunASR"]
        assert len(funasr_results) == 1
        assert funasr_results[0].status == DependencyStatus.NOT_REQUIRED

    def test_has_blocking_errors_no_errors(self):
        """测试无阻止性错误"""
        manager = DependencyManager()
        manager.results = [
            DependencyCheckResult(
                status=DependencyStatus.AVAILABLE,
                dependency=CORE_DEPENDENCIES[0],
                installed_version="1.0.0",
            )
        ]
        assert manager.has_blocking_errors() is False

    def test_has_blocking_errors_with_errors(self):
        """测试有阻止性错误"""
        manager = DependencyManager()
        manager.results = [
            DependencyCheckResult(
                status=DependencyStatus.MISSING,
                dependency=Dependency(
                    name="Test",
                    package_name="test",
                    min_version="1.0.0",
                    required=True,
                ),
            )
        ]
        assert manager.has_blocking_errors() is True

    def test_get_missing_dependencies(self):
        """测试获取缺失依赖"""
        manager = DependencyManager()
        missing_dep = Dependency(
            name="Missing",
            package_name="missing",
            min_version="1.0.0",
            required=True,
        )
        manager.results = [
            DependencyCheckResult(
                status=DependencyStatus.MISSING,
                dependency=missing_dep,
            )
        ]
        missing = manager.get_missing_dependencies()
        assert len(missing) == 1
        assert missing[0].name == "Missing"

    def test_get_version_warnings(self):
        """测试获取版本警告"""
        manager = DependencyManager()
        dep = Dependency(
            name="OldVersion",
            package_name="old",
            min_version="2.0.0",
            required=True,
        )
        manager.results = [
            DependencyCheckResult(
                status=DependencyStatus.VERSION_MISMATCH,
                dependency=dep,
                installed_version="1.0.0",
                message="版本过低",
            )
        ]
        warnings = manager.get_version_warnings()
        assert len(warnings) == 1
        assert warnings[0].status == DependencyStatus.VERSION_MISMATCH


class TestDependencyGroups:
    """依赖组测试"""

    def test_core_dependencies_defined(self):
        """测试核心依赖已定义"""
        assert len(CORE_DEPENDENCIES) > 0
        names = [d.name for d in CORE_DEPENDENCIES]
        assert "NumPy" in names
        assert "Pygame" in names
        assert "DashScope" in names

    def test_local_asr_dependencies_optional(self):
        """测试本地 ASR 依赖为可选"""
        for dep in LOCAL_ASR_DEPENDENCIES:
            assert dep.required is False
            assert dep.config_flag is not None

    def test_interpreter_dependencies_required(self):
        """测试 Open Interpreter 依赖为必需"""
        for dep in INTERPRETER_DEPENDENCIES:
            assert dep.required is True