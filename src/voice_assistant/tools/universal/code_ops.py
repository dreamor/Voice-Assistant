"""
通用工具操作 - code_ops
执行 Python 代码片段。
"""
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_TIMEOUT_SECONDS = 120
MAX_OUTPUT_BYTES = 8 * 1024
DEFAULT_TIMEOUT = 30


def run_python_code(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """执行一段 Python 代码并返回 stdout / stderr。

    在独立子进程中运行，受 ``timeout`` 限制。输出超过
    ``MAX_OUTPUT_BYTES`` (8KB) 时尾部截断。

    Args:
        code: 完整 Python 源码
        timeout: 最大执行秒数 (1-120)

    Returns:
        人类可读结果摘要
    """
    if not code or not code.strip():
        return "错误: code 不能为空"

    try:
        timeout_clamped = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        timeout_clamped = DEFAULT_TIMEOUT

    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout_clamped,
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        return f"错误: 执行超时 ({timeout_clamped}s)"
    except FileNotFoundError as e:
        return f"错误: 找不到 Python 解释器: {e}"
    except Exception as e:
        return f"错误: 启动失败: {type(e).__name__}: {e}"

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    stdout_trunc = stdout[-MAX_OUTPUT_BYTES:] if len(stdout) > MAX_OUTPUT_BYTES else stdout
    stderr_trunc = stderr[-MAX_OUTPUT_BYTES:] if len(stderr) > MAX_OUTPUT_BYTES else stderr

    parts = [f"returncode={proc.returncode}"]
    if stdout_trunc:
        if len(stdout) > MAX_OUTPUT_BYTES:
            parts.append(f"stdout (尾部, 截断自 {len(stdout)}B):\n{stdout_trunc}")
        else:
            parts.append(f"stdout:\n{stdout_trunc}")
    if stderr_trunc:
        if len(stderr) > MAX_OUTPUT_BYTES:
            parts.append(f"stderr (尾部, 截断自 {len(stderr)}B):\n{stderr_trunc}")
        else:
            parts.append(f"stderr:\n{stderr_trunc}")

    if proc.returncode != 0 and not stderr_trunc:
        parts.append("(非零返回码但无 stderr 输出)")

    return "\n".join(parts)
