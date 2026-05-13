"""run_python_code tool 测试"""
import sys

import pytest

from voice_assistant.tools.universal.code_ops import (
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    run_python_code,
)


class TestRunPythonCode:
    def test_simple_print(self):
        out = run_python_code('print("hello")')
        assert "returncode=0" in out
        assert "hello" in out

    def test_returncode_nonzero(self):
        out = run_python_code('import sys; sys.exit(2)')
        assert "returncode=2" in out

    def test_syntax_error(self):
        out = run_python_code('def (')
        assert "returncode=" in out
        assert "SyntaxError" in out or "syntax" in out.lower()

    def test_runtime_exception_in_stderr(self):
        out = run_python_code('raise ValueError("boom")')
        assert "returncode=1" in out
        assert "ValueError" in out

    def test_timeout(self):
        out = run_python_code('import time; time.sleep(5)', timeout=1)
        assert "超时" in out

    def test_empty_code(self):
        assert "不能为空" in run_python_code("")
        assert "不能为空" in run_python_code("   \n\t  ")

    def test_max_timeout_clamped(self):
        # 不真正运行 9999 秒，只验证 clamp 不抛错
        out = run_python_code('print("ok")', timeout=99999)
        assert "returncode=0" in out

    def test_negative_timeout_clamped_to_min(self):
        out = run_python_code('print("ok")', timeout=-5)
        assert "returncode=0" in out

    def test_stdout_truncation(self):
        # 输出超过 MAX_OUTPUT_BYTES
        n = MAX_OUTPUT_BYTES * 2
        out = run_python_code(f'print("x" * {n})')
        assert "returncode=0" in out
        assert "截断自" in out

    def test_cwd_is_home(self):
        # 验证 cwd 默认为 Home
        out = run_python_code('import os; print(os.getcwd())')
        from pathlib import Path
        assert str(Path.home()) in out

    def test_constants(self):
        assert MAX_TIMEOUT_SECONDS == 120
        assert MAX_OUTPUT_BYTES == 8 * 1024


class TestToolDefinitionRegistered:
    def test_run_python_code_in_universal_tools(self):
        """确认 run_python_code 已加入 universal tool 注册表"""
        from voice_assistant.tools.universal import get_universal_tools

        names = {t.name for t in get_universal_tools()}
        assert "run_python_code" in names

    def test_run_python_code_is_dangerous(self):
        """安全级别为 DANGEROUS（二次确认）"""
        from voice_assistant.security.safe_guard import SecurityLevel
        from voice_assistant.tools.universal import get_universal_tools

        tool = next(t for t in get_universal_tools() if t.name == "run_python_code")
        assert tool.security_level == SecurityLevel.DANGEROUS
