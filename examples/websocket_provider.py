import asyncio
import gohumanloop as ghl
from gohumanloop.providers.websocket_provider import WebSocketProvider

async def main():
    # 创建 WebSocket 提供者
    provider = WebSocketProvider(
        websocket_url="wss://api.gohumanloop.com/ws",
        auth_token="your_api_key"
    )
    
    # 创建管理器
    manager = ghl.create_manager(provider)
    
    # 连接到 WebSocket 服务器
    await provider.connect()
    
    # 创建回调
    class MyCallback(ghl.ApprovalCallback):
        async def on_approval_received(self, request_id, result):
            print(f"收到批准结果: {result.status.value}")
            print(f"反馈: {result.feedback}")
            
        async def on_approval_timeout(self, request_id):
            print(f"请求 {request_id} 超时")
            
        async def on_approval_error(self, request_id, error):
            print(f"请求 {request_id} 错误: {error}")
    
    # 请求批准（非阻塞模式）
    request_id = await manager.request_approval(
        task_id="websocket_example",
        context={
            "title": "WebSocket 批准示例",
            "description": "这是一个使用 WebSocket 的批准请求示例",
            "action": "执行重要操作"
        },
        callback=MyCallback(),
        blocking=False,
        timeout=120  # 2分钟超时
    )
    
    print(f"已发送批准请求，ID: {request_id}")
    
    # 等待一段时间后检查状态
    await asyncio.sleep(10)
    result = await manager.check_status(request_id)
    print(f"当前状态: {result.status.value}")
    
    # 等待更长时间以便接收回调
    await asyncio.sleep(60)
    
    # 断开连接
    await provider.disconnect()

if __name__ == "__main__":
    asyncio.run(main())