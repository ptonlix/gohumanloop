import asyncio
import os
from typing import Awaitable, Any, Optional, Union
from pydantic import SecretStr
import logging

logger = logging.getLogger(__name__)


def run_async_safely(coro: Awaitable[Any]) -> Any:
    """
    Safely run async coroutines in synchronous environment
    Will raise RuntimeError if called in async environment
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # No running event loop
        loop = None

    if loop is not None:
        raise RuntimeError(
            "Detected running event loop! "
            "You should use 'await' directly instead of run_async_safely(). "
            "If you really need to call sync code from async context, "
            "consider using asyncio.to_thread() or other proper methods."
        )

    # Handle synchronous environment
    try:
        loop = asyncio.get_event_loop()
        logger.debug("Using existing event loop.")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        own_loop = True
        logger.debug("Created new event loop.")
    else:
        own_loop = False

    try:
        return loop.run_until_complete(coro)
    finally:
        if own_loop and not loop.is_closed():
            loop.close()
            asyncio.set_event_loop(None)


def get_secret_from_env(
    key: Union[str, list, tuple],
    default: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[SecretStr]:
    """Get a value from an environment variable."""
    if isinstance(key, (list, tuple)):
        for k in key:
            if k in os.environ:
                return SecretStr(os.environ[k])
    if isinstance(key, str) and key in os.environ:
        return SecretStr(os.environ[key])
    if isinstance(default, str):
        return SecretStr(default)
    if default is None:
        return None
    if error_message:
        raise ValueError(error_message)
    msg = (
        f"Did not find {key}, please add an environment variable"
        f" `{key}` which contains it, or pass"
        f" `{key}` as a named parameter."
    )
    raise ValueError(msg)
