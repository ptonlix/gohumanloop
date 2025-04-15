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
        ret_key: str = "approval_result",
        timeout: Optional[int] = None,
        execute_on_reject: bool = False,
    ) -> HumanLoopWrapper:
        """审批场景装饰器"""
        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
            
        def decorator(fn):
                return self._approve_cli(fn, task_id, conversation_id, ret_key, timeout, execute_on_reject)
        return HumanLoopWrapper(decorator)

    def _approve_cli(
        self,
        fn: Callable[[T], R],
        task_id: str,
        conversation_id: str,
        ret_key: str = "approval_result",
        timeout: Optional[int] = None,
        execute_on_reject: bool = False,
    ) -> Callable[[T], R | None]:
        """
        将函数类型从 Callable[[T], R] 转换为 Callable[[T], R | None]
        
        通过关键字参数传递审批结果，保持原函数签名不变
        
        这种方式的优势:
        1. 不改变原函数的返回类型，保持与LangGraph工作流的兼容性
        2. 被装饰函数可以选择是否使用审批结果信息
        3. 可以传递更丰富的审批上下文信息
        
        注意:
        - 被装饰函数需要接受approval_key参数才能获取审批结果
        - 如果审批被拒绝，根据execute_on_reject参数决定是否执行函数
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | None:
            result = await self.manager.request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.APPROVAL,
                context={
                    "function": fn.__name__,
                    "signature": str(fn.__code__.co_varnames),
                    "args": str(args),
                    "kwargs": str(kwargs),
                    "doc": fn.__doc__ or "No documentation available",
                    "approval_template": f"""
Function Name: {fn.__name__}
Parameters: {', '.join(fn.__code__.co_varnames)}
Arguments: {args}
Keyword Arguments: {kwargs}
Documentation: {fn.__doc__ or 'No documentation available'}

Please review and approve/reject this function execution.
"""
                },
                timeout=timeout or self.default_timeout,
                blocking=True
            )

            # 初始化审批结果对象为None
            approval_info = None
            
            if isinstance(result, HumanLoopResult):
                # 如果结果是HumanLoopResult类型，则构建完整的审批信息
                approval_info = {
                    'conversation_id': result.conversation_id,
                    'request_id': result.request_id,
                    'loop_type': result.loop_type,
                    'status': result.status,
                    'response': result.response,
                    'feedback': result.feedback,
                    'responded_by': result.responded_by,
                    'responded_at': result.responded_at,
                    'error': result.error
                }

            kwargs[ret_key] = approval_info
            # 检查审批结果
            if isinstance(result, HumanLoopResult):
                # 根据审批状态处理
                if result.status == HumanLoopStatus.APPROVED:
                    if iscoroutinefunction(fn):
                        return await fn(*args, **kwargs)
                    return fn(*args, **kwargs)
                elif result.status == HumanLoopStatus.REJECTED:
                     # 如果设置了拒绝后执行，则执行函数
                    if execute_on_reject:
                        if iscoroutinefunction(fn):
                            return await fn(*args, **kwargs)
                        return fn(*args, **kwargs)
                    # 否则返回拒绝信息
                    reason = result.response
                    raise ValueError(f"Function {fn.__name__} execution not approved: {reason}")
                
            else:
                raise ValueError(f"Approval timeout or error for {fn.__name__}")

        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | None:
            return asyncio.run(async_wrapper(*args, **kwargs))

        # 根据被装饰函数类型返回对应的wrapper
        if iscoroutinefunction(fn):
            return async_wrapper # type: ignore
        return sync_wrapper

    def require_info(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        ret_key: str = "info_result",
        timeout: Optional[int] = None,
    ) -> HumanLoopWrapper:
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
        ret_key: str = "info_result",
        timeout: Optional[int] = None,
    ) -> Callable[[T], R | None]:
        """信息获取场景的内部实现装饰器
        将函数类型从 Callable[[T], R] 转换为 Callable[[T], R | None]
        
        主要功能:
        1. 通过人机交互获取所需信息
        2. 将获取的信息通过ret_key注入到函数参数中
        3. 支持同步和异步函数调用
        
        参数说明:
        - fn: 被装饰的目标函数
        - task_id: 任务唯一标识
        - conversation_id: 对话唯一标识
        - ret_key: 信息注入的参数名
        - timeout: 超时时间(秒)
        
        返回:
        - 装饰后的函数，保持原函数签名
        - 如果人机交互失败，抛出ValueError
        
        注意:
        - 被装饰函数需要接受ret_key参数才能获取交互结果
        - 交互结果包含完整的上下文信息
        - 支持异步和同步函数自动适配
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | None:
            result = await self.manager.request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.INFORMATION,
                context={
                    "function": fn.__name__,
                    "signature": str(fn.__code__.co_varnames),
                    "args": str(args),
                    "kwargs": str(kwargs),
                    "doc": fn.__doc__ or "No documentation available",
                    "info_template": f"""
Function Name: {fn.__name__}
Parameters: {', '.join(fn.__code__.co_varnames)}
Arguments: {args}
Keyword Arguments: {kwargs}
Documentation: {fn.__doc__ or 'No documentation available'}

Please provide the required information for this function.
"""
                },
                timeout=timeout or self.default_timeout,
                blocking=True
            )

            # 初始化审批结果对象为None
            resp_info = None

            if isinstance(result, HumanLoopResult):
                # 如果结果是HumanLoopResult类型，则构建完整的审批信息
                resp_info = {
                    'conversation_id': result.conversation_id,
                    'request_id': result.request_id,
                    'loop_type': result.loop_type,
                    'status': result.status,
                    'response': result.response,
                    'feedback': result.feedback,
                    'responded_by': result.responded_by,
                    'responded_at': result.responded_at,
                    'error': result.error
                }

            kwargs[ret_key] = resp_info

            # 检查结果是否有效
            if isinstance(result, HumanLoopResult):
                # 返回获取信息结果，由用户去判断是否使用
                if iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                return fn(*args, **kwargs)
            else:
                raise ValueError(f"Info request timeout or error for {fn.__name__}")

        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | None:
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
