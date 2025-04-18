from abc import ABC
from typing import Dict, Any, Optional, List, Tuple
import asyncio
import time
import uuid
from datetime import datetime
from collections import defaultdict

from gohumanloop.core.interface import (
    HumanLoopProvider, HumanLoopResult, HumanLoopStatus, HumanLoopType
)

class BaseProvider(HumanLoopProvider, ABC):
    """基础人机循环提供者实现"""
    
    def __init__(self, name: str,  config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # 用户自定义名称，如果未提供则使用UUID
        self.name = name
        # 存储请求信息，使用 (conversation_id, request_id) 作为键
        self._requests = {}
        # 存储对话信息，包括对话中的请求列表和最新请求ID
        self._conversations = {}
        # 用于快速查找对话中的请求
        self._conversation_requests = defaultdict(list)
        # 存储超时任务
        self._timeout_tasks = {}

    def __str__(self) -> str:
        """返回该实例的描述信息"""
        total_conversations = len(self._conversations)
        total_requests = len(self._requests)
        active_requests = sum(1 for req in self._requests.values()
                            if req["status"] in [HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS])
        
        return (f"conversations={total_conversations}, "
                f"total_requests={total_requests}, "
                f"active_requests={active_requests})")
    
    def __repr__(self) -> str:
        """返回该实例的详细描述信息"""
        return self.__str__()

    def _generate_request_id(self) -> str:
        """生成唯一请求ID"""
        return str(uuid.uuid4())
        
    def _store_request(
        self,
        conversation_id: str,
        request_id: str,
        task_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Dict[str, Any],
        timeout: Optional[int],
    ) -> None:
        """存储请求信息"""
        # 使用元组 (conversation_id, request_id) 作为键存储请求信息
        self._requests[(conversation_id, request_id)] = {
            "task_id": task_id,
            "loop_type": loop_type,
            "context": context,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
            "status": HumanLoopStatus.PENDING,
            "timeout": timeout,
        }
        
        # 更新对话信息
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = {
                "task_id": task_id,
                "latest_request_id": None,
                "created_at": datetime.now().isoformat(),
            }
        
        # 添加请求到对话的请求列表
        self._conversation_requests[conversation_id].append(request_id)
        # 更新最新请求ID
        self._conversations[conversation_id]["latest_request_id"] = request_id
        
    def _get_request(self, conversation_id: str, request_id: str) -> Optional[Dict[str, Any]]:
        """获取请求信息"""
        return self._requests.get((conversation_id, request_id))
        
    def _get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取对话信息"""
        return self._conversations.get(conversation_id)
        
    def _get_conversation_requests(self, conversation_id: str) -> List[str]:
        """获取对话中的所有请求ID"""
        return self._conversation_requests.get(conversation_id, [])
        
    async def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> HumanLoopResult:
        """请求人机循环
        
        Args:
            task_id: 任务标识符
            conversation_id: 对话ID，用于多轮对话
            loop_type: 循环类型
            context: 提供给人类的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            
        Returns:
            HumanLoopResult: 包含请求ID和初始状态的结果对象
        """
        # 子类需要实现此方法
        raise NotImplementedError("Subclasses must implement request_humanloop")
        
    async def check_request_status(
        self,
        conversation_id: str,
        request_id: str
    ) -> HumanLoopResult:
        """检查请求状态
        
        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求
            
        Returns:
            HumanLoopResult: 包含当前请求状态的结果对象，包括状态、响应数据等信息
        """
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Request '{request_id}' not found in conversation '{conversation_id}'"
            )
            
        # 子类需要实现具体的状态检查逻辑
        raise NotImplementedError("Subclasses must implement check_request_status")
    
    async def check_conversation_status(
        self,
        conversation_id: str
    ) -> HumanLoopResult:
        """检查对话状态
        
        Args:
            conversation_id: 对话标识符
            
        Returns:
            HumanLoopResult: 包含对话最新请求的状态
        """
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found"
            )
            
        latest_request_id = conversation_info.get("latest_request_id")
        if not latest_request_id:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"No requests found in conversation '{conversation_id}'"
            )
            
        return await self.check_request_status(conversation_id, latest_request_id)
        
    async def cancel_request(
        self,
        conversation_id: str,
        request_id: str
    ) -> bool:
        """取消人机循环请求
        
        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求
            
        Returns:
            bool: 取消是否成功，True表示取消成功，False表示取消失败
        """

         # 取消超时任务
        if (conversation_id, request_id) in self._timeout_tasks:
            self._timeout_tasks[(conversation_id, request_id)].cancel()
            del self._timeout_tasks[(conversation_id, request_id)]

        request_key = (conversation_id, request_id)
        if request_key in self._requests:
            # 更新请求状态为已取消
            self._requests[request_key]["status"] = HumanLoopStatus.CANCELLED
            return True
        return False
    
    async def cancel_conversation(
        self,
        conversation_id: str
    ) -> bool:
        """取消整个对话
        
        Args:
            conversation_id: 对话标识符
            
        Returns:
            bool: 取消是否成功
        """
        if conversation_id not in self._conversations:
            return False
            
        # 取消对话中的所有请求
        success = True
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                # 更新请求状态为已取消
                # 只有请求处在中间状态(PENDING/IN_PROGRESS)时才能取消
                if self._requests[request_key]["status"] in [HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS]:
                    self._requests[request_key]["status"] = HumanLoopStatus.CANCELLED
                    
                    # 取消该请求的超时任务
                    if request_key in self._timeout_tasks:
                        self._timeout_tasks[request_key].cancel()
                        del self._timeout_tasks[request_key]
            else:
                success = False
                
        return success
        
    async def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """继续人机循环
        
        Args:
            conversation_id: 对话ID，用于多轮对话
            context: 提供给人类的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            
        Returns:
            HumanLoopResult: 包含请求ID和状态的结果对象
        """
        # 检查对话是否存在
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found"
            )
            
        # 子类需要实现具体的继续对话逻辑
        raise NotImplementedError("Subclasses must implement continue_humanloop")
        
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取指定对话的完整历史记录
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            List[Dict[str, Any]]: 对话历史记录列表，每个元素包含请求ID、状态、上下文、响应等信息
        """
        conversation_history = []
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                request_info = self._requests[request_key]
                conversation_history.append({
                    "request_id": request_id,
                    "status": request_info.get("status").value if request_info.get("status") else None,
                    "context": request_info.get("context"),
                    "response": request_info.get("response"),
                    "responded_by": request_info.get("responded_by"),
                    "responded_at": request_info.get("responded_at")
                })
        return conversation_history


    def _create_timeout_task(
        self, 
        conversation_id: str,
        request_id: str, 
        timeout: int
    ):
        """创建超时任务
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            timeout: 超时时间（秒）
        """
        async def timeout_task():
            await asyncio.sleep(timeout)
            
            # 检查当前状态
            request_info = self._get_request(conversation_id, request_id)
            if not request_info:
                return
                
            current_status = request_info.get("status", HumanLoopStatus.PENDING)
            
            # 只有当状态为PENDING时才触发超时
            # INPROGRESS状态表示对话正在进行中，不应视为超时
            if current_status == HumanLoopStatus.PENDING:
                # 更新请求状态为超时
                request_info["status"] = HumanLoopStatus.EXPIRED
                request_info["error"] = "Request timed out"
            # 如果状态是INPROGRESS，重置超时任务
            elif current_status == HumanLoopStatus.INPROGRESS:
                # 对于进行中的对话，我们可以选择延长超时时间
                # 这里我们简单地重新创建一个超时任务，使用相同的超时时间
                if (conversation_id, request_id) in self._timeout_tasks:
                    self._timeout_tasks[(conversation_id, request_id)].cancel()
                new_task = asyncio.create_task(timeout_task())
                self._timeout_tasks[(conversation_id, request_id)] = new_task
                
        task = asyncio.create_task(timeout_task())
        self._timeout_tasks[(conversation_id, request_id)] = task
    