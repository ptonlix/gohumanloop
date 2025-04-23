import asyncio
import os
from typing import Optional, Union
from pydantic import SecretStr
def run_async_safely(coro):
    """安全地运行异步协程，避免事件循环冲突"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # 如果没有事件循环，创建一个新的
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)


def get_secret_from_env(
    key: Union[str, list, tuple],
    default: Optional[str] = None,
    error_message: Optional[str] = None
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