from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Generic, Union
import asyncio
from functools import wraps

from gohumanloop.core.interface import HumanLoopManager, ApprovalCallback, ApprovalResult, ApprovalStatus

T = TypeVar('T')

class LanggraphApprovalCallback(ApprovalCallback):
    """为Langgraph设计的批准回调实现"""
    
    def __init__(
        self, 
        on_approved: Optional[Callable[[str, ApprovalResult], Awaitable[None]]] = None,
        on_rejected: Optional[Callable[[str, ApprovalResult], Awaitable[None]]] = None,
        on_timeout: Optional[Callable[[str], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str, str], Awaitable[None]]] = None
    ):
        self.on_approved = on_approved
        self.on_rejected = on_rejected
        self.on_timeout = on_timeout
        self.on_error = on_error
        
    async def on_approval_received(self, request_id: str, result: ApprovalResult):
        """当收到批准结果时的回调"""
        if result.status == ApprovalStatus.APPROVED and self.on_approved:
            await self.on_approved(request_id, result)
        elif result.status == ApprovalStatus.REJECTED and self.on_rejected:
            await self.on_rejected(request_id, result)
            
    async def on_approval_timeout(self, request_id: str):
        """当批准请求超时时的回调"""
        if self.on_timeout:
            await self.on_timeout(request_id)
            
    async def on_approval_error(self, request_id: str, error: str):
        """当批准请求发生错误时的回调"""
        if self.on_error:
            await self.on_error(request_id, error)

class LanggraphAdapter:
    """Langgraph适配器"""
    
    def __init__(self, human_loop_manager: HumanLoopManager):
        self.manager = human_loop_manager
        
    def requires_approval(
        self, 
        context_extractor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        task_id_extractor: Optional[Callable[[Dict[str, Any]], str]] = None,
        metadata_extractor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        timeout: Optional[int] = None,
        blocking: bool = True
    ):
        """装饰器，用于标记需要人类批准的Langgraph节点函数
        
        Args:
            context_extractor: 从状态中提取上下文的函数
            task_id_extractor: 从状态中提取任务ID的函数
            metadata_extractor: 从状态中提取元数据的函数
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(state):
                # 提取上下文、任务ID和元数据
                context = context_extractor(state) if context_extractor else state
                task_id = task_id_extractor(state) if task_id_extractor else str(id(state))
                metadata = metadata_extractor(state) if metadata_extractor else {}
                
                # 请求人类批准
                result = await self.manager.request_approval(
                    task_id=task_id,
                    context=context,
                    metadata=metadata,
                    timeout=timeout,
                    blocking=blocking
                )
                
                if blocking:
                    # 如果是阻塞模式，检查结果
                    if result.status == ApprovalStatus.APPROVED:
                        # 批准后执行原函数
                        return await func(state)
                    elif result.status == ApprovalStatus.REJECTED:
                        # 被拒绝，返回带有拒绝信息的状态
                        state["approval_rejected"] = True
                        state["approval_feedback"] = result.feedback
                        return state
                    else:
                        # 其他状态（错误、超时等）
                        state["approval_error"] = True
                        state["approval_status"] = result.status.value
                        state["approval_error_message"] = result.error
                        return state
                else:
                    # 非阻塞模式，将请求ID添加到状态中
                    state["approval_request_id"] = result
                    return state
                    
            return wrapper
        return decorator