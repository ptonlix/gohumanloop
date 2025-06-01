import asyncio
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from gohumanloop.core.interface import HumanLoopResult, HumanLoopStatus, HumanLoopType
from gohumanloop.providers.base import BaseProvider


class TerminalProvider(BaseProvider):
    """Terminal-based human-in-the-loop provider implementation

    This provider interacts with users through command line interface, suitable for testing and simple scenarios.
    Users can respond to requests via terminal input, supporting approval, information collection and conversation type interactions.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Initialize terminal provider

        Args:
            name: Provider name
            config: Configuration options, may include:
        """
        super().__init__(name, config)

        # Store running terminal input tasks
        self._terminal_input_tasks: Dict[Tuple[str, str], Future] = {}
        # Create thread pool for background service execution
        self._executor = ThreadPoolExecutor(max_workers=10)

    def __del__(self) -> None:
        """Destructor to ensure thread pool is properly closed"""
        self._executor.shutdown(wait=False)

        for task_key, future in list(self._terminal_input_tasks.items()):
            future.cancel()
        self._terminal_input_tasks.clear()

    def __str__(self) -> str:
        base_str = super().__str__()
        terminal_info = (
            "- Terminal Provider: Terminal-based human-in-the-loop implementation\n"
        )
        return f"{terminal_info}{base_str}"

    async def async_request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Request human-in-the-loop interaction through terminal

        Args:
            task_id: Task identifier
            conversation_id: Conversation ID for multi-turn dialogs
            loop_type: Loop type
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and initial status
        """
        # Generate request ID
        request_id = self._generate_request_id()

        # Store request information
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=loop_type,
            context=context,
            metadata=metadata or {},
            timeout=timeout,
        )

        # Create initial result object
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type,
            status=HumanLoopStatus.PENDING,
        )

        self._terminal_input_tasks[
            (conversation_id, request_id)
        ] = self._executor.submit(
            self._run_async_terminal_interaction, conversation_id, request_id, timeout
        )

        return result

    async def _process_terminal_interaction_with_timeout(
        self, conversation_id: str, request_id: str, timeout: Optional[int]
    ) -> None:
        """Process terminal interaction with timeout functionality"""
        try:
            if timeout:
                # Set timeout using wait_for
                await asyncio.wait_for(
                    self._process_terminal_interaction(conversation_id, request_id),
                    timeout=timeout,
                )
            else:
                # No timeout limit
                await self._process_terminal_interaction(conversation_id, request_id)

        except asyncio.TimeoutError:
            # Handle timeout
            request_info = self._get_request(conversation_id, request_id)
            if request_info and request_info.get("status") == HumanLoopStatus.PENDING:
                request_info["status"] = HumanLoopStatus.EXPIRED
                request_info["error"] = "Request timed out"
                print(f"\nRequest {request_id} has timed out after {timeout} seconds")

    def _run_async_terminal_interaction(
        self, conversation_id: str, request_id: str, timeout: int | None
    ) -> None:
        """Run asynchronous terminal interaction in a separate thread"""
        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run interaction processing in the new event loop
            loop.run_until_complete(
                self._process_terminal_interaction_with_timeout(
                    conversation_id, request_id, timeout
                )
            )
        finally:
            loop.close()
            # Remove from task dictionary
            if (conversation_id, request_id) in self._terminal_input_tasks:
                del self._terminal_input_tasks[(conversation_id, request_id)]

    async def async_check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        """Check request status

        Args:
            conversation_id: Conversation identifier
            request_id: Request identifier

        Returns:
            HumanLoopResult: Result object containing current status
        """
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Request '{request_id}' not found in conversation '{conversation_id}'",
            )

        # Build result object
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=request_info.get("loop_type", HumanLoopType.CONVERSATION),
            status=request_info.get("status", HumanLoopStatus.PENDING),
            response=request_info.get("response", {}),
            feedback=request_info.get("feedback", {}),
            responded_by=request_info.get("responded_by", None),
            responded_at=request_info.get("responded_at", None),
            error=request_info.get("error", None),
        )

        return result

    async def async_continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Continue human-in-the-loop interaction for multi-turn conversations

        Args:
            conversation_id: Conversation identifier
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and status
        """
        # Check if conversation exists
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found",
            )

        # Generate new request ID
        request_id = self._generate_request_id()

        # Get task ID
        task_id = conversation_info.get("task_id", "unknown_task")

        # Store request information
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.CONVERSATION,  # Default to conversation type for continued dialog
            context=context,
            metadata=metadata or {},
            timeout=timeout,
        )

        # Create initial result object
        result = HumanLoopResult(
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=HumanLoopType.CONVERSATION,
            status=HumanLoopStatus.PENDING,
        )

        # Start async task to process user input
        self._terminal_input_tasks[
            (conversation_id, request_id)
        ] = self._executor.submit(
            self._run_async_terminal_interaction, conversation_id, request_id, timeout
        )

        return result

    async def _process_terminal_interaction(
        self, conversation_id: str, request_id: str
    ) -> None:
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return

        prompt = self.build_prompt(
            task_id=request_info["task_id"],
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=request_info["loop_type"],
            created_at=request_info.get("created_at", ""),
            context=request_info["context"],
            metadata=request_info.get("metadata"),
        )

        loop_type = request_info["loop_type"]

        # Display prompt message
        print(prompt)

        # Handle different interaction types based on loop type
        if loop_type == HumanLoopType.APPROVAL:
            await self._async_handle_approval_interaction(
                conversation_id, request_id, request_info
            )
        elif loop_type == HumanLoopType.INFORMATION:
            await self._async_handle_information_interaction(
                conversation_id, request_id, request_info
            )
        else:  # HumanLoopType.CONVERSATION
            await self._async_handle_conversation_interaction(
                conversation_id, request_id, request_info
            )

    async def _async_handle_approval_interaction(
        self, conversation_id: str, request_id: str, request_info: Dict[str, Any]
    ) -> None:
        """Handle approval type interaction

        Args:
            conversation_id: Conversation ID
            request_id: Request ID
            request_info: Request information
        """
        print("\nPlease enter your decision (approve/reject):")

        # Execute blocking input() call in thread pool using run_in_executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input)
        # Process response
        response = response.strip().lower()
        if response in ["approve", "yes", "y", "同意", "批准"]:
            status = HumanLoopStatus.APPROVED
            response_data = ""
        elif response in ["reject", "no", "n", "拒绝", "不同意"]:
            status = HumanLoopStatus.REJECTED
            print("\nPlease enter the reason for rejection:")
            reason = await loop.run_in_executor(None, input)
            response_data = reason
        else:
            print("\nInvalid input, please enter 'approve' or 'reject'")
            # Recursively handle approval interaction
            await self._async_handle_approval_interaction(
                conversation_id, request_id, request_info
            )
            return

        # Update request information
        request_info["status"] = status
        request_info["response"] = response_data
        request_info["responded_by"] = "terminal_user"
        request_info["responded_at"] = datetime.now().isoformat()

        print(f"\nYour decision has been recorded: {status.value}")

    async def _async_handle_information_interaction(
        self, conversation_id: str, request_id: str, request_info: Dict[str, Any]
    ) -> None:
        """Handle information collection type interaction

        Args:
            conversation_id: Conversation ID
            request_id: Request ID
            request_info: Request information
        """
        print("\nPlease provide the required information:")

        # Execute blocking input() call in thread pool using run_in_executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input)

        # Update request information
        request_info["status"] = HumanLoopStatus.COMPLETED
        request_info["response"] = response
        request_info["responded_by"] = "terminal_user"
        request_info["responded_at"] = datetime.now().isoformat()

        print("\nYour information has been recorded")

    async def _async_handle_conversation_interaction(
        self, conversation_id: str, request_id: str, request_info: Dict[str, Any]
    ) -> None:
        """Handle conversation type interaction

        Args:
            conversation_id: Conversation ID
            request_id: Request ID
            request_info: Request information
        """
        print("\nPlease enter your response (type 'exit' to end conversation):")

        # Execute blocking input() call in thread pool using run_in_executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input)

        # Process response
        if response.strip().lower() in ["exit", "quit", "结束", "退出"]:
            status = HumanLoopStatus.COMPLETED
            print("\nConversation ended")
        else:
            status = HumanLoopStatus.INPROGRESS

        # Update request information
        request_info["status"] = status
        request_info["response"] = response
        request_info["responded_by"] = "terminal_user"
        request_info["responded_at"] = datetime.now().isoformat()

        print("\nYour response has been recorded")

    async def async_cancel_request(self, conversation_id: str, request_id: str) -> bool:
        """Cancel human-in-the-loop request

        Args:
            conversation_id: Conversation identifier for multi-turn dialogues
            request_id: Request identifier for specific interaction request

        Return:
            bool: Whether cancellation was successful, True indicates successful cancellation,
                 False indicates cancellation failed
        """
        request_key = (conversation_id, request_id)
        if request_key in self._terminal_input_tasks:
            self._terminal_input_tasks[request_key].cancel()
            del self._terminal_input_tasks[request_key]

        # 调用父类方法取消请求
        return await super().async_cancel_request(conversation_id, request_id)

    async def async_cancel_conversation(self, conversation_id: str) -> bool:
        """Cancel the entire conversation

        Args:
            conversation_id: Conversation identifier

        Returns:
            bool: Whether cancellation was successful
        """
        # 取消所有相关的邮件检查任务
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._terminal_input_tasks:
                self._terminal_input_tasks[request_key].cancel()
                del self._terminal_input_tasks[request_key]

        # 调用父类方法取消对话
        return await super().async_cancel_conversation(conversation_id)
