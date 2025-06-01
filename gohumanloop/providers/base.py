from abc import ABC
from typing import Dict, Any, Optional, List, Tuple
import json
import uuid
from datetime import datetime
from collections import defaultdict
from gohumanloop.utils.threadsafedict import ThreadSafeDict
from gohumanloop.utils import run_async_safely

from gohumanloop.core.interface import (
    HumanLoopProvider,
    HumanLoopResult,
    HumanLoopStatus,
    HumanLoopType,
)


class BaseProvider(HumanLoopProvider, ABC):
    """Base implementation of human-in-the-loop provider"""

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # Custom name, will use UUID if not provided
        self.name = name
        # Store request information using (conversation_id, request_id) as key
        self._requests: ThreadSafeDict[
            Tuple[str, str], Dict[str, Any]
        ] = (
            ThreadSafeDict()
        )  # Using thread-safe dictionary to store request information
        # Store conversation information, including request list and latest request ID
        self._conversations: Dict[str, Dict[str, Any]] = {}
        # For quick lookup of requests in conversations
        self._conversation_requests: defaultdict[str, List[str]] = defaultdict(list)

        self.prompt_template = self.config.get("prompt_template", "{context}")

    def __str__(self) -> str:
        """Returns a string description of this instance"""
        total_conversations = len(self._conversations)
        total_requests = len(self._requests)
        active_requests = sum(
            1
            for req in self._requests.values()
            if req["status"] in [HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS]
        )

        return (
            f"conversations={total_conversations}, "
            f"total_requests={total_requests}, "
            f"active_requests={active_requests})"
        )

    def __repr__(self) -> str:
        """Returns a detailed string representation of this instance"""
        return self.__str__()

    def _generate_request_id(self) -> str:
        """Generates a unique request ID"""
        return str(uuid.uuid4())

    def _update_request_status_error(
        self,
        conversation_id: str,
        request_id: str,
        error: Optional[str] = None,
    ) -> None:
        """Update request status"""
        request_key = (conversation_id, request_id)
        if request_key in self._requests:
            self._requests[request_key]["status"] = HumanLoopStatus.ERROR
            self._requests[request_key]["error"] = error

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
        """Store request information"""
        # Store request information using tuple (conversation_id, request_id) as key
        self._requests[(conversation_id, request_id)] = {
            "task_id": task_id,
            "loop_type": loop_type,
            "context": context,
            "metadata": metadata,
            "created_at": datetime.now().isoformat(),
            "status": HumanLoopStatus.PENDING,
            "timeout": timeout,
        }

        # Update conversation information
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = {
                "task_id": task_id,
                "latest_request_id": None,
                "created_at": datetime.now().isoformat(),
            }

        # Add request to conversation request list
        self._conversation_requests[conversation_id].append(request_id)
        # Update latest request ID
        self._conversations[conversation_id]["latest_request_id"] = request_id

    def _get_request(
        self, conversation_id: str, request_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get request information"""
        ret: Optional[Dict[str, Any]] = self._requests.get(
            (conversation_id, request_id)
        )
        return ret

    def _get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation information"""
        return self._conversations.get(conversation_id)

    def _get_conversation_requests(self, conversation_id: str) -> List[str]:
        """Get all request IDs in the conversation"""
        return self._conversation_requests.get(conversation_id, [])

    async def async_request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Request human-in-the-loop interaction

        Args:
            task_id: Task identifier
            conversation_id: Conversation ID for multi-turn dialogues
            loop_type: Type of human loop interaction
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and initial status
        """
        # Subclasses must implement this method
        raise NotImplementedError("Subclasses must implement request_humanloop")

    def request_humanloop(
        self,
        task_id: str,
        conversation_id: str,
        loop_type: HumanLoopType,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Request human-in-the-loop interaction (synchronous version)

        Args:
            task_id: Task identifier
            conversation_id: Conversation ID for multi-turn dialogues
            loop_type: Type of human loop interaction
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and initial status
        """

        result: HumanLoopResult = run_async_safely(
            self.async_request_humanloop(
                task_id=task_id,
                conversation_id=conversation_id,
                loop_type=loop_type,
                context=context,
                metadata=metadata,
                timeout=timeout,
            )
        )
        return result

    async def async_check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        """Check request status

        Args:
            conversation_id: Conversation identifier for multi-turn dialogues
            request_id: Request identifier for specific interaction request

        Returns:
            HumanLoopResult: Result object containing current request status, including status, response data, etc.
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

        # Subclasses need to implement specific status check logic
        raise NotImplementedError("Subclasses must implement check_request_status")

    def check_request_status(
        self, conversation_id: str, request_id: str
    ) -> HumanLoopResult:
        """Check conversation status (synchronous version)

        Args:
            conversation_id: Conversation identifier

        Returns:
            HumanLoopResult: Result containing the status of the latest request in the conversation
        """

        result: HumanLoopResult = run_async_safely(
            self.async_check_request_status(
                conversation_id=conversation_id, request_id=request_id
            )
        )

        return result

    async def async_check_conversation_status(
        self, conversation_id: str
    ) -> HumanLoopResult:
        """Check conversation status

        Args:
            conversation_id: Conversation identifier

        Returns:
            HumanLoopResult: Result containing the status of the latest request in the conversation
        """
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found",
            )

        latest_request_id = conversation_info.get("latest_request_id")
        if not latest_request_id:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"No requests found in conversation '{conversation_id}'",
            )

        return await self.async_check_request_status(conversation_id, latest_request_id)

    def check_conversation_status(self, conversation_id: str) -> HumanLoopResult:
        """Check conversation status (synchronous version)

        Args:
            conversation_id: Conversation identifier

        Returns:
            HumanLoopResult: Result containing the status of the latest request in the conversation
        """

        result: HumanLoopResult = run_async_safely(
            self.async_check_conversation_status(conversation_id=conversation_id)
        )

        return result

    async def async_cancel_request(self, conversation_id: str, request_id: str) -> bool:
        """Cancel human-in-the-loop request

        Args:
            conversation_id: Conversation identifier for multi-turn dialogues
            request_id: Request identifier for specific interaction request

        Returns:
            bool: Whether cancellation was successful, True indicates success, False indicates failure
        """

        request_key = (conversation_id, request_id)
        if request_key in self._requests:
            # Update request status to cancelled
            self._requests[request_key]["status"] = HumanLoopStatus.CANCELLED
            return True
        return False

    def cancel_request(self, conversation_id: str, request_id: str) -> bool:
        """Cancel human-in-the-loop request (synchronous version)

        Args:
            conversation_id: Conversation identifier for multi-turn dialogues
            request_id: Request identifier for specific interaction request

        Returns:
            bool: Whether cancellation was successful, True indicates success, False indicates failure
        """

        result: bool = run_async_safely(
            self.async_cancel_request(
                conversation_id=conversation_id, request_id=request_id
            )
        )

        return result

    async def async_cancel_conversation(self, conversation_id: str) -> bool:
        """Cancel the entire conversation

        Args:
            conversation_id: Conversation identifier

        Returns:
            bool: Whether the cancellation was successful
        """
        if conversation_id not in self._conversations:
            return False

        # Cancel all requests in the conversation
        success = True
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                # Update request status to cancelled
                # Only requests in intermediate states (PENDING/IN_PROGRESS) can be cancelled
                if self._requests[request_key]["status"] in [
                    HumanLoopStatus.PENDING,
                    HumanLoopStatus.INPROGRESS,
                ]:
                    self._requests[request_key]["status"] = HumanLoopStatus.CANCELLED
            else:
                success = False

        return success

    def cancel_conversation(self, conversation_id: str) -> bool:
        """Cancel the entire conversation (synchronous version)

        Args:
            conversation_id: Conversation identifier

        Returns:
            bool: Whether the cancellation was successful
        """

        result: bool = run_async_safely(
            self.async_cancel_conversation(conversation_id=conversation_id)
        )

        return result

    async def async_continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Continue human-in-the-loop interaction

        Args:
            conversation_id: Conversation ID for multi-turn dialogues
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

        # Subclasses need to implement specific continuation logic
        raise NotImplementedError("Subclasses must implement continue_humanloop")

    def continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Continue human-in-the-loop interaction (synchronous version)

        Args:
            conversation_id: Conversation ID for multi-turn dialogues
            context: Context information provided to human
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and status
        """

        result: HumanLoopResult = run_async_safely(
            self.async_continue_humanloop(
                conversation_id=conversation_id,
                context=context,
                metadata=metadata,
                timeout=timeout,
            )
        )

        return result

    async def async_get_conversation_history(
        self, conversation_id: str
    ) -> List[Dict[str, Any]]:
        """Get complete history for the specified conversation

        Args:
            conversation_id: Conversation identifier

        Returns:
            List[Dict[str, Any]]: List of conversation history records, each containing request ID,
                                 status, context, response and other information
        """
        conversation_history = []
        for request_id in self._get_conversation_requests(conversation_id):
            request_key = (conversation_id, request_id)
            if request_key in self._requests:
                request_info = self._requests[request_key]
                conversation_history.append(
                    {
                        "request_id": request_id,
                        "status": request_info.get("status").value
                        if request_info.get("status")
                        else None,
                        "context": request_info.get("context"),
                        "response": request_info.get("response"),
                        "responded_by": request_info.get("responded_by"),
                        "responded_at": request_info.get("responded_at"),
                    }
                )
        return conversation_history

    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get complete history for the specified conversation (synchronous version)

        Args:
            conversation_id: Conversation identifier

        Returns:
            List[Dict[str, Any]]: List of conversation history records, each containing request ID,
                                 status, context, response and other information
        """

        result: List[Dict[str, Any]] = run_async_safely(
            self.async_get_conversation_history(conversation_id=conversation_id)
        )

        return result

    def build_prompt(
        self,
        task_id: str,
        conversation_id: str,
        request_id: str,
        loop_type: Any,
        created_at: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        color: Optional[bool] = None,
    ) -> str:
        """
        Dynamically generate prompt based on content, only showing sections with content,
        and adapt to different terminal color display.
        color: None=auto detect, True=force color, False=no color
        """

        # Auto detect if terminal supports ANSI colors
        def _supports_color() -> bool:
            try:
                import sys

                if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
                    return False
                import os

                if os.name == "nt":
                    # Windows 10+ supports ANSI, older versions don't
                    return "ANSICON" in os.environ or "WT_SESSION" in os.environ
                return True
            except Exception:
                return False

        if color is None:
            color = _supports_color()

        # Define colors
        if color:
            COLOR_TITLE = "\033[94m"  # bright blue
            COLOR_RESET = "\033[0m"
        else:
            COLOR_TITLE = ""
            COLOR_RESET = ""

        lines = []
        lines.append(f"{COLOR_TITLE}=== Task Information ==={COLOR_RESET}")
        lines.append(f"Task ID: {task_id}")
        lines.append(f"Conversation ID: {conversation_id}")
        lines.append(f"Request ID: {request_id}")
        lines.append(f"HumanLoop Type: {getattr(loop_type, 'value', loop_type)}")
        lines.append(f"Created At: {created_at}")

        if context.get("message"):
            lines.append(f"\n{COLOR_TITLE}=== Main Context ==={COLOR_RESET}")
            lines.append(json.dumps(context["message"], indent=2, ensure_ascii=False))

        if context.get("additional"):
            lines.append(f"\n{COLOR_TITLE}=== Additional Context ==={COLOR_RESET}")
            lines.append(
                json.dumps(context["additional"], indent=2, ensure_ascii=False)
            )

        if metadata:
            lines.append(f"\n{COLOR_TITLE}=== Metadata ==={COLOR_RESET}")
            lines.append(json.dumps(metadata, indent=2, ensure_ascii=False))

        if context.get("question"):
            lines.append(f"\n{COLOR_TITLE}=== Question ==={COLOR_RESET}")
            lines.append(str(context["question"]))

        lines.append(f"\n{COLOR_TITLE}=== END ==={COLOR_RESET}")

        return "\n".join(lines)
