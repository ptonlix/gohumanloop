from typing import (
    Dict,
    Any,
    Optional,
    Callable,
    Awaitable,
    TypeVar,
    Union,
)
import asyncio
import uuid
import time
import logging

from gohumanloop.core.interface import (
    HumanLoopRequest,
    HumanLoopResult,
    HumanLoopStatus,
    HumanLoopType,
    HumanLoopCallback,
    HumanLoopProvider,
)
from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.terminal_provider import TerminalProvider
from gohumanloop.adapters.base_adapter import HumanloopAdapter

logger = logging.getLogger(__name__)

# Define TypeVars for input and output types
T = TypeVar("T")
R = TypeVar("R", bound=Union[Any, None])


# Check LangGraph version
def _check_langgraph_version() -> bool:
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


class LangGraphHumanLoopCallback(HumanLoopCallback):
    """LangGraph-specific human loop callback, compatible with TypedDict or Pydantic BaseModel State"""

    def __init__(
        self,
        state: Any,
        async_on_request: Optional[
            Callable[[Any, HumanLoopProvider, HumanLoopRequest], Awaitable[Any]]
        ] = None,
        async_on_update: Optional[
            Callable[[Any, HumanLoopProvider, HumanLoopResult], Awaitable[Any]]
        ] = None,
        async_on_timeout: Optional[
            Callable[[Any, HumanLoopProvider, HumanLoopResult], Awaitable[Any]]
        ] = None,
        async_on_error: Optional[
            Callable[[Any, HumanLoopProvider, Exception], Awaitable[Any]]
        ] = None,
    ) -> None:
        self.state = state
        self.async_on_request = async_on_request
        self.async_on_update = async_on_update
        self.async_on_timeout = async_on_timeout
        self.async_on_error = async_on_error

    async def async_on_humanloop_request(
        self, provider: HumanLoopProvider, request: HumanLoopRequest
    ) -> Any:
        if self.async_on_request:
            await self.async_on_request(self.state, provider, request)

    async def async_on_humanloop_update(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        if self.async_on_update:
            await self.async_on_update(self.state, provider, result)

    async def async_on_humanloop_timeout(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        if self.async_on_timeout:
            await self.async_on_timeout(self.state, provider, result)

    async def async_on_humanloop_error(
        self, provider: HumanLoopProvider, error: Exception
    ) -> Any:
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

    async def async_on_request(
        state: Any, provider: HumanLoopProvider, request: HumanLoopRequest
    ) -> Any:
        """Log human interaction request events"""
        logger.info(f"Provider ID: {provider.name}")
        logger.info(
            f"Human interaction request "
            f"task_id={request.task_id}, "
            f"conversation_id={request.conversation_id}, "
            f"loop_type={request.loop_type}, "
            f"context={request.context}, "
            f"metadata={request.metadata}, "
            f"timeout={request.timeout}, "
            f"created_at={request.created_at}"
        )

    async def async_on_update(
        state: Any, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        """Log human interaction update events"""
        logger.info(f"Provider ID: {provider.name}")
        logger.info(
            f"Human interaction update "
            f"conversation_id={result.conversation_id}, "
            f"request_id={result.request_id},"
            f"status={result.status}, "
            f"response={result.response}, "
            f"responded_by={result.responded_by}, "
            f"responded_at={result.responded_at}, "
            f"feedback={result.feedback}"
        )

    async def async_on_timeout(
        state: Any, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        """Log human interaction timeout events"""

        logger.info(f"Provider ID: {provider.name}")
        logger.info(
            f"Human interaction timeout "
            f"conversation_id={result.conversation_id}, "
            f"request_id={result.request_id},"
            f"status={result.status}, "
            f"response={result.response}, "
            f"responded_by={result.responded_by}, "
            f"responded_at={result.responded_at}, "
            f"feedback={result.feedback}"
        )
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.warning(f"Human interaction timeout - Time: {current_time}")

        # Alert logic can be added here, such as sending notifications

    async def async_on_error(
        state: Any, provider: HumanLoopProvider, error: Exception
    ) -> Any:
        """Log human interaction error events"""

        logger.info(f"Provider ID: {provider.name}")
        from datetime import datetime

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.error(f"Human interaction error - Time: {current_time} Error: {error}")

    return LangGraphHumanLoopCallback(
        state=state,
        async_on_request=async_on_request,
        async_on_update=async_on_update,
        async_on_timeout=async_on_timeout,
        async_on_error=async_on_error,
    )


# Create HumanLoopManager instance
manager = DefaultHumanLoopManager(
    initial_providers=TerminalProvider(name="LGDefaultProvider")
)

# Create LangGraphAdapter instance
default_adapter = HumanloopAdapter(manager, default_timeout=60)

default_conversation_id = str(uuid.uuid4())

_SKIP_NEXT_HUMANLOOP = False


def interrupt(value: Any, lg_humanloop: HumanloopAdapter = default_adapter) -> Any:
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


def create_resume_command(lg_humanloop: HumanloopAdapter = default_adapter) -> Any:
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
    def poll_for_result() -> Optional[Dict[str, Any]]:
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
    lg_humanloop: HumanloopAdapter = default_adapter
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
    async def poll_for_result() -> Optional[Dict[str, Any]]:
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
