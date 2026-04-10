"""执行器基类测试"""
import pytest
from voice_assistant.executors.base import BaseExecutor


class ConcreteExecutor(BaseExecutor):
    """测试用具体执行器"""

    def execute(self, **kwargs):
        return {"status": "success", "data": kwargs}

    def can_handle(self, intent_type: str) -> bool:
        return intent_type in ["test", "demo"]


class AnotherExecutor(BaseExecutor):
    """另一个测试执行器"""

    def execute(self, **kwargs):
        return "executed"

    def can_handle(self, intent_type: str) -> bool:
        return intent_type == "another"


class TestBaseExecutor:
    """测试 BaseExecutor 抽象类"""

    def test_cannot_instantiate_abstract_class(self):
        """测试不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BaseExecutor()

    def test_concrete_executor_creation(self):
        """测试具体执行器可以创建"""
        executor = ConcreteExecutor()
        assert executor is not None

    def test_execute_method(self):
        """测试 execute 方法"""
        executor = ConcreteExecutor()
        result = executor.execute(command="test", value=123)

        assert result["status"] == "success"
        assert result["data"]["command"] == "test"
        assert result["data"]["value"] == 123

    def test_can_handle_matching_intent(self):
        """测试 can_handle 匹配的意图"""
        executor = ConcreteExecutor()

        assert executor.can_handle("test") is True
        assert executor.can_handle("demo") is True

    def test_can_handle_non_matching_intent(self):
        """测试 can_handle 不匹配的意图"""
        executor = ConcreteExecutor()

        assert executor.can_handle("unknown") is False
        assert executor.can_handle("another") is False

    def test_different_executors_different_handling(self):
        """测试不同执行器处理不同意图"""
        executor1 = ConcreteExecutor()
        executor2 = AnotherExecutor()

        assert executor1.can_handle("test") is True
        assert executor2.can_handle("test") is False

        assert executor1.can_handle("another") is False
        assert executor2.can_handle("another") is True

    def test_execute_with_no_kwargs(self):
        """测试无参数执行"""
        executor = ConcreteExecutor()
        result = executor.execute()

        assert result["status"] == "success"
        assert result["data"] == {}

    def test_execute_with_complex_kwargs(self):
        """测试复杂参数执行"""
        executor = ConcreteExecutor()
        result = executor.execute(
            nested={"key": "value"},
            items=[1, 2, 3],
            flag=True
        )

        assert result["data"]["nested"]["key"] == "value"
        assert result["data"]["items"] == [1, 2, 3]
        assert result["data"]["flag"] is True


class TestExecutorProtocol:
    """测试执行器协议"""

    def test_executor_interface_completeness(self):
        """测试执行器接口完整性"""
        executor = ConcreteExecutor()

        # 必须有 execute 方法
        assert hasattr(executor, 'execute')
        assert callable(executor.execute)

        # 必须有 can_handle 方法
        assert hasattr(executor, 'can_handle')
        assert callable(executor.can_handle)

    def test_executor_return_types(self):
        """测试执行器返回类型"""
        executor = ConcreteExecutor()

        # execute 可以返回任意类型
        result = executor.execute()
        assert result is not None

        # can_handle 必须返回 bool
        can_handle_result = executor.can_handle("test")
        assert isinstance(can_handle_result, bool)