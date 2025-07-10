from typing import (
    cast,
    Dict,
    List,
    Any,
    Optional,
    Callable,
    TypeVar,
    Union,
    Type,
    AsyncIterator,
    Iterator,
    Coroutine,
)
from types import TracebackType
from functools import wraps
import uuid
from inspect import iscoroutinefunction
from contextlib import asynccontextmanager, contextmanager
import logging

from gohumanloop.utils import run_async_safely, generate_function_summary
from gohumanloop.core.interface import (
    HumanLoopRequest,
    HumanLoopResult,
    HumanLoopStatus,
    HumanLoopType,
    HumanLoopCallback,
    HumanLoopProvider,
    HumanLoopManager,
)

logger = logging.getLogger(__name__)

# Define TypeVars for input and output types
T = TypeVar("T")
R = TypeVar("R", bound=Union[Any, None])


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


class HumanloopAdapter:
    """Humanloop adapter for simplifying human-in-the-loop integration

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

    async def __aenter__(self) -> "HumanloopAdapter":
        """Implements async context manager protocol, automatically manages manager lifecycle"""

        manager = cast(Any, self.manager)
        if hasattr(manager, "__aenter__"):
            await manager.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Implements async context manager protocol, automatically manages manager lifecycle"""

        manager = cast(Any, self.manager)
        if hasattr(manager, "__aexit__"):
            await manager.__aexit__(exc_type, exc_val, exc_tb)

        return None

    def __enter__(self) -> "HumanloopAdapter":
        """Implements sync context manager protocol, automatically manages manager lifecycle"""

        manager = cast(Any, self.manager)
        if hasattr(manager, "__enter__"):
            manager.__enter__()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Implements sync context manager protocol, automatically manages manager lifecycle"""

        manager = cast(Any, self.manager)
        if hasattr(manager, "__exit__"):
            manager.__exit__(exc_type, exc_val, exc_tb)

        return None

    @asynccontextmanager
    async def asession(self) -> AsyncIterator["HumanloopAdapter"]:
        """Provides async context manager for managing session lifecycle

        Example:
            async with adapter.session():
                # Use adapter here
        """
        try:
            manager = cast(Any, self.manager)
            if hasattr(manager, "__aenter__"):
                await manager.__aenter__()
            yield self
        finally:
            if hasattr(manager, "__aexit__"):
                await manager.__aexit__(None, None, None)

    @contextmanager
    def session(self) -> Iterator["HumanloopAdapter"]:
        """Provides a synchronous context manager for managing session lifecycle

        Example:
            with adapter.sync_session():
                # Use adapter here
        """
        try:
            manager = cast(Any, self.manager)
            if hasattr(manager, "__enter__"):
                manager.__enter__()
            yield self
        finally:
            if hasattr(manager, "__exit__"):
                manager.__exit__(None, None, None)

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

        def decorator(fn: Callable) -> Callable:
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
    ) -> Union[
        Callable[[T], Coroutine[Any, Any, R]],  # For async functions
        Callable[[T], R],  # For sync functions
    ]:
        """
        Converts function type from Callable[[T], R] to Callable[[T], R]

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
        async def async_wrapper(*args: Any, **kwargs: Any) -> R:
            # Check if ret_key exists in function parameters
            if ret_key not in fn.__code__.co_varnames:
                raise ValueError(
                    f"Function {fn.__name__} must have parameter named {ret_key}"
                )

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
                    "message": generate_function_summary(fn, args, kwargs),
                    "function": {
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

                # Inject approval info into kwargs
                kwargs[ret_key] = approval_info

            # Check approval result
            if isinstance(result, HumanLoopResult):
                # Handle based on approval status
                if result.status == HumanLoopStatus.APPROVED:
                    if iscoroutinefunction(fn):
                        ret = await fn(*args, **kwargs)
                    else:
                        ret = fn(*args, **kwargs)
                    return cast(R, ret)
                elif result.status == HumanLoopStatus.REJECTED:
                    # If execute on reject is set, run the function
                    if execute_on_reject:
                        if iscoroutinefunction(fn):
                            ret = await fn(*args, **kwargs)
                        else:
                            ret = fn(*args, **kwargs)
                        return cast(R, ret)
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
        def sync_wrapper(*args: Any, **kwargs: Any) -> R:
            ret = run_async_safely(async_wrapper(*args, **kwargs))
            return cast(R, ret)

        # Return corresponding wrapper based on decorated function type
        if iscoroutinefunction(fn):
            return async_wrapper
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

        def decorator(fn: Callable) -> Callable:
            return self._conversation_cli(
                fn,
                task_id,
                conversation_id,
                state_key,
                ret_key,
                additional,
                metadata,
                provider_id,
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
    ) -> Union[
        Callable[[T], Coroutine[Any, Any, R]],  # For async functions
        Callable[[T], R],  # For sync functions
    ]:
        """Internal decorator implementation for multi-turn conversation scenario

        Converts function type from Callable[[T], R] to Callable[[T], R]

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
        async def async_wrapper(*args: Any, **kwargs: Any) -> R:
            # Check if ret_key exists in function parameters
            if ret_key not in fn.__code__.co_varnames:
                raise ValueError(
                    f"Function {fn.__name__} must have parameter named {ret_key}"
                )

            # Determine if callback is instance or factory function
            cb = None
            state = args[0] if args else None
            if callable(callback) and not isinstance(callback, HumanLoopCallback):
                cb = callback(state)
            else:
                cb = callback

            # First try to get node_input from kwargs using state_key
            node_input = kwargs.get(state_key)

            # If not found in kwargs, try to get from first argument (state)
            if node_input is None and state and isinstance(state, dict):
                node_input = state.get(state_key, {})

            # If still not found, use empty dict as default
            if node_input is None:
                node_input = {}

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
                        "message": generate_function_summary(fn, args, kwargs),
                        "function": {
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
                # Inject conversation info into kwargs
                kwargs[ret_key] = conversation_info

            if isinstance(result, HumanLoopResult):
                if iscoroutinefunction(fn):
                    ret = await fn(*args, **kwargs)
                else:
                    ret = fn(*args, **kwargs)
                return cast(R, ret)
            else:
                raise ValueError(
                    f"Conversation request timeout or error for {fn.__name__}"
                )

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> R:
            ret = run_async_safely(async_wrapper(*args, **kwargs))
            return cast(R, ret)

        if iscoroutinefunction(fn):
            return async_wrapper
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

        def decorator(fn: Callable) -> Callable:
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
    ) -> Union[
        Callable[[T], Coroutine[Any, Any, R]],  # For async functions
        Callable[[T], R],  # For sync functions
    ]:
        """Internal decorator implementation for information gathering scenario
        Converts function type from Callable[[T], R] to Callable[[T], R]

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
        async def async_wrapper(*args: Any, **kwargs: Any) -> R:
            # Check if ret_key exists in function parameters
            if ret_key not in fn.__code__.co_varnames:
                raise ValueError(
                    f"Function {fn.__name__} must have parameter named {ret_key}"
                )

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
                    "message": generate_function_summary(fn, args, kwargs),
                    "function": {
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
            # Initialize response info object as None
            resp_info = None

            if isinstance(result, HumanLoopResult):
                # If result is HumanLoopResult type, build complete response info
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
                # Inject approval info into kwargs
                kwargs[ret_key] = resp_info

            # Check if result is valid
            if isinstance(result, HumanLoopResult):
                # Return the information result, let user decide whether to use it
                # Handle based on completed status
                if result.status == HumanLoopStatus.COMPLETED:
                    if iscoroutinefunction(fn):
                        ret = await fn(*args, **kwargs)
                    else:
                        ret = fn(*args, **kwargs)
                    return cast(R, ret)
                else:
                    raise ValueError(
                        f"Function {fn.__name__} infomartion request error: {result.status}"
                    )
            else:
                raise ValueError(f"Info request timeout or error for {fn.__name__}")

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> R:
            ret = run_async_safely(async_wrapper(*args, **kwargs))
            return cast(R, ret)

        # Return corresponding wrapper based on decorated function type
        if iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper


class AgentOpsHumanLoopCallback(HumanLoopCallback):
    """AgentOps-specific human loop callback, compatible with TypedDict or Pydantic BaseModel State

    This implementation integrates with AgentOps for monitoring and tracking human-in-the-loop interactions.
    It records events, tracks metrics, and provides observability for human-agent interactions.
    """

    def __init__(self, session_tags: Optional[List[str]] = None) -> None:
        self.session_tags = session_tags or ["gohumanloop"]
        self._operation = None
        self._initialize_agentops()

    def _initialize_agentops(self) -> None:
        """Initialize AgentOps if available, otherwise fall back gracefully."""
        try:
            import importlib.util

            if importlib.util.find_spec("agentops"):
                from agentops.sdk import operation  # type: ignore
                import agentops  # type: ignore

                self._operation = operation
                agentops.init(tags=self.session_tags)
            else:
                raise ImportError(
                    "AgentOps package not installed. Features disabled. "
                    "Please install with: pip install agentops"
                )
        except Exception as e:
            logger.warning(f"AgentOps initialization failed: {e}")

    @property
    def operation_decorator(self) -> Callable:
        """Return the appropriate decorator based on AgentOps availability."""
        return self._operation if self._operation is not None else lambda f: f

    async def async_on_humanloop_request(
        self, provider: HumanLoopProvider, request: HumanLoopRequest
    ) -> Any:
        """Handle human loop start events."""

        @self.operation_decorator
        async def callback_humanloop_request() -> Any:
            # Create event data
            event_data = {
                "event_type": "gohumanloop_request",
                "provider": provider.name,
                "task_id": request.task_id,
                "conversation_id": request.conversation_id,
                "request_id": request.request_id,
                "loop_type": request.loop_type.value,
                "context": request.context,
                "metadata": request.metadata,
                "timeout": request.timeout,
                "created_at": request.created_at,
            }
            return event_data

        return await callback_humanloop_request()

    async def async_on_humanloop_update(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        """Handle human loop update events.

        Args:
            provider: The human loop provider instance
            result: The human loop result containing status and response
        """

        @self.operation_decorator
        async def callback_humanloop_update() -> Any:
            # Create event data
            event_data = {
                "event_type": "gohumanloop_update",
                "provider": provider.name,
                "conversation_id": result.conversation_id,
                "request_id": result.request_id,
                "loop_type": result.loop_type.value,
                "status": result.status.value,
                "response": result.response,
                "feedback": result.feedback,
                "responded_by": result.responded_by,
                "responded_at": result.responded_at,
                "error": result.error,
            }

            return event_data

        return await callback_humanloop_update()

    async def async_on_humanloop_timeout(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        """Handle human loop timeout events.

        Args:
            provider: The human loop provider instance
        """

        @self.operation_decorator
        async def callback_humanloop_timeout() -> Any:
            # Create error event
            error_data = {
                "event_type": "gohumanloop_timeout",
                "provider": provider.name,
                "conversation_id": result.conversation_id,
                "request_id": result.request_id,
                "loop_type": result.loop_type.value,
                "status": result.status.value,
                "response": result.response,
                "feedback": result.feedback,
                "responded_by": result.responded_by,
                "responded_at": result.responded_at,
                "error": result.error,
            }

            return error_data

        return await callback_humanloop_timeout()

    async def async_on_humanloop_error(
        self, provider: HumanLoopProvider, error: Exception
    ) -> Any:
        """Handle human loop error events.

        Args:
            provider: The human loop provider instance
            error: The exception that occurred
        """

        @self.operation_decorator
        async def callback_humanloop_error() -> Any:
            # Create error event
            error_data = {
                "event_type": "gohumanloop_error",
                "provider": provider.name,
                "error": str(error),
            }

            # Record the error event
            return error_data

        return await callback_humanloop_error()
