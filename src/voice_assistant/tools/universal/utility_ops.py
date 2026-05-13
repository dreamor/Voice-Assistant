"""
通用工具操作 - utility_ops
计算器等通用工具
"""
import logging
import math

logger = logging.getLogger(__name__)

# 安全数学函数白名单
_SAFE_MATH = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sum": sum, "pow": pow,
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "pi": math.pi, "e": math.e,
    "ceil": math.ceil, "floor": math.floor,
}

# 禁止的危险内置函数
_BLOCKED_NAMES = frozenset({"__import__", "exec", "eval", "compile", "open", "input"})


def calculate(expression: str) -> str:
    """安全计算数学表达式

    支持基本运算 (+, -, *, /, **, %) 和常用数学函数。
    不执行任意代码，仅解析数学表达式。

    Args:
        expression: 数学表达式，如 "2 + 3 * 4" 或 "sqrt(144) + pi"
    """
    expr = expression.strip()

    for blocked in _BLOCKED_NAMES:
        if blocked in expr:
            return f"不允许的操作: {blocked}"

    cleaned = expr.replace("^", "**")

    try:
        result = eval(cleaned, {"__builtins__": {}}, _SAFE_MATH)
        if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
            return f"{expression} = {int(result)}"
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "错误: 除以零"
    except SyntaxError:
        return f"表达式语法错误: {expression}"
    except NameError as e:
        return f"未知函数或变量: {e}"
    except Exception as e:
        return f"计算失败: {e}"
