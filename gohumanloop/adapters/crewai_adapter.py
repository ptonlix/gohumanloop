from typing import Dict, Any, Optional, Callable, List, Union
import asyncio
from functools import wraps

from gohumanloop.core.interface import HumanLoopManager, ApprovalCallback, ApprovalResult, ApprovalStatus

class CrewAIApprovalCallback(ApprovalCallback):
    """为CrewAI设计的批准回调实现"""
    
    def __init__(
        self, 
        on_approved: Optional[Callable] = None,
        on_rejected: Optional[Callable] = None,
        on_timeout: Optional[Callable] = None,
        on_error: Optional[Callable] = None
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

class CrewAIAdapter:
    """CrewAI适配器"""
    
    def __init__(self, human_loop_manager: HumanLoopManager):
        self.manager = human_loop_manager
        
    def requires_approval(
        self, 
        context_builder: Optional[Callable[[Any, List[Any]], Dict[str, Any]]] = None,
        task_id_builder: Optional[Callable[[Any, List[Any]], str]] = None,
        metadata_builder: Optional[Callable[[Any, List[Any]], Dict[str, Any]]] = None,
        timeout: Optional[int] = None,
        blocking: bool = True
    ):
        """装饰器，用于标记需要人类批准的CrewAI任务
        
        Args:
            context_builder: 构建上下文的函数
            task_id_builder: 构建任务ID的函数
            metadata_builder: 构建元数据的函数
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(self_agent, *args, **kwargs):
                # 构建上下文、任务ID和元数据
                context = context_builder(self_agent, args) if context_builder else {
                    "agent": self_agent.name,
                    "task": getattr(self_agent, "task", "Unknown Task"),
                    "args": str(args)
                }
                
                task_id = task_id_builder(self_agent, args) if task_id_builder else f"{self_agent.name}_{id(self_agent)}"
                metadata = metadata_builder(self_agent, args) if metadata_builder else {}
                
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
                        return await func(self_agent, *args, **kwargs)
                    elif result.status == ApprovalStatus.REJECTED:
                        # 被拒绝，返回拒绝信息
                        return f"Task was rejected by human reviewer. Feedback: {result.feedback}"
                    else:
                        # 其他状态（错误、超时等）
                        return f"Approval error: {result.status.value} - {result.error}"
                else:
                    # 非阻塞模式，将请求ID添加到状态中并继续执行
                    setattr(self_agent, "_approval_request_id", result)
                    return await func(self_agent, *args, **kwargs)
                    
            return wrapper
        return decorator