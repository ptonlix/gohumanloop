import unittest
from unittest.mock import MagicMock, AsyncMock
from unittest.async_case import IsolatedAsyncioTestCase

from gohumanloop.core.interface import (
    HumanLoopStatus,
    HumanLoopType,
    HumanLoopResult,
)
from gohumanloop.core.manager import DefaultHumanLoopManager


class MockHumanLoopProvider:
    """模拟人机循环提供者"""

    def __init__(self, name="mock_provider"):
        self.name = name
        self.async_request_humanloop = AsyncMock()
        self.request_humanloop = MagicMock()
        self.async_check_request_status = AsyncMock()
        self.check_request_status = MagicMock()
        self.async_check_conversation_status = AsyncMock()
        self.check_conversation_status = MagicMock()
        self.async_cancel_request = AsyncMock()
        self.cancel_request = MagicMock()
        self.async_cancel_conversation = AsyncMock()
        self.cancel_conversation = MagicMock()
        self.async_continue_humanloop = AsyncMock()
        self.continue_humanloop = MagicMock()


class MockHumanLoopCallback:
    """模拟人机循环回调"""

    def __init__(self):
        self.async_on_humanloop_request = AsyncMock()
        self.async_on_humanloop_update = AsyncMock()
        self.async_on_humanloop_timeout = AsyncMock()
        self.async_on_humanloop_error = AsyncMock()


class TestDefaultHumanLoopManager(IsolatedAsyncioTestCase):
    """测试 DefaultHumanLoopManager 类"""

    def setUp(self):
        """测试前准备"""
        self.provider = MockHumanLoopProvider()
        self.manager = DefaultHumanLoopManager()

    async def test_register_provider(self):
        """测试注册提供者"""
        # 测试异步注册
        provider_id = await self.manager.async_register_provider(
            self.provider, "test_provider"
        )
        self.assertEqual(provider_id, "test_provider")
        self.assertIn("test_provider", self.manager.providers)
        self.assertEqual(self.manager.providers["test_provider"], self.provider)

        # 测试同步注册
        provider2 = MockHumanLoopProvider(name="provider2")
        provider_id2 = self.manager.register_provider(provider2, "provider2")
        self.assertEqual(provider_id2, "provider2")
        print(self.manager.providers)
        self.assertIn("provider2", self.manager.providers)

        # 测试自动生成ID
        provider3 = MockHumanLoopProvider()
        provider_id3 = self.manager.register_provider(provider3, None)
        self.assertTrue(provider_id3.startswith("provider_"))

    async def test_request_humanloop(self):
        """测试请求人机循环"""
        # 注册提供者
        await self.manager.async_register_provider(self.provider, "test_provider")
        self.manager.default_provider_id = "test_provider"

        # 模拟提供者的响应
        mock_result = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )
        self.provider.async_request_humanloop.return_value = mock_result

        # 测试异步请求
        result = await self.manager.async_request_humanloop(
            task_id="test-task",
            conversation_id="test-conv",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            blocking=False,
        )

        # 验证结果
        self.assertEqual(result, "test-req")
        self.provider.async_request_humanloop.assert_called_once()

        # 验证内部状态更新
        self.assertIn("test-task", self.manager._task_conversations)
        self.assertIn("test-conv", self.manager._task_conversations["test-task"])
        self.assertIn("test-conv", self.manager._conversation_requests)
        self.assertIn("test-req", self.manager._conversation_requests["test-conv"])
        self.assertEqual(
            self.manager._request_task[("test-conv", "test-req")], "test-task"
        )
        self.assertEqual(
            self.manager._conversation_provider["test-conv"], "test_provider"
        )

    async def test_continue_humanloop(self):
        """测试继续人机循环"""
        # 注册提供者
        await self.manager.async_register_provider(self.provider, "test_provider")
        self.manager.default_provider_id = "test_provider"

        # 先创建一个对话
        mock_result1 = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req-1",
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.COMPLETED,
        )
        self.provider.async_request_humanloop.return_value = mock_result1

        await self.manager.async_request_humanloop(
            task_id="test-task",
            conversation_id="test-conv",
            loop_type=HumanLoopType.CONVERSATION,
            context={"message": "Hello"},
        )

        # 模拟继续对话的响应
        mock_result2 = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req-2",
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.PENDING,
        )
        self.provider.async_continue_humanloop.return_value = mock_result2

        # 测试继续对话
        result = await self.manager.async_continue_humanloop(
            conversation_id="test-conv",
            context={"message": "How are you?"},
            blocking=False,
        )

        # 验证结果
        self.assertEqual(result, "test-req-2")
        self.provider.async_continue_humanloop.assert_called_once()

        # 验证内部状态更新
        self.assertIn("test-req-2", self.manager._conversation_requests["test-conv"])

    async def test_check_request_status(self):
        """测试检查请求状态"""
        # 注册提供者
        await self.manager.async_register_provider(self.provider, "test_provider")
        self.manager.default_provider_id = "test_provider"

        # 模拟提供者的响应
        mock_result = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED,
            response={"decision": "approved"},
        )
        self.provider.async_check_request_status.return_value = mock_result

        # 测试检查状态
        result = await self.manager.async_check_request_status(
            conversation_id="test-conv",
            request_id="test-req",
        )

        # 验证结果
        self.assertEqual(result.status, HumanLoopStatus.APPROVED)
        self.assertEqual(result.response, {"decision": "approved"})
        self.provider.async_check_request_status.assert_called_once_with(
            "test-conv", "test-req"
        )

    async def test_cancel_request(self):
        """测试取消请求"""
        # 注册提供者
        await self.manager.async_register_provider(self.provider, "test_provider")
        self.manager.default_provider_id = "test_provider"

        # 先创建一个请求
        mock_result = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )
        self.provider.async_request_humanloop.return_value = mock_result

        await self.manager.async_request_humanloop(
            task_id="test-task",
            conversation_id="test-conv",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
        )

        # 模拟取消请求的响应
        self.provider.async_cancel_request.return_value = True

        # 测试取消请求
        result = await self.manager.async_cancel_request(
            conversation_id="test-conv",
            request_id="test-req",
        )

        # 验证结果
        self.assertTrue(result)
        self.provider.async_cancel_request.assert_called_once_with(
            "test-conv", "test-req"
        )

        # 验证内部状态更新
        self.assertNotIn("test-req", self.manager._conversation_requests["test-conv"])

    async def test_callback_mechanism(self):
        """测试回调机制"""
        # 注册提供者
        await self.manager.async_register_provider(self.provider, "test_provider")
        self.manager.default_provider_id = "test_provider"

        # 创建回调
        callback = MockHumanLoopCallback()

        # 模拟提供者的响应
        mock_result1 = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )
        self.provider.async_request_humanloop.return_value = mock_result1

        # 发送请求
        await self.manager.async_request_humanloop(
            task_id="test-task",
            conversation_id="test-conv",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            callback=callback,
        )

        # 模拟状态更新
        mock_result2 = HumanLoopResult(
            conversation_id="test-conv",
            request_id="test-req",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED,
            response={"decision": "approved"},
        )
        self.provider.async_check_request_status.return_value = mock_result2

        # 检查状态，这应该触发回调
        await self.manager.async_check_request_status(
            conversation_id="test-conv",
            request_id="test-req",
        )

        # 验证回调被调用
        callback.async_on_humanloop_update.assert_called_once()
        args, kwargs = callback.async_on_humanloop_update.call_args
        self.assertEqual(args[0], self.provider)
        self.assertEqual(args[1].status, HumanLoopStatus.APPROVED)

    async def test_error_handling(self):
        """测试错误处理"""
        # 注册提供者
        await self.manager.async_register_provider(self.provider, "test_provider")
        self.manager.default_provider_id = "test_provider"

        # 创建回调
        callback = MockHumanLoopCallback()

        # 模拟提供者抛出异常
        self.provider.async_request_humanloop.side_effect = ValueError("Test error")

        # 测试异常处理
        with self.assertRaises(ValueError):
            await self.manager.async_request_humanloop(
                task_id="test-task",
                conversation_id="test-conv",
                loop_type=HumanLoopType.APPROVAL,
                context={"message": "Please approve"},
                callback=callback,
            )

        # 验证错误回调被调用
        callback.async_on_humanloop_error.assert_called_once()
        args, kwargs = callback.async_on_humanloop_error.call_args
        self.assertEqual(args[0], self.provider)
        self.assertIsInstance(args[1], ValueError)


if __name__ == "__main__":
    unittest.main()
