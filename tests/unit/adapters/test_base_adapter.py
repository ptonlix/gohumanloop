import unittest
from unittest.mock import MagicMock

from gohumanloop.adapters.base_adapter import (
    HumanloopAdapter,
    HumanLoopWrapper,
)
from gohumanloop.core.interface import (
    HumanLoopManager,
)


class TestLangGraphAdapter(unittest.TestCase):
    """LangGraphAdapter 类的单元测试"""

    def setUp(self):
        """测试前的准备工作"""
        # 创建模拟的 HumanLoopManager
        self.mock_manager = MagicMock(spec=HumanLoopManager)
        # 创建测试用的适配器实例
        self.adapter = HumanloopAdapter(self.mock_manager, default_timeout=30)

    def test_initialization(self):
        """测试 LangGraphAdapter 类的初始化"""
        # 测试初始化参数是否正确设置
        self.assertEqual(self.adapter.manager, self.mock_manager)
        self.assertEqual(self.adapter.default_timeout, 30)

        # 测试默认超时参数
        adapter_no_timeout = HumanloopAdapter(self.mock_manager)
        self.assertIsNone(adapter_no_timeout.default_timeout)

    def test_human_loop_wrapper(self):
        """测试 HumanLoopWrapper 类"""

        # 创建一个简单的装饰器函数
        def simple_decorator(fn):
            return fn

        # 创建 HumanLoopWrapper 实例
        wrapper = HumanLoopWrapper(simple_decorator)

        # 测试目标函数
        def target_function():
            return "测试成功"

        # 测试 wrap 方法
        wrapped_fn = wrapper.wrap(target_function)
        self.assertEqual(wrapped_fn(), "测试成功")

        # 测试 __call__ 方法
        called_fn = wrapper(target_function)
        self.assertEqual(called_fn(), "测试成功")


if __name__ == "__main__":
    unittest.main()
