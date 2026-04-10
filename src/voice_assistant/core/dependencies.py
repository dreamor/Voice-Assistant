"""
依赖管理模块
检查和验证项目依赖，支持配置感知的条件依赖加载
"""
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class DependencyStatus(Enum):
    """依赖状态"""
    AVAILABLE = "available"
    MISSING = "missing"
    VERSION_MISMATCH = "version_mismatch"
    NOT_REQUIRED = "not_required"


@dataclass
class Dependency:
    """依赖项定义"""
    name: str  # 显示名称
    package_name: str  # Python 包名（用于 import）
    min_version: str  # 最低版本
    max_version: Optional[str] = None  # 最高版本（不包含）
    required: bool = True  # 是否必需
    config_flag: Optional[str] = None  # 配置项路径，如 "llm.use_local"
    install_hint: str = ""  # 安装提示
    version_attr: str = "__version__"  # 版本属性名

    def get_install_command(self) -> str:
        """获取安装命令"""
        if self.install_hint:
            return self.install_hint
        pkg_name = self.package_name.replace("_", "-")
        if self.max_version:
            return f"pip install '{pkg_name}>={self.min_version},<{self.max_version}'"
        return f"pip install '{pkg_name}>={self.min_version}'"


@dataclass
class DependencyCheckResult:
    """依赖检查结果"""
    status: DependencyStatus
    dependency: Dependency
    installed_version: Optional[str] = None
    message: str = ""

    @property
    def is_ok(self) -> bool:
        """检查是否通过"""
        return self.status in (DependencyStatus.AVAILABLE, DependencyStatus.NOT_REQUIRED)

    @property
    def should_fail(self) -> bool:
        """是否应该阻止启动"""
        return self.status == DependencyStatus.MISSING and self.dependency.required


# 定义依赖组
CORE_DEPENDENCIES = [
    # 音频处理
    Dependency(
        name="NumPy",
        package_name="numpy",
        min_version="1.21.0",
        max_version="3.0.0",
        required=True,
        install_hint="pip install 'numpy>=1.21.0,<3.0.0'"
    ),
    Dependency(
        name="SoundDevice",
        package_name="sounddevice",
        min_version="0.4.0",
        max_version="0.6.0",
        required=True,
        install_hint="pip install 'sounddevice>=0.4.0,<0.6.0'"
    ),
    Dependency(
        name="SoundFile",
        package_name="soundfile",
        min_version="0.13.1",
        max_version="1.0.0",
        required=True,
        install_hint="pip install 'soundfile>=0.13.1,<1.0.0'"
    ),
    Dependency(
        name="Pygame",
        package_name="pygame",
        min_version="2.6.1",
        max_version="3.0.0",
        required=True,
        install_hint="pip install 'pygame>=2.6.1,<3.0.0'"
    ),
    # TTS
    Dependency(
        name="Edge-TTS",
        package_name="edge_tts",
        min_version="7.2.0",
        max_version="8.0.0",
        required=True,
        install_hint="pip install 'edge-tts>=7.2.0,<8.0.0'"
    ),
    # STT
    Dependency(
        name="DashScope",
        package_name="dashscope",
        min_version="1.25.0",
        max_version="2.0.0",
        required=True,
        install_hint="pip install 'dashscope>=1.25.0,<2.0.0'"
    ),
    # HTTP
    Dependency(
        name="Requests",
        package_name="requests",
        min_version="2.32.0",
        max_version="3.0.0",
        required=True,
        install_hint="pip install 'requests>=2.32.0,<3.0.0'"
    ),
    # 配置
    Dependency(
        name="PyYAML",
        package_name="yaml",
        min_version="6.0",
        max_version="7.0",
        required=True,
        install_hint="pip install 'PyYAML>=6.0,<7.0'"
    ),
    Dependency(
        name="Python-Dotenv",
        package_name="dotenv",
        min_version="1.2.0",
        max_version="2.0.0",
        required=True,
        install_hint="pip install 'python-dotenv>=1.2.0,<2.0.0'"
    ),
]

LOCAL_LLM_DEPENDENCIES = [
    Dependency(
        name="LiteRT-LM",
        package_name="litert_lm",
        min_version="0.10.0",
        required=False,  # 可选依赖
        config_flag="llm.use_local",  # 仅当 llm.use_local=true 时需要
        install_hint="pip install litert-lm-api-nightly"
    ),
]

INTERPRETER_DEPENDENCIES = [
    Dependency(
        name="Open Interpreter",
        package_name="interpreter",
        min_version="0.3.0",
        max_version="0.5.0",
        required=True,
        install_hint="pip install 'open-interpreter>=0.3.0,<0.5.0'"
    ),
]


def parse_version(version_str: str) -> tuple:
    """解析版本字符串为元组"""
    # 处理类似 "1.2.3" 或 "1.2.3.dev0" 的版本
    parts = version_str.split(".")
    result = []
    for part in parts:
        # 提取数字部分
        num = ""
        for char in part:
            if char.isdigit():
                num += char
            else:
                break
        if num:
            result.append(int(num))
        else:
            break
    return tuple(result)


def compare_versions(v1: str, v2: str) -> int:
    """比较两个版本，返回 -1, 0, 1"""
    t1 = parse_version(v1)
    t2 = parse_version(v2)
    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    return 0


def get_installed_version(package_name: str, version_attr: str = "__version__") -> Optional[str]:
    """获取已安装包的版本"""
    # 首先尝试从 importlib.metadata 获取（最可靠）
    try:
        import importlib.metadata
        # 常见的包名映射
        package_name_map = {
            "yaml": "pyyaml",
            "dotenv": "python-dotenv",
            "edge_tts": "edge-tts",
            "litert_lm": "litert-lm-api-nightly",
            "interpreter": "open-interpreter",
        }
        pkg_name = package_name_map.get(package_name, package_name.replace("_", "-"))
        return importlib.metadata.version(pkg_name)
    except Exception:
        pass

    # 然后尝试从模块属性获取
    try:
        module = __import__(package_name)
        # 尝试常见的版本属性
        for attr in [version_attr, "__version__", "VERSION", "version", "__VERSION__"]:
            version = getattr(module, attr, None)
            if version and isinstance(version, str):
                return version
            # 有些模块的 version 是模块本身
            if version and hasattr(version, '__str__'):
                v_str = str(version)
                # 如果看起来像版本号
                if any(c.isdigit() for c in v_str):
                    return v_str
    except ImportError:
        pass

    return None


def check_dependency(dep: Dependency) -> DependencyCheckResult:
    """检查单个依赖"""
    installed_version = get_installed_version(dep.package_name, dep.version_attr)

    if installed_version is None:
        return DependencyCheckResult(
            status=DependencyStatus.MISSING,
            dependency=dep,
            message=f"{dep.name} 未安装"
        )

    # 检查最低版本
    if compare_versions(installed_version, dep.min_version) < 0:
        return DependencyCheckResult(
            status=DependencyStatus.VERSION_MISMATCH,
            dependency=dep,
            installed_version=installed_version,
            message=f"{dep.name} 版本过低: {installed_version} < {dep.min_version}"
        )

    # 检查最高版本
    if dep.max_version and compare_versions(installed_version, dep.max_version) >= 0:
        return DependencyCheckResult(
            status=DependencyStatus.VERSION_MISMATCH,
            dependency=dep,
            installed_version=installed_version,
            message=f"{dep.name} 版本过高: {installed_version} >= {dep.max_version}"
        )

    return DependencyCheckResult(
        status=DependencyStatus.AVAILABLE,
        dependency=dep,
        installed_version=installed_version,
        message=f"{dep.name} {installed_version} ✓"
    )


def get_config_value(config, path: str) -> Optional[bool]:
    """从配置对象获取嵌套值"""
    parts = path.split(".")
    obj = config
    for part in parts:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return None
    return bool(obj)


class DependencyManager:
    """依赖管理器"""

    def __init__(self):
        self.results: list[DependencyCheckResult] = []

    def check_all(self, config=None, verbose: bool = True) -> list[DependencyCheckResult]:
        """检查所有依赖"""
        self.results = []

        # 检查核心依赖
        for dep in CORE_DEPENDENCIES:
            result = check_dependency(dep)
            self.results.append(result)
            if verbose:
                self._log_result(result)

        # 检查本地 LLM 依赖（条件性）
        for dep in LOCAL_LLM_DEPENDENCIES:
            should_check = True
            if dep.config_flag and config:
                config_value = get_config_value(config, dep.config_flag)
                should_check = config_value is True

            if should_check:
                result = check_dependency(dep)
                self.results.append(result)
                if verbose:
                    self._log_result(result)
            else:
                result = DependencyCheckResult(
                    status=DependencyStatus.NOT_REQUIRED,
                    dependency=dep,
                    message=f"{dep.name} (跳过: {dep.config_flag}=false)"
                )
                self.results.append(result)
                if verbose:
                    logger.info(f"  ⊙ {result.message}")

        # 检查 Open Interpreter 依赖
        for dep in INTERPRETER_DEPENDENCIES:
            result = check_dependency(dep)
            self.results.append(result)
            if verbose:
                self._log_result(result)

        return self.results

    def _log_result(self, result: DependencyCheckResult):
        """记录检查结果"""
        if result.status == DependencyStatus.AVAILABLE:
            logger.info(f"  ✓ {result.message}")
        elif result.status == DependencyStatus.NOT_REQUIRED:
            logger.info(f"  ⊙ {result.message}")
        elif result.status == DependencyStatus.MISSING:
            if result.dependency.required:
                logger.error(f"  ✗ {result.message}")
            else:
                logger.warning(f"  ⚠ {result.message}")
        elif result.status == DependencyStatus.VERSION_MISMATCH:
            logger.warning(f"  ⚠ {result.message}")

    def has_blocking_errors(self) -> bool:
        """是否有阻止启动的错误"""
        return any(r.should_fail for r in self.results)

    def get_missing_dependencies(self) -> list[Dependency]:
        """获取缺失的必需依赖"""
        return [
            r.dependency for r in self.results
            if r.status == DependencyStatus.MISSING and r.dependency.required
        ]

    def get_version_warnings(self) -> list[DependencyCheckResult]:
        """获取版本警告"""
        return [
            r for r in self.results
            if r.status == DependencyStatus.VERSION_MISMATCH
        ]

    def print_summary(self):
        """打印检查摘要"""
        print("\n" + "=" * 50)
        print("  依赖检查结果")
        print("=" * 50)

        for result in self.results:
            status_icon = {
                DependencyStatus.AVAILABLE: "✓",
                DependencyStatus.MISSING: "✗",
                DependencyStatus.VERSION_MISMATCH: "⚠",
                DependencyStatus.NOT_REQUIRED: "⊙",
            }.get(result.status, "?")

            if result.installed_version:
                print(f"  {status_icon} {result.dependency.name}: {result.installed_version}")
            else:
                print(f"  {status_icon} {result.dependency.name}: 未安装")

        print("=" * 50)

        missing = self.get_missing_dependencies()
        if missing:
            print("\n缺失的必需依赖:")
            for dep in missing:
                print(f"  • {dep.name}: {dep.get_install_command()}")

        warnings = self.get_version_warnings()
        if warnings:
            print("\n版本警告:")
            for r in warnings:
                print(f"  • {r.message}")

        if self.has_blocking_errors():
            print("\n❌ 存在必需依赖缺失，无法启动")
            return False
        else:
            print("\n✅ 所有必需依赖已满足")
            return True


def check_dependencies(config=None, verbose: bool = True) -> DependencyManager:
    """检查依赖的便捷函数"""
    manager = DependencyManager()
    manager.check_all(config, verbose)
    return manager


def validate_environment(config=None) -> bool:
    """验证环境是否满足运行要求

    Args:
        config: 配置对象，用于条件依赖检查

    Returns:
        True 如果环境验证通过，False 否则
    """
    print("\n正在检查依赖...")

    manager = check_dependencies(config, verbose=True)

    if verbose:
        manager.print_summary()

    return not manager.has_blocking_errors()


def get_dependency_report() -> str:
    """获取依赖报告（用于调试）"""
    lines = ["依赖报告:", "-" * 40]
    all_deps = CORE_DEPENDENCIES + LOCAL_LLM_DEPENDENCIES + INTERPRETER_DEPENDENCIES

    for dep in all_deps:
        version = get_installed_version(dep.package_name, dep.version_attr)
        status = "✓" if version else "✗"
        version_str = version or "未安装"
        lines.append(f"  {status} {dep.name}: {version_str}")

    return "\n".join(lines)


__all__ = [
    'Dependency',
    'DependencyStatus',
    'DependencyCheckResult',
    'DependencyManager',
    'check_dependency',
    'check_dependencies',
    'validate_environment',
    'get_dependency_report',
    'CORE_DEPENDENCIES',
    'LOCAL_LLM_DEPENDENCIES',
    'INTERPRETER_DEPENDENCIES',
]