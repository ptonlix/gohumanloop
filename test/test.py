import asyncio

async def nested_coroutine():
    print("Nested coroutine running")
    await asyncio.sleep(1)
    return "Nested result"

async def main():
    print("Main coroutine running")
    result = run_async_safely(nested_coroutine())  # 在 asyncio.run() 内部调用
    print("Got result:", result)

def run_async_safely(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

asyncio.run(main())