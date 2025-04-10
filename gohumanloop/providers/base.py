from abc import ABC
from typing import Dict, Any, Optional, List
import asyncio
import time
import uuid
from datetime import datetime

from gohumanloop.core.interface import HumanLoopProvider, ApprovalResult, ApprovalStatus

class BaseProvider(HumanLoopProvider, ABC):
    """基础人机交互提供者实现"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._requests = {}  # 存储请求信息
        
    def _generate_request_id(self) -> str:
        """生成唯一请求ID"""
        return str(uuid.uuid4())
        
    def _store_request(self, request_id: str, task_id: str, context: Dict[str, Any], 
                      metadata: Dict[str, Any], timeout: Optional[int]) -> None:
        """存储请求信息"""
        self._requests[request_id] = {
            "task_id": task_id,
            "context": context,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
            "status": ApprovalStatus.PENDING,
            "timeout": timeout
        }
        
    async def cancel_approval_request(self, request_id: str) -> bool:
        """取消批准请求的基本实现"""
        if request_id in self._requests:
            del self._requests[request_id]
            return True
        return False