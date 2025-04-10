from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, runtime_checkable, List, Union, Callable, Awaitable
from enum import Enum

class ApprovalStatus(Enum):
    """枚举批准状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"

# 添加交互类型枚举
class InteractionType(Enum):
    """枚举人机交互类型"""
    APPROVAL = "approval"  # 审批类型
    INFORMATION = "information"  # 信息获取类型
    CONVERSATION = "conversation"  # 对话类型

class ApprovalRequest:
    """批准请求的数据模型"""
    def __init__(
        self,
        task_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.task_id = task_id
        self.context = context
        self.metadata = metadata or {}
        self.request_id = request_id
        self.timeout = timeout
        self.created_at = None  # 将在请求创建时设置

class ApprovalResult:
    """批准结果的数据模型"""
    def __init__(
        self,
        request_id: str,
        status: ApprovalStatus,
        feedback: Optional[Dict[str, Any]] = None,
        approved_by: Optional[str] = None,
        approved_at: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.request_id = request_id
        self.status = status
        self.feedback = feedback or {}
        self.approved_by = approved_by
        self.approved_at = approved_at
        self.error = error

# 添加人机交互请求模型
class HumanInteractionRequest:
    """人机交互请求的数据模型"""
    def __init__(
        self,
        task_id: str,
        interaction_type: InteractionType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        timeout: Optional[int] = None,
        conversation_id: Optional[str] = None,  # 用于关联多轮对话
    ):
        self.task_id = task_id
        self.interaction_type = interaction_type
        self.context = context
        self.metadata = metadata or {}
        self.request_id = request_id
        self.timeout = timeout
        self.conversation_id = conversation_id
        self.created_at = None  # 将在请求创建时设置

# 添加人机交互结果模型
class HumanInteractionResult:
    """人机交互结果的数据模型"""
    def __init__(
        self,
        request_id: str,
        interaction_type: InteractionType,
        status: ApprovalStatus,  # 复用ApprovalStatus表示交互状态
        response: Optional[Dict[str, Any]] = None,  # 人类提供的响应数据
        feedback: Optional[Dict[str, Any]] = None,
        responded_by: Optional[str] = None,
        responded_at: Optional[str] = None,
        error: Optional[str] = None,
        conversation_id: Optional[str] = None,  # 用于关联多轮对话
    ):
        self.request_id = request_id
        self.interaction_type = interaction_type
        self.status = status
        self.response = response or {}
        self.feedback = feedback or {}
        self.responded_by = responded_by
        self.responded_at = responded_at
        self.error = error
        self.conversation_id = conversation_id

@runtime_checkable
class HumanLoopProvider(Protocol):
    """Human-in-the-loop Provider Protocol"""
    
    @abstractmethod
    async def request_approval(
        self,
        task_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> ApprovalResult:
        """请求人类批准
        
        Args:
            task_id: 任务标识符
            context: 提供给人类审核者的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            
        Returns:
            ApprovalResult: 包含请求ID和初始状态的结果对象
        """
        pass

    @abstractmethod
    async def check_approval_status(
        self, 
        request_id: str
    ) -> ApprovalResult:
        """检查批准状态
        
        Args:
            request_id: 请求标识符
            
        Returns:
            ApprovalResult: 包含当前状态的结果对象
        """
        pass
        
    @abstractmethod
    async def cancel_approval_request(
        self,
        request_id: str
    ) -> bool:
        """取消批准请求
        
        Args:
            request_id: 请求标识符
            
        Returns:
            bool: 取消是否成功
        """
        pass
    
    # 添加人机交互方法
    @abstractmethod
    async def request_human_interaction(
        self,
        task_id: str,
        interaction_type: InteractionType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        conversation_id: Optional[str] = None
    ) -> HumanInteractionResult:
        """请求人机交互
        
        Args:
            task_id: 任务标识符
            interaction_type: 交互类型
            context: 提供给人类的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            conversation_id: 对话ID，用于多轮对话
            
        Returns:
            HumanInteractionResult: 包含请求ID和初始状态的结果对象
        """
        pass
    
    @abstractmethod
    async def check_interaction_status(
        self, 
        request_id: str
    ) -> HumanInteractionResult:
        """检查交互状态
        
        Args:
            request_id: 请求标识符
            
        Returns:
            HumanInteractionResult: 包含当前状态的结果对象
        """
        pass
    
    @abstractmethod
    async def continue_conversation(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> HumanInteractionResult:
        """继续多轮对话
        
        Args:
            conversation_id: 对话ID
            context: 提供给人类的上下文信息
            metadata: 附加元数据
            timeout: 请求超时时间（秒）
            
        Returns:
            HumanInteractionResult: 包含请求ID和初始状态的结果对象
        """
        pass
    
    @abstractmethod
    async def end_conversation(
        self,
        conversation_id: str
    ) -> bool:
        """结束多轮对话
        
        Args:
            conversation_id: 对话ID
            
        Returns:
            bool: 结束是否成功
        """
        pass

class ApprovalCallback(ABC):
    """批准回调的抽象类"""
    
    @abstractmethod
    async def on_approval_received(
        self, 
        request_id: str, 
        result: ApprovalResult
    ):
        """当收到批准结果时的回调
        
        Args:
            request_id: 请求标识符
            result: 批准结果
        """
        pass
        
    @abstractmethod
    async def on_approval_timeout(
        self,
        request_id: str
    ):
        """当批准请求超时时的回调
        
        Args:
            request_id: 请求标识符
        """
        pass
        
    @abstractmethod
    async def on_approval_error(
        self,
        request_id: str,
        error: str
    ):
        """当批准请求发生错误时的回调
        
        Args:
            request_id: 请求标识符
            error: 错误信息
        """
        pass

# 添加人机交互回调
class HumanInteractionCallback(ABC):
    """人机交互回调的抽象类"""
    
    @abstractmethod
    async def on_interaction_received(
        self, 
        request_id: str, 
        result: HumanInteractionResult
    ):
        """当收到交互结果时的回调
        
        Args:
            request_id: 请求标识符
            result: 交互结果
        """
        pass
    
    @abstractmethod
    async def on_conversation_update(
        self,
        conversation_id: str,
        result: HumanInteractionResult
    ):
        """当对话更新时的回调
        
        Args:
            conversation_id: 对话标识符
            result: 最新的交互结果
        """
        pass
        
    @abstractmethod
    async def on_interaction_timeout(
        self,
        request_id: str
    ):
        """当交互请求超时时的回调
        
        Args:
            request_id: 请求标识符
        """
        pass
        
    @abstractmethod
    async def on_interaction_error(
        self,
        request_id: str,
        error: str
    ):
        """当交互请求发生错误时的回调
        
        Args:
            request_id: 请求标识符
            error: 错误信息
        """
        pass

class HumanLoopManager(ABC):
    """人机交互管理器的抽象类"""
    
    @abstractmethod
    async def register_provider(
        self,
        provider: HumanLoopProvider,
        provider_id: Optional[str] = None
    ):
        """注册人机交互提供者
        
        Args:
            provider: 人机交互提供者实例
            provider_id: 提供者标识符（可选）
        """
        pass
        
    @abstractmethod
    async def request_approval(
        self,
        task_id: str,
        context: Dict[str, Any],
        callback: Optional[ApprovalCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False
    ) -> Union[str, ApprovalResult]:
        """请求人类批准
        
        Args:
            task_id: 任务标识符
            context: 提供给人类审核者的上下文信息
            callback: 回调对象（可选）
            metadata: 附加元数据
            provider_id: 使用特定提供者的ID（可选）
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
            
        Returns:
            Union[str, ApprovalResult]: 如果blocking=False，返回请求ID；否则返回批准结果
        """
        pass
    
    # 添加人机交互方法
    @abstractmethod
    async def request_human_interaction(
        self,
        task_id: str,
        interaction_type: InteractionType,
        context: Dict[str, Any],
        callback: Optional[HumanInteractionCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
        conversation_id: Optional[str] = None
    ) -> Union[str, HumanInteractionResult]:
        """请求人机交互
        
        Args:
            task_id: 任务标识符
            interaction_type: 交互类型
            context: 提供给人类的上下文信息
            callback: 回调对象（可选）
            metadata: 附加元数据
            provider_id: 使用特定提供者的ID（可选）
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
            conversation_id: 对话ID，用于多轮对话
            
        Returns:
            Union[str, HumanInteractionResult]: 如果blocking=False，返回请求ID；否则返回交互结果
        """
        pass
    
    @abstractmethod
    async def continue_conversation(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        callback: Optional[HumanInteractionCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False
    ) -> Union[str, HumanInteractionResult]:
        """继续多轮对话
        
        Args:
            conversation_id: 对话ID
            context: 提供给人类的上下文信息
            callback: 回调对象（可选）
            metadata: 附加元数据
            provider_id: 使用特定提供者的ID（可选）
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
            
        Returns:
            Union[str, HumanInteractionResult]: 如果blocking=False，返回请求ID；否则返回交互结果
        """
        pass
    
    @abstractmethod
    async def end_conversation(
        self,
        conversation_id: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """结束多轮对话
        
        Args:
            conversation_id: 对话ID
            provider_id: 使用特定提供者的ID（可选）
            
        Returns:
            bool: 结束是否成功
        """
        pass