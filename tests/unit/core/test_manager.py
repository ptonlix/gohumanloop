import unittest
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from unittest import IsolatedAsyncioTestCase
from typing import Dict, Any, Optional, List, Union, Set

from gohumanloop.core.interface import (
    HumanLoopType,
    HumanLoopStatus,
    HumanLoopResult,
    HumanLoopCallback,
    HumanLoopProvider,
    HumanLoopRequest
)
from gohumanloop.core.manager import DefaultHumanLoopManager


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
        timeout: Optional[int] = None
    ) -> HumanLoopResult:
        return await self.request_humanloop_mock(
            task_id, conversation_id, loop_type, context, metadata, timeout
        )
    
    async def check_request_status(
        self,
        conversation_id: str,
        request_id: str
    ) -> HumanLoopResult:
        return await self.check_request_status_mock(conversation_id, request_id)
    
    async def check_conversation_status(
        self,
        conversation_id: str
    ) -> HumanLoopResult:
        return await self.check_conversation_status_mock(conversation_id)
    
    async def cancel_request(
        self,
        conversation_id: str,
        request_id: str
    ) -> bool:
        return await self.cancel_request_mock(conversation_id, request_id)
    
    async def cancel_conversation(
        self,
        conversation_id: str
    ) -> bool:
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


class TestDefaultHumanLoopManager(IsolatedAsyncioTestCase):
    """测试 DefaultHumanLoopManager 类"""
    
    def setUp(self):
        """测试前的准备工作"""
        self.provider = MockHumanLoopProvider()
        self.manager = DefaultHumanLoopManager(self.provider)
        self.callback = MockCallbackImplementation()
        
        # 设置模拟返回值
        self.result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING
        )
        self.provider.request_humanloop_mock.return_value = self.result
        self.provider.check_request_status_mock.return_value = self.result
        self.provider.check_conversation_status_mock.return_value = self.result
        self.provider.cancel_request_mock.return_value = True
        self.provider.cancel_conversation_mock.return_value = True
        self.provider.continue_humanloop_mock.return_value = self.result
    
    def test_initialization(self):
        """测试 DefaultHumanLoopManager 类的初始化"""
        # 测试空初始化
        manager = DefaultHumanLoopManager()
        self.assertEqual(len(manager.providers), 0)
        self.assertIsNone(manager.default_provider_id)
        
        # 测试单个提供者初始化
        provider = MockHumanLoopProvider(name="SingleProvider")
        manager = DefaultHumanLoopManager(provider)
        self.assertEqual(len(manager.providers), 1)
        self.assertEqual(manager.default_provider_id, "SingleProvider")
        self.assertIn("SingleProvider", manager.providers)
        
        # 测试多个提供者初始化
        provider1 = MockHumanLoopProvider(name="Provider1")
        provider2 = MockHumanLoopProvider(name="Provider2")
        manager = DefaultHumanLoopManager([provider1, provider2])
        self.assertEqual(len(manager.providers), 2)
        self.assertEqual(manager.default_provider_id, "Provider1")
        self.assertIn("Provider1", manager.providers)
        self.assertIn("Provider2", manager.providers)
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_register_provider(self):
        """测试提供者注册功能"""
        manager = DefaultHumanLoopManager()
        
        # 测试注册提供者并指定ID
        provider1 = MockHumanLoopProvider(name="Provider1")
        provider_id1 = await manager.register_provider(provider1, "custom-id")
        self.assertEqual(provider_id1, "custom-id")
        self.assertEqual(manager.default_provider_id, "custom-id")
        self.assertIn("custom-id", manager.providers)
        
        # 测试注册提供者但不指定ID
        provider2 = MockHumanLoopProvider(name="Provider2")
        provider_id2 = await manager.register_provider(provider2)
        self.assertIn(provider_id2, manager.providers)
        self.assertEqual(manager.default_provider_id, "custom-id")  # 默认提供者不变
        
        # 验证提供者数量
        self.assertEqual(len(manager.providers), 2)
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_request_humanloop(self):
        """测试请求人机循环功能"""
        # 测试非阻塞模式
        request_id = await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            callback=self.callback,
            metadata={"priority": "high"},
            timeout=60,
            blocking=False
        )
        
        self.assertEqual(request_id, "test-request")
        self.provider.request_humanloop_mock.assert_called_once()
        
        result2 = HumanLoopResult(
            conversation_id="test-conversation2",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED
        )
        self.provider.check_request_status_mock.return_value = result2

        # 测试阻塞模式
        result = await self.manager.request_humanloop(
            task_id="test-task2",
            conversation_id="test-conversation2",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            blocking=True
        )
        
        self.assertEqual(result, result2)

        self.provider.check_request_status_mock.return_value = self.result
        
        # 测试使用指定的提供者
        provider2 = MockHumanLoopProvider(name="Provider2")
        provider2.request_humanloop_mock.return_value = self.result
        await self.manager.register_provider(provider2, "provider2")
        
        await self.manager.request_humanloop(
            task_id="test-task3",
            conversation_id="test-conversation3",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            provider_id="provider2"
        )
        
        provider2.request_humanloop_mock.assert_called_once()
        
        # 测试提供者不存在的情况
        with self.assertRaises(ValueError):
            await self.manager.request_humanloop(
                task_id="test-task4",
                conversation_id="test-conversation4",
                loop_type=HumanLoopType.APPROVAL,
                context={"message": "Please approve"},
                provider_id="non-existent-provider"
            )
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_continue_humanloop(self):
        """测试继续人机循环功能"""
        # 先创建一个对话
        await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"}
        )
        
        # 测试继续对话
        request_id = await self.manager.continue_humanloop(
            conversation_id="test-conversation",
            context={"message": "Additional information"},
            callback=self.callback,
            metadata={"priority": "high"},
            timeout=60,
            blocking=False
        )
        
        self.assertEqual(request_id, "test-request")
        self.provider.continue_humanloop_mock.assert_called_once()
        
        result2 = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED
        )
        self.provider.check_request_status_mock.return_value = result2
        # 测试阻塞模式
        result = await self.manager.continue_humanloop(
            conversation_id="test-conversation",
            context={"message": "More information"},
            blocking=True
        )
        
        self.assertEqual(result, result2)

        self.provider.check_request_status_mock.return_value = self.result

        # 测试使用不同的提供者继续对话（应该失败）
        provider2 = MockHumanLoopProvider(name="Provider2")
        await self.manager.register_provider(provider2, "provider2")
        
        with self.assertRaises(ValueError):
            await self.manager.continue_humanloop(
                conversation_id="test-conversation",
                context={"message": "More information"},
                provider_id="provider2"
            )
        
        # 测试继续不存在的对话
        await self.manager.continue_humanloop(
            conversation_id="new-conversation",
            context={"message": "New conversation"},
            provider_id="MockProvider"
        )
        
        # 测试提供者不存在的情况
        with self.assertRaises(ValueError):
            await self.manager.continue_humanloop(
                conversation_id="another-conversation",
                context={"message": "Another conversation"},
                provider_id="non-existent-provider"
            )
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_check_request_status(self):
        """测试检查请求状态功能"""
        # 先创建一个请求
        await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"}
        )
        
        # 测试检查请求状态
        result = await self.manager.check_request_status(
            conversation_id="test-conversation",
            request_id="test-request"
        )
        
        self.assertEqual(result, self.result)
        self.provider.check_request_status_mock.assert_called_once_with("test-conversation", "test-request")
        
        # 测试使用指定的提供者
        provider2 = MockHumanLoopProvider(name="Provider2")
        provider2.check_request_status_mock.return_value = self.result
        await self.manager.register_provider(provider2, "provider2")
        
        await self.manager.check_request_status(
            conversation_id="test-conversation",
            request_id="test-request",
            provider_id="provider2"
        )
        
        provider2.check_request_status_mock.assert_called_once_with("test-conversation", "test-request")
        
        # 测试提供者不存在的情况
        with self.assertRaises(ValueError):
            await self.manager.check_request_status(
                conversation_id="test-conversation",
                request_id="test-request",
                provider_id="non-existent-provider"
            )
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_check_conversation_status(self):
        """测试检查对话状态功能"""
        # 先创建一个对话
        await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"}
        )
        
        # 测试检查对话状态
        result = await self.manager.check_conversation_status(
            conversation_id="test-conversation"
        )
        
        self.assertEqual(result, self.result)
        self.provider.check_conversation_status_mock.assert_called_once_with("test-conversation")
        
        # 测试使用指定的提供者
        provider2 = MockHumanLoopProvider(name="Provider2")
        provider2.check_conversation_status_mock.return_value = self.result
        await self.manager.register_provider(provider2, "provider2")
        
        await self.manager.check_conversation_status(
            conversation_id="test-conversation",
            provider_id="provider2"
        )
        
        provider2.check_conversation_status_mock.assert_called_once_with("test-conversation")
        
        # 测试提供者不存在的情况
        with self.assertRaises(ValueError):
            await self.manager.check_conversation_status(
                conversation_id="test-conversation",
                provider_id="non-existent-provider"
            )
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_cancel_request(self):
        """测试取消请求功能"""
        # 先创建一个请求
        await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"}
        )
        
        # 测试取消请求
        result = await self.manager.cancel_request(
            conversation_id="test-conversation",
            request_id="test-request"
        )
        
        self.assertTrue(result)
        self.provider.cancel_request_mock.assert_called_once_with("test-conversation", "test-request")
        
        # 测试使用指定的提供者
        provider2 = MockHumanLoopProvider(name="Provider2")
        provider2.cancel_request_mock.return_value = True
        await self.manager.register_provider(provider2, "provider2")
        
        await self.manager.cancel_request(
            conversation_id="test-conversation",
            request_id="test-request",
            provider_id="provider2"
        )
        
        provider2.cancel_request_mock.assert_called_once_with("test-conversation", "test-request")
        
        # 测试提供者不存在的情况
        with self.assertRaises(ValueError):
            await self.manager.cancel_request(
                conversation_id="test-conversation",
                request_id="test-request",
                provider_id="non-existent-provider"
            )
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_cancel_conversation(self):
        """测试取消对话功能"""
        # 先创建一个对话
        await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"}
        )
        
        # 测试取消对话
        result = await self.manager.cancel_conversation(
            conversation_id="test-conversation"
        )
        
        self.assertTrue(result)
        self.provider.cancel_conversation_mock.assert_called_once_with("test-conversation")
        
        # 测试使用指定的提供者
        provider2 = MockHumanLoopProvider(name="Provider2")
        provider2.cancel_conversation_mock.return_value = True
        await self.manager.register_provider(provider2, "provider2")
        
        await self.manager.cancel_conversation(
            conversation_id="test-conversation",
            provider_id="provider2"
        )
        
        provider2.cancel_conversation_mock.assert_called_once_with("test-conversation")
        
        # 测试提供者不存在的情况
        with self.assertRaises(ValueError):
            await self.manager.cancel_conversation(
                conversation_id="test-conversation",
                provider_id="non-existent-provider"
            )
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_timeout_handling(self):
        """测试超时处理功能"""
        # 模拟超时处理
        with patch('asyncio.create_task') as mock_create_task:
            # 创建一个请求并设置超时
            await self.manager.request_humanloop(
                task_id="test-task",
                conversation_id="test-conversation",
                loop_type=HumanLoopType.APPROVAL,
                context={"message": "Please approve"},
                callback=self.callback,
                timeout=5
            )
            
            # 验证是否创建了超时任务
            mock_create_task.assert_called_once()
            
            # 手动触发超时处理函数
            timeout_handler = mock_create_task.call_args[0][0]
            await timeout_handler
            
            # 验证回调是否被调用
            self.assertTrue(self.callback.timeout_called)
            self.assertEqual(self.callback.last_provider.name, "MockProvider")
    
    @pytest.mark.asyncio(loop_scope="module")
    async def test_callback_handling(self):
        """测试回调处理功能"""
        # 创建一个请求并设置回调
        await self.manager.request_humanloop(
            task_id="test-task",
            conversation_id="test-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            callback=self.callback
        )
        
        # 模拟状态更新
        updated_result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED
        )
        self.provider.check_request_status_mock.return_value = updated_result
        
        # 检查状态并触发回调
        result = await self.manager.check_request_status(
            conversation_id="test-conversation",
            request_id="test-request"
        )
        
        # 验证回调是否被调用
        self.assertTrue(self.callback.update_called)
        self.assertEqual(self.callback.last_provider.name, "MockProvider")
        self.assertEqual(self.callback.last_result, updated_result)
        
        # 测试错误回调
        error_provider = MockHumanLoopProvider(name="ErrorProvider")
        error_provider.check_request_status_mock.side_effect = Exception("Test error")
        await self.manager.register_provider(error_provider, "error-provider")
        
        # 重置回调状态
        self.callback.error_called = False
        self.callback.last_error = None
        
        # 创建一个新请求
        error_result = HumanLoopResult(
            conversation_id="error-conversation",
            request_id="error-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING
        )
        error_provider.request_humanloop_mock.return_value = error_result
        
        await self.manager.request_humanloop(
            task_id="error-task",
            conversation_id="error-conversation",
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "Please approve"},
            callback=self.callback,
            provider_id="error-provider"
        )
        
        # 触发错误
        with self.assertRaises(Exception):
            await self.manager.check_request_status(
                conversation_id="error-conversation",
                request_id="error-request",
                provider_id="error-provider"
            )
        
        # 验证错误回调是否被调用
        self.assertTrue(self.callback.error_called)
        self.assertEqual(self.callback.last_provider.name, "ErrorProvider")
        self.assertIsNotNone(self.callback.last_error)


if __name__ == "__main__":
    unittest.main()