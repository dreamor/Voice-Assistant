"""utility_ops 单元测试"""
import pytest
from voice_assistant.tools.universal.utility_ops import calculate


class TestCalculate:
    def test_basic_arithmetic(self):
        assert "5" in calculate(expression="2 + 3")
        assert "6" in calculate(expression="10 - 4")
        assert "21" in calculate(expression="3 * 7")
        assert "5" in calculate(expression="20 / 4")

    def test_float_result(self):
        result = calculate(expression="1 / 3")
        assert "0.333" in result

    def test_complex_expression(self):
        result = calculate(expression="(2 + 3) * 4")
        assert "20" in result

    def test_power(self):
        result = calculate(expression="2 ** 10")
        assert "1024" in result

    def test_math_functions(self):
        result = calculate(expression="abs(-5)")
        assert "5" in result

    def test_round_function(self):
        result = calculate(expression="round(3.14159, 2)")
        assert "3.14" in result

    def test_min_max(self):
        assert "3" in calculate(expression="min(3, 5, 7)")
        assert "7" in calculate(expression="max(3, 5, 7)")

    def test_empty_expression(self):
        result = calculate(expression="")
        assert "错误" in result or "失败" in result

    def test_dangerous_names_blocked(self):
        result = calculate(expression="__import__('os').system('ls')")
        assert "不允许" in result

    def test_eval_blocked(self):
        result = calculate(expression="eval('1+1')")
        assert "不允许" in result

    def test_exec_blocked(self):
        result = calculate(expression="exec('print(1)')")
        assert "不允许" in result

    def test_open_blocked(self):
        result = calculate(expression="open('/etc/passwd')")
        assert "不允许" in result

    def test_caret_power(self):
        result = calculate(expression="2 ^ 3")
        assert "8" in result

    def test_division_by_zero(self):
        result = calculate(expression="1 / 0")
        assert "除以零" in result

    def test_unknown_name(self):
        result = calculate(expression="foo(1)")
        assert "未知" in result