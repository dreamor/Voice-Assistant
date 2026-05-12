"""
执行器基类
定义执行器的标准接口
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseExecutor(ABC):
    """执行器基类"""

    @abstractmethod
    def execute(self, **kwargs: Any) -> Any:
        """执行操作并返回结果"""
        pass

    @abstractmethod
    def can_handle(self, intent_type: str) -> bool:
        """判断是否可以处理该意图类型"""
        pass