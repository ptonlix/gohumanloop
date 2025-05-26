import unittest
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, Optional
from unittest.async_case import IsolatedAsyncioTestCase

from gohumanloop.core.interface import (
    HumanLoopStatus,
    HumanLoopType,
    HumanLoopRequest,
    HumanLoopResult,
    HumanLoopProvider,
    HumanLoopCallback,
)


class TestHumanLoopStatus(unittest.TestCase):
    """测试 HumanLoopStatus 枚举"""

    def test_status_values(self):
        """测试状态值"""
        self.assertEqual(HumanLoopStatus.PENDING.value, "pending")
        self.assertEqual(HumanLoopStatus.APPROVED.value, "approved")
        self.assertEqual(HumanLoopStatus.REJECTED.value, "rejected")
        self.assertEqual(HumanLoopStatus.EXPIRED.value, "expired")
        self.assertEqual(HumanLoopStatus.ERROR.value, "error")
        self.assertEqual(HumanLoopStatus.COMPLETED.value, "completed")
        self.assertEqual(HumanLoopStatus.INPROGRESS.value, "inprogress")
        self.assertEqual(HumanLoopStatus.CANCELLED.value, "cancelled")


class TestHumanLoopType(unittest.TestCase):
    """测试 HumanLoopType 枚举"""

    def test_type_values(self):
        """测试类型值"""
        self.assertEqual(HumanLoopType.APPROVAL.value, "approval")
        self.assertEqual(HumanLoopType.INFORMATION.value, "information")
        self.assertEqual(HumanLoopType.CONVERSATION.value, "conversation")


class TestHumanLoopRequest(unittest.TestCase):
    """测试 HumanLoopRequest 数据类"""

    def test_request_creation(self):
        """测试请求创建"""
        request = HumanLoopRequest(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve this action"},
            metadata={"source": "unit-test"},
            request_id="test-request",
            timeout=60,
        )

        self.assertEqual(request.task_id, "test-task")
        self.assertEqual(request.conversation_id, "test-conversation")
        self.assertEqual(request.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(request.context, {"message": "Please approve this action"})
        self.assertEqual(request.metadata, {"source": "unit-test"})
        self.assertEqual(request.request_id, "test-request")
        self.assertEqual(request.timeout, 60)

    def test_request_defaults(self):
        """测试请求默认值"""
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


class TestHumanLoopResult(unittest.TestCase):
    """测试 HumanLoopResult 数据类"""

    def test_result_creation(self):
        """测试结果创建"""
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED,
            response={"decision": "approved"},
            feedback={"comment": "Looks good"},
            responded_by="test-user",
            responded_at="2023-01-01T12:00:00Z",
        )

        self.assertEqual(result.conversation_id, "test-conversation")
        self.assertEqual(result.request_id, "test-request")
        self.assertEqual(result.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(result.status, HumanLoopStatus.APPROVED)
        self.assertEqual(result.response, {"decision": "approved"})
        self.assertEqual(result.feedback, {"comment": "Looks good"})
        self.assertEqual(result.responded_by, "test-user")
        self.assertEqual(result.responded_at, "2023-01-01T12:00:00Z")
        self.assertIsNone(result.error)

    def test_result_defaults(self):
        """测试结果默认值"""
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

    def test_result_with_error(self):
        """测试带有错误的结果"""
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.ERROR,
            error="Something went wrong",
        )

        self.assertEqual(result.conversation_id, "test-conversation")
        self.assertEqual(result.request_id, "test-request")
        self.assertEqual(result.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(result.status, HumanLoopStatus.ERROR)
        self.assertEqual(result.error, "Something went wrong")


# 创建一个模拟的回调实现
class MockCallbackImplementation(HumanLoopCallback):
    """模拟的回调实现"""

    def __init__(self):
        self.update_called = False
        self.timeout_called = False
        self.error_called = False
        self.last_provider = None
        self.last_result = None
        self.last_error = None

    async def async_on_humanloop_request(
        self, provider: HumanLoopProvider, request: HumanLoopRequest
    ) -> None:
        self.update_called = True
        self.last_provider = provider
        self.last_request = request

    async def async_on_humanloop_update(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> None:
        self.update_called = True
        self.last_provider = provider
        self.last_result = result

    async def async_on_humanloop_timeout(
        self,
        provider: HumanLoopProvider,
        result: HumanLoopResult,
    ) -> None:
        self.timeout_called = True
        self.last_provider = provider

    async def async_on_humanloop_error(
        self, provider: HumanLoopProvider, error: Exception
    ) -> None:
        self.error_called = True
        self.last_provider = provider
        self.last_error = error


class TestHumanLoopCallback(IsolatedAsyncioTestCase):
    """测试 HumanLoopCallback 抽象类"""

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
        await callback.async_on_humanloop_update(provider_mock, result)
        self.assertTrue(callback.update_called)
        self.assertEqual(callback.last_provider, provider_mock)
        self.assertEqual(callback.last_result, result)

        # 测试超时回调
        await callback.async_on_humanloop_timeout(provider_mock, result)
        self.assertTrue(callback.timeout_called)
        self.assertEqual(callback.last_provider, provider_mock)

        # 测试错误回调
        error = Exception("Test error")
        await callback.async_on_humanloop_error(provider_mock, error)
        self.assertTrue(callback.error_called)
        self.assertEqual(callback.last_provider, provider_mock)
        self.assertEqual(callback.last_error, error)


# 创建一个模拟的 HumanLoopProvider 实现
class MockHumanLoopProvider:
    """模拟的 HumanLoopProvider 实现"""

    def __init__(self, name="MockProvider"):
        self.name = name
        self.async_request_humanloop_mock = AsyncMock()
        self.request_humanloop_mock = MagicMock()
        self.async_check_request_status_mock = AsyncMock()
        self.check_request_status_mock = MagicMock()
        self.async_check_conversation_status_mock = AsyncMock()
        self.check_conversation_status_mock = MagicMock()
        self.async_cancel_request_mock = AsyncMock()
        self.cancel_request_mock = MagicMock()
        self.async_cancel_conversation_mock = AsyncMock()
        self.cancel_conversation_mock = MagicMock()
        self.async_continue_humanloop_mock = AsyncMock()
        self.continue_humanloop_mock = MagicMock()

    async def async_request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        return await self.async_request_humanloop_mock(
            task_id, conversation_id, loop_type, context, metadata, timeout
        )

    def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        return self.request_humanloop_mock(
            task_id, conversation_id, loop_type, context, metadata, timeout
        )

    async def async_check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        return await self.async_check_request_status_mock(conversation_id, request_id)

    def check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        return self.check_request_status_mock(conversation_id, request_id)

    async def async_check_conversation_status(
        self, conversation_id: str
    ) -> HumanLoopResult:
        return await self.async_check_conversation_status_mock(conversation_id)

    def check_conversation_status(self, conversation_id: str) -> HumanLoopResult:
        return self.check_conversation_status_mock(conversation_id)

    async def async_cancel_request(self, conversation_id: str, request_id: str) -> bool:
        return await self.async_cancel_request_mock(conversation_id, request_id)

    def cancel_request(self, conversation_id: str, request_id: str) -> bool:
        return self.cancel_request_mock(conversation_id, request_id)

    async def async_cancel_conversation(self, conversation_id: str) -> bool:
        return await self.async_cancel_conversation_mock(conversation_id)

    def cancel_conversation(self, conversation_id: str) -> bool:
        return self.cancel_conversation_mock(conversation_id)

    async def async_continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        return await self.async_continue_humanloop_mock(
            conversation_id, context, metadata, timeout
        )

    def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        return self.continue_humanloop_mock(conversation_id, context, metadata, timeout)


class TestHumanLoopProvider(IsolatedAsyncioTestCase):
    """测试 HumanLoopProvider 协议"""

    def test_provider_protocol_compliance(self):
        """测试提供者是否符合协议要求"""
        provider = MockHumanLoopProvider()

        # 验证是否实现了所有必需的属性和方法
        self.assertTrue(hasattr(provider, "name"))
        self.assertTrue(hasattr(provider, "async_request_humanloop"))
        self.assertTrue(hasattr(provider, "request_humanloop"))
        self.assertTrue(hasattr(provider, "async_check_request_status"))
        self.assertTrue(hasattr(provider, "check_request_status"))
        self.assertTrue(hasattr(provider, "async_check_conversation_status"))
        self.assertTrue(hasattr(provider, "check_conversation_status"))
        self.assertTrue(hasattr(provider, "async_cancel_request"))
        self.assertTrue(hasattr(provider, "cancel_request"))
        self.assertTrue(hasattr(provider, "async_cancel_conversation"))
        self.assertTrue(hasattr(provider, "cancel_conversation"))
        self.assertTrue(hasattr(provider, "async_continue_humanloop"))
        self.assertTrue(hasattr(provider, "continue_humanloop"))

        # 验证是否符合 HumanLoopProvider 协议
        # 注意：由于 Protocol 是运行时检查，我们需要确保实现了所有必需的方法
        self.assertTrue(isinstance(provider, HumanLoopProvider))

    @pytest.mark.asyncio(loop_scope="module")
    async def test_async_provider_methods(self):
        """测试异步提供者方法"""
        provider = MockHumanLoopProvider()

        # 设置模拟返回值
        result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )

        provider.async_request_humanloop_mock.return_value = result
        provider.async_check_request_status_mock.return_value = result
        provider.async_check_conversation_status_mock.return_value = result
        provider.async_cancel_request_mock.return_value = True
        provider.async_cancel_conversation_mock.return_value = True
        provider.async_continue_humanloop_mock.return_value = result

        # 测试 async_request_humanloop 方法
        response = await provider.async_request_humanloop(
            "test-task",
            "test-conversation",
            HumanLoopType.APPROVAL,
            {"message": "Please approve"},
        )
        self.assertEqual(response, result)
        provider.async_request_humanloop_mock.assert_called_once()

        # 测试 async_check_request_status 方法
        response = await provider.async_check_request_status(
            "test-conversation", "test-request"
        )
        self.assertEqual(response, result)
        provider.async_check_request_status_mock.assert_called_once_with(
            "test-conversation", "test-request"
        )

        # 测试 async_check_conversation_status 方法
        response = await provider.async_check_conversation_status("test-conversation")
        self.assertEqual(response, result)
        provider.async_check_conversation_status_mock.assert_called_once_with(
            "test-conversation"
        )

        # 测试 async_cancel_request 方法
        response = await provider.async_cancel_request(
            "test-conversation", "test-request"
        )
        self.assertTrue(response)
        provider.async_cancel_request_mock.assert_called_once_with(
            "test-conversation", "test-request"
        )

        # 测试 async_cancel_conversation 方法
        response = await provider.async_cancel_conversation("test-conversation")
        self.assertTrue(response)
        provider.async_cancel_conversation_mock.assert_called_once_with(
            "test-conversation"
        )

        # 测试 async_continue_humanloop 方法
        response = await provider.async_continue_humanloop(
            "test-conversation", {"message": "Additional information"}
        )
        self.assertEqual(response, result)
        provider.async_continue_humanloop_mock.assert_called_once()

    def test_sync_provider_methods(self):
        """测试同步提供者方法"""
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
        response = provider.request_humanloop(
            "test-task",
            "test-conversation",
            HumanLoopType.APPROVAL,
            {"message": "Please approve"},
        )
        self.assertEqual(response, result)
        provider.request_humanloop_mock.assert_called_once()

        # 测试 check_request_status 方法
        response = provider.check_request_status("test-conversation", "test-request")
        self.assertEqual(response, result)
        provider.check_request_status_mock.assert_called_once_with(
            "test-conversation", "test-request"
        )

        # 测试 check_conversation_status 方法
        response = provider.check_conversation_status("test-conversation")
        self.assertEqual(response, result)
        provider.check_conversation_status_mock.assert_called_once_with(
            "test-conversation"
        )

        # 测试 cancel_request 方法
        response = provider.cancel_request("test-conversation", "test-request")
        self.assertTrue(response)
        provider.cancel_request_mock.assert_called_once_with(
            "test-conversation", "test-request"
        )

        # 测试 cancel_conversation 方法
        response = provider.cancel_conversation("test-conversation")
        self.assertTrue(response)
        provider.cancel_conversation_mock.assert_called_once_with("test-conversation")

        # 测试 continue_humanloop 方法
        response = provider.continue_humanloop(
            "test-conversation", {"message": "Additional information"}
        )
        self.assertEqual(response, result)
        provider.continue_humanloop_mock.assert_called_once()
