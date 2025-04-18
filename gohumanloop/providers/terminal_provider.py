import asyncio
import sys
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from gohumanloop.core.interface import (HumanLoopResult, HumanLoopStatus, HumanLoopType)
from gohumanloop.providers.base import BaseProvider

class TerminalProvider(BaseProvider):
    """基于终端交互的人机循环提供者实现
    
    这个提供者通过命令行与用户进行交互，适用于测试和简单场景。
    用户可以通过终端输入来响应请求，支持审批、信息收集和对话类型的交互。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """初始化终端提供者
        
        Args:
            name: 提供者名称
            config: 配置信息，可包含以下字段：
                - prompt_template: 提示模板，用于格式化显示给用户的内容，默认为 "{context}"
                - show_metadata: 是否在交互时显示请求元数据，默认为 True
        """
        super().__init__(name, config)
        self.prompt_template = self.config.get("prompt_template", "{context}")
        self.show_metadata = self.config.get("show_metadata", True)
         
    def __str__(self) -> str:
        base_str = super().__str__()
        terminal_info = f"- 终端提供者: 基于终端交互的人机循环实现\n"
        return f"{terminal_info}{base_str}"
    
    async def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> HumanLoopResult:
        """请求人机循环，通过终端与用户交互
        
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
        # 生成请求ID
        request_id = self._generate_request_id()
        
        # 存储请求信息
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=loop_type,
            context=context,
            metadata=metadata or {},
            timeout=timeout
        )
        
        # 创建初始结果对象
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            status=HumanLoopStatus.PENDING
        )
        
        # 启动异步任务处理用户输入
        asyncio.create_task(self._process_terminal_interaction(conversation_id, request_id))
        
        # 如果设置了超时，创建超时任务
        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout)
        
        return result
        
    async def check_request_status(
        self,
        conversation_id: str,
        request_id: str
    ) -> HumanLoopResult:
        """检查请求状态
        
        Args:
            conversation_id: 对话标识符
            request_id: 请求标识符
            
        Returns:
            HumanLoopResult: 包含当前状态的结果对象
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
        
        # 构建结果对象
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=request_info.get("loop_type", HumanLoopType.CONVERSATION),
            status=request_info.get("status", HumanLoopStatus.PENDING),
            response=request_info.get("response", {}),
            feedback=request_info.get("feedback", {}),
            responded_by=request_info.get("responded_by", None),
            responded_at=request_info.get("responded_at", None),
            error=request_info.get("error", None)
        )
        
        return result
        
    async def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """继续人机循环，用于多轮对话
        
        Args:
            conversation_id: 对话ID
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
        
        # 生成新的请求ID
        request_id = self._generate_request_id()
        
        # 获取任务ID
        task_id = conversation_info.get("task_id", "unknown_task")
        
        # 存储请求信息
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.CONVERSATION,  # 继续对话默认为对话类型
            context=context,
            metadata=metadata or {},
            timeout=timeout
        )
        
        # 创建初始结果对象
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.PENDING
        )
        
        # 启动异步任务处理用户输入
        asyncio.create_task(self._process_terminal_interaction(conversation_id, request_id))
        
        # 如果设置了超时，创建超时任务
        if timeout:
            self._create_timeout_task(conversation_id, request_id, timeout)
        
        return result
    
    async def _process_terminal_interaction(self, conversation_id: str, request_id: str):
        """处理终端交互
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
        """
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return 
        
        # 构建提示信息
        context_str = self._format_context(request_info["context"])
        prompt = self.prompt_template.format(context=context_str)
        
        # 显示元数据（如果配置为显示）
        if self.show_metadata and request_info["metadata"]:
            metadata_str = json.dumps(request_info["metadata"], indent=2, ensure_ascii=False)
            print(f"\n--- 元数据 ---\n{metadata_str}\n")
        
        # 显示对话和请求ID
        print(f"\n=== 对话ID: {conversation_id} | 请求ID: {request_id} ===")
        
        # 显示循环类型
        loop_type = request_info["loop_type"]
        print(f"--- 交互类型: {loop_type.value} ---\n")
        
        # 显示提示信息
        print(prompt)
        
        # 根据循环类型处理不同的交互方式
        if loop_type == HumanLoopType.APPROVAL:
            await self._handle_approval_interaction(conversation_id, request_id, request_info)
        elif loop_type == HumanLoopType.INFORMATION:
            await self._handle_information_interaction(conversation_id, request_id, request_info)
        else:  # HumanLoopType.CONVERSATION
            await self._handle_conversation_interaction(conversation_id, request_id, request_info)
    
    async def _handle_approval_interaction(self, conversation_id: str, request_id: str, request_info: Dict[str, Any]):
        """处理审批类型的交互
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            request_info: 请求信息
        """
        print("\n请输入您的决定 (approve/reject):")
        
        # 使用 run_in_executor 在线程池中执行阻塞的 input() 调用
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input)

        # 更新状态为进行中
        request_info["status"] = HumanLoopStatus.INPROGRESS
        
        # 处理响应
        response = response.strip().lower()
        if response in ["approve", "yes", "y", "同意", "批准"]:
            status = HumanLoopStatus.APPROVED
            response_data = ""
        elif response in ["reject", "no", "n", "拒绝", "不同意"]:
            status = HumanLoopStatus.REJECTED
            print("\n请输入拒绝原因:")
            reason = await loop.run_in_executor(None, input)
            response_data = reason
        else:
            print("\n无效的输入，请输入 approve 或 reject")
            # 递归调用处理审批交互
            await self._handle_approval_interaction(conversation_id, request_id, request_info)
            return
        
        # 更新请求信息
        request_info["status"] = status
        request_info["response"] = response_data
        request_info["responded_by"] = "terminal_user"
        request_info["responded_at"] = datetime.now().isoformat()
        
        print(f"\n已记录您的决定: {status.value}")
    
    async def _handle_information_interaction(self, conversation_id: str, request_id: str, request_info: Dict[str, Any]):
        """处理信息收集类型的交互
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            request_info: 请求信息
        """
        print("\n请提供所需信息:")
        
        # 使用 run_in_executor 在线程池中执行阻塞的 input() 调用
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input)
        
        # 更新请求信息
        request_info["status"] = HumanLoopStatus.COMPLETED
        request_info["response"] = response
        request_info["responded_by"] = "terminal_user"
        request_info["responded_at"] = datetime.now().isoformat()
        
        print("\n已记录您提供的信息")
    
    async def _handle_conversation_interaction(self, conversation_id: str, request_id: str, request_info: Dict[str, Any]):
        """处理对话类型的交互
        
        Args:
            conversation_id: 对话ID
            request_id: 请求ID
            request_info: 请求信息
        """
        print("\n请输入您的回复 (输入 'exit' 结束对话):")
        
        # 使用 run_in_executor 在线程池中执行阻塞的 input() 调用
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input)
        
        # 处理响应
        if response.strip().lower() in ["exit", "quit", "结束", "退出"]:
            status = HumanLoopStatus.COMPLETED
            print("\n对话已结束")
        else:
            status = HumanLoopStatus.INPROGRESS

        # 更新请求信息
        request_info["status"] = status
        request_info["response"] = response
        request_info["responded_by"] = "terminal_user"
        request_info["responded_at"] = datetime.now().isoformat()
        
        print("\n已记录您的回复")
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文信息为字符串
        
        Args:
            context: 上下文信息
            
        Returns:
            str: 格式化后的字符串
        """
        # 如果上下文是字符串，直接返回
        if isinstance(context, str):
            return context
            
        # 如果上下文包含 "message" 字段，优先使用它
        if "message" in context:
            return context["message"]
            
        # 否则将整个上下文转换为 JSON 字符串
        return json.dumps(context, indent=2, ensure_ascii=False)
