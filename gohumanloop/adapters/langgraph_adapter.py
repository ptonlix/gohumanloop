from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Union, List
from functools import wraps
import asyncio
import uuid
from inspect import iscoroutinefunction
from contextlib import asynccontextmanager, contextmanager

from gohumanloop.utils import run_async_safely
from gohumanloop.core.interface import (
    HumanLoopManager, HumanLoopResult, HumanLoopStatus, HumanLoopType, HumanLoopCallback, HumanLoopProvider
)

# Define TypeVars for input and output types
T = TypeVar("T")
R = TypeVar('R')

# 检查LangGraph版本
def _check_langgraph_version():
    """检查LangGraph版本，判断是否支持interrupt功能"""
    try:
        import importlib.metadata
        version = importlib.metadata.version("langgraph")
        version_parts = version.split('.')
        major, minor, patch = int(version_parts[0]), int(version_parts[1]), int(version_parts[2])
        
        # 从0.2.57版本开始支持interrupt
        return (major > 0 or (major == 0 and (minor > 2 or (minor == 2 and patch >= 57))))
    except (importlib.metadata.PackageNotFoundError, ValueError, IndexError):
        # 如果无法确定版本，假设不支持
        return False

# 根据版本导入相应功能
_SUPPORTS_INTERRUPT = _check_langgraph_version()
if _SUPPORTS_INTERRUPT:
    try:
        from langgraph.types import interrupt as _lg_interrupt
        from langgraph.types import Command as _lg_Command
    except ImportError:
        _SUPPORTS_INTERRUPT = False

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
    
    提供三种场景的装饰器:
    - require_approval: 需要人工审批
    - require_info: 需要人工提供信息
    - require_conversation: 需要进行多轮对话
    """

    def __init__(
        self,
        manager: HumanLoopManager,
        default_timeout: Optional[int] = None
    ):
        self.manager = manager
        self.default_timeout = default_timeout

    async def __aenter__(self):
        """实现异步上下文管理器协议，自动管理manager的生命周期"""
        if hasattr(self.manager, '__aenter__'):
            await self.manager.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """实现异步上下文管理器协议，自动管理manager的生命周期"""
        if hasattr(self.manager, '__aexit__'):
            await self.manager.__aexit__(exc_type, exc_val, exc_tb)
            
    def __enter__(self):
        """实现同步上下文管理器协议，自动管理manager的生命周期"""
        if hasattr(self.manager, '__enter__'):
            self.manager.__enter__()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """实现同步上下文管理器协议，自动管理manager的生命周期"""
        if hasattr(self.manager, '__exit__'):
            self.manager.__exit__(exc_type, exc_val, exc_tb)
            
    @asynccontextmanager
    async def asession(self):
        """提供异步上下文管理器，用于管理会话生命周期
        
        示例:
            async with adapter.session():
                # 在这里使用adapter
        """
        try:
            if hasattr(self.manager, '__aenter__'):
                await self.manager.__aenter__()
            yield self
        finally:
            if hasattr(self.manager, '__aexit__'):
                await self.manager.__aexit__(None, None, None)
                
    @contextmanager
    def session(self):
        """提供同步上下文管理器，用于管理会话生命周期
        
        示例:
            with adapter.sync_session():
                # 在这里使用adapter
        """
        try:
            if hasattr(self.manager, '__enter__'):
                self.manager.__enter__()
            yield self
        finally:
            if hasattr(self.manager, '__exit__'):
                self.manager.__exit__(None, None, None)

    def require_approval(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        ret_key: str = "approval_result",
        additional: Optional[str] = "",
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        execute_on_reject: bool = False,
        callback: Optional[Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]] = None,
    ) -> HumanLoopWrapper:
        """审批场景装饰器"""
        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
            
        def decorator(fn):
            return self._approve_cli(fn, task_id, conversation_id, ret_key, additional, metadata, provider_id,  timeout, execute_on_reject, callback)
        return HumanLoopWrapper(decorator)

    def _approve_cli(
        self,
        fn: Callable[[T], R],
        task_id: str,
        conversation_id: str,
        ret_key: str = "approval_result",
        additional: Optional[str] = "",
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        execute_on_reject: bool = False,
        callback: Optional[Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]] = None,
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
            # 判断 callback 是实例还是工厂函数
            cb = None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                # 工厂函数，传入state
                state = args[0] if args else None
                cb = callback(state)
            else:
                cb = callback

            result = await self.manager.request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.APPROVAL,
                context={
                    "message": f"""
Function Name: {fn.__name__}
Function Signature: {str(fn.__code__.co_varnames)}
Arguments: {str(args)}
Keyword Arguments: {str(kwargs)}
Documentation: {fn.__doc__ or "No documentation available"}
""",
                    "question": "Please review and approve/reject this human loop execution.",
                    "additional": additional
                },
                callback=cb,
                metadata=metadata,
                provider_id=provider_id,
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
            return run_async_safely(async_wrapper(*args, **kwargs))

        # 根据被装饰函数类型返回对应的wrapper
        if iscoroutinefunction(fn):
            return async_wrapper # type: ignore
        return sync_wrapper

    def require_conversation(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        state_key: str = "conv_info",
        ret_key: str = "conv_result",
        additional: Optional[str] = "",
        provider_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        callback: Optional[Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]] = None,
    ) -> HumanLoopWrapper:
        """多轮对话场景装饰器"""

        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        def decorator(fn):
            return self._conversation_cli(fn, task_id, conversation_id, state_key, ret_key, additional, provider_id, metadata, timeout, callback)
        return HumanLoopWrapper(decorator)

    def _conversation_cli(
        self,
        fn: Callable[[T], R],
        task_id: str,
        conversation_id: str,
        state_key: str = "conv_info",
        ret_key: str = "conv_result",
        additional: Optional[str] = "",
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        callback: Optional[Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]] = None,
    ) -> Callable[[T], R | None]:
        """多轮对话场景的内部实现装饰器"""

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | None:
            # 判断 callback 是实例还是工厂函数
            cb = None
            state = args[0] if args else None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                cb = callback(state)
            else:
                cb = callback

            node_input = None
            if state:
                # 从State中关键字段获取输入信息
                node_input = state.get(state_key, {})

            # 组合提问内容
            question_content = f"Please respond to the following information:\n{node_input}"
            
            # 检查是否已存在对话，决定使用request_humanloop还是continue_humanloop
            conversation_requests = await self.manager.check_conversation_exist(task_id, conversation_id)
            
            result = None
            if conversation_requests:
                # 已存在对话，使用continue_humanloop
                result = await self.manager.continue_humanloop(
                    conversation_id=conversation_id,
                    context={
                        "message": f"""
Function Name: {fn.__name__}
Function Signature: {str(fn.__code__.co_varnames)}
Arguments: {str(args)}
Keyword Arguments: {str(kwargs)}
Documentation: {fn.__doc__ or "No documentation available"}
""",
                        "question": question_content,
                        "additional": additional
                    },
                    timeout=timeout or self.default_timeout,
                    callback=cb,
                    metadata=metadata,
                    provider_id=provider_id,
                    blocking=True
                )
            else:
                # 新对话，使用request_humanloop
                result = await self.manager.request_humanloop(
                    task_id=task_id,
                    conversation_id=conversation_id,
                    loop_type=HumanLoopType.CONVERSATION,
                    context={
                        "message": f"""
Function Name: {fn.__name__}
Function Signature: {str(fn.__code__.co_varnames)}
Arguments: {str(args)}
Keyword Arguments: {str(kwargs)}
Documentation: {fn.__doc__ or "No documentation available"}
""",
                        "question": question_content,
                        "additional": additional
                    },
                    timeout=timeout or self.default_timeout,
                    callback=cb,
                    metadata=metadata,
                    provider_id=provider_id,
                    blocking=True
                )

            # 初始化对话结果对象为None
            conversation_info = None

            if isinstance(result, HumanLoopResult):
                conversation_info = {
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

            kwargs[ret_key] = conversation_info

            if isinstance(result, HumanLoopResult):
                if iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                return fn(*args, **kwargs)
            else:
                raise ValueError(f"Conversation request timeout or error for {fn.__name__}")

        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | None:
            return run_async_safely(async_wrapper(*args, **kwargs))

        if iscoroutinefunction(fn):
            return async_wrapper # type: ignore
        return sync_wrapper

    def require_info(
        self,
        task_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        ret_key: str = "info_result",
        additional: Optional[str] = "",
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        callback: Optional[Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]] = None,
    ) -> HumanLoopWrapper:
        """信息获取场景装饰器"""

        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        def decorator(fn):
            return self._get_info_cli(fn, task_id, conversation_id, ret_key, additional, metadata, provider_id, timeout, callback)
        return HumanLoopWrapper(decorator)

    def _get_info_cli(
        self,
        fn: Callable[[T], R],
        task_id: str,
        conversation_id: str,
        ret_key: str = "info_result",
        additional: Optional[str] = "",
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        callback: Optional[Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]] = None,
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

              # 判断 callback 是实例还是工厂函数
            cb = None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                # 工厂函数，传入state
                state = args[0] if args else None
                cb = callback(state)
            else:
                cb = callback
                
            result = await self.manager.request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.INFORMATION,
                context={
                    "message": f"""
Function Name: {fn.__name__}
Function Signature: {str(fn.__code__.co_varnames)}
Arguments: {str(args)}
Keyword Arguments: {str(kwargs)}
Documentation: {fn.__doc__ or "No documentation available"}
""",
                    "question": "Please provide the required information for the human loop",
                    "additional": additional
                },
                timeout=timeout or self.default_timeout,
                callback=cb,
                metadata=metadata,
                provider_id=provider_id,
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
           return run_async_safely(async_wrapper(*args, **kwargs))

        # 根据被装饰函数类型返回对应的wrapper
        if iscoroutinefunction(fn):
            return async_wrapper # type: ignore
        return sync_wrapper
    
class LangGraphHumanLoopCallback(HumanLoopCallback):
    """LangGraph专用的人机循环回调，适配TypedDict或Pydantic BaseModel的State"""
    def __init__(
        self,
        state: Any,
        on_update: Optional[Callable[[Any, HumanLoopProvider, HumanLoopResult], Awaitable[None]]] = None,
        on_timeout: Optional[Callable[[Any, HumanLoopProvider], Awaitable[None]]] = None,
        on_error: Optional[Callable[[Any, HumanLoopProvider, Exception], Awaitable[None]]] = None
    ):
        self.state = state
        self.on_update = on_update
        self.on_timeout = on_timeout
        self.on_error = on_error

    async def on_humanloop_update(
        self,
        provider: HumanLoopProvider,
        result: HumanLoopResult
    ):
        if self.on_update:
            await self.on_update(self.state, provider, result)

    async def on_humanloop_timeout(
        self,
        provider: HumanLoopProvider,
    ):
        if self.on_timeout:
            await self.on_timeout(self.state, provider)

    async def on_humanloop_error(
        self,
        provider: HumanLoopProvider,
        error: Exception
    ):
        if self.on_error:
            await self.on_error(self.state, provider, error)


def default_langgraph_callback_factory(state: Any) -> LangGraphHumanLoopCallback:
    """为LangGraph框架提供默认的人机交互回调工厂
    
    该回调专注于:
    1. 记录人机交互事件的日志
    2. 提供调试信息
    3. 收集性能指标
    
    注意: 该回调不会修改state，保持状态管理的清晰性
    
    参数:
        state: LangGraph状态对象，仅用于日志关联
        
    返回:
        配置好的LangGraphHumanLoopCallback实例
    """
    import logging
    
    logger = logging.getLogger("gohumanloop.langgraph")
    
    async def on_update(state, provider: HumanLoopProvider, result: HumanLoopResult):
        """记录人机交互更新事件"""
        logger.info(f"提供者ID: {provider.name}")
        logger.info(
            f"人机交互更新 "
            f"状态={result.status}, "
            f"响应={result.response}, "
            f"响应者={result.responded_by}, "
            f"响应时间={result.responded_at}, "
            f"反馈={result.feedback}"
        )
        

    async def on_timeout(state, provider: HumanLoopProvider):
        """记录人机交互超时事件"""
        
        logger.info(f"提供者ID: {provider.name}")
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.warning(f"人机交互超时 - 发生时间: {current_time}")
        
        
        # 这里可以添加告警逻辑，如发送通知等

    async def on_error(state, provider: HumanLoopProvider, error: Exception):
        """记录人机交互错误事件"""
      
        logger.info(f"提供者ID: {provider.name}")
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.error(f"人机交互错误 -  发生时间: {current_time} 错误信息: {error}")

    return LangGraphHumanLoopCallback(
        state=state,
        on_update=on_update,
        on_timeout=on_timeout,
        on_error=on_error
    )

from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider

# 创建 HumanLoopManager 实例
manager = DefaultHumanLoopManager(initial_providers=TerminalProvider(name="LGDefaultProvider"))

# 创建 LangGraphAdapter 实例
default_adapter = LangGraphAdapter(manager, default_timeout=60)

default_conversation_id = str(uuid.uuid4())

# 修改 interrupt 函数
def interrupt(value: Any, lg_humanloop: LangGraphAdapter = default_adapter) -> Any:
    """
    封装LangGraph的interrupt功能，用于中断图执行并等待人工输入
    
    如果LangGraph版本不支持interrupt，将抛出RuntimeError
    
    参数:
        value: 任何可JSON序列化的值，将展示给人类用户
        lg_humanloop: LangGraphAdapter实例，默认使用全局实例
        
    返回:
        人类用户提供的输入值
    """
    if not _SUPPORTS_INTERRUPT:
        raise RuntimeError(
            "LangGraph版本过低，不支持interrupt功能。请升级到0.2.57或更高版本。"
            "可以使用: pip install --upgrade langgraph>=0.2.57"
        )
    
    # 获取当前事件循环或创建新的
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # 如果没有事件循环，创建一个新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.create_task(lg_humanloop.manager.request_humanloop(
        task_id="lg_interrupt",
        conversation_id=default_conversation_id,
        loop_type=HumanLoopType.INFORMATION,
        context={
            "message": f"{value}",
            "question": "The execution has been interrupted. Please review the above information and provide your input to continue.",
        },
        blocking=False,
    ))
    
    # 返回LangGraph的interrupt
    return _lg_interrupt(value)

def create_resume_command(lg_humanloop: LangGraphAdapter = default_adapter) -> Any:
    """
    创建用于恢复被中断图执行的Command对象
    
    如果LangGraph版本不支持Command，将抛出RuntimeError
    
    参数:
        lg_humanloop: LangGraphAdapter实例，默认使用全局实例
        
    返回:
        Command对象，可用于graph.stream方法
    """
    if not _SUPPORTS_INTERRUPT:
        raise RuntimeError(
            "LangGraph版本过低，不支持Command功能。请升级到0.2.57或更高版本。"
            "可以使用: pip install --upgrade langgraph>=0.2.57"
        )

    # 定义异步轮询函数
    async def poll_for_result():
        poll_interval = 1.0  # 轮询间隔（秒）
        while True:
            result = await lg_humanloop.manager.check_conversation_status(default_conversation_id)
            # 如果状态是最终状态（非PENDING），返回结果
            if result.status != HumanLoopStatus.PENDING:
                return result.response
            # 等待一段时间后再次轮询
            await asyncio.sleep(poll_interval)
    
    # 同步等待异步结果
    response = run_async_safely(poll_for_result())
    return _lg_Command(resume=response)

async def acreate_resume_command(lg_humanloop: LangGraphAdapter = default_adapter) -> Any:
    """
    创建用于恢复被中断图执行的Command对象的异步版本
    
    如果LangGraph版本不支持Command，将抛出RuntimeError
    
    参数:
        lg_humanloop: LangGraphAdapter实例，默认使用全局实例
        
    返回:
        Command对象，可用于graph.astream方法
    """
    if not _SUPPORTS_INTERRUPT:
        raise RuntimeError(
            "LangGraph版本过低，不支持Command功能。请升级到0.2.57或更高版本。"
            "可以使用: pip install --upgrade langgraph>=0.2.57"
        )

    # 定义异步轮询函数
    async def poll_for_result():
        poll_interval = 1.0  # 轮询间隔（秒）
        while True:
            result = await lg_humanloop.manager.check_conversation_status(default_conversation_id)
            # 如果状态是最终状态（非PENDING），返回结果
            if result.status != HumanLoopStatus.PENDING:
                return result.response
            # 等待一段时间后再次轮询
            await asyncio.sleep(poll_interval)
    
    # 直接等待异步结果
    response = await poll_for_result()
    return _lg_Command(resume=response)
    