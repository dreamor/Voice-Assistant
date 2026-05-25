"""
工具注册中心 - 统一管理所有 Agent Tool
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from voice_assistant.security.safe_guard import GuardResult, SafeGuard, SecurityLevel
from voice_assistant.security.validation import tool_limiter
from voice_assistant.tools.tool_groups import get_tools_for_groups

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果（结构化）"""
    success: bool
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    needs_confirmation: bool = False
    guard_result: GuardResult | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（向后兼容）"""
        result: dict[str, Any] = {
            "success": self.success,
            "result": self.output,
            "needs_confirmation": self.needs_confirmation,
        }
        if self.guard_result is not None:
            result["guard_result"] = self.guard_result
        result.update(self.data)
        return result


def _validate_arguments(parameters: dict, arguments: dict) -> list[str]:
    """根据 JSON Schema 校验参数，返回错误列表

    仅校验 required 字段和基本类型匹配，不引入 jsonschema 依赖。
    """
    errors: list[str] = []
    required = parameters.get("required", [])
    props = parameters.get("properties", {})

    for name in required:
        if name not in arguments or arguments[name] is None:
            errors.append(f"缺少必填参数: {name}")

    for name, value in arguments.items():
        if name not in props:
            continue
        expected = props[name].get("type")
        if expected and value is not None:
            # bool 是 int 子类，需优先检查
            if expected in ("integer", "number") and isinstance(value, bool):
                errors.append(f"参数 '{name}' 应为 {expected}，实际为 boolean")
                continue
            type_map = {
                "string": str, "integer": int, "number": (int, float),
                "boolean": bool, "array": list, "object": dict,
            }
            expected_type = type_map.get(expected)
            if expected_type and not isinstance(value, expected_type):
                errors.append(
                    f"参数 '{name}' 应为 {expected}，实际为 {type(value).__name__}"
                )
    return errors


@dataclass
class ToolDefinition:
    """单个工具的定义"""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable
    security_level: SecurityLevel = SecurityLevel.WRITE
    platforms: list[str] = field(default_factory=lambda: ["mac", "windows", "linux"])

    def to_openai_function(self) -> dict:
        """转为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """工具注册中心"""

    def __init__(self, current_platform: str, safe_guard: SafeGuard | None = None):
        self._tools: dict[str, ToolDefinition] = {}
        self._platform = current_platform
        self._guard = safe_guard or SafeGuard()

    def register(self, tool: ToolDefinition):
        """注册工具"""
        if self._platform not in tool.platforms:
            logger.debug(f"[ToolRegistry] 跳过非当前平台工具: {tool.name}")
            return
        if tool.name in self._tools:
            logger.warning(f"[ToolRegistry] 工具重复注册，覆盖: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"[ToolRegistry] 注册工具: {tool.name} (level={tool.security_level.value})")

    def register_all(self, tools: list[ToolDefinition]):
        for t in tools:
            self.register(t)

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get_openai_tools(self, groups: list[str] | None = None) -> list[dict]:
        """导出为 OpenAI function calling tools 列表

        Args:
            groups: 工具分组名列表。None 表示返回所有工具（向后兼容）。
        """
        allowed = get_tools_for_groups(groups)
        if allowed is None:
            return [t.to_openai_function() for t in self._tools.values()]
        return [
            t.to_openai_function()
            for name, t in self._tools.items()
            if name in allowed
        ]

    def execute(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """执行工具（含速率限制、安全检查和参数校验）

        Returns:
            {"success": bool, "result": str, "needs_confirmation": bool, "guard_result": ...}
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False, output=f"未知工具: {tool_name}"
            ).to_dict()

        # 速率限制检查
        allowed, rate_msg = tool_limiter.check(tool_name)
        if not allowed:
            return ToolResult(success=False, output=rate_msg).to_dict()

        # 参数校验
        validation_errors = _validate_arguments(tool.parameters, arguments)
        if validation_errors:
            return ToolResult(
                success=False, output=f"参数校验失败: {'; '.join(validation_errors)}"
            ).to_dict()

        # 安全检查
        guard = self._guard.check(tool_name, arguments, tool.security_level)
        from voice_assistant.security.safe_guard import GuardAction

        if guard.action == GuardAction.BLOCKED:
            return ToolResult(
                success=False, output=f"操作被阻止: {guard.message}"
            ).to_dict()

        if guard.action in (GuardAction.CONFIRM_NEEDED, GuardAction.DOUBLE_CONFIRM):
            return ToolResult(
                success=True, output=guard.message,
                needs_confirmation=True, guard_result=guard
            ).to_dict()

        # 自动执行 (READ_ONLY)
        return self._execute_internal(tool_name, arguments)

    def execute_confirmed(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """用户确认后的执行（跳过安全检查）"""
        return self._execute_internal(tool_name, arguments)

    def _execute_internal(self, tool_name: str, arguments: dict) -> dict[str, Any]:
        """内部执行"""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False, output=f"未知工具: {tool_name}"
            ).to_dict()

        try:
            logger.info(f"[ToolRegistry] 执行: {tool_name}({arguments})")
            result = tool.handler(**arguments)
            if isinstance(result, str):
                return ToolResult(success=True, output=result).to_dict()
            if isinstance(result, dict):
                result["needs_confirmation"] = False
                return result
            return ToolResult(success=True, output=str(result)).to_dict()
        except TypeError as e:
            logger.error(f"[ToolRegistry] 参数错误 {tool_name}: {e}")
            return ToolResult(
                success=False, output=f"参数错误: {e}"
            ).to_dict()
        except Exception as e:
            logger.error(f"[ToolRegistry] 执行失败 {tool_name}: {e}")
            return ToolResult(
                success=False, output=f"执行失败: {e}"
            ).to_dict()

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_tools_by_level(self, level: SecurityLevel) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.security_level == level]
