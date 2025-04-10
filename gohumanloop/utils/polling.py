import asyncio
from typing import Callable, Any, Optional, TypeVar, Awaitable

T = TypeVar('T')

class PollingHelper:
    """轮询辅助工具"""
    
    @staticmethod
    async def poll_until(
        poll_func: Callable[[], Awaitable[T]],
        condition_func: Callable[[T], bool],
        interval: float = 1.0,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        on_timeout: Optional[Callable[[], Awaitable[T]]] = None,
        on_max_retries: Optional[Callable[[], Awaitable[T]]] = None
    ) -> T:
        """
        轮询直到满足条件
        
        Args:
            poll_func: 轮询函数，返回要检查的值
            condition_func: 条件函数，检查轮询结果是否满足条件
            interval: 轮询间隔（秒）
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
            on_timeout: 超时时的回调函数
            on_max_retries: 达到最大重试次数时的回调函数
            
        Returns:
            满足条件的轮询结果
        """
        start_time = asyncio.get_event_loop().time()
        retries = 0
        
        while True:
            # 检查是否超时
            if timeout is not None and (asyncio.get_event_loop().time() - start_time) >= timeout:
                if on_timeout:
                    return await on_timeout()
                raise TimeoutError(f"Polling timed out after {timeout} seconds")
                
            # 检查是否达到最大重试次数
            if max_retries is not None and retries >= max_retries:
                if on_max_retries:
                    return await on_max_retries()
                raise RuntimeError(f"Polling reached maximum retries ({max_retries})")
                
            # 执行轮询
            result = await poll_func()
            
            # 检查条件
            if condition_func(result):
                return result
                
            # 等待下一次轮询
            await asyncio.sleep(interval)
            retries += 1