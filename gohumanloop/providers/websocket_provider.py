import asyncio
import json
import uuid
from typing import Dict, Any, Optional, List, Callable, Awaitable
import websockets
from websockets.exceptions import ConnectionClosed

from gohumanloop.providers.base import BaseProvider
from gohumanloop.core.interface import ApprovalResult, ApprovalStatus

class WebSocketProvider(BaseProvider):
    """通过WebSocket实现人机交互的提供者"""
    
    def __init__(
        self, 
        websocket_url: str, 
        auth_token: Optional[str] = None,
        reconnect_attempts: int = 3,
        reconnect_delay: float = 1.0,
        **kwargs
    ):
        super().__init__(kwargs.get("config"))
        self.websocket_url = websocket_url
        self.auth_token = auth_token
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.connection = None
        self.connected = False
        self.pending_messages = []
        self.message_handlers = {}
        self.connection_task = None
        
    async def connect(self):
        """连接到WebSocket服务器"""
        if self.connected:
            return
            
        attempts = 0
        while attempts < self.reconnect_attempts:
            try:
                headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else None
                self.connection = await websockets.connect(self.websocket_url, extra_headers=headers)
                self.connected = True
                
                # 启动消息处理任务
                self.connection_task = asyncio.create_task(self._handle_messages())
                
                # 发送所有待处理的消息
                for message in self.pending_messages:
                    await self.connection.send(json.dumps(message))
                self.pending_messages = []
                
                return
            except Exception as e:
                attempts += 1
                if attempts >= self.reconnect_attempts:
                    raise ConnectionError(f"Failed to connect to WebSocket server: {str(e)}")
                await asyncio.sleep(self.reconnect_delay)
                
    async def disconnect(self):
        """断开与WebSocket服务器的连接"""
        if self.connection_task:
            self.connection_task.cancel()
            self.connection_task = None
            
        if self.connection:
            await self.connection.close()
            self.connection = None
            
        self.connected = False
        
    async def _handle_messages(self):
        """处理接收到的WebSocket消息"""
        try:
            async for message in self.connection:
                try:
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    if message_type == "approval_update" and "request_id" in data:
                        request_id = data["request_id"]
                        if request_id in self.message_handlers:
                            await self.message_handlers[request_id](data)
                except json.JSONDecodeError:
                    pass  # 忽略无效的JSON
        except ConnectionClosed:
            self.connected = False
            # 尝试重新连接
            asyncio.create_task(self.connect())
            
    async def _send_message(self, message: Dict[str, Any]):
        """发送WebSocket消息"""
        if not self.connected:
            try:
                await self.connect()
            except ConnectionError:
                self.pending_messages.append(message)
                return
                
        try:
            await self.connection.send(json.dumps(message))
        except Exception:
            self.pending_messages.append(message)
            self.connected = False
            # 尝试重新连接
            asyncio.create_task(self.connect())
            
    async def _register_message_handler(
        self, 
        request_id: str, 
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """注册消息处理器"""
        self.message_handlers[request_id] = handler
        
    async def request_approval(
        self,
        task_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> ApprovalResult:
        """通过WebSocket请求人类批准"""
        request_id = self._generate_request_id()
        metadata = metadata or {}
        
        # 存储请求信息
        self._store_request(request_id, task_id, context, metadata, timeout)
        
        # 构建消息
        message = {
            "type": "approval_request",
            "request_id": request_id,
            "task_id": task_id,
            "context": context,
            "metadata": metadata,
            "timeout": timeout
        }
        
        # 发送消息
        await self._send_message(message)
        
        return ApprovalResult(
            request_id=request_id,
            status=ApprovalStatus.PENDING
        )
            
    async def check_approval_status(self, request_id: str) -> ApprovalResult:
        """通过WebSocket检查批准状态"""
        # 构建消息
        message = {
            "type": "approval_status",
            "request_id": request_id
        }
        
        # 创建一个Future来接收响应
        response_future = asyncio.Future()
        
        # 注册消息处理器
        async def handle_response(data):
            status_str = data.get("status", "pending").lower()
            
            # 将字符串状态转换为枚举
            status_map = {
                "pending": ApprovalStatus.PENDING,
                "approved": ApprovalStatus.APPROVED,
                "rejected": ApprovalStatus.REJECTED,
                "expired": ApprovalStatus.EXPIRED,
                "error": ApprovalStatus.ERROR
            }
            status = status_map.get(status_str, ApprovalStatus.PENDING)
            
            result = ApprovalResult(
                request_id=request_id,
                status=status,
                feedback=data.get("feedback"),
                approved_by=data.get("approved_by"),
                approved_at=data.get("approved_at"),
                error=data.get("error")
            )
            
            response_future.set_result(result)
            
        await self._register_message_handler(request_id, handle_response)
        
        # 发送消息
        await self._send_message(message)
        
        try:
            # 等待响应，设置超时
            return await asyncio.wait_for(response_future, timeout=10.0)
        except asyncio.TimeoutError:
            # 如果超时，返回错误结果
            return ApprovalResult(
                request_id=request_id,
                status=ApprovalStatus.ERROR,
                error="WebSocket response timeout"
            )
        finally:
            # 清理消息处理器
            if request_id in self.message_handlers:
                del self.message_handlers[request_id]
                
    async def cancel_approval_request(self, request_id: str) -> bool:
        """通过WebSocket取消批准请求"""
        # 构建消息
        message = {
            "type": "approval_cancel",
            "request_id": request_id
        }
        
        # 发送消息
        await self._send_message(message)
        
        # 从本地存储中删除
        return await super().cancel_approval_request(request_id)