import unittest
import pytest
import asyncio
import time
import os
from unittest.mock import AsyncMock, MagicMock, patch, call
from unittest import IsolatedAsyncioTestCase
from typing import Dict, Any, Optional, List, Union

from gohumanloop.core.interface import (
    HumanLoopType,
    HumanLoopStatus,
    HumanLoopResult,
    HumanLoopCallback,
    HumanLoopProvider,
)
from gohumanloop.manager.ghl_manager import GoHumanLoopManager
from gohumanloop.providers.ghl_provider import GoHumanLoopProvider
from gohumanloop.models.glh_model import GoHumanLoopConfig


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


class MockCallbackImplementation:
    """测试回调接口的实现类"""

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


class TestGoHumanLoopManager(IsolatedAsyncioTestCase):
    """测试 GoHumanLoopManager 类"""

    def setUp(self):
        """测试前的准备工作"""
        # 设置环境变量
        os.environ["GOHUMANLOOP_API_KEY"] = "test-api-key"
        os.environ["GOHUMANLOOP_API_BASE_URL"] = "https://test.gohumanloop.com"

        # 创建模拟对象
        self.mock_provider = MockHumanLoopProvider(name="MockProvider")

        # 模拟 GoHumanLoopProvider
        self.patcher = patch("gohumanloop.manager.ghl_manager.GoHumanLoopProvider")
        self.mock_ghl_provider_class = self.patcher.start()
        self.mock_ghl_provider = self.mock_ghl_provider_class.return_value
        self.mock_ghl_provider.name = "GoHumanLoop"

        # 设置模拟返回值
        self.result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.PENDING,
        )

        # 修复：将 check_request_status 设置为 AsyncMock
        self.mock_ghl_provider.check_request_status = AsyncMock(
            return_value=self.result
        )
        self.mock_ghl_provider.check_conversation_status = AsyncMock(
            return_value=self.result
        )
        self.mock_ghl_provider.cancel_request = AsyncMock(return_value=True)
        self.mock_ghl_provider.cancel_conversation = AsyncMock(return_value=True)
        self.mock_ghl_provider.continue_humanloop = AsyncMock(return_value=self.result)
        self.mock_ghl_provider.request_humanloop = AsyncMock(return_value=self.result)

        # 模拟 aiohttp.ClientSession
        self.session_patcher = patch("aiohttp.ClientSession")
        self.mock_session_class = self.session_patcher.start()
        self.mock_session = self.mock_session_class.return_value
        self.mock_response = AsyncMock()
        self.mock_response.status = 200
        self.mock_response.ok = True
        self.mock_response.json.return_value = {"success": True}
        self.mock_session.post.return_value.__aenter__.return_value = self.mock_response

    def tearDown(self):
        """测试后的清理工作"""
        self.patcher.stop()
        self.session_patcher.stop()

        # 清理环境变量
        if "GOHUMANLOOP_API_KEY" in os.environ:
            del os.environ["GOHUMANLOOP_API_KEY"]
        if "GOHUMANLOOP_API_BASE_URL" in os.environ:
            del os.environ["GOHUMANLOOP_API_BASE_URL"]

    def test_initialization(self):
        """测试 GoHumanLoopManager 类的初始化"""
        # 测试默认初始化
        with patch("asyncio.get_event_loop") as mock_get_event_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = False
            mock_get_event_loop.return_value = mock_loop

            with patch.object(GoHumanLoopManager, "start_sync_task") as mock_start_sync:
                manager = GoHumanLoopManager()

                # 验证 GoHumanLoopProvider 是否被正确创建
                self.mock_ghl_provider_class.assert_called_once()

                # 验证默认提供者是否正确设置
                self.assertEqual(manager.default_provider_id, "GoHumanLoop")

                # 验证同步任务是否启动
                mock_start_sync.assert_called_once()

        # 测试带参数初始化
        with patch("asyncio.get_event_loop") as mock_get_event_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = False
            mock_get_event_loop.return_value = mock_loop

            with patch.object(GoHumanLoopManager, "start_sync_task") as mock_start_sync:
                additional_provider = MockHumanLoopProvider(name="AdditionalProvider")
                manager = GoHumanLoopManager(
                    request_timeout=30,
                    poll_interval=10,
                    max_retries=5,
                    sync_interval=120,
                    additional_providers=[additional_provider],
                    auto_start_sync=True,
                    config={"custom_param": "value"},
                )

                # 验证 GoHumanLoopProvider 是否被正确创建并传入参数
                self.mock_ghl_provider_class.assert_called_with(
                    name="GoHumanLoop",
                    request_timeout=30,
                    poll_interval=10,
                    max_retries=5,
                    config={"custom_param": "value"},
                )

                # 验证额外提供者是否被添加
                self.assertEqual(len(manager.providers), 2)

                # 验证同步间隔是否正确设置
                self.assertEqual(manager.sync_interval, 120)

                # 验证同步任务是否启动
                mock_start_sync.assert_called_once()

        # 测试禁用自动同步
        with patch("asyncio.get_event_loop") as mock_get_event_loop:
            mock_loop = MagicMock()
            mock_loop.is_running.return_value = False
            mock_get_event_loop.return_value = mock_loop

            with patch.object(GoHumanLoopManager, "start_sync_task") as mock_start_sync:
                manager = GoHumanLoopManager(auto_start_sync=False)

                # 验证同步任务是否未启动
                mock_start_sync.assert_not_called()

    @pytest.mark.asyncio(loop_scope="module")
    async def test_get_ghl_provider(self):
        """测试获取 GoHumanLoop 提供者实例"""
        manager = GoHumanLoopManager(auto_start_sync=False)

        # 模拟 get_provider 方法
        with patch.object(
            manager, "get_provider", return_value=self.mock_ghl_provider
        ) as mock_get_provider:
            provider = await manager.get_ghl_provider()

            # 验证是否调用了 get_provider 方法
            mock_get_provider.assert_called_once_with("GoHumanLoop")

            # 验证返回的提供者是否正确
            self.assertEqual(provider, self.mock_ghl_provider)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_async_data_to_platform(self):
        """测试数据同步功能"""
        # 创建管理器并禁用自动同步
        manager = GoHumanLoopManager(auto_start_sync=False)

        # 模拟任务和对话数据
        manager._task_conversations = {"test-task": ["test-conversation"]}
        manager._conversation_requests = {"test-conversation": ["test-request"]}
        manager._conversation_provider = {"test-conversation": "GoHumanLoop"}

        # 模拟 _asend_task_data_to_platform 方法
        with patch.object(manager, "_asend_task_data_to_platform") as mock_send:
            # 执行数据同步
            await manager.async_data_to_platform()

            mock_send.assert_called_once()

    @pytest.mark.asyncio(loop_scope="module")
    async def test_cancel_conversation(self):
        """测试取消对话功能"""
        # 创建管理器并禁用自动同步
        manager = GoHumanLoopManager(auto_start_sync=False)

        # 模拟对话数据
        manager._conversation_provider = {"test-conversation": "GoHumanLoop"}
        manager._conversation_requests = {"test-conversation": ["test-request"]}

        # 模拟父类的 cancel_conversation 方法
        with patch(
            "gohumanloop.core.manager.DefaultHumanLoopManager.cancel_conversation",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_cancel:
            # 执行取消对话
            result = await manager.cancel_conversation("test-conversation")

            # 验证是否调用了父类方法
            mock_cancel.assert_called_once_with("test-conversation", "GoHumanLoop")

            # 验证是否保存了取消信息
            self.assertIn("test-conversation", manager._cancelled_conversations)
            self.assertEqual(
                manager._cancelled_conversations["test-conversation"]["provider_id"],
                "GoHumanLoop",
            )
            self.assertEqual(
                manager._cancelled_conversations["test-conversation"]["request_ids"],
                ["test-request"],
            )

            # 验证返回值
            self.assertTrue(result)

    @pytest.mark.asyncio(loop_scope="module")
    async def test_check_request_status(self):
        """测试检查请求状态功能"""
        # 创建管理器并禁用自动同步
        manager = GoHumanLoopManager(auto_start_sync=False)

        # 模拟对话数据
        manager._conversation_provider = {"test-conversation": "GoHumanLoop"}
        # 确保 providers 字典中有正确的提供者
        manager.providers = {"GoHumanLoop": self.mock_ghl_provider}

        # 设置请求状态为已批准
        approved_result = HumanLoopResult(
            conversation_id="test-conversation",
            request_id="test-request",
            loop_type=HumanLoopType.APPROVAL,
            status=HumanLoopStatus.APPROVED,
        )

        # 正确设置 check_request_status 方法的返回值
        self.mock_ghl_provider.check_request_status = AsyncMock(
            return_value=approved_result
        )

        # 模拟 async_data_to_platform 方法
        with patch.object(manager, "async_data_to_platform") as mock_sync:
            # 模拟 _trigger_update_callback 方法
            with patch.object(manager, "_trigger_update_callback") as mock_trigger:
                # 添加回调
                manager._callbacks = {
                    ("test-conversation", "test-request"): MagicMock()
                }

                # 执行检查请求状态
                result = await manager.check_request_status(
                    "test-conversation", "test-request"
                )

                # 验证是否调用了提供者的方法
                self.mock_ghl_provider.check_request_status.assert_called_once_with(
                    "test-conversation", "test-request"
                )

                # 验证是否同步了数据
                mock_sync.assert_called_once()

                # 验证是否触发了回调
                mock_trigger.assert_called_once()

                # 验证返回值
                self.assertEqual(result, approved_result)

    def test_shutdown(self):
        """测试关闭管理器功能"""
        # 创建管理器并禁用自动同步
        manager = GoHumanLoopManager(auto_start_sync=False)

        # 模拟同步线程
        manager._sync_thread = MagicMock()
        manager._sync_thread.is_alive.return_value = True

        # 模拟 sync_data_to_platform 方法
        with patch.object(manager, "sync_data_to_platform") as mock_sync:
            # 模拟 print 函数
            with patch("builtins.print") as mock_print:
                # 执行关闭
                manager.shutdown()

                # 验证是否设置了停止事件
                self.assertTrue(manager._sync_thread_stop_event.is_set())

                # 验证是否等待线程结束
                manager._sync_thread.join.assert_called_once_with(timeout=5)

                # 验证是否同步了数据
                mock_sync.assert_called_once()

                # 验证是否打印了完成消息
                mock_print.assert_called_with("最终同步数据同步完成")


if __name__ == "__main__":
    unittest.main()
