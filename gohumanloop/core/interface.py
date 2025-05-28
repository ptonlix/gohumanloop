from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Optional,
    Protocol,
    runtime_checkable,
    Union,
)
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class HumanLoopStatus(Enum):
    """Enumeration of human-in-the-loop states"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"
    COMPLETED = "completed"  # For completing non-approval interactions
    INPROGRESS = "inprogress"  # Intermediate state for multi-turn dialogues, indicating ongoing conversation
    CANCELLED = "cancelled"  # For cancelled requests


class HumanLoopType(Enum):
    """Enumeration of human-in-the-loop types"""

    APPROVAL = "approval"  # Approval type
    INFORMATION = "information"  # Information gathering type
    CONVERSATION = "conversation"  # Conversation type


"""
## Relationship between task_id, conversation_id and request_id
1. Hierarchical relationship:

   - task_id is at the highest level, representing business tasks
   - conversation_id is at the middle level, representing a complete dialogue session
   - request_id is at the lowest level, representing a single interaction request
2. Mapping relationship:

   - One task_id may correspond to multiple conversation_ids (a task may require multiple conversations)
   - One conversation_id may correspond to multiple request_ids (a conversation may contain multiple rounds of interaction)
"""


@dataclass
class HumanLoopRequest:
    """人机循环请求的数据模型 / Human loop request data model"""

    task_id: str  # 任务ID / Task identifier
    conversation_id: str  # 用于关联多轮对话 / Used to associate multi-turn conversations
    loop_type: HumanLoopType  # 循环类型 / Loop type
    context: Dict[str, Any]  # 交互上下文信息 / Interaction context information
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )  # 元数据信息 / Metadata information
    request_id: Optional[str] = None  # 请求ID / Request identifier
    timeout: Optional[int] = None  # 超时时间（秒） / Timeout duration (seconds)
    created_at: Optional[
        datetime
    ] = None  # 将在请求创建时设置 / Will be set when request is created


@dataclass
class HumanLoopResult:
    """人机循环结果的数据模型 / Human loop result data model"""

    conversation_id: str  # 用于关联多轮对话 / Used to associate multi-turn conversations
    request_id: str  # 请求ID / Request identifier
    loop_type: HumanLoopType  # 循环类型 / Loop type
    status: HumanLoopStatus  # 循环状态 / Loop status
    response: Dict[str, Any] = field(
        default_factory=dict
    )  # 人类提供的响应数据 / Response data provided by human
    feedback: Dict[str, Any] = field(
        default_factory=dict
    )  # 反馈信息 / Feedback information
    responded_by: Optional[str] = None  # 响应者 / Responder
    responded_at: Optional[str] = None  # 响应时间 / Response time
    error: Optional[str] = None  # 错误信息 / Error message


@runtime_checkable
class HumanLoopProvider(Protocol):
    """Human-in-the-loop Provider Protocol"""

    name: str  # 提供者名称

    @abstractmethod
    async def async_request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
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
    def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """请求人机循环（同步版本）

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
    async def async_check_request_status(
        self, conversation_id: str, request_id: str
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
    def check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        """检查请求状态（同步版本）

        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求

        Returns:
            HumanLoopResult: 包含当前请求状态的结果对象，包括状态、响应数据等信息
        """
        pass

    @abstractmethod
    async def async_check_conversation_status(
        self, conversation_id: str
    ) -> HumanLoopResult:
        """检查对话状态

        Args:
            conversation_id: 对话标识符

        Returns:
            HumanLoopResult: 包含对话最新请求的状态
        """
        pass

    @abstractmethod
    def check_conversation_status(self, conversation_id: str) -> HumanLoopResult:
        """检查对话状态（同步版本）

        Args:
            conversation_id: 对话标识符

        Returns:
            HumanLoopResult: 包含对话最新请求的状态
        """
        pass

    @abstractmethod
    async def async_cancel_request(self, conversation_id: str, request_id: str) -> bool:
        """取消人机循环请求

        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求

        Returns:
            bool: 取消是否成功，True表示取消成功，False表示取消失败
        """
        pass

    @abstractmethod
    def cancel_request(self, conversation_id: str, request_id: str) -> bool:
        """取消人机循环请求（同步版本）

        Args:
            conversation_id: 对话标识符，用于关联多轮对话
            request_id: 请求标识符，用于标识具体的交互请求

        Returns:
            bool: 取消是否成功，True表示取消成功，False表示取消失败
        """
        pass

    @abstractmethod
    async def async_cancel_conversation(self, conversation_id: str) -> bool:
        """取消整个对话

        Args:
            conversation_id: 对话标识符

        Returns:
            bool: 取消是否成功
        """
        pass

    @abstractmethod
    def cancel_conversation(self, conversation_id: str) -> bool:
        """取消整个对话（同步版本）

        Args:
            conversation_id: 对话标识符

        Returns:
            bool: 取消是否成功
        """
        pass

    @abstractmethod
    async def async_continue_humanloop(
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

    @abstractmethod
    def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """继续人机循环（同步版本）

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
    async def async_on_humanloop_request(
        self, provider: HumanLoopProvider, request: HumanLoopRequest
    ) -> Any:
        """当人机循环请求开始时的回调

        Args:
            provider: 人机循环提供者实例
            request: 循环请求
        """
        pass

    @abstractmethod
    async def async_on_humanloop_update(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        """当请求更新时的回调

        Args:
            provider: 人机循环提供者实例
            result: 循环结果
        """
        pass

    @abstractmethod
    async def async_on_humanloop_timeout(
        self, provider: HumanLoopProvider, result: HumanLoopResult
    ) -> Any:
        """当请求超时时的回调

        Args:
            provider: 人机循环提供者实例
        """
        pass

    @abstractmethod
    async def async_on_humanloop_error(
        self, provider: HumanLoopProvider, error: Exception
    ) -> Any:
        """当请求发生错误时的回调

        Args:
            provider: 人机循环提供者实例
            error: 错误信息
        """
        pass


class HumanLoopManager(ABC):
    """人机循环管理器的抽象类"""

    @abstractmethod
    async def async_register_provider(
        self, provider: HumanLoopProvider, provider_id: Optional[str] = None
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
    def register_provider(
        self, provider: HumanLoopProvider, provider_id: Optional[str] = None
    ) -> str:
        """注册人机循环提供者（同步版本）

        Args:
            provider: 人机循环提供者实例
            provider_id: 提供者标识符（可选）

        Returns:
            str: 注册成功后的提供者ID
        """
        pass

    @abstractmethod
    async def async_request_humanloop(
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
    def request_humanloop(
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
        """请求人机循环（同步版本）

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
    async def async_continue_humanloop(
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
    def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        callback: Optional[HumanLoopCallback] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider_id: Optional[str] = None,
        timeout: Optional[int] = None,
        blocking: bool = False,
    ) -> Union[str, HumanLoopResult]:
        """继续人机循环（同步版本）

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
    async def async_check_request_status(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
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
    def check_request_status(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查请求状态（同步版本）

        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            provider_id: 使用特定提供者的ID（可选）

        Returns:
            HumanLoopResult: 包含当前请求状态的结果对象
        """
        pass

    @abstractmethod
    async def async_check_conversation_status(
        self, conversation_id: str, provider_id: Optional[str] = None
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
    def check_conversation_status(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> HumanLoopResult:
        """检查对话状态（同步版本）

        Args:
            conversation_id: 对话标识符
            provider_id: 使用特定提供者的ID（可选）

        Returns:
            HumanLoopResult: 包含对话最新请求的状态
        """
        pass

    @abstractmethod
    async def async_cancel_request(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
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
    def cancel_request(
        self, conversation_id: str, request_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """取消特定请求（同步版本）

        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            provider_id: 使用特定提供者的ID（可选）

        Returns:
            bool: 取消是否成功
        """
        pass

    @abstractmethod
    async def async_cancel_conversation(
        self, conversation_id: str, provider_id: Optional[str] = None
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
    def cancel_conversation(
        self, conversation_id: str, provider_id: Optional[str] = None
    ) -> bool:
        """取消整个对话（同步版本）

        Args:
            conversation_id: 对话标识符
            provider_id: 使用特定提供者的ID（可选）

        Returns:
            bool: 取消是否成功
        """
        pass

    @abstractmethod
    async def async_get_provider(
        self, provider_id: Optional[str] = None
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
    def get_provider(self, provider_id: Optional[str] = None) -> HumanLoopProvider:
        """获取指定的提供者实例（同步版本）

        Args:
            provider_id: 提供者ID，如果为None则返回默认提供者

        Returns:
            HumanLoopProvider: 提供者实例

        Raises:
            ValueError: 如果指定的提供者不存在
        """
        pass

    @abstractmethod
    async def async_list_providers(self) -> Dict[str, HumanLoopProvider]:
        """列出所有注册的提供者

        Returns:
            Dict[str, HumanLoopProvider]: 提供者ID到提供者实例的映射
        """
        pass

    @abstractmethod
    def list_providers(self) -> Dict[str, HumanLoopProvider]:
        """列出所有注册的提供者（同步版本）

        Returns:
            Dict[str, HumanLoopProvider]: 提供者ID到提供者实例的映射
        """
        pass

    @abstractmethod
    async def async_set_default_provider(self, provider_id: str) -> bool:
        """设置默认提供者

        Args:
            provider_id: 提供者ID

        Returns:
            bool: 设置是否成功

        Raises:
            ValueError: 如果指定的提供者不存在
        """
        pass

    @abstractmethod
    def set_default_provider(self, provider_id: str) -> bool:
        """设置默认提供者（同步版本）

        Args:
            provider_id: 提供者ID

        Returns:
            bool: 设置是否成功

        Raises:
            ValueError: 如果指定的提供者不存在
        """
        pass

    @abstractmethod
    async def async_check_conversation_exist(
        self,
        task_id: str,
        conversation_id: str,
    ) -> bool:
        """检查对话是否存在

        Args:
            task_id: 任务标识符，用于标识业务任务
            conversation_id: 对话标识符，用于标识具体对话会话
        Returns:
            bool: 如果对话存在返回True，否则返回False
        """
        pass

    @abstractmethod
    def check_conversation_exist(
        self,
        task_id: str,
        conversation_id: str,
    ) -> bool:
        """检查对话状态（同步版本）

        Args:
            conversation_id: 对话标识符
        Returns:
            bool: 如果对话存在返回True，否则返回False
        """
        pass

    @abstractmethod
    async def async_shutdown(self) -> None:
        """关闭管理器(异步方法)"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭管理器(同步方法)"""
        pass
