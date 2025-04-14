from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Union, List
from functools import wraps
import asyncio
import uuid
from inspect import iscoroutinefunction

from gohumanloop.core.interface import (
    HumanLoopManager, HumanLoopResult, HumanLoopStatus, HumanLoopType
)

# Define TypeVars for input and output types
T = TypeVar("T")
R = TypeVar('R')

class HumanLoopWrapper:
    def __init__(
        self,
        decorator: Callable[[Any], Callable],
    ) -> None:
        self.decorator = decorator

    def wrap(self, fn: Callable) -> Callable:
        return self.decorator(fn)

    def __call__(self, fn: Callable) -> Callable:
        return self.decorator(fn)

class LangGraphAdapter:
    """LangGraph适配器，用于简化人机循环集成
    
    提供四种场景的装饰器:
    - require_approval: 需要人工审批
    - require_info: 需要人工提供信息
    - require_conversation: 需要进行多轮对话
    - require_human: 通用人机交互
    """

    def __init__(
        self,
        manager: HumanLoopManager,
        default_timeout: Optional[int] = None
    ):
        self.manager = manager
        self.default_timeout = default_timeout


    def require_approval(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """审批场景装饰器"""
        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
            
        def decorator(fn):
                return self._approve_cli(fn, task_id, conversation_id, timeout)
        return HumanLoopWrapper(decorator)

    def _approve_cli(
        self,
        fn: Callable[[T], R],
        task_id: str,
        conversation_id: str,
        timeout: Optional[int]
    ) -> Callable[[T], R | str]:
        """
        将函数类型从 Callable[[T], R] 转换为 Callable[[T], R | str]
        
        这种转换主要用于LLM场景:
        1. 允许函数返回字符串形式的错误信息
        2. 保持与原始返回类型的兼容性
        3. 便于错误处理和消息传递
        
        注意:
        - 这种方式可能会影响类型检查
        - 建议在确保框架支持异常处理的情况下使用标准的异常处理机制
        - 当前实现是为了兼容不同框架的临时解决方案
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | str:
            result = await self.manager.request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.APPROVAL,
                context={
                    "function": fn.__name__,
                    "signature": str(fn.__code__.co_varnames),
                    "doc": fn.__doc__ or "No documentation available",
                    "approval_template": f"""
Function Name: {fn.__name__}
Parameters: {', '.join(fn.__code__.co_varnames)}
Documentation: {fn.__doc__ or 'No documentation available'}

Please review and approve/reject this function execution.
"""
                },
                timeout=timeout or self.default_timeout,
                blocking=True
            )
            
            # 检查审批结果
            if not isinstance(result, HumanLoopResult):
                return "Error: Invalid approval result"
                
            # 根据审批状态处理
            if result.status == HumanLoopStatus.APPROVED:
                try:
                    if iscoroutinefunction(fn):
                        return await fn(*args, **kwargs)
                    return fn(*args, **kwargs)
                except Exception as e:
                    return f"Error running {fn.__name__}: {e}"
            elif result.status == HumanLoopStatus.REJECTED:
                return f"Function {fn.__name__} was rejected: {result.response}"
            else:
                return f"Approval timeout or error for {fn.__name__}"

        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | str:
            return asyncio.run(async_wrapper(*args, **kwargs))

        # 根据被装饰函数类型返回对应的wrapper
        if iscoroutinefunction(fn):
            return async_wrapper # type: ignore
        return sync_wrapper

    def require_info(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        ret_key: str = "response",
        timeout: Optional[int] = None,
    ):
        """信息获取场景装饰器"""

        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        def decorator(fn):
            return self._get_info_cli(fn, task_id, conversation_id, ret_key, timeout)
        return HumanLoopWrapper(decorator)

    def _get_info_cli(
        self,
        fn: Callable[[T], R],
        task_id: str,
        conversation_id: str,
        ret_key: str = "response", # 接收关键字参数
        timeout: Optional[int] = None,
    ) -> Callable[[T], R | str]:
        """信息获取场景装饰器
        将函数类型从 Callable[[T], R] 转换为 Callable[[T], R | str]
        
        这种转换主要用于LLM场景:
        1. 允许函数返回字符串形式的错误信息
        2. 保持与原始返回类型的兼容性
        3. 便于错误处理和消息传递
        
        注意:
        - 这种方式可能会影响类型检查
        - 建议在确保框架支持异常处理的情况下使用标准的异常处理机制
        - 当前实现是为了兼容不同框架的临时解决方案
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | str:
            result = await self.manager.request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.INFORMATION,
                context={
                    "function": fn.__name__,
                    "signature": str(fn.__code__.co_varnames),
                    "doc": fn.__doc__ or "No documentation available",
                    "info_template": f"""
Function Name: {fn.__name__}
Parameters: {', '.join(fn.__code__.co_varnames)}
Documentation: {fn.__doc__ or 'No documentation available'}

Please provide the required information for this function.
"""
                },
                timeout=timeout or self.default_timeout,
                blocking=True
            )

            # 检查结果是否有效
            if not isinstance(result, HumanLoopResult):
                return "Error: Invalid information result"

            # 根据状态处理结果
            if result.status == HumanLoopStatus.COMPLETED:
                try:
                    kwargs[ret_key] = result.response
                    return fn(*args, **kwargs)
                except Exception as e:
                    return f"Error running {fn.__name__}: {e}"
            else:
                return f"Information gathering failed or timed out for {fn.__name__}: {result.response}"
        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | str:
            return asyncio.run(async_wrapper(*args, **kwargs))

        # 根据被装饰函数类型返回对应的wrapper
        if iscoroutinefunction(fn):
            return async_wrapper # type: ignore
        return sync_wrapper
    
class LanggraphHumanLoopCallback:
    """Langgraph专用的人机循环回调"""
    
    def __init__(
        self,
        on_update: Optional[Callable[[Dict[str, Any], HumanLoopResult], Awaitable[None]]] = None,
        on_timeout: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Dict[str, Any], str], Awaitable[None]]] = None
    ):
        self.on_update = on_update
        self.on_timeout = on_timeout
        self.on_error = on_error
        
    async def on_humanloop_update(self, state: Dict[str, Any], result: HumanLoopResult):
        """状态更新回调"""
        if self.on_update:
            await self.on_update(state, result)
            
    async def on_humanloop_timeout(self, state: Dict[str, Any]):
        """超时回调"""
        if self.on_timeout:
            await self.on_timeout(state)
            
    async def on_humanloop_error(self, state: Dict[str, Any], error: str):
        """错误回调"""
        if self.on_error:
            await self.on_error(state, error)
