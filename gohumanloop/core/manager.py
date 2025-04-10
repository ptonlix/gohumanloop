from typing import Dict, Any, Optional, List, Union
import asyncio
import time
from datetime import datetime

from gohumanloop.core.interface import HumanLoopManager, HumanLoopProvider, ApprovalCallback, ApprovalResult, ApprovalStatus

class DefaultHumanLoopManager(HumanLoopManager):
    """默认人机交互管理器实现"""
    
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
        """注册人机交互提供者"""
        return self.register_provider_sync(provider, provider_id)
        
    async def request_approval(
        self,
        task_id: str,
        context: Dict[str, Any],
        callback: Optional[ApprovalCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False
    ) -> Union[str, ApprovalResult]:
        """请求人类批准"""
        # 确定使用哪个提供者
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        provider = self.providers[provider_id]
        
        # 发送请求
        result = await provider.request_approval(
            task_id=task_id,
            context=context,
            metadata=metadata,
            timeout=timeout
        )
        
        request_id = result.request_id
        
        # 如果提供了回调，存储它
        if callback:
            self._callbacks[request_id] = callback
            
        # 如果设置了超时，创建超时任务
        if timeout:
            self._create_timeout_task(request_id, timeout, provider, callback)
            
        # 如果是阻塞模式，等待结果
        if blocking:
            return await self._wait_for_result(request_id, provider, timeout)
        else:
            return request_id
            
    async def check_status(self, request_id: str, provider_id: Optional[str] = None) -> ApprovalResult:
        """检查批准状态"""
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        provider = self.providers[provider_id]
        return await provider.check_approval_status(request_id)
        
    async def cancel_request(self, request_id: str, provider_id: Optional[str] = None) -> bool:
        """取消批准请求"""
        provider_id = provider_id or self.default_provider_id
        if not provider_id or provider_id not in self.providers:
            raise ValueError(f"Provider '{provider_id}' not found")
            
        provider = self.providers[provider_id]
        
        # 取消超时任务
        if request_id in self._timeout_tasks:
            self._timeout_tasks[request_id].cancel()
            del self._timeout_tasks[request_id]
            
        # 从回调映射中删除
        if request_id in self._callbacks:
            del self._callbacks[request_id]
            
        return await provider.cancel_approval_request(request_id)
        
    def _create_timeout_task(
        self, 
        request_id: str, 
        timeout: int, 
        provider: HumanLoopProvider,
        callback: Optional[ApprovalCallback]
    ):
        """创建超时任务"""
        async def timeout_task():
            await asyncio.sleep(timeout)
            # 检查当前状态
            result = await provider.check_approval_status(request_id)
            if result.status == ApprovalStatus.PENDING:
                # 如果仍在等待，触发超时回调
                if callback:
                    await callback.on_approval_timeout(request_id)
                    
        task = asyncio.create_task(timeout_task())
        self._timeout_tasks[request_id] = task
        
    async def _wait_for_result(
        self, 
        request_id: str, 
        provider: HumanLoopProvider, 
        timeout: Optional[int] = None
    ) -> ApprovalResult:
        """等待批准结果"""
        start_time = time.time()
        poll_interval = 1.0  # 轮询间隔（秒）
        
        while True:
            result = await provider.check_approval_status(request_id)
            
            # 如果不再是等待状态，返回结果
            if result.status != ApprovalStatus.PENDING:
                return result
                
            # 检查是否超时
            if timeout and (time.time() - start_time) > timeout:
                return ApprovalResult(
                    request_id=request_id,
                    status=ApprovalStatus.EXPIRED,
                    error="Request timed out"
                )
                
            # 等待一段时间后再次轮询
            await asyncio.sleep(poll_interval)