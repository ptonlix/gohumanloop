from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol, runtime_checkable, List, Union, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class HumanLoopStatus(Enum):
    """枚举人机循环状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"
    COMPLETED = "completed"  # 用于非审批类交互完成
    INPROGRESS = "inprogress"  # 用于多轮对话的中间状态，表示对话正在进行中
    CANCELLED = "cancelled"  # 用于取消请求

class HumanLoopType(Enum):
    """枚举人机循环类型"""
    APPROVAL = "approval"  # 审批类型
    INFORMATION = "information"  # 信息获取类型
    CONVERSATION = "conversation"  # 对话类型

"""
## task_id conversation_id request_id 三者之间的关系
1. 层次关系 ：
   
   - task_id 位于最高层，代表业务任务
   - conversation_id 位于中间层，代表一次完整的对话会话
   - request_id 位于最低层，代表单次交互请求
2. 映射关系 ：
   
   - 一个 task_id 可能对应多个 conversation_id （一个任务可能需要多次对话）
   - 一个 conversation_id 可能对应多个 request_id （一次对话可能包含多轮交互）
"""
@dataclass
class HumanLoopRequest:
    """人机循环请求的数据模型 / Human loop request data model"""
    task_id: str  # 任务ID / Task identifier
    conversation_id: str# 用于关联多轮对话 / Used to associate multi-turn conversations
    loop_type: HumanLoopType  # 循环类型 / Loop type
    context: Dict[str, Any]  # 交互上下文信息 / Interaction context information
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据信息 / Metadata information
    request_id: Optional[str] = None  # 请求ID / Request identifier
    timeout: Optional[int] = None  # 超时时间（秒） / Timeout duration (seconds)
    created_at: Optional[datetime] = None  # 将在请求创建时设置 / Will be set when request is created

@dataclass
class HumanLoopResult:
    """人机循环结果的数据模型 / Human loop result data model"""
    conversation_id: str  # 用于关联多轮对话 / Used to associate multi-turn conversations
    request_id: str  # 请求ID / Request identifier
    loop_type: HumanLoopType  # 循环类型 / Loop type
    status: HumanLoopStatus  # 循环状态 / Loop status
    response: Dict[str, Any] = field(default_factory=dict)  # 人类提供的响应数据 / Response data provided by human
    feedback: Dict[str, Any] = field(default_factory=dict)  # 反馈信息 / Feedback information
    responded_by: Optional[str] = None  # 响应者 / Responder
    responded_at: Optional[str] = None  # 响应时间 / Response time
    error: Optional[str] = None  # 错误信息 / Error message

@runtime_checkable
class HumanLoopProvider(Protocol):
    """Human-in-the-loop Provider Protocol"""
    
    @abstractmethod
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
        pass

    @abstractmethod
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
        pass
    @abstractmethod
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
        pass
        
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass

class HumanLoopCallback(ABC):
    """人机循环回调的抽象类"""
    
    @abstractmethod
    async def on_humanloop_update(
        self, 
        conversation_id: str,
        request_id: str, 
        result: HumanLoopResult
    ):
        """当请求更新时的回调
        
        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            result: 循环结果
        """
        pass
        
    @abstractmethod
    async def on_humanloop_timeout(
        self,
        conversation_id: str,
        request_id: str
    ):
        """当请求超时时的回调
        
        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
        """
        pass
        
    @abstractmethod
    async def on_humanloop_error(
        self,
        conversation_id: str,
        request_id: str,
        error: str
    ):
        """当请求发生错误时的回调
        
        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            error: 错误信息
        """
        pass

class HumanLoopManager(ABC):
    """人机循环管理器的抽象类"""
    
    @abstractmethod
    async def register_provider(
        self,
        provider: HumanLoopProvider,
        provider_id: Optional[str] = None
    ) -> str:
        """注册人机循环提供者
        
        Args:
            provider: 人机循环提供者实例
            provider_id: 提供者标识符（可选）
            
        Returns:
            str: 注册成功后的提供者ID
        """
        pass
        
    @abstractmethod
    async def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """请求人机循环
        
        Args:
            task_id: 任务标识符
            conversation_id: 对话ID，用于多轮对话
            loop_type: 循环类型
            context: 提供给人类的上下文信息
            callback: 回调对象（可选）
            metadata: 附加元数据
            provider_id: 使用特定提供者的ID（可选）
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
            
        Returns:
            Union[str, HumanLoopResult]: 如果blocking=False，返回请求ID；否则返回循环结果
        """
        pass
    
    @abstractmethod
    async def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """继续人机循环
        
        Args:
            conversation_id: 对话ID，用于多轮对话
            context: 提供给人类的上下文信息
            callback: 回调对象（可选）
            metadata: 附加元数据
            provider_id: 使用特定提供者的ID（可选）
            timeout: 请求超时时间（秒）
            blocking: 是否阻塞等待结果
            
        Returns:
            Union[str, HumanLoopResult]: 如果blocking=False，返回请求ID；否则返回循环结果
        """
        pass
    
    @abstractmethod
    async def check_request_status(
        self,
        conversation_id: str,
        request_id: str,
        provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查请求状态
        
        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            provider_id: 使用特定提供者的ID（可选）
            
        Returns:
            HumanLoopResult: 包含当前请求状态的结果对象
        """
        pass
    
    @abstractmethod
    async def check_conversation_status(
        self,
        conversation_id: str,
        provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查对话状态
        
        Args:
            conversation_id: 对话标识符
            provider_id: 使用特定提供者的ID（可选）
            
        Returns:
            HumanLoopResult: 包含对话最新请求的状态
        """
        pass
    
    @abstractmethod
    async def cancel_request(
        self,
        conversation_id: str,
        request_id: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """取消特定请求
        
        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            provider_id: 使用特定提供者的ID（可选）
            
        Returns:
            bool: 取消是否成功
        """
        pass
    
    @abstractmethod
    async def cancel_conversation(
        self,
        conversation_id: str,
        provider_id: Optional[str] = None
    ) -> bool:
        """取消整个对话
        
        Args:
            conversation_id: 对话标识符
            provider_id: 使用特定提供者的ID（可选）
            
        Returns:
            bool: 取消是否成功
        """
        pass
    
    @abstractmethod
    async def get_provider(
        self,
        provider_id: Optional[str] = None
    ) -> HumanLoopProvider:
        """获取指定的提供者实例
        
        Args:
            provider_id: 提供者ID，如果为None则返回默认提供者
            
        Returns:
            HumanLoopProvider: 提供者实例
            
        Raises:
            ValueError: 如果指定的提供者不存在
        """
        pass
    
    @abstractmethod
    async def list_providers(self) -> Dict[str, HumanLoopProvider]:
        """列出所有注册的提供者
        
        Returns:
            Dict[str, HumanLoopProvider]: 提供者ID到提供者实例的映射
        """
        pass
    
    @abstractmethod
    async def set_default_provider(
        self,
        provider_id: str
    ) -> bool:
        """设置默认提供者
        
        Args:
            provider_id: 提供者ID
            
        Returns:
            bool: 设置是否成功
            
        Raises:
            ValueError: 如果指定的提供者不存在
        """
        pass