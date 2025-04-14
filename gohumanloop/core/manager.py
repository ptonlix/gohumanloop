from typing import Dict, Any, Optional, List, Union
import asyncio
import time
from datetime import datetime

from gohumanloop.core.interface import (
    HumanLoopManager, HumanLoopProvider, HumanLoopCallback,
    HumanLoopResult, HumanLoopStatus, HumanLoopType
)

class DefaultHumanLoopManager(HumanLoopManager):
    """默认人机循环管理器实现"""
    
    def __init__(self, default_provider: Optional[HumanLoopProvider] = None):
        self.providers = {}
        self.default_provider_id = None
        if default_provider:
            self.register_provider_sync(default_provider, "default")
            self.default_provider_id = "default"
        
        # 存储请求和回调的映射
        self._callbacks = {}
        # 存储请求的超时任务
        self._timeout_tasks = {}
        
    def register_provider_sync(self, provider: HumanLoopProvider, provider_id: Optional[str]) -> str:
        """同步注册提供者（用于初始化）"""
        if not provider_id:
            provider_id = f"provider_{len(self.providers) + 1}"
            
        self.providers[provider_id] = provider
        
        if not self.default_provider_id:
            self.default_provider_id = provider_id
            
        return provider_id
        
    async def register_provider(self, provider: HumanLoopProvider, provider_id: Optional[str] = None) -> str:
        """注册人机循环提供者"""
        return self.register_provider_sync(provider, provider_id)
        
    async def request_humanloop(
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
            
        provider = self.providers[provider_id]
        
        # 发送请求
        result = await provider.request_humanloop(
            task_id=task_id,
            conversation_id=conversation_id,
            loop_type=loop_type,
            context=context,
            metadata=metadata,
            timeout=timeout
        )
        
        request_id = result.request_id
        
        # 如果提供了回调，存储它
        if callback:
            self._callbacks[(conversation_id, request_id)] = callback
            
        # 如果设置了超时，创建超时任务
        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout, provider, callback)
            
        # 如果是阻塞模式，等待结果
        if blocking:
            return await self._wait_for_result(conversation_id, request_id, provider, timeout)
        else:
            return request_id
    
    async def continue_humanloop(
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
        # 确定使用哪个提供者
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        provider = self.providers[provider_id]
        
        # 发送继续请求
        result = await provider.continue_humanloop(
            conversation_id=conversation_id,
            context=context,
            metadata=metadata,
            timeout=timeout,
        )
        
        request_id = result.request_id
        
        # 如果提供了回调，存储它
        if callback:
            self._callbacks[(conversation_id, request_id)] = callback
            
        # 如果设置了超时，创建超时任务
        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout, provider, callback)
            
        # 如果是阻塞模式，等待结果
        if blocking:
            return await self._wait_for_result(conversation_id, request_id, provider, timeout)
        else:
            return request_id
            
    async def check_request_status(
        self,
        conversation_id: str,
        request_id: str,
        provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查请求状态"""
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        provider = self.providers[provider_id]
        result = await provider.check_request_status(conversation_id, request_id)
        
        # 如果有回调且状态不是等待或进行中，触发状态更新回调
        if (conversation_id, request_id) in self._callbacks and result.status not in [HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS]:
            await self._trigger_update_callback(conversation_id, request_id, result)
            
        return result
    
    async def check_conversation_status(
        self,
        conversation_id: str,
        provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查对话状态"""
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        provider = self.providers[provider_id]
        return await provider.check_conversation_status(conversation_id)
    
    async def cancel_request(
        self,
        conversation_id: str,
        request_id: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """取消特定请求"""
        provider_id = provider_id or self.default_provider_id
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
            
        return await provider.cancel_request(conversation_id, request_id)
    
    async def cancel_conversation(
        self,
        conversation_id: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """取消整个对话"""
        provider_id = provider_id or self.default_provider_id
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
            
        return await provider.cancel_conversation(conversation_id)
    
    async def get_provider(
        self,
        provider_id: Optional[str] = None
    ) -> HumanLoopProvider:
        """获取指定的提供者实例"""
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        return self.providers[provider_id]
    
    async def list_providers(self) -> Dict[str, HumanLoopProvider]:
        """列出所有注册的提供者"""
        return self.providers
    
    async def set_default_provider(
        self,
        provider_id: str
    ) -> bool:
        """设置默认提供者"""
        if provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        self.default_provider_id = provider_id
        return True
        
    def _create_timeout_task(
        self, 
        conversation_id: str,
        request_id: str, 
        timeout: int, 
        provider: HumanLoopProvider,
        callback: Optional[HumanLoopCallback]
    ):
        """创建超时任务"""
        async def timeout_task():
            await asyncio.sleep(timeout)
            # 检查当前状态
            result = await provider.check_request_status(conversation_id, request_id)
            
            # 只有当状态为PENDING时才触发超时回调
            # INPROGRESS状态表示对话正在进行中，不应视为超时
            if result.status == HumanLoopStatus.PENDING:
                if callback:
                    await callback.on_humanloop_timeout(conversation_id, request_id)
            # 如果状态是INPROGRESS，重置超时任务
            elif result.status == HumanLoopStatus.INPROGRESS:
                # 对于进行中的对话，我们可以选择延长超时时间
                # 这里我们简单地重新创建一个超时任务，使用相同的超时时间
                if (conversation_id, request_id) in self._timeout_tasks:
                    self._timeout_tasks[(conversation_id, request_id)].cancel()
                new_task = asyncio.create_task(timeout_task())
                self._timeout_tasks[(conversation_id, request_id)] = new_task
                    
        task = asyncio.create_task(timeout_task())
        self._timeout_tasks[(conversation_id, request_id)] = task
        
    async def _wait_for_result(
        self, 
        conversation_id: str,
        request_id: str, 
        provider: HumanLoopProvider, 
        timeout: Optional[int] = None
    ) -> HumanLoopResult:
        """等待循环结果"""
        start_time = time.time()
        poll_interval = 1.0  # 轮询间隔（秒）
        
        while True:
            result = await provider.check_request_status(conversation_id, request_id)
            
            # 如果状态是最终状态（非PENDING和INPROGRESS），返回结果
            if result.status != HumanLoopStatus.PENDING and result.status != HumanLoopStatus.INPROGRESS:
                if (conversation_id, request_id) in self._callbacks:
                    await self._trigger_update_callback(conversation_id, request_id, result)
                return result
                
            # 检查是否超时，但只对PENDING状态进行超时检查
            # 对于INPROGRESS状态，我们允许它继续运行
            if timeout and (time.time() - start_time) > timeout and result.status == HumanLoopStatus.PENDING:
                result = HumanLoopResult(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    loop_type=result.loop_type,
                    status=HumanLoopStatus.EXPIRED,
                    error="Request timed out while waiting for response"
                )
                if (conversation_id, request_id) in self._callbacks:
                    await self._trigger_update_callback(conversation_id, request_id, result)
                return result
                
            # 等待一段时间后再次轮询
            await asyncio.sleep(poll_interval)
    
    async def _trigger_update_callback(self, conversation_id: str, request_id: str, result: HumanLoopResult):
        """触发状态更新回调"""
        callback = self._callbacks.get((conversation_id, request_id))
        if callback:
            try:
                await callback.on_humanloop_update(conversation_id, request_id, result)
                # 如果状态是最终状态，可以考虑移除回调
                if result.status not in [HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS]:
                    del self._callbacks[(conversation_id, request_id)]
            except Exception as e:
                # 处理回调执行过程中的异常
                try:
                    await callback.on_humanloop_error(conversation_id, request_id, str(e))
                except:
                    # 如果错误回调也失败，只能忽略
                    pass