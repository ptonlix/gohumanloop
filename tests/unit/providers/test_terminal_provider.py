import asyncio
import unittest
import json
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from gohumanloop.providers.terminal_provider import TerminalProvider
from gohumanloop.core.interface import HumanLoopStatus, HumanLoopType, HumanLoopResult


class TestTerminalProviderInit(TestCase):
    """测试 TerminalProvider 类的初始化"""

    def test_init_with_name(self):
        """测试使用名称初始化"""
        provider = TerminalProvider(name="test_terminal_provider")
        self.assertEqual(provider.name, "test_terminal_provider")
        self.assertEqual(provider.config, {})
        self.assertEqual(provider.prompt_template, "{context}")

    def test_init_with_config(self):
        """测试使用配置初始化"""
        config = {"prompt_template": "终端交互: {context}", "other_config": "value"}
        provider = TerminalProvider(name="test_terminal_provider", config=config)
        self.assertEqual(provider.name, "test_terminal_provider")
        self.assertEqual(provider.config, config)
        self.assertEqual(provider.prompt_template, "终端交互: {context}")

    def test_str_representation(self):
        """测试字符串表示"""
        provider = TerminalProvider(name="test_terminal_provider")
        self.assertIn("Terminal Provider", str(provider))
        self.assertIn("conversations=0", str(provider))
        self.assertIn("total_requests=0", str(provider))
        self.assertIn("active_requests=0", str(provider))


class TestTerminalInteraction(IsolatedAsyncioTestCase):
    """测试终端交互功能"""

    async def test_process_terminal_interaction_approval(self):
        """测试处理审批类型的终端交互"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv_1"
        request_id = "test_req_1"
        task_id = "test_task_1"

        # 模拟请求信息
        request_info = {
            "task_id": task_id,
            "loop_type": HumanLoopType.APPROVAL,
            "context": {"message": "请审批此请求", "question": "请审批"},
            "metadata": {},
            "status": HumanLoopStatus.PENDING,
            "created_at": datetime.now().isoformat(),
        }

        # 存储请求信息
        provider._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.APPROVAL,
            request_info["context"],
            request_info["metadata"],
            None,
        )

        # 模拟用户输入
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = "approve"
            mock_loop.return_value.run_in_executor = mock_executor

            # 调用处理函数
            await provider._handle_approval_interaction(
                conversation_id,
                request_id,
                provider._requests[(conversation_id, request_id)],
            )

            # 验证请求状态是否已更新
            updated_request = provider._get_request(conversation_id, request_id)
            self.assertEqual(updated_request["status"], HumanLoopStatus.APPROVED)
            self.assertIn("responded_at", updated_request)
            self.assertEqual(updated_request["responded_by"], "terminal_user")

    async def test_process_terminal_interaction_rejection(self):
        """测试处理拒绝审批的终端交互"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv_2"
        request_id = "test_req_2"
        task_id = "test_task_2"

        # 模拟请求信息
        request_info = {
            "task_id": task_id,
            "loop_type": HumanLoopType.APPROVAL,
            "context": {"message": "请审批此请求", "question": "请审批"},
            "metadata": {},
            "status": HumanLoopStatus.PENDING,
            "created_at": datetime.now().isoformat(),
        }

        # 存储请求信息
        provider._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.APPROVAL,
            request_info["context"],
            request_info["metadata"],
            None,
        )

        # 模拟用户输入 - 先拒绝，然后提供原因
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            # 第一次调用返回 "reject"，第二次调用返回拒绝原因
            mock_executor.side_effect = ["reject", "需要更多信息"]
            mock_loop.return_value.run_in_executor = mock_executor

            # 调用处理函数
            await provider._handle_approval_interaction(
                conversation_id,
                request_id,
                provider._requests[(conversation_id, request_id)],
            )

            # 验证请求状态是否已更新
            updated_request = provider._get_request(conversation_id, request_id)
            self.assertEqual(updated_request["status"], HumanLoopStatus.REJECTED)
            self.assertEqual(updated_request["response"], "需要更多信息")
            self.assertIn("responded_at", updated_request)
            self.assertEqual(updated_request["responded_by"], "terminal_user")

    async def test_process_terminal_interaction_information(self):
        """测试处理信息收集类型的终端交互"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv_3"
        request_id = "test_req_3"
        task_id = "test_task_3"

        # 模拟请求信息
        request_info = {
            "task_id": task_id,
            "loop_type": HumanLoopType.INFORMATION,
            "context": {"message": "请提供信息", "question": "请提供信息"},
            "metadata": {},
            "status": HumanLoopStatus.PENDING,
            "created_at": datetime.now().isoformat(),
        }

        # 存储请求信息
        provider._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.INFORMATION,
            request_info["context"],
            request_info["metadata"],
            None,
        )

        # 模拟用户输入
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = "这是我提供的信息"
            mock_loop.return_value.run_in_executor = mock_executor

            # 调用处理函数
            await provider._handle_information_interaction(
                conversation_id,
                request_id,
                provider._requests[(conversation_id, request_id)],
            )

            # 验证请求状态是否已更新
            updated_request = provider._get_request(conversation_id, request_id)
            self.assertEqual(updated_request["status"], HumanLoopStatus.COMPLETED)
            self.assertEqual(updated_request["response"], "这是我提供的信息")
            self.assertIn("responded_at", updated_request)
            self.assertEqual(updated_request["responded_by"], "terminal_user")

    async def test_process_terminal_interaction_conversation(self):
        """测试处理对话类型的终端交互"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv_4"
        request_id = "test_req_4"
        task_id = "test_task_4"

        # 模拟请求信息
        request_info = {
            "task_id": task_id,
            "loop_type": HumanLoopType.CONVERSATION,
            "context": {"message": "您好，有什么可以帮您的？"},
            "metadata": {},
            "status": HumanLoopStatus.PENDING,
            "created_at": datetime.now().isoformat(),
        }

        # 存储请求信息
        provider._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.CONVERSATION,
            request_info["context"],
            request_info["metadata"],
            None,
        )

        # 模拟用户输入 - 继续对话
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = "我需要帮助解决一个问题"
            mock_loop.return_value.run_in_executor = mock_executor

            # 调用处理函数
            await provider._handle_conversation_interaction(
                conversation_id,
                request_id,
                provider._requests[(conversation_id, request_id)],
            )

            # 验证请求状态是否已更新
            updated_request = provider._get_request(conversation_id, request_id)
            self.assertEqual(updated_request["status"], HumanLoopStatus.INPROGRESS)
            self.assertEqual(updated_request["response"], "我需要帮助解决一个问题")
            self.assertIn("responded_at", updated_request)
            self.assertEqual(updated_request["responded_by"], "terminal_user")

    async def test_process_terminal_interaction_conversation_exit(self):
        """测试处理对话类型的终端交互 - 退出对话"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv_5"
        request_id = "test_req_5"
        task_id = "test_task_5"

        # 模拟请求信息
        request_info = {
            "task_id": task_id,
            "loop_type": HumanLoopType.CONVERSATION,
            "context": {"message": "您好，有什么可以帮您的？"},
            "metadata": {},
            "status": HumanLoopStatus.PENDING,
            "created_at": datetime.now().isoformat(),
        }

        # 存储请求信息
        provider._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.CONVERSATION,
            request_info["context"],
            request_info["metadata"],
            None,
        )

        # 模拟用户输入 - 退出对话
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            mock_executor.return_value = "exit"
            mock_loop.return_value.run_in_executor = mock_executor

            # 调用处理函数
            await provider._handle_conversation_interaction(
                conversation_id,
                request_id,
                provider._requests[(conversation_id, request_id)],
            )

            # 验证请求状态是否已更新
            updated_request = provider._get_request(conversation_id, request_id)
            self.assertEqual(updated_request["status"], HumanLoopStatus.COMPLETED)
            self.assertEqual(updated_request["response"], "exit")
            self.assertIn("responded_at", updated_request)
            self.assertEqual(updated_request["responded_by"], "terminal_user")


class TestHumanLoopRequest(IsolatedAsyncioTestCase):
    """测试请求人机循环功能"""

    async def test_request_humanloop(self):
        """测试请求人机循环"""
        provider = TerminalProvider(name="test_terminal_provider")

        # 模拟 _process_terminal_interaction 方法，避免实际的终端交互
        with patch.object(
            provider, "_process_terminal_interaction", new_callable=AsyncMock
        ) as mock_process:
            # 发起请求
            result = await provider.request_humanloop(
                task_id="test_task",
                conversation_id="test_conv",
                loop_type=HumanLoopType.APPROVAL,
                context={"message": "请审批此请求", "question": "请审批"},
                metadata={"test_key": "test_value"},
                timeout=60,
            )

            # 验证结果
            self.assertEqual(result.conversation_id, "test_conv")
            self.assertIsNotNone(result.request_id)
            self.assertEqual(result.loop_type, HumanLoopType.APPROVAL)
            self.assertEqual(result.status, HumanLoopStatus.PENDING)

            # 验证请求是否已存储
            request_info = provider._get_request("test_conv", result.request_id)
            self.assertIsNotNone(request_info)
            self.assertEqual(request_info["task_id"], "test_task")
            self.assertEqual(request_info["loop_type"], HumanLoopType.APPROVAL)
            self.assertEqual(
                request_info["context"],
                {"message": "请审批此请求", "question": "请审批"},
            )
            self.assertEqual(request_info["metadata"], {"test_key": "test_value"})
            self.assertEqual(request_info["status"], HumanLoopStatus.PENDING)
            self.assertEqual(request_info["timeout"], 60)

            # 验证是否调用了处理函数
            mock_process.assert_called_once_with("test_conv", result.request_id)

    async def test_check_request_status(self):
        """测试检查请求状态"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv"
        request_id = "test_req"
        task_id = "test_task"

        # 存储请求信息
        provider._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.APPROVAL,
            context={"message": "请审批此请求", "question": "请审批"},
            metadata={},
            timeout=None,
        )

        # 更新请求状态
        provider._requests[(conversation_id, request_id)][
            "status"
        ] = HumanLoopStatus.APPROVED
        provider._requests[(conversation_id, request_id)]["response"] = {
            "decision": "approved"
        }
        provider._requests[(conversation_id, request_id)][
            "responded_by"
        ] = "terminal_user"
        provider._requests[(conversation_id, request_id)][
            "responded_at"
        ] = datetime.now().isoformat()

        # 检查请求状态
        result = await provider.check_request_status(conversation_id, request_id)

        # 验证结果
        self.assertEqual(result.conversation_id, conversation_id)
        self.assertEqual(result.request_id, request_id)
        self.assertEqual(result.loop_type, HumanLoopType.APPROVAL)
        self.assertEqual(result.status, HumanLoopStatus.APPROVED)
        self.assertEqual(result.response, {"decision": "approved"})
        self.assertEqual(result.responded_by, "terminal_user")
        self.assertIsNotNone(result.responded_at)

    async def test_check_nonexistent_request_status(self):
        """测试检查不存在的请求状态"""
        provider = TerminalProvider(name="test_terminal_provider")

        # 检查不存在的请求状态
        result = await provider.check_request_status("non_existent", "non_existent")

        # 验证结果
        self.assertEqual(result.conversation_id, "non_existent")
        self.assertEqual(result.request_id, "non_existent")
        self.assertEqual(result.status, HumanLoopStatus.ERROR)
        self.assertIn("not found", result.error)

    async def test_continue_humanloop(self):
        """测试继续人机循环对话"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv"
        request_id = "test_req"
        task_id = "test_task"

        # 存储初始请求信息
        provider._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.CONVERSATION,
            context={"message": "您好，有什么可以帮您的？"},
            metadata={},
            timeout=None,
        )

        # 模拟 _process_terminal_interaction 方法，避免实际的终端交互
        with patch.object(
            provider, "_process_terminal_interaction", new_callable=AsyncMock
        ) as mock_process:
            # 继续对话
            result = await provider.continue_humanloop(
                conversation_id=conversation_id,
                context={"message": "感谢您的回复，还有其他问题吗？"},
                metadata={"test_key": "test_value"},
                timeout=60,
            )

            # 验证结果
            self.assertEqual(result.conversation_id, conversation_id)
            self.assertIsNotNone(result.request_id)
            self.assertNotEqual(result.request_id, request_id)  # 新的请求ID
            self.assertEqual(result.loop_type, HumanLoopType.CONVERSATION)
            self.assertEqual(result.status, HumanLoopStatus.PENDING)

            # 验证新请求是否已存储
            request_info = provider._get_request(conversation_id, result.request_id)
            self.assertIsNotNone(request_info)
            self.assertEqual(request_info["task_id"], task_id)
            self.assertEqual(request_info["loop_type"], HumanLoopType.CONVERSATION)
            self.assertEqual(
                request_info["context"], {"message": "感谢您的回复，还有其他问题吗？"}
            )
            self.assertEqual(request_info["metadata"], {"test_key": "test_value"})
            self.assertEqual(request_info["status"], HumanLoopStatus.PENDING)
            self.assertEqual(request_info["timeout"], 60)

            # 验证是否调用了处理函数
            mock_process.assert_called_once_with(conversation_id, result.request_id)

    async def test_continue_nonexistent_conversation(self):
        """测试继续不存在的对话"""
        provider = TerminalProvider(name="test_terminal_provider")

        # 继续不存在的对话
        result = await provider.continue_humanloop(
            conversation_id="non_existent", context={"message": "继续对话"}
        )

        # 验证结果
        self.assertEqual(result.conversation_id, "non_existent")
        self.assertEqual(result.request_id, "")
        self.assertEqual(result.status, HumanLoopStatus.ERROR)
        self.assertIn("not found", result.error)


class TestTerminalInputProcessing(IsolatedAsyncioTestCase):
    """测试终端输入处理功能"""

    async def test_handle_approval_interaction_invalid_input(self):
        """测试处理无效的审批输入"""
        provider = TerminalProvider(name="test_terminal_provider")
        conversation_id = "test_conv"
        request_id = "test_req"
        task_id = "test_task"

        # 模拟请求信息
        request_info = {
            "task_id": task_id,
            "loop_type": HumanLoopType.APPROVAL,
            "context": {"message": "请审批此请求", "question": "请审批"},
            "metadata": {},
            "status": HumanLoopStatus.PENDING,
            "created_at": datetime.now().isoformat(),
        }

        # 存储请求信息
        provider._store_request(
            conversation_id,
            request_id,
            task_id,
            HumanLoopType.APPROVAL,
            request_info["context"],
            request_info["metadata"],
            None,
        )

        # 模拟用户输入 - 先输入无效值，然后输入有效值
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock()
            # 第一次调用返回无效值，第二次调用返回有效值
            mock_executor.side_effect = ["invalid", "approve"]
            mock_loop.return_value.run_in_executor = mock_executor

            # 模拟 _handle_approval_interaction 方法，以便测试递归调用
            original_method = provider._handle_approval_interaction
            call_count = [0]

            async def mock_handle_approval(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    # 第一次调用，使用原始方法
                    return await original_method(*args, **kwargs)
                else:
                    # 第二次调用，直接更新状态
                    provider._requests[(conversation_id, request_id)][
                        "status"
                    ] = HumanLoopStatus.APPROVED
                    provider._requests[(conversation_id, request_id)]["response"] = ""
                    provider._requests[(conversation_id, request_id)][
                        "responded_by"
                    ] = "terminal_user"
                    provider._requests[(conversation_id, request_id)][
                        "responded_at"
                    ] = datetime.now().isoformat()

            with patch.object(
                provider,
                "_handle_approval_interaction",
                side_effect=mock_handle_approval,
            ):
                # 调用处理函数
                await provider._handle_approval_interaction(
                    conversation_id,
                    request_id,
                    provider._requests[(conversation_id, request_id)],
                )

                # 验证请求状态是否已更新
                updated_request = provider._get_request(conversation_id, request_id)
                self.assertEqual(updated_request["status"], HumanLoopStatus.APPROVED)
                self.assertIn("responded_at", updated_request)
                self.assertEqual(updated_request["responded_by"], "terminal_user")


class TestTerminalOutputFormatting(TestCase):
    """测试终端输出格式化功能"""

    def test_build_prompt_approval(self):
        """测试构建审批类型的提示信息"""
        provider = TerminalProvider(name="test_terminal_provider")
        task_id = "test_task"
        conversation_id = "test_conv"
        request_id = "test_req"
        created_at = datetime.now().isoformat()
        context = {"message": "请审批此请求", "question": "请审批"}
        metadata = {"test_key": "test_value"}

        # 构建提示信息
        prompt = provider.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.APPROVAL,
            created_at=created_at,
            context=context,
            metadata=metadata,
        )

        # 验证提示信息
        self.assertIn("请审批此请求", prompt)
        self.assertIn("请审批", prompt)
        self.assertIn(task_id, prompt)
        self.assertIn(conversation_id, prompt)
        self.assertIn(request_id, prompt)
        self.assertIn("approval", prompt)

    def test_build_prompt_information(self):
        """测试构建信息收集类型的提示信息"""
        provider = TerminalProvider(name="test_terminal_provider")
        task_id = "test_task"
        conversation_id = "test_conv"
        request_id = "test_req"
        created_at = datetime.now().isoformat()
        context = {"message": "请提供信息", "question": "请提供信息"}
        metadata = {"test_key": "test_value"}

        # 构建提示信息
        prompt = provider.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.INFORMATION,
            created_at=created_at,
            context=context,
            metadata=metadata,
        )

        # 验证提示信息
        self.assertIn("请提供信息", prompt)
        self.assertIn(task_id, prompt)
        self.assertIn(conversation_id, prompt)
        self.assertIn(request_id, prompt)
        self.assertIn("information", prompt)

    def test_build_prompt_conversation(self):
        """测试构建对话类型的提示信息"""
        provider = TerminalProvider(name="test_terminal_provider")
        task_id = "test_task"
        conversation_id = "test_conv"
        request_id = "test_req"
        created_at = datetime.now().isoformat()
        context = {"message": "您好，有什么可以帮您的？"}
        metadata = {"test_key": "test_value"}

        # 构建提示信息
        prompt = provider.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            created_at=created_at,
            context=context,
            metadata=metadata,
        )

        # 验证提示信息
        self.assertIn("您好，有什么可以帮您的？", prompt)
        self.assertIn(task_id, prompt)
        self.assertIn(conversation_id, prompt)
        self.assertIn(request_id, prompt)
        self.assertIn("conversation", prompt)

    def test_build_prompt_custom_template(self):
        """测试使用自定义模板构建提示信息"""
        provider = TerminalProvider(name="test_terminal_provider")
        task_id = "test_task"
        conversation_id = "test_conv"
        request_id = "test_req"
        created_at = datetime.now().isoformat()
        context = {"message": "测试消息"}
        metadata = {}

        # 构建提示信息
        prompt = provider.build_prompt(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            created_at=created_at,
            context=context,
            metadata=metadata,
        )

        # 验证提示信息
        self.assertIn("测试消息", prompt)


if __name__ == "__main__":
    unittest.main()
