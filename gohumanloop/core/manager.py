from typing import Dict, Any, Optional, List, Union
import asyncio
from datetime import datetime
from gohumanloop.utils import run_async_safely

from gohumanloop.core.interface import (
    HumanLoopRequest,
    HumanLoopManager,
    HumanLoopProvider,
    HumanLoopCallback,
    HumanLoopResult,
    HumanLoopStatus,
    HumanLoopType,
)


class DefaultHumanLoopManager(HumanLoopManager):
    """默认人机循环管理器实现"""

    def __init__(
        self,
        initial_providers: Optional[
            Union[HumanLoopProvider, List[HumanLoopProvider]]
        ] = None,
    ):
        self.providers: dict[str, HumanLoopProvider] = {}
        self.default_provider_id = None

        # 存储请求和回调的映射
        self._callbacks: dict[tuple[str, str], HumanLoopCallback] = {}
        # 存储请求的超时任务
        self._timeout_tasks: dict[tuple[str, str], asyncio.Task] = {}

        # 存储task_id与conversation_id的映射关系
        self._task_conversations: dict[
            str, set[str]
        ] = {}  # task_id -> Set[conversation_id]
        # 存储conversation_id与request_id的映射关系
        self._conversation_requests: dict[
            str, list[str]
        ] = {}  # conversation_id -> List[request_id]
        # 存储request_id与task_id的反向映射
        self._request_task: dict[
            tuple[str, str], str
        ] = {}  # (conversation_id, request_id) -> task_id
        # 存储对话对应的provider_id
        self._conversation_provider: dict[
            str, str
        ] = {}  # conversation_id -> provider_id

        # 初始化提供者
        if initial_providers:
            if isinstance(initial_providers, list):
                # 处理提供者列表
                for provider in initial_providers:
                    self.register_provider_sync(provider, provider.name)
                    if self.default_provider_id is None:
                        self.default_provider_id = provider.name
            else:
                # 处理单个提供者
                self.register_provider_sync(initial_providers, initial_providers.name)
                self.default_provider_id = initial_providers.name

    def register_provider_sync(
        self, provider: HumanLoopProvider, provider_id: Optional[str]
    ) -> str:
        """同步注册提供者（用于初始化）"""
        if not provider_id:
            provider_id = f"provider_{len(self.providers) + 1}"

        self.providers[provider_id] = provider

        if not self.default_provider_id:
            self.default_provider_id = provider_id

        return provider_id

    async def async_register_provider(
        self, provider: HumanLoopProvider, provider_id: Optional[str] = None
    ) -> str:
        """注册人机循环提供者"""
        return self.register_provider_sync(provider, provider_id)

    def register_provider(
        self, provider: HumanLoopProvider, provider_id: Optional[str] = None
    ) -> str:
        """注册人机循环提供者（同步版本）"""
        return self.register_provider_sync(provider, provider_id)

    async def async_request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """请求人机循环"""
        # 确定使用哪个提供者
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        # 检查对话是否已存在且使用了不同的提供者
        if (
            conversation_id in self._conversation_provider
            and self._conversation_provider[conversation_id] != provider_id
        ):
            raise ValueError(
                f"Conversation '{conversation_id}' already exists with a different provider"
            )

        provider = self.providers[provider_id]

        try:
            # 发送请求
            result = await provider.async_request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=loop_type,
                context=context,
                metadata=metadata,
                timeout=timeout,
            )

            request_id = result.request_id

            if not request_id:
                raise ValueError(
                    f"Failed to request humanloop for conversation '{conversation_id}'"
                )

            # 存储task_id、conversation_id和request_id的关系
            if task_id not in self._task_conversations:
                self._task_conversations[task_id] = set()
            self._task_conversations[task_id].add(conversation_id)

            if conversation_id not in self._conversation_requests:
                self._conversation_requests[conversation_id] = []
            self._conversation_requests[conversation_id].append(request_id)

            self._request_task[(conversation_id, request_id)] = task_id
            # 存储对话对应的provider_id
            self._conversation_provider[conversation_id] = provider_id

            # 如果提供了回调，存储它
            if callback:
                try:
                    # 创建请求对象
                    request = HumanLoopRequest(
                        task_id=task_id,
                        conversation_id=conversation_id,
                        loop_type=loop_type,
                        context=context,
                        metadata=metadata or {},
                        timeout=timeout,
                        created_at=datetime.now(),
                    )
                    await callback.async_on_humanloop_request(provider, request)
                except Exception as e:
                    # 处理回调执行过程中的异常
                    try:
                        await callback.async_on_humanloop_error(provider, e)
                    except Exception:
                        # 如果错误回调也失败，只能忽略
                        pass
                self._callbacks[(conversation_id, request_id)] = callback

            # 如果是阻塞模式，等待结果
            if blocking:
                return await self._async_wait_for_result(
                    conversation_id, request_id, provider, timeout
                )
            else:
                return request_id
        except Exception as e:
            # 处理请求过程中的异常
            if callback:
                try:
                    await callback.async_on_humanloop_error(provider, e)
                except Exception:
                    # 如果错误回调也失败，只能忽略
                    pass
            raise  # 重新抛出异常，让调用者知道发生了错误

    def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """请求人机循环（同步版本）"""

        result: Union[str, HumanLoopResult] = run_async_safely(
            self.async_request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=loop_type,
                context=context,
                callback=callback,
                metadata=metadata,
                provider_id=provider_id,
                timeout=timeout,
                blocking=blocking,
            )
        )

        return result

    async def async_continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """继续人机循环"""
        # 确定使用哪个提供者，优先使用对话已关联的提供者
        if conversation_id in self._conversation_provider:
            stored_provider_id = self._conversation_provider[conversation_id]
            if provider_id and provider_id != stored_provider_id:
                raise ValueError(
                    f"Conversation '{conversation_id}' already exists with provider '{stored_provider_id}'"
                )
            provider_id = stored_provider_id
        else:
            provider_id = provider_id or self.default_provider_id

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        provider = self.providers[provider_id]

        try:
            # 发送继续请求
            result = await provider.async_continue_humanloop(
                conversation_id=conversation_id,
                context=context,
                metadata=metadata,
                timeout=timeout,
            )

            request_id = result.request_id

            if not request_id:
                raise ValueError(
                    f"Failed to continue humanloop for conversation '{conversation_id}'"
                )

            # 更新conversation_id和request_id的关系
            if conversation_id not in self._conversation_requests:
                self._conversation_requests[conversation_id] = []
            self._conversation_requests[conversation_id].append(request_id)

            # 查找此conversation_id对应的task_id
            task_id = None
            for t_id, convs in self._task_conversations.items():
                if conversation_id in convs:
                    task_id = t_id
                    break

            if task_id:
                self._request_task[(conversation_id, request_id)] = task_id

            # 存储对话对应的provider_id，如果对话不存在才存储
            if conversation_id not in self._conversation_provider:
                self._conversation_provider[conversation_id] = provider_id

            # 如果提供了回调，存储它
            if callback:
                try:
                    # 创建请求对象
                    request = HumanLoopRequest(
                        task_id=task_id or "",
                        conversation_id=conversation_id,
                        loop_type=HumanLoopType.CONVERSATION,
                        context=context,
                        metadata=metadata or {},
                        timeout=timeout,
                        created_at=datetime.now(),
                    )
                    await callback.async_on_humanloop_request(provider, request)
                except Exception as e:
                    # 处理回调执行过程中的异常
                    try:
                        await callback.async_on_humanloop_error(provider, e)
                    except Exception:
                        # 如果错误回调也失败，只能忽略
                        pass
                self._callbacks[(conversation_id, request_id)] = callback

            # 如果是阻塞模式，等待结果
            if blocking:
                return await self._async_wait_for_result(
                    conversation_id, request_id, provider, timeout
                )
            else:
                return request_id
        except Exception as e:
            # 处理继续请求过程中的异常
            if callback:
                try:
                    await callback.async_on_humanloop_error(provider, e)
                except Exception:
                    # 如果错误回调也失败，只能忽略
                    pass
            raise  # 重新抛出异常，让调用者知道发生了错误

    def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """继续人机循环（同步版本）"""

        result: Union[str, HumanLoopResult] = run_async_safely(
            self.async_continue_humanloop(
                conversation_id=conversation_id,
                context=context,
                callback=callback,
                metadata=metadata,
                provider_id=provider_id,
                timeout=timeout,
                blocking=blocking,
            )
        )

        return result

    async def async_check_request_status(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查请求状态"""
        # 如果没有指定provider_id，尝试从存储的映射中获取
        if provider_id is None:
            stored_provider_id = self._conversation_provider.get(conversation_id)
            provider_id = stored_provider_id or self.default_provider_id

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        provider = self.providers[provider_id]

        try:
            result = await provider.async_check_request_status(
                conversation_id, request_id
            )

            # 如果有回调且状态不是等待或进行中，触发状态更新回调
            if (
                conversation_id,
                request_id,
            ) in self._callbacks and result.status not in [HumanLoopStatus.PENDING]:
                await self._async_trigger_update_callback(
                    conversation_id, request_id, provider, result
                )

            return result
        except Exception as e:
            # 处理检查状态过程中的异常
            callback = self._callbacks.get((conversation_id, request_id))
            if callback:
                try:
                    await callback.async_on_humanloop_error(provider, e)
                except Exception:
                    # 如果错误回调也失败，只能忽略
                    pass
            raise  # 重新抛出异常，让调用者知道发生了错误

    def check_request_status(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查请求状态（同步版本）"""

        result: HumanLoopResult = run_async_safely(
            self.async_check_request_status(
                conversation_id=conversation_id,
                request_id=request_id,
                provider_id=provider_id,
            )
        )

        return result

    async def async_check_conversation_status(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查对话状态"""
        # 优先使用对话已关联的提供者
        if provider_id is None:
            stored_provider_id = self._conversation_provider.get(conversation_id)
            provider_id = stored_provider_id or self.default_provider_id

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        #  检查对话指定provider_id或默认provider_id最后一次请求的状态
        provider = self.providers[provider_id]

        try:
            #  检查对话指定provider_id或默认provider_id最后一次请求的状态
            result = await provider.async_check_conversation_status(conversation_id)

            if (
                conversation_id in self._conversation_requests
                and self._conversation_requests[conversation_id]
            ):
                last_request_id = self._conversation_requests[conversation_id][-1]
                callback = self._callbacks.get((conversation_id, last_request_id))

                if callback and result.status not in [HumanLoopStatus.PENDING]:
                    # 如果有回调且状态不是等待或进行中，触发状态更新回调
                    await self._async_trigger_update_callback(
                        conversation_id, last_request_id, provider, result
                    )

            return result
        except Exception as e:
            # 处理检查对话状态过程中的异常
            # 尝试找到与此对话关联的最后一个请求的回调
            if callback:
                try:
                    await callback.async_on_humanloop_error(provider, e)
                except Exception:
                    # 如果错误回调也失败，只能忽略
                    pass
            raise  # 重新抛出异常，让调用者知道发生了错误

    def check_conversation_status(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查对话状态（同步版本）"""

        result: HumanLoopResult = run_async_safely(
            self.async_check_conversation_status(
                conversation_id=conversation_id, provider_id=provider_id
            )
        )

        return result

    async def async_cancel_request(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """取消特定请求"""
        if provider_id is None:
            stored_provider_id = self._conversation_provider.get(conversation_id)
            provider_id = stored_provider_id or self.default_provider_id

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        provider = self.providers[provider_id]

        # 取消超时任务
        if (conversation_id, request_id) in self._timeout_tasks:
            self._timeout_tasks[(conversation_id, request_id)].cancel()
            del self._timeout_tasks[(conversation_id, request_id)]

        # 从回调映射中删除
        if (conversation_id, request_id) in self._callbacks:
            del self._callbacks[(conversation_id, request_id)]

        # 清理request关联
        if (conversation_id, request_id) in self._request_task:
            del self._request_task[(conversation_id, request_id)]

        # 从conversation_requests中移除
        if conversation_id in self._conversation_requests:
            if request_id in self._conversation_requests[conversation_id]:
                self._conversation_requests[conversation_id].remove(request_id)

        return await provider.async_cancel_request(conversation_id, request_id)

    def cancel_request(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """取消特定请求（同步版本）"""

        result: bool = run_async_safely(
            self.async_cancel_request(
                conversation_id=conversation_id,
                request_id=request_id,
                provider_id=provider_id,
            )
        )

        return result

    async def async_cancel_conversation(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """取消整个对话"""
        # 优先使用对话已关联的提供者
        if provider_id is None:
            stored_provider_id = self._conversation_provider.get(conversation_id)
            provider_id = stored_provider_id or self.default_provider_id

        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        provider = self.providers[provider_id]

        # 取消与此对话相关的所有超时任务和回调
        keys_to_remove = []
        for key in self._timeout_tasks:
            if key[0] == conversation_id:
                self._timeout_tasks[key].cancel()
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._timeout_tasks[key]

        keys_to_remove = []
        for key in self._callbacks:
            if key[0] == conversation_id:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._callbacks[key]

        # 清理与此对话相关的task映射关系
        # 1. 从task_conversations中移除此对话
        task_ids_to_update = []
        for task_id, convs in self._task_conversations.items():
            if conversation_id in convs:
                task_ids_to_update.append(task_id)

        for task_id in task_ids_to_update:
            self._task_conversations[task_id].remove(conversation_id)
            # 如果task没有关联的对话了，可以考虑删除该task记录
            if not self._task_conversations[task_id]:
                del self._task_conversations[task_id]

        # 2. 获取并清理所有与此对话相关的请求
        request_ids = self._conversation_requests.get(conversation_id, [])
        for request_id in request_ids:
            # 清理request_task映射
            if (conversation_id, request_id) in self._request_task:
                del self._request_task[(conversation_id, request_id)]

        # 3. 清理conversation_requests映射
        if conversation_id in self._conversation_requests:
            del self._conversation_requests[conversation_id]

        # 4. 清理provider关联
        if conversation_id in self._conversation_provider:
            del self._conversation_provider[conversation_id]

        return await provider.async_cancel_conversation(conversation_id)

    def cancel_conversation(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """取消整个对话（同步版本）"""

        result: bool = run_async_safely(
            self.async_cancel_conversation(
                conversation_id=conversation_id, provider_id=provider_id
            )
        )

        return result

    async def async_get_provider(
        self, provider_id: Optional[str] = None
    ) -> HumanLoopProvider:
        """获取指定的提供者实例"""
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        return self.providers[provider_id]

    def get_provider(self, provider_id: Optional[str] = None) -> HumanLoopProvider:
        """获取指定的提供者实例（同步版本）"""

        result: HumanLoopProvider = run_async_safely(
            self.async_get_provider(provider_id=provider_id)
        )

        return result

    async def async_list_providers(self) -> Dict[str, HumanLoopProvider]:
        """列出所有注册的提供者"""
        return self.providers

    def list_providers(self) -> Dict[str, HumanLoopProvider]:
        """列出所有注册的提供者（同步版本）"""

        result: Dict[str, HumanLoopProvider] = run_async_safely(
            self.async_list_providers()
        )

        return result

    async def async_set_default_provider(self, provider_id: str) -> bool:
        """设置默认提供者"""
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")

        self.default_provider_id = provider_id
        return True

    def set_default_provider(self, provider_id: str) -> bool:
        """设置默认提供者（同步版本）"""

        result: bool = run_async_safely(
            self.async_set_default_provider(provider_id=provider_id)
        )

        return result

    async def _async_wait_for_result(
        self,
        conversation_id: str,
        request_id: str,
        provider: HumanLoopProvider,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """等待循环结果"""
        poll_interval = 1.0  # 轮询间隔（秒）

        while True:
            result = await self.async_check_request_status(
                conversation_id, request_id, provider.name
            )

            # 如果状态是最终状态（非PENDING），返回结果
            if result.status != HumanLoopStatus.PENDING:
                return result

            # 等待一段时间后再次轮询
            await asyncio.sleep(poll_interval)

    async def _async_trigger_update_callback(
        self,
        conversation_id: str,
        request_id: str,
        provider: HumanLoopProvider,
        result: HumanLoopResult,
    ) -> None:
        """触发状态更新回调"""
        callback: Optional[HumanLoopCallback] = self._callbacks.get(
            (conversation_id, request_id)
        )
        if callback:
            try:
                await callback.async_on_humanloop_update(provider, result)
                if result.status == HumanLoopStatus.EXPIRED:
                    await callback.async_on_humanloop_timeout(provider, result)
                # 如果状态是最终状态，可以考虑移除回调
                if result.status not in [
                    HumanLoopStatus.PENDING,
                    HumanLoopStatus.INPROGRESS,
                ]:
                    del self._callbacks[(conversation_id, request_id)]
            except Exception as e:
                # 处理回调执行过程中的异常
                try:
                    await callback.async_on_humanloop_error(provider, e)
                except Exception:
                    # 如果错误回调也失败，只能忽略
                    pass

        # 添加新方法用于获取task相关信息

    async def async_get_task_conversations(self, task_id: str) -> List[str]:
        """获取任务关联的所有对话ID

        Args:
            task_id: 任务ID

        Returns:
            List[str]: 与任务关联的对话ID列表
        """
        return list(self._task_conversations.get(task_id, set()))

    def get_task_conversations(self, task_id: str) -> List[str]:
        """获取任务关联的所有对话ID

        Args:
            task_id: 任务ID

        Returns:
            List[str]: 与任务关联的对话ID列表
        """
        return list(self._task_conversations.get(task_id, set()))

    async def async_get_conversation_requests(self, conversation_id: str) -> List[str]:
        """获取对话关联的所有请求ID

        Args:
            conversation_id: 对话ID

        Returns:
            List[str]: 与对话关联的请求ID列表
        """
        ret: List[str] = self._conversation_requests.get(conversation_id, [])
        return ret

    def get_conversation_requests(self, conversation_id: str) -> List[str]:
        """获取对话关联的所有请求ID

        Args:
            conversation_id: 对话ID

        Returns:
            List[str]: 与对话关联的请求ID列表
        """
        ret: List[str] = self._conversation_requests.get(conversation_id, [])

        return ret

    async def async_get_request_task(
        self, conversation_id: str, request_id: str
    ) -> Optional[str]:
        """获取请求关联的任务ID

        Args:
            conversation_id: 对话ID
            request_id: 请求ID

        Returns:
            Optional[str]: 关联的任务ID，如果不存在则返回None
        """
        ret: Optional[str] = self._request_task.get((conversation_id, request_id))

        return ret

    async def async_get_conversation_provider(
        self, conversation_id: str
    ) -> Optional[str]:
        """获取请求关联的提供者ID

        Args:
            conversation_id: 对话ID

        Returns:
            Optional[str]: 关联的提供者ID，如果不存在则返回None
        """
        ret: Optional[str] = self._conversation_provider.get(conversation_id)

        return ret

    async def async_check_conversation_exist(
        self,
        task_id: str,
        conversation_id: str,
    ) -> bool:
        """判断对话是否已存在

        Args:
            conversation_id: 对话标识符
            provider_id: 使用特定提供者的ID（可选）

        Returns:
            bool: 如果对话存在返回True，否则返回False
        """
        # 检查task_id是否存在且conversation_id是否在该task的对话集合中
        if (
            task_id in self._task_conversations
            and conversation_id in self._task_conversations[task_id]
        ):
            # 进一步验证该对话是否有关联的请求
            if (
                conversation_id in self._conversation_requests
                and self._conversation_requests[conversation_id]
            ):
                return True

        return False

    def check_conversation_exist(
        self,
        task_id: str,
        conversation_id: str,
    ) -> bool:
        """判断对话是否已存在

        Args:
            conversation_id: 对话标识符
            provider_id: 使用特定提供者的ID（可选）

        Returns:
            bool: 如果对话存在返回True，否则返回False
        """
        # 检查task_id是否存在且conversation_id是否在该task的对话集合中
        if (
            task_id in self._task_conversations
            and conversation_id in self._task_conversations[task_id]
        ):
            # 进一步验证该对话是否有关联的请求
            if (
                conversation_id in self._conversation_requests
                and self._conversation_requests[conversation_id]
            ):
                return True

        return False

    async def async_shutdown(self) -> None:
        pass

    def shutdown(self) -> None:
        pass
