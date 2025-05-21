import unittest
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from unittest import IsolatedAsyncioTestCase
from datetime import datetime
from typing import Dict, Any, Optional

from gohumanloop.core.interface import (
    HumanLoopType,
    HumanLoopStatus,
    HumanLoopResult,
    HumanLoopCallback,
    HumanLoopProvider,
    HumanLoopRequest,
)


class TestHumanLoopType(unittest.TestCase):
    """测试 HumanLoopType 枚举类型"""

    def test_enum_values(self):
        """测试枚举值是否正确"""
        self.assertEqual(HumanLoopType.APPROVAL.value, "approval")
        self.assertEqual(HumanLoopType.INFORMATION.value, "information")
        self.assertEqual(HumanLoopType.CONVERSATION.value, "conversation")

    def test_enum_comparison(self):
        """测试枚举比较"""
        self.assertEqual(HumanLoopType.APPROVAL, HumanLoopType.APPROVAL)
        self.assertNotEqual(HumanLoopType.APPROVAL, HumanLoopType.INFORMATION)
        self.assertNotEqual(HumanLoopType.APPROVAL, HumanLoopType.CONVERSATION)

    def test_enum_string_representation(self):
        """测试枚举的字符串表示"""
        self.assertEqual(str(HumanLoopType.APPROVAL), "HumanLoopType.APPROVAL")
        self.assertEqual(str(HumanLoopType.INFORMATION), "HumanLoopType.INFORMATION")
        self.assertEqual(str(HumanLoopType.CONVERSATION), "HumanLoopType.CONVERSATION")


class TestHumanLoopStatus(unittest.TestCase):
    """测试 HumanLoopStatus 枚举类型"""

    def test_enum_values(self):
        """测试枚举值是否正确"""
        self.assertEqual(HumanLoopStatus.PENDING.value, "pending")
        self.assertEqual(HumanLoopStatus.APPROVED.value, "approved")
        self.assertEqual(HumanLoopStatus.REJECTED.value, "rejected")
        self.assertEqual(HumanLoopStatus.EXPIRED.value, "expired")
        self.assertEqual(HumanLoopStatus.ERROR.value, "error")
        self.assertEqual(HumanLoopStatus.COMPLETED.value, "completed")
        self.assertEqual(HumanLoopStatus.INPROGRESS.value, "inprogress")
        self.assertEqual(HumanLoopStatus.CANCELLED.value, "cancelled")

    def test_enum_comparison(self):
        """测试枚举比较"""
        self.assertEqual(HumanLoopStatus.PENDING, HumanLoopStatus.PENDING)
        self.assertNotEqual(HumanLoopStatus.PENDING, HumanLoopStatus.APPROVED)
        self.assertNotEqual(HumanLoopStatus.APPROVED, HumanLoopStatus.REJECTED)

    def test_enum_string_representation(self):
        """测试枚举的字符串表示"""
        self.assertEqual(str(HumanLoopStatus.PENDING), "HumanLoopStatus.PENDING")
        self.assertEqual(str(HumanLoopStatus.APPROVED), "HumanLoopStatus.APPROVED")
        self.assertEqual(str(HumanLoopStatus.REJECTED), "HumanLoopStatus.REJECTED")


class TestHumanLoopResult(unittest.TestCase):
    """测试 HumanLoopResult 数据类"""

    def test_initialization(self):
        """测试初始化"""
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )

        self.assertEqual(result.conversation_id, "test-conversation")
        self.assertEqual(result.request_id, "test-request")
        self.assertEqual(result.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(result.status, HumanLoopStatus.PENDING)
        self.assertEqual(result.response, {})
        self.assertEqual(result.feedback, {})
        self.assertIsNone(result.responded_by)
        self.assertIsNone(result.responded_at)
        self.assertIsNone(result.error)

    def test_initialization_with_optional_fields(self):
        """测试带可选字段的初始化"""
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED,
            response={"decision": "yes"},
            feedback={"comment": "looks good"},
            responded_by="user1",
            responded_at="2023-01-01T12:00:00Z",
            error=None,
        )

        self.assertEqual(result.conversation_id, "test-conversation")
        self.assertEqual(result.request_id, "test-request")
        self.assertEqual(result.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(result.status, HumanLoopStatus.APPROVED)
        self.assertEqual(result.response, {"decision": "yes"})
        self.assertEqual(result.feedback, {"comment": "looks good"})
        self.assertEqual(result.responded_by, "user1")
        self.assertEqual(result.responded_at, "2023-01-01T12:00:00Z")
        self.assertIsNone(result.error)

    def test_error_state(self):
        """测试错误状态"""
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.ERROR,
            error="Something went wrong",
        )

        self.assertEqual(result.status, HumanLoopStatus.ERROR)
        self.assertEqual(result.error, "Something went wrong")


class TestHumanLoopRequest(unittest.TestCase):
    """测试 HumanLoopRequest 数据类"""

    def test_initialization(self):
        """测试初始化"""
        request = HumanLoopRequest(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve this action"},
        )

        self.assertEqual(request.task_id, "test-task")
        self.assertEqual(request.conversation_id, "test-conversation")
        self.assertEqual(request.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(request.context, {"message": "Please approve this action"})
        self.assertEqual(request.metadata, {})
        self.assertIsNone(request.request_id)
        self.assertIsNone(request.timeout)
        self.assertIsNone(request.created_at)

    def test_initialization_with_optional_fields(self):
        """测试带可选字段的初始化"""
        created_time = datetime.now()
        request = HumanLoopRequest(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.INFORMATION,
            context={"question": "What is your name?"},
            metadata={"priority": "high"},
            request_id="test-request",
            timeout=60,
            created_at=created_time,
        )

        self.assertEqual(request.task_id, "test-task")
        self.assertEqual(request.conversation_id, "test-conversation")
        self.assertEqual(request.loop_type, HumanLoopType.INFORMATION)
        self.assertEqual(request.context, {"question": "What is your name?"})
        self.assertEqual(request.metadata, {"priority": "high"})
        self.assertEqual(request.request_id, "test-request")
        self.assertEqual(request.timeout, 60)
        self.assertEqual(request.created_at, created_time)


# 创建一个实现 HumanLoopCallback 的测试类
class MockCallbackImplementation(HumanLoopCallback):
    """测试 HumanLoopCallback 接口的实现类"""

    def __init__(self):
        self.update_called = False
        self.timeout_called = False
        self.error_called = False
        self.last_result = None
        self.last_provider = None
        self.last_error = None

    async def on_humanloop_update(self, provider, result):
        self.update_called = True
        self.last_provider = provider
        self.last_result = result

    async def on_humanloop_timeout(self, provider):
        self.timeout_called = True
        self.last_provider = provider

    async def on_humanloop_error(self, provider, error):
        self.error_called = True
        self.last_provider = provider
        self.last_error = error


class TestHumanLoopCallback(IsolatedAsyncioTestCase):
    """测试 HumanLoopCallback 接口"""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_callback_methods(self):
        """测试回调方法"""
        callback = MockCallbackImplementation()
        provider_mock = MagicMock()
        provider_mock.name = "TestProvider"

        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED,
        )

        # 测试更新回调
        await callback.on_humanloop_update(provider_mock, result)
        self.assertTrue(callback.update_called)
        self.assertEqual(callback.last_provider, provider_mock)
        self.assertEqual(callback.last_result, result)

        # 测试超时回调
        await callback.on_humanloop_timeout(provider_mock)
        self.assertTrue(callback.timeout_called)
        self.assertEqual(callback.last_provider, provider_mock)

        # 测试错误回调
        error = Exception("Test error")
        await callback.on_humanloop_error(provider_mock, error)
        self.assertTrue(callback.error_called)
        self.assertEqual(callback.last_provider, provider_mock)
        self.assertEqual(callback.last_error, error)


# 创建一个模拟的 HumanLoopProvider 实现
class MockHumanLoopProvider:
    """模拟的 HumanLoopProvider 实现"""

    def __init__(self, name="MockProvider"):
        self.name = name
        self.request_humanloop_mock = AsyncMock()
        self.check_request_status_mock = AsyncMock()
        self.check_conversation_status_mock = AsyncMock()
        self.cancel_request_mock = AsyncMock()
        self.cancel_conversation_mock = AsyncMock()
        self.continue_humanloop_mock = AsyncMock()

    async def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        return await self.request_humanloop_mock(
            task_id, conversation_id, loop_type, context, metadata, timeout
        )

    async def check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        return await self.check_request_status_mock(conversation_id, request_id)

    async def check_conversation_status(self, conversation_id: str) -> HumanLoopResult:
        return await self.check_conversation_status_mock(conversation_id)

    async def cancel_request(self, conversation_id: str, request_id: str) -> bool:
        return await self.cancel_request_mock(conversation_id, request_id)

    async def cancel_conversation(self, conversation_id: str) -> bool:
        return await self.cancel_conversation_mock(conversation_id)

    async def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        return await self.continue_humanloop_mock(
            conversation_id, context, metadata, timeout
        )


class TestHumanLoopProvider(IsolatedAsyncioTestCase):
    """测试 HumanLoopProvider 协议"""

    def test_provider_protocol_compliance(self):
        """测试提供者是否符合协议要求"""
        provider = MockHumanLoopProvider()

        # 验证是否实现了所有必需的属性和方法
        self.assertTrue(hasattr(provider, "name"))
        self.assertTrue(hasattr(provider, "request_humanloop"))
        self.assertTrue(hasattr(provider, "check_request_status"))
        self.assertTrue(hasattr(provider, "check_conversation_status"))
        self.assertTrue(hasattr(provider, "cancel_request"))
        self.assertTrue(hasattr(provider, "cancel_conversation"))
        self.assertTrue(hasattr(provider, "continue_humanloop"))

        # 验证是否符合 HumanLoopProvider 协议
        # 注意：由于 Protocol 是运行时检查，我们需要确保实现了所有必需的方法
        self.assertTrue(isinstance(provider, HumanLoopProvider))

    @pytest.mark.asyncio(loop_scope="module")
    async def test_provider_methods(self):
        """测试提供者方法"""
        provider = MockHumanLoopProvider()

        # 设置模拟返回值
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )

        provider.request_humanloop_mock.return_value = result
        provider.check_request_status_mock.return_value = result
        provider.check_conversation_status_mock.return_value = result
        provider.cancel_request_mock.return_value = True
        provider.cancel_conversation_mock.return_value = True
        provider.continue_humanloop_mock.return_value = result

        # 测试 request_humanloop 方法
        response = await provider.request_humanloop(
            "test-task",
            "test-conversation",
            HumanLoopType.APPROVAL,
            {"message": "Please approve"},
        )
        self.assertEqual(response, result)
        provider.request_humanloop_mock.assert_called_once()

        # 测试 check_request_status 方法
        response = await provider.check_request_status(
            "test-conversation", "test-request"
        )
        self.assertEqual(response, result)
        provider.check_request_status_mock.assert_called_once_with(
            "test-conversation", "test-request"
        )

        # 测试 check_conversation_status 方法
        response = await provider.check_conversation_status("test-conversation")
        self.assertEqual(response, result)
        provider.check_conversation_status_mock.assert_called_once_with(
            "test-conversation"
        )

        # 测试 cancel_request 方法
        response = await provider.cancel_request("test-conversation", "test-request")
        self.assertTrue(response)
        provider.cancel_request_mock.assert_called_once_with(
            "test-conversation", "test-request"
        )

        # 测试 cancel_conversation 方法
        response = await provider.cancel_conversation("test-conversation")
        self.assertTrue(response)
        provider.cancel_conversation_mock.assert_called_once_with("test-conversation")

        # 测试 continue_humanloop 方法
        response = await provider.continue_humanloop(
            "test-conversation", {"message": "Additional information"}
        )
        self.assertEqual(response, result)
        provider.continue_humanloop_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
