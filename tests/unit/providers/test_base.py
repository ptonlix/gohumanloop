import asyncio
import uuid
import unittest
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock

from gohumanloop.providers.base import BaseProvider
from gohumanloop.core.interface import HumanLoopStatus, HumanLoopType, HumanLoopResult


class MockBaseProvider(BaseProvider):
    """测试用的 BaseProvider 实现类，重写必要的抽象方法"""

    async def request_humanloop(
        self, task_id, conversation_id, loop_type, context, metadata=None, timeout=None
    ):
        request_id = self._generate_request_id()
        self._store_request(
            conversation_id,
            request_id,
            task_id,
            loop_type,
            context,
            metadata or {},
            timeout,
        )

        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout)

        return HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            status=HumanLoopStatus.PENDING,
        )

    async def check_request_status(self, conversation_id, request_id):
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Request '{request_id}' not found in conversation '{conversation_id}'",
            )

        return HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=request_info["loop_type"],
            status=request_info["status"],
        )

    async def continue_humanloop(
        self, conversation_id, context, metadata=None, timeout=None
    ):
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found",
            )

        task_id = conversation_info["task_id"]
        request_id = self._generate_request_id()

        self._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.CONVERSATION,
            context,
            metadata or {},
            timeout,
        )

        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout)

        return HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.PENDING,
        )


class TestBaseProviderInit(TestCase):
    """测试 BaseProvider 类的初始化"""

    def test_init_with_name(self):
        """测试使用名称初始化"""
        provider = MockBaseProvider(name="test_provider")
        self.assertEqual(provider.name, "test_provider")
        self.assertEqual(provider.config, {})
        self.assertEqual(provider.prompt_template, "{context}")

    def test_init_with_config(self):
        """测试使用配置初始化"""
        config = {"prompt_template": "Custom: {context}", "other_config": "value"}
        provider = MockBaseProvider(name="test_provider", config=config)
        self.assertEqual(provider.name, "test_provider")
        self.assertEqual(provider.config, config)
        self.assertEqual(provider.prompt_template, "Custom: {context}")

    def test_str_representation(self):
        """测试字符串表示"""
        provider = MockBaseProvider(name="test_provider")
        self.assertEqual(
            str(provider), "conversations=0, total_requests=0, active_requests=0)"
        )
        self.assertEqual(
            repr(provider), "conversations=0, total_requests=0, active_requests=0)"
        )


class TestRequestIdGeneration(TestCase):
    """测试请求ID生成功能"""

    def test_generate_request_id(self):
        """测试生成唯一请求ID"""
        provider = MockBaseProvider(name="test_provider")
        request_id = provider._generate_request_id()
        self.assertIsInstance(request_id, str)

        # 验证是否为有效的UUID
        try:
            uuid_obj = uuid.UUID(request_id)
            self.assertEqual(str(uuid_obj), request_id)
        except ValueError:
            self.fail("Generated request ID is not a valid UUID")

    def test_unique_request_ids(self):
        """测试生成的请求ID是唯一的"""
        provider = MockBaseProvider(name="test_provider")
        request_ids = set()

        # 生成多个请求ID并确保它们都是唯一的
        for _ in range(100):
            request_id = provider._generate_request_id()
            self.assertNotIn(request_id, request_ids)
            request_ids.add(request_id)


class TestRequestStorage(TestCase):
    """测试请求存储功能"""

    def test_store_request(self):
        """测试存储请求信息"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {"source": "test"}
        timeout = 60

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 验证请求是否正确存储
        request_key = (conversation_id, request_id)
        self.assertIn(request_key, provider._requests)
        stored_request = provider._requests[request_key]
        self.assertEqual(stored_request["task_id"], task_id)
        self.assertEqual(stored_request["loop_type"], loop_type)
        self.assertEqual(stored_request["context"], context)
        self.assertEqual(stored_request["metadata"], metadata)
        self.assertEqual(stored_request["status"], HumanLoopStatus.PENDING)
        self.assertEqual(stored_request["timeout"], timeout)

        # 验证对话信息是否正确存储
        self.assertIn(conversation_id, provider._conversations)
        self.assertEqual(provider._conversations[conversation_id]["task_id"], task_id)
        self.assertEqual(
            provider._conversations[conversation_id]["latest_request_id"], request_id
        )

        # 验证对话请求列表是否正确更新
        self.assertIn(request_id, provider._conversation_requests[conversation_id])

    def test_get_request(self):
        """测试获取请求信息"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {"source": "test"}
        timeout = 60

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 获取并验证请求信息
        request_info = provider._get_request(conversation_id, request_id)
        self.assertIsNotNone(request_info)
        self.assertEqual(request_info["task_id"], task_id)
        self.assertEqual(request_info["loop_type"], loop_type)

        # 测试获取不存在的请求
        self.assertIsNone(provider._get_request("non_existent", "non_existent"))

    def test_get_conversation(self):
        """测试获取对话信息"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = None

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 获取并验证对话信息
        conversation_info = provider._get_conversation(conversation_id)
        self.assertIsNotNone(conversation_info)
        self.assertEqual(conversation_info["task_id"], task_id)
        self.assertEqual(conversation_info["latest_request_id"], request_id)

        # 测试获取不存在的对话
        self.assertIsNone(provider._get_conversation("non_existent"))

    def test_get_conversation_requests(self):
        """测试获取对话中的所有请求ID"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_ids = ["req_1", "req_2", "req_3"]
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = None

        # 存储多个请求
        for request_id in request_ids:
            provider._store_request(
                conversation_id,
                request_id,
                task_id,
                loop_type,
                context,
                metadata,
                timeout,
            )

        # 获取并验证对话中的请求ID列表
        conversation_requests = provider._get_conversation_requests(conversation_id)
        self.assertEqual(set(conversation_requests), set(request_ids))

        # 测试获取不存在的对话的请求ID列表
        self.assertEqual(provider._get_conversation_requests("non_existent"), [])


class TestRequestStatusUpdate(TestCase):
    """测试请求状态更新功能"""

    def test_update_request_status_error(self):
        """测试更新请求状态为错误"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = None

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 更新请求状态为错误
        error_message = "Test error"
        provider._update_request_status_error(
            conversation_id, request_id, error_message
        )

        # 验证状态是否正确更新
        request_info = provider._get_request(conversation_id, request_id)
        self.assertEqual(request_info["status"], HumanLoopStatus.ERROR)
        self.assertEqual(request_info["error"], error_message)

    def test_update_nonexistent_request(self):
        """测试更新不存在的请求状态"""
        provider = MockBaseProvider(name="test_provider")

        # 更新不存在的请求状态不应引发异常
        provider._update_request_status_error("non_existent", "non_existent", "Error")

        # 验证不存在的请求没有被创建
        self.assertIsNone(provider._get_request("non_existent", "non_existent"))


class TestTimeoutTask(IsolatedAsyncioTestCase):
    """测试超时任务创建功能"""

    async def test_create_timeout_task(self):
        """测试创建超时任务"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = 0.1  # 使用较短的超时时间进行测试

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 创建超时任务
        provider._create_timeout_task(conversation_id, request_id, timeout)

        # 验证超时任务是否已创建
        self.assertIn((conversation_id, request_id), provider._timeout_tasks)

        # 等待超时任务执行完成
        await asyncio.sleep(0.2)

        # 验证请求状态是否已更新为超时
        request_info = provider._get_request(conversation_id, request_id)
        self.assertEqual(request_info["status"], HumanLoopStatus.EXPIRED)
        self.assertEqual(request_info["error"], "Request timed out")

    async def test_timeout_task_with_inprogress_status(self):
        """测试进行中状态的请求的超时任务行为"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = 0.1  # 使用较短的超时时间进行测试

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 将请求状态设置为进行中
        provider._requests[(conversation_id, request_id)][
            "status"
        ] = HumanLoopStatus.INPROGRESS

        provider._create_timeout_task(conversation_id, request_id, timeout)

        # 取消这个模拟任务
        provider._timeout_tasks[(conversation_id, request_id)].cancel()

        # 验证进行中状态的请求不会被标记为超时
        request_info = provider._get_request(conversation_id, request_id)
        self.assertEqual(request_info["status"], HumanLoopStatus.INPROGRESS)
        self.assertNotIn("error", request_info)


class TestCancelRequest(IsolatedAsyncioTestCase):
    """测试取消请求功能"""

    async def test_cancel_request(self):
        """测试取消请求"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_id = "req_1"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = 60

        provider._store_request(
            conversation_id, request_id, task_id, loop_type, context, metadata, timeout
        )

        # 创建超时任务
        mock_task = MagicMock()
        provider._timeout_tasks[(conversation_id, request_id)] = mock_task

        # 取消请求
        result = await provider.cancel_request(conversation_id, request_id)

        # 验证取消结果
        self.assertTrue(result)

        # 验证请求状态是否已更新为取消
        request_info = provider._get_request(conversation_id, request_id)
        self.assertEqual(request_info["status"], HumanLoopStatus.CANCELLED)

        # 验证超时任务是否已取消
        mock_task.cancel.assert_called_once()
        self.assertNotIn((conversation_id, request_id), provider._timeout_tasks)

    async def test_cancel_nonexistent_request(self):
        """测试取消不存在的请求"""
        provider = MockBaseProvider(name="test_provider")

        # 取消不存在的请求
        result = await provider.cancel_request("non_existent", "non_existent")

        # 验证取消结果
        self.assertFalse(result)


class TestCancelConversation(IsolatedAsyncioTestCase):
    """测试取消对话功能"""

    async def test_cancel_conversation(self):
        """测试取消整个对话"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        request_ids = ["req_1", "req_2", "req_3"]
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = 60

        # 存储多个请求
        for request_id in request_ids:
            provider._store_request(
                conversation_id,
                request_id,
                task_id,
                loop_type,
                context,
                metadata,
                timeout,
            )

            # 创建超时任务
            mock_task = MagicMock()
            provider._timeout_tasks[(conversation_id, request_id)] = mock_task

        # 取消对话
        result = await provider.cancel_conversation(conversation_id)

        # 验证取消结果
        self.assertTrue(result)

        # 验证所有请求状态是否已更新为取消
        for request_id in request_ids:
            request_info = provider._get_request(conversation_id, request_id)
            self.assertEqual(request_info["status"], HumanLoopStatus.CANCELLED)

            # 验证超时任务是否已取消
            mock_task = provider._timeout_tasks.get((conversation_id, request_id))
            if mock_task:
                mock_task.cancel.assert_called_once()
            self.assertNotIn((conversation_id, request_id), provider._timeout_tasks)

    async def test_cancel_nonexistent_conversation(self):
        """测试取消不存在的对话"""
        provider = MockBaseProvider(name="test_provider")

        # 取消不存在的对话
        result = await provider.cancel_conversation("non_existent")

        # 验证取消结果
        self.assertFalse(result)

    async def test_cancel_conversation_with_completed_requests(self):
        """测试取消包含已完成请求的对话"""
        provider = MockBaseProvider(name="test_provider")
        conversation_id = "conv_1"
        pending_request_id = "req_pending"
        completed_request_id = "req_completed"
        task_id = "task_1"
        loop_type = HumanLoopType.CONVERSATION
        context = {"message": "Hello"}
        metadata = {}
        timeout = 60

        # 存储一个待处理请求和一个已完成请求
        provider._store_request(
            conversation_id,
            pending_request_id,
            task_id,
            loop_type,
            context,
            metadata,
            timeout,
        )
        provider._store_request(
            conversation_id,
            completed_request_id,
            task_id,
            loop_type,
            context,
            metadata,
            timeout,
        )

        # 将一个请求标记为已完成
        provider._requests[(conversation_id, completed_request_id)][
            "status"
        ] = HumanLoopStatus.COMPLETED

        # 为待处理请求创建超时任务
        mock_task = MagicMock()
        provider._timeout_tasks[(conversation_id, pending_request_id)] = mock_task

        # 取消对话
        result = await provider.cancel_conversation(conversation_id)

        # 验证取消结果
        self.assertTrue(result)

        # 验证待处理请求状态是否已更新为取消
        pending_request_info = provider._get_request(
            conversation_id, pending_request_id
        )
        self.assertEqual(pending_request_info["status"], HumanLoopStatus.CANCELLED)

        # 验证已完成请求状态是否保持不变
        completed_request_info = provider._get_request(
            conversation_id, completed_request_id
        )
        self.assertEqual(completed_request_info["status"], HumanLoopStatus.COMPLETED)

        # 验证待处理请求的超时任务是否已取消
        mock_task.cancel.assert_called_once()
        self.assertNotIn((conversation_id, pending_request_id), provider._timeout_tasks)
