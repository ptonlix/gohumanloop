from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Union
from functools import wraps
import asyncio
import uuid
import time
from inspect import iscoroutinefunction
from contextlib import asynccontextmanager, contextmanager
import logging

from gohumanloop.utils import run_async_safely
from gohumanloop.core.interface import (
    HumanLoopManager,
    HumanLoopResult,
    HumanLoopStatus,
    HumanLoopType,
    HumanLoopCallback,
    HumanLoopProvider,
)
from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider

logger = logging.getLogger(__name__)

# Define TypeVars for input and output types
T = TypeVar("T")
R = TypeVar("R")


# Check LangGraph version
def _check_langgraph_version():
    """Check LangGraph version to determine if interrupt feature is supported"""
    try:
        import importlib.metadata

        version = importlib.metadata.version("langgraph")
        version_parts = version.split(".")
        major, minor, patch = (
            int(version_parts[0]),
            int(version_parts[1]),
            int(version_parts[2]),
        )

        # Interrupt support starts from version 0.2.57
        return major > 0 or (major == 0 and (minor > 2 or (minor == 2 and patch >= 57)))
    except (importlib.metadata.PackageNotFoundError, ValueError, IndexError):
        # If version cannot be determined, assume no support
        return False


# Import corresponding features based on version
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
    """LangGraph adapter for simplifying human-in-the-loop integration

    Provides decorators for three scenarios:
    - require_approval: Requires human approval
    - require_info: Requires human input information
    - require_conversation: Requires multi-turn conversation
    """

    def __init__(
        self, manager: HumanLoopManager, default_timeout: Optional[int] = None
    ):
        self.manager = manager
        self.default_timeout = default_timeout

    async def __aenter__(self):
        """Implements async context manager protocol, automatically manages manager lifecycle"""
        if hasattr(self.manager, "__aenter__"):
            await self.manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Implements async context manager protocol, automatically manages manager lifecycle"""
        if hasattr(self.manager, "__aexit__"):
            await self.manager.__aexit__(exc_type, exc_val, exc_tb)

    def __enter__(self):
        """Implements sync context manager protocol, automatically manages manager lifecycle"""
        if hasattr(self.manager, "__enter__"):
            self.manager.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Implements sync context manager protocol, automatically manages manager lifecycle"""
        if hasattr(self.manager, "__exit__"):
            self.manager.__exit__(exc_type, exc_val, exc_tb)

    @asynccontextmanager
    async def asession(self):
        """Provides async context manager for managing session lifecycle

        Example:
            async with adapter.session():
                # Use adapter here
        """
        try:
            if hasattr(self.manager, "__aenter__"):
                await self.manager.__aenter__()
            yield self
        finally:
            if hasattr(self.manager, "__aexit__"):
                await self.manager.__aexit__(None, None, None)

    @contextmanager
    def session(self):
        """Provides a synchronous context manager for managing session lifecycle

        Example:
            with adapter.sync_session():
                # Use adapter here
        """
        try:
            if hasattr(self.manager, "__enter__"):
                self.manager.__enter__()
            yield self
        finally:
            if hasattr(self.manager, "__exit__"):
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
        callback: Optional[
            Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]
        ] = None,
    ) -> HumanLoopWrapper:
        """Decorator for approval scenario"""
        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        def decorator(fn):
            return self._approve_cli(
                fn,
                task_id,
                conversation_id,
                ret_key,
                additional,
                metadata,
                provider_id,
                timeout,
                execute_on_reject,
                callback,
            )

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
        callback: Optional[
            Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]
        ] = None,
    ) -> Callable[[T], R | None]:
        """
        Converts function type from Callable[[T], R] to Callable[[T], R | None]

        Passes approval results through keyword arguments while maintaining original function signature

        Benefits of this approach:
        1. Maintains original function return type, keeping compatibility with LangGraph workflow
        2. Decorated function can optionally use approval result information
        3. Can pass richer approval context information

        Parameters:
        - fn: Target function to be decorated
        - task_id: Unique task identifier for tracking approval requests
        - conversation_id: Unique conversation identifier for tracking approval sessions
        - ret_key: Parameter name used to inject approval results into function kwargs
        - additional: Additional context information to show to approvers
        - metadata: Optional metadata dictionary passed with request
        - provider_id: Optional provider identifier to route requests
        - timeout: Timeout in seconds for approval response
        - execute_on_reject: Whether to execute function on rejection
        - callback: Optional callback object or factory function for approval events

        Returns:
        - Decorated function maintaining original signature
        - Raises ValueError if approval fails or is rejected

        Notes:
        - Decorated function must accept ret_key parameter to receive approval results
        - If approval is rejected, execution depends on execute_on_reject parameter
        - Approval results contain complete context including:
            - conversation_id: Unique conversation identifier
            - request_id: Unique request identifier
            - loop_type: Type of human loop (APPROVAL)
            - status: Current approval status
            - response: Approver's response
            - feedback: Optional approver feedback
            - responded_by: Approver identity
            - responded_at: Response timestamp
            - error: Error information if any
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | None:
            # Determine if callback is instance or factory function
            cb = None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                # Factory function, pass state
                state = args[0] if args else None
                cb = callback(state)
            else:
                cb = callback

            result = await self.manager.async_request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.APPROVAL,
                context={
                    "message": {
                        "function_name": fn.__name__,
                        "function_signature": str(fn.__code__.co_varnames),
                        "arguments": str(args),
                        "keyword_arguments": str(kwargs),
                        "documentation": fn.__doc__ or "No documentation available",
                    },
                    "question": "Please review and approve/reject this human loop execution.",
                    "additional": additional,
                },
                callback=cb,
                metadata=metadata,
                provider_id=provider_id,
                timeout=timeout or self.default_timeout,
                blocking=True,
            )

            # Initialize approval result object as None
            approval_info = None

            if isinstance(result, HumanLoopResult):
                # If result is HumanLoopResult type, build complete approval info
                approval_info = {
                    "conversation_id": result.conversation_id,
                    "request_id": result.request_id,
                    "loop_type": result.loop_type,
                    "status": result.status,
                    "response": result.response,
                    "feedback": result.feedback,
                    "responded_by": result.responded_by,
                    "responded_at": result.responded_at,
                    "error": result.error,
                }

            kwargs[ret_key] = approval_info
            # Check approval result
            if isinstance(result, HumanLoopResult):
                # Handle based on approval status
                if result.status == HumanLoopStatus.APPROVED:
                    if iscoroutinefunction(fn):
                        return await fn(*args, **kwargs)
                    return fn(*args, **kwargs)
                elif result.status == HumanLoopStatus.REJECTED:
                    # If execute on reject is set, run the function
                    if execute_on_reject:
                        if iscoroutinefunction(fn):
                            return await fn(*args, **kwargs)
                        return fn(*args, **kwargs)
                    # Otherwise return rejection info
                    reason = result.response
                    raise ValueError(
                        f"Function {fn.__name__} execution not approved: {reason}"
                    )
                else:
                    raise ValueError(
                        f"Approval error for {fn.__name__}: approval status: {result.status} and {result.error}"
                    )
            else:
                raise ValueError(f"Unknown approval error: {fn.__name__}")

        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | None:
            return run_async_safely(async_wrapper(*args, **kwargs))

        # Return corresponding wrapper based on decorated function type
        if iscoroutinefunction(fn):
            return async_wrapper  # type: ignore
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
        callback: Optional[
            Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]
        ] = None,
    ) -> HumanLoopWrapper:
        """Decorator for multi-turn conversation scenario"""

        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        def decorator(fn):
            return self._conversation_cli(
                fn,
                task_id,
                conversation_id,
                state_key,
                ret_key,
                additional,
                provider_id,
                metadata,
                timeout,
                callback,
            )

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
        callback: Optional[
            Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]
        ] = None,
    ) -> Callable[[T], R | None]:
        """Internal decorator implementation for multi-turn conversation scenario

        Converts function type from Callable[[T], R] to Callable[[T], R | None]

        Main features:
        1. Conduct multi-turn conversations through human-machine interaction
        2. Inject conversation results into function parameters via ret_key
        3. Support both synchronous and asynchronous function calls

        Parameters:
        - fn: Target function to be decorated
        - task_id: Unique task identifier for tracking human interaction requests
        - conversation_id: Unique conversation identifier for tracking interaction sessions
        - state_key: Key name used to get conversation input info from state
        - ret_key: Parameter name used to inject human interaction results into function kwargs
        - additional: Additional context information to show to users
        - metadata: Optional metadata dictionary passed along with request
        - provider_id: Optional provider identifier to route requests to specific provider
        - timeout: Timeout in seconds for human response, defaults to adapter's default_timeout
        - callback: Optional callback object or factory function for handling human interaction events

        Returns:
        - Decorated function maintaining original signature
        - Raises ValueError if human interaction fails

        Notes:
        - Decorated function must accept ret_key parameter to receive interaction results
        - Interaction results contain complete context information including:
            - conversation_id: Unique conversation identifier
            - request_id: Unique request identifier
            - loop_type: Human interaction type (CONVERSATION)
            - status: Current request status
            - response: Human provided response
            - feedback: Optional human feedback
            - responded_by: Responder identity
            - responded_at: Response timestamp
            - error: Error information if any
        - Automatically adapts to async and sync functions
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | None:
            # Determine if callback is instance or factory function
            cb = None
            state = args[0] if args else None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                cb = callback(state)
            else:
                cb = callback

            node_input = None
            if state:
                # Get input information from key fields in State
                node_input = state.get(state_key, {})

            # Compose question content
            question_content = (
                f"Please respond to the following information:\n{node_input}"
            )

            # Check if conversation exists to determine whether to use request_humanloop or continue_humanloop
            conversation_requests = await self.manager.async_check_conversation_exist(
                task_id, conversation_id
            )

            result = None
            if conversation_requests:
                # Existing conversation, use continue_humanloop
                result = await self.manager.async_continue_humanloop(
                    conversation_id=conversation_id,
                    context={
                        "message": {
                            "function_name": fn.__name__,
                            "function_signature": str(fn.__code__.co_varnames),
                            "arguments": str(args),
                            "keyword_arguments": str(kwargs),
                            "documentation": fn.__doc__ or "No documentation available",
                        },
                        "question": question_content,
                        "additional": additional,
                    },
                    timeout=timeout or self.default_timeout,
                    callback=cb,
                    metadata=metadata,
                    provider_id=provider_id,
                    blocking=True,
                )
            else:
                # New conversation, use request_humanloop
                result = await self.manager.async_request_humanloop(
                    task_id=task_id,
                    conversation_id=conversation_id,
                    loop_type=HumanLoopType.CONVERSATION,
                    context={
                        "message": {
                            "function_name": fn.__name__,
                            "function_signature": str(fn.__code__.co_varnames),
                            "arguments": str(args),
                            "keyword_arguments": str(kwargs),
                            "documentation": fn.__doc__ or "No documentation available",
                        },
                        "question": question_content,
                        "additional": additional,
                    },
                    timeout=timeout or self.default_timeout,
                    callback=cb,
                    metadata=metadata,
                    provider_id=provider_id,
                    blocking=True,
                )

            # Initialize conversation result object as None
            conversation_info = None

            if isinstance(result, HumanLoopResult):
                conversation_info = {
                    "conversation_id": result.conversation_id,
                    "request_id": result.request_id,
                    "loop_type": result.loop_type,
                    "status": result.status,
                    "response": result.response,
                    "feedback": result.feedback,
                    "responded_by": result.responded_by,
                    "responded_at": result.responded_at,
                    "error": result.error,
                }

            kwargs[ret_key] = conversation_info

            if isinstance(result, HumanLoopResult):
                if iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                return fn(*args, **kwargs)
            else:
                raise ValueError(
                    f"Conversation request timeout or error for {fn.__name__}"
                )

        @wraps(fn)
        def sync_wrapper(*args, **kwargs) -> R | None:
            return run_async_safely(async_wrapper(*args, **kwargs))

        if iscoroutinefunction(fn):
            return async_wrapper  # type: ignore
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
        callback: Optional[
            Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]
        ] = None,
    ) -> HumanLoopWrapper:
        """Decorator for information gathering scenario"""

        if task_id is None:
            task_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        def decorator(fn):
            return self._get_info_cli(
                fn,
                task_id,
                conversation_id,
                ret_key,
                additional,
                metadata,
                provider_id,
                timeout,
                callback,
            )

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
        callback: Optional[
            Union[HumanLoopCallback, Callable[[Any], HumanLoopCallback]]
        ] = None,
    ) -> Callable[[T], R | None]:
        """Internal decorator implementation for information gathering scenario
        Converts function type from Callable[[T], R] to Callable[[T], R | None]

        Main features:
        1. Get required information through human-machine interaction
        2. Inject obtained information into function parameters via ret_key
        3. Support both synchronous and asynchronous function calls

        Parameters:
        - fn: Target function to be decorated
        - task_id: Unique task identifier for tracking the human loop request
        - conversation_id: Unique conversation identifier for tracking the interaction session
        - ret_key: Parameter name used to inject the human loop result into function kwargs
        - additional: Additional context information to be shown to human user
        - metadata: Optional metadata dictionary to be passed with the request
        - provider_id: Optional provider identifier to route request to specific provider
        - timeout: Timeout in seconds for human response, defaults to adapter's default_timeout
        - callback: Optional callback object or factory function for handling human loop events

        Returns:
        - Decorated function maintaining original signature
        - Raises ValueError if human interaction fails

        Notes:
        - Decorated function must accept ret_key parameter to receive interaction results
        - Interaction results contain complete context information including:
            - conversation_id: Unique conversation identifier
            - request_id: Unique request identifier
            - loop_type: Type of human loop (INFORMATION)
            - status: Current status of the request
            - response: Human provided response
            - feedback: Optional feedback from human
            - responded_by: Identity of responder
            - responded_at: Response timestamp
            - error: Error information if any
        - Automatically adapts to async and sync functions
        """

        @wraps(fn)
        async def async_wrapper(*args, **kwargs) -> R | None:
            # Determine if callback is an instance or factory function
            # callback: can be HumanLoopCallback instance or factory function
            # - If factory function: accepts state parameter and returns HumanLoopCallback instance
            # - If HumanLoopCallback instance: use directly
            cb = None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                # Factory function mode: get state from args and create callback instance
                # state is typically the first argument, None if args is empty
                state = args[0] if args else None
                cb = callback(state)
            else:
                cb = callback

            result = await self.manager.async_request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=HumanLoopType.INFORMATION,
                context={
                    "message": {
                        "function_name": fn.__name__,
                        "function_signature": str(fn.__code__.co_varnames),
                        "arguments": str(args),
                        "keyword_arguments": str(kwargs),
                        "documentation": fn.__doc__ or "No documentation available",
                    },
                    "question": "Please provide the required information for the human loop",
                    "additional": additional,
                },
                timeout=timeout or self.default_timeout,
                callback=cb,
                metadata=metadata,
                provider_id=provider_id,
                blocking=True,
            )

            # 初始化审批结果对象为None
            resp_info = None

            if isinstance(result, HumanLoopResult):
                # 如果结果是HumanLoopResult类型，则构建完整的审批信息
                resp_info = {
                    "conversation_id": result.conversation_id,
                    "request_id": result.request_id,
                    "loop_type": result.loop_type,
                    "status": result.status,
                    "response": result.response,
                    "feedback": result.feedback,
                    "responded_by": result.responded_by,
                    "responded_at": result.responded_at,
                    "error": result.error,
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
            return async_wrapper  # type: ignore
        return sync_wrapper


class LangGraphHumanLoopCallback(HumanLoopCallback):
    """LangGraph-specific human loop callback, compatible with TypedDict or Pydantic BaseModel State"""

    def __init__(
        self,
        state: Any,
        async_on_update: Optional[
            Callable[[Any, HumanLoopProvider, HumanLoopResult], Awaitable[None]]
        ] = None,
        async_on_timeout: Optional[
            Callable[[Any, HumanLoopProvider], Awaitable[None]]
        ] = None,
        async_on_error: Optional[
            Callable[[Any, HumanLoopProvider, Exception], Awaitable[None]]
        ] = None,
    ):
        self.state = state
        self.async_on_update = async_on_update
        self.async_on_timeout = async_on_timeout
        self.async_on_error = async_on_error

    async def async_on_humanloop_update(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ):
        if self.async_on_update:
            await self.async_on_update(self.state, provider, result)

    async def async_on_humanloop_timeout(
        self,
        provider: HumanLoopProvider,
    ):
        if self.async_on_timeout:
            await self.async_on_timeout(self.state, provider)

    async def async_on_humanloop_error(
        self, provider: HumanLoopProvider, error: Exception
    ):
        if self.async_on_error:
            await self.async_on_error(self.state, provider, error)


def default_langgraph_callback_factory(state: Any) -> LangGraphHumanLoopCallback:
    """Default human-loop callback factory for LangGraph framework

    This callback focuses on:
    1. Logging human interaction events
    2. Providing debug information
    3. Collecting performance metrics

    Note: This callback does not modify state to maintain clear state management

    Args:
        state: LangGraph state object, only used for log correlation

    Returns:
        Configured LangGraphHumanLoopCallback instance
    """

    async def async_on_update(
        state, provider: HumanLoopProvider, result: HumanLoopResult
    ):
        """Log human interaction update events"""
        logger.info(f"Provider ID: {provider.name}")
        logger.info(
            f"Human interaction update "
            f"status={result.status}, "
            f"response={result.response}, "
            f"responded_by={result.responded_by}, "
            f"responded_at={result.responded_at}, "
            f"feedback={result.feedback}"
        )

    async def async_on_timeout(state, provider: HumanLoopProvider):
        """Log human interaction timeout events"""

        logger.info(f"Provider ID: {provider.name}")
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.warning(f"Human interaction timeout - Time: {current_time}")

        # Alert logic can be added here, such as sending notifications

    async def async_on_error(state, provider: HumanLoopProvider, error: Exception):
        """Log human interaction error events"""

        logger.info(f"Provider ID: {provider.name}")
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.error(f"Human interaction error - Time: {current_time} Error: {error}")

    return LangGraphHumanLoopCallback(
        state=state,
        async_on_update=async_on_update,
        async_on_timeout=async_on_timeout,
        async_on_error=async_on_error,
    )


# Create HumanLoopManager instance
manager = DefaultHumanLoopManager(
    initial_providers=TerminalProvider(name="LGDefaultProvider")
)

# Create LangGraphAdapter instance
default_adapter = LangGraphAdapter(manager, default_timeout=60)

default_conversation_id = str(uuid.uuid4())

_SKIP_NEXT_HUMANLOOP = False


def interrupt(value: Any, lg_humanloop: LangGraphAdapter = default_adapter) -> Any:
    """
    Wraps LangGraph's interrupt functionality to pause graph execution and wait for human input

    Raises RuntimeError if LangGraph version doesn't support interrupt

    Args:
        value: Any JSON-serializable value that will be shown to human user
        lg_humanloop: LangGraphAdapter instance, defaults to global instance

    Returns:
        Input value provided by human user
    """

    global _SKIP_NEXT_HUMANLOOP

    if not _SUPPORTS_INTERRUPT:
        raise RuntimeError(
            "LangGraph version too low, interrupt not supported. Please upgrade to version 0.2.57 or higher."
            "You can use: pip install --upgrade langgraph>=0.2.57"
        )

    if not _SKIP_NEXT_HUMANLOOP:
        # Get current event loop or create new one
        try:
            lg_humanloop.manager.request_humanloop(
                task_id="lg_interrupt",
                conversation_id=default_conversation_id,
                loop_type=HumanLoopType.INFORMATION,
                context={
                    "message": f"{value}",
                    "question": "The execution has been interrupted. Please review the above information and provide your input to continue.",
                },
                blocking=False,
            )
        except Exception as e:
            logger.exception(f"Error in interrupt: {e}")
    else:
        # Reset flag to allow normal human intervention trigger next time
        _SKIP_NEXT_HUMANLOOP = False

    # Return LangGraph's interrupt
    return _lg_interrupt(value)


def create_resume_command(lg_humanloop: LangGraphAdapter = default_adapter) -> Any:
    """
    Create a Command object to resume interrupted graph execution

    Will raise RuntimeError if LangGraph version doesn't support Command

    Args:
        lg_humanloop: LangGraphAdapter instance, defaults to global instance

    Returns:
        Command object that can be used with graph.stream method
    """

    global _SKIP_NEXT_HUMANLOOP

    if not _SUPPORTS_INTERRUPT:
        raise RuntimeError(
            "LangGraph version too low, Command feature not supported. Please upgrade to 0.2.57 or higher."
            "You can use: pip install --upgrade langgraph>=0.2.57"
        )

    # Define async polling function
    def poll_for_result():
        poll_interval = 1.0  # Polling interval (seconds)
        while True:
            result = lg_humanloop.manager.check_conversation_status(
                default_conversation_id
            )
            # If status is final state (not PENDING), return result
            if result.status != HumanLoopStatus.PENDING:
                return result.response
            # Wait before polling again
            time.sleep(poll_interval)

    _SKIP_NEXT_HUMANLOOP = True

    response = poll_for_result()
    return _lg_Command(resume=response)


async def acreate_resume_command(
    lg_humanloop: LangGraphAdapter = default_adapter
) -> Any:
    """
    Create an async version of Command object to resume interrupted graph execution

    Will raise RuntimeError if LangGraph version doesn't support Command

    Args:
        lg_humanloop: LangGraphAdapter instance, defaults to global instance

    Returns:
        Command object that can be used with graph.astream method
    """
    global _SKIP_NEXT_HUMANLOOP

    if not _SUPPORTS_INTERRUPT:
        raise RuntimeError(
            "LangGraph version too low, Command feature not supported. Please upgrade to 0.2.57 or higher."
            "You can use: pip install --upgrade langgraph>=0.2.57"
        )

    # Define async polling function
    async def poll_for_result():
        poll_interval = 1.0  # Polling interval (seconds)
        while True:
            result = await lg_humanloop.manager.async_check_conversation_status(
                default_conversation_id
            )
            # If status is final state (not PENDING), return result
            if result.status != HumanLoopStatus.PENDING:
                return result.response
            # Wait before polling again
            await asyncio.sleep(poll_interval)

    _SKIP_NEXT_HUMANLOOP = True

    # Wait for async result directly
    response = await poll_for_result()
    return _lg_Command(resume=response)
