from typing import Dict, Any, Optional, List, Type
from types import TracebackType
import os
import asyncio
import aiohttp
import time
import threading
from datetime import datetime

from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.ghl_provider import GoHumanLoopProvider
from gohumanloop.core.interface import (
    HumanLoopProvider,
    HumanLoopStatus,
    HumanLoopResult,
)
from gohumanloop.utils import get_secret_from_env
from gohumanloop.models.glh_model import GoHumanLoopConfig


class GoHumanLoopManager(DefaultHumanLoopManager):
    """
    GoHumanLoop 官方平台的人机交互管理器

    这个管理器专门使用 GoHumanLoopProvider 作为提供者，用于将交互过程数据传输到 GoHumanLoop 平台。
    它是 DefaultHumanLoopManager 的一个特殊实现，简化了与 GoHumanLoop 平台的集成。

    主要职责:
    1. 管理整个人机交互任务
    2. 将交互任务数据统一传输到 GoHumanLoop 平台
    """

    def __init__(
        self,
        request_timeout: int = 60,
        poll_interval: int = 5,
        max_retries: int = 3,
        sync_interval: int = 60,  # 数据同步间隔（秒）
        additional_providers: Optional[List[HumanLoopProvider]] = None,
        auto_start_sync: bool = True,  # 是否自动启动数据同步任务
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化 GoHumanLoop 管理器

        Args:
            request_timeout: API 请求超时时间（秒），默认60秒
            poll_interval: 轮询检查请求状态的时间间隔（秒），默认5秒
            max_retries: API 请求失败时的最大重试次数，默认3次
            sync_interval: 数据同步到平台的时间间隔（秒），默认60秒
            additional_providers: 额外的人机交互提供者列表，可选
            auto_start_sync: 是否在初始化时自动启动数据同步任务，默认为True
            config: 附加配置参数字典，可选
        """
        # Get API key from environment variables (if not provided)
        api_key = get_secret_from_env("GOHUMANLOOP_API_KEY")

        if api_key is None:
            raise ValueError("GOHUMANLOOP_API_KEY environment variable is not set!")

        # Get API base URL from environment variables (if not provided)
        api_base_url = os.environ.get(
            "GOHUMANLOOP_API_BASE_URL", "https://www.gohumanloop.com"
        )

        # Validate configuration using pydantic model
        self.ghl_config = GoHumanLoopConfig(api_key=api_key, api_base_url=api_base_url)

        self.name = "GoHumanLoop"
        # 创建 GoHumanLoop 提供者
        ghl_provider = GoHumanLoopProvider(
            name=self.name,
            request_timeout=request_timeout,
            poll_interval=poll_interval,
            max_retries=max_retries,
            config=config,
        )

        # 初始化提供者列表
        providers: List[HumanLoopProvider] = [ghl_provider]
        if additional_providers:
            providers.extend(additional_providers)

        # 调用父类初始化方法
        super().__init__(initial_providers=providers)

        # 设置 GoHumanLoop 提供者为默认提供者
        self.default_provider_id = self.name

        # 存储最近同步时间
        self._last_sync_time = time.time()

        # 同步间隔
        self.sync_interval = sync_interval

        # 存储已取消的请求和对话信息
        self._cancelled_conversations: Dict[
            str, Dict[str, Any]
        ] = {}  # conversation_id -> 取消信息

        # 数据同步任务引用
        self._sync_task: asyncio.Task[None] | None = None

        # 同步模式相关属性
        self._sync_thread: threading.Thread | None = None
        self._sync_thread_stop_event = threading.Event()

        # 启动数据同步任务
        if auto_start_sync:
            # 判断是否处在异步环境
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self.async_start_sync_task())
            else:
                self.start_sync_task()

    async def async_get_ghl_provider(self) -> GoHumanLoopProvider:
        """
        获取 GoHumanLoop 提供者实例

        Returns:
            GoHumanLoopProvider: GoHumanLoop 提供者实例
        """
        provider = await self.async_get_provider(self.default_provider_id)
        # 添加类型转换确保返回正确类型
        assert isinstance(provider, GoHumanLoopProvider)
        return provider

    async def async_start_sync_task(self) -> None:
        """启动数据同步任务"""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._async_data_periodically())

    async def _async_data_periodically(self) -> None:
        """定期同步数据到 GoHumanLoop 平台"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                await self.async_data_to_platform()
            except Exception as e:
                # 记录错误但不中断同步循环
                print(f"数据同步错误: {str(e)}")
            except asyncio.CancelledError:
                # 任务被取消时，确保最后同步一次数据
                try:
                    await self.async_data_to_platform()
                except Exception as e:
                    print(f"最终数据同步错误: {str(e)}")
                raise  # 重新抛出取消异常

    def start_sync_task(self) -> None:
        """启动同步版本的数据同步任务"""
        if self._sync_thread is None or not self._sync_thread.is_alive():
            self._sync_thread_stop_event.clear()
            self._sync_thread = threading.Thread(
                target=self._sync_data_periodically, daemon=True
            )
            self._sync_thread.start()

    def _sync_data_periodically(self) -> None:
        """同步版本：定期同步数据到 GoHumanLoop 平台"""
        while not self._sync_thread_stop_event.is_set():
            try:
                # 同步版本使用 time.sleep 而不是 asyncio.sleep
                time.sleep(self.sync_interval)
                self.sync_data_to_platform()
            except Exception as e:
                # 记录错误但不中断同步循环
                print(f"同步数据同步错误: {str(e)}")

        # 线程结束前执行最后一次同步
        try:
            self.sync_data_to_platform()
        except Exception as e:
            print(f"最终同步数据同步错误: {str(e)}")

    async def async_data_to_platform(self) -> None:
        """
        同步数据到 GoHumanLoop 平台

        此方法收集所有任务的数据，并通过 API 发送到 GoHumanLoop 平台
        """
        current_time = time.time()

        # 获取所有任务ID
        task_ids = list(self._task_conversations.keys())

        # 对每个任务进行数据同步
        for task_id in task_ids:
            # 获取任务相关的所有对话
            conversations = await self.async_get_task_conversations(task_id)

            # 收集任务数据
            task_data: Dict[str, Any] = {
                "task_id": task_id,
                "conversations": [],
                "timestamp": datetime.now().isoformat(),
            }

            # 收集每个对话的数据
            for conversation_id in conversations:
                # 获取对话中的所有请求
                request_ids = await self.async_get_conversation_requests(
                    conversation_id
                )

                conversation_data: Dict[str, Any] = {
                    "conversation_id": conversation_id,
                    "provider_id": self._conversation_provider.get(conversation_id),
                    "requests": [],
                }

                # 收集每个请求的数据
                for request_id in request_ids:
                    result = await self._async_get_request_status(
                        conversation_id, request_id
                    )

                    # 添加请求数据
                    conversation_data["requests"].append(
                        {
                            "request_id": request_id,
                            "status": result.status.value,
                            "loop_type": result.loop_type.value,
                            "response": result.response,
                            "feedback": result.feedback,
                            "responded_by": result.responded_by,
                            "responded_at": result.responded_at,
                            "error": result.error,
                        }
                    )

                # 添加对话数据
                task_data["conversations"].append(conversation_data)

            # 检查是否有已取消的对话需要添加
            for conv_id, cancel_info in self._cancelled_conversations.items():
                if conv_id not in conversations:
                    # 创建已取消对话的数据
                    cancelled_conv_data: Dict[str, Any] = {
                        "conversation_id": conv_id,
                        "provider_id": cancel_info.get("provider_id"),
                        "requests": [],
                    }

                    # 添加此对话中的已取消请求
                    for request_id in cancel_info.get("request_ids", []):
                        result = await self._async_get_request_status(
                            conv_id, request_id, cancel_info.get("provider_id")
                        )

                        # 添加请求数据
                        cancelled_conv_data["requests"].append(
                            {
                                "request_id": request_id,
                                "status": result.status.value,
                                "loop_type": result.loop_type.value,
                                "response": result.response,
                                "feedback": result.feedback,
                                "responded_by": result.responded_by,
                                "responded_at": result.responded_at,
                                "error": result.error,
                            }
                        )

                    # 添加已取消的对话
                    task_data["conversations"].append(cancelled_conv_data)

            # 发送数据到平台
            await self._async_send_task_data_to_platform(task_data)

        # 更新最后同步时间
        self._last_sync_time = current_time

    def sync_data_to_platform(self) -> None:
        """
        同步版本：同步数据到 GoHumanLoop 平台

        此方法收集所有任务的数据，并通过 API 发送到 GoHumanLoop 平台
        """
        current_time = time.time()

        # 获取所有任务ID
        task_ids = list(self._task_conversations.keys())

        # 对每个任务进行数据同步
        for task_id in task_ids:
            # 获取任务相关的所有对话
            # 使用同步方式运行异步方法
            loop = asyncio.new_event_loop()
            conversations = self.get_task_conversations(task_id)

            # 收集任务数据
            task_data: Dict[str, Any] = {
                "task_id": task_id,
                "conversations": [],
                "timestamp": datetime.now().isoformat(),
            }

            # 收集每个对话的数据
            for conversation_id in conversations:
                # 获取对话中的所有请求
                request_ids = self.get_conversation_requests(conversation_id)

                conversation_data: Dict[str, Any] = {
                    "conversation_id": conversation_id,
                    "provider_id": self._conversation_provider.get(conversation_id),
                    "requests": [],
                }

                # 收集每个请求的数据
                for request_id in request_ids:
                    result = loop.run_until_complete(
                        self._async_get_request_status(conversation_id, request_id)
                    )

                    # 添加请求数据
                    conversation_data["requests"].append(
                        {
                            "request_id": request_id,
                            "status": result.status.value,
                            "loop_type": result.loop_type.value,
                            "response": result.response,
                            "feedback": result.feedback,
                            "responded_by": result.responded_by,
                            "responded_at": result.responded_at,
                            "error": result.error,
                        }
                    )

                # 添加对话数据
                task_data["conversations"].append(conversation_data)

            # 检查是否有已取消的对话需要添加
            for conv_id, cancel_info in self._cancelled_conversations.items():
                if conv_id not in conversations:
                    # 创建已取消对话的数据
                    cancelled_conv_data: Dict[str, Any] = {
                        "conversation_id": conv_id,
                        "provider_id": cancel_info.get("provider_id"),
                        "requests": [],
                    }

                    # 添加此对话中的已取消请求
                    for request_id in cancel_info.get("request_ids", []):
                        result = loop.run_until_complete(
                            self._async_get_request_status(
                                conv_id, request_id, cancel_info.get("provider_id")
                            )
                        )

                        # 添加请求数据
                        cancelled_conv_data["requests"].append(
                            {
                                "request_id": request_id,
                                "status": result.status.value,
                                "loop_type": result.loop_type.value,
                                "response": result.response,
                                "feedback": result.feedback,
                                "responded_by": result.responded_by,
                                "responded_at": result.responded_at,
                                "error": result.error,
                            }
                        )

                    # 添加已取消的对话
                    task_data["conversations"].append(cancelled_conv_data)

            # 发送数据到平台
            loop.run_until_complete(self._async_send_task_data_to_platform(task_data))
            loop.close()

        # 更新最后同步时间
        self._last_sync_time = current_time

    async def _async_send_task_data_to_platform(
        self, task_data: Dict[str, Any]
    ) -> None:
        """发送任务数据到 GoHumanLoop 平台"""
        try:
            # 构建 API 请求 URL
            api_base_url = self.ghl_config.api_base_url
            url = f"{api_base_url}/v1/humanloop/tasks/sync"

            # 构建请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.ghl_config.api_key.get_secret_value()}",
            }

            # 使用 aiohttp 直接发送请求，而不依赖于 provider
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        url=url,
                        headers=headers,
                        json=task_data,
                        timeout=30,  # 设置合理的超时时间
                    ) as response:
                        # 处理 404 错误
                        if response.status == 404:
                            print(f"同步任务数据失败: API 端点不存在 - {url}")
                            return
                        # 处理 401 错误
                        elif response.status == 401:
                            print("同步任务数据失败: 认证失败 - 请检查 API 密钥")
                            return

                        # 处理其他错误状态码
                        if not response.ok:
                            print(
                                f"同步任务数据失败: HTTP {response.status} - {response.reason}"
                            )
                            return

                        response_data = await response.json()

                        if not response_data.get("success", False):
                            error_msg = response_data.get("error", "未知错误")
                            print(f"同步任务数据失败: {error_msg}")
                except aiohttp.ClientError as e:
                    print(f"HTTP 请求异常: {str(e)}")
        except Exception as e:
            print(f"发送任务数据到平台异常: {str(e)}")

    async def async_cancel_conversation(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """
        取消整个对话，并保存取消信息用于后续同步

        重写父类方法，在调用父类方法前保存对话信息
        """
        # 获取对话关联的provider_id
        if provider_id is None:
            provider_id = self._conversation_provider.get(conversation_id)

        # 保存对话取消信息，包括provider_id
        self._cancelled_conversations[conversation_id] = {
            "request_ids": list(self._conversation_requests.get(conversation_id, [])),
            "provider_id": provider_id,
        }

        # 调用父类方法执行实际取消操作
        return await super().async_cancel_conversation(conversation_id, provider_id)

    def __str__(self) -> str:
        """返回此实例的字符串描述"""
        return f"GoHumanLoop(default_provider={self.default_provider_id}, providers={len(self.providers)})"

    async def _async_get_request_status(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """
        获取请求状态的辅助方法

        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            provider_id: 提供者ID（可选）

        Returns:
            HumanLoopResult: 请求状态结果
        """
        # check_request_status
        if provider_id is None:
            provider_id = self._conversation_provider.get(conversation_id)

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        provider = self.providers[provider_id]
        return await provider.async_check_request_status(conversation_id, request_id)

    async def async_check_request_status(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """
        重写父类方法，增加数据同步操作
        """
        # 如果没有指定provider_id，尝试从存储的映射中获取
        if provider_id is None:
            stored_provider_id = self._conversation_provider.get(conversation_id)
            provider_id = stored_provider_id or self.default_provider_id

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        provider = self.providers[provider_id]
        result = await provider.async_check_request_status(conversation_id, request_id)

        # 如果有回调且状态不是等待或进行中
        if result.status not in [HumanLoopStatus.PENDING]:
            # 同步数据到平台
            await self.async_data_to_platform()
            # 触发状态更新回调
            if (conversation_id, request_id) in self._callbacks:
                await self._async_trigger_update_callback(
                    conversation_id, request_id, provider, result
                )

        return result

    def shutdown(self) -> None:
        """
        关闭管理器并确保数据同步（同步版本）

        在程序退出前调用此方法，确保所有数据都被同步到平台
        """
        # 停止同步线程
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread_stop_event.set()
            self._sync_thread.join(timeout=5)  # 等待线程结束，最多5秒

        # 执行最后一次同步数据同步
        try:
            self.sync_data_to_platform()
            print("最终同步数据同步完成")
        except Exception as e:
            print(f"最终同步数据同步失败: {str(e)}")

    async def async_shutdown(self) -> None:
        """
        关闭管理器并确保数据同步（异步版本）

        在程序退出前调用此方法，确保所有数据都被同步到平台
        """
        # 取消周期性同步任务
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass  # 预期的异常，忽略
        # 执行最后一次数据同步
        try:
            await self.async_data_to_platform()
            print("最终异步数据同步完成")
        except Exception as e:
            print(f"最终异步数据同步失败: {str(e)}")

    async def __aenter__(self) -> "GoHumanLoopManager":
        """实现异步上下文管理器协议的进入方法"""
        await self.async_start_sync_task()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """实现异步上下文管理器协议的退出方法"""
        await self.async_shutdown()
        return None

    def __enter__(self) -> "GoHumanLoopManager":
        """实现同步上下文管理器协议的进入方法"""
        # 使用同步模式
        self.start_sync_task()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """实现同步上下文管理器协议的退出方法"""
        self.shutdown()
        return None
