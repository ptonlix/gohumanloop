import asyncio
import logging
from typing import Dict, Any, Optional, Tuple

import aiohttp
from pydantic import SecretStr
from concurrent.futures import ThreadPoolExecutor, Future
from gohumanloop.core.interface import HumanLoopResult, HumanLoopStatus, HumanLoopType
from gohumanloop.providers.base import BaseProvider
from gohumanloop.models.api_model import (
    APIResponse,
    HumanLoopRequestData,
    HumanLoopStatusParams,
    HumanLoopStatusResponse,
    HumanLoopCancelData,
    HumanLoopCancelConversationData,
    HumanLoopContinueData,
)

logger = logging.getLogger(__name__)


class APIProvider(BaseProvider):
    """API-based human-in-the-loop provider that supports integration with third-party service platforms

    This provider communicates with a central service platform via HTTP requests, where the service platform
    handles specific third-party service integrations (such as WeChat, Feishu, DingTalk, etc.).
    """

    def __init__(
        self,
        name: str,
        api_base_url: str,
        api_key: Optional[SecretStr] = None,
        default_platform: Optional[str] = None,
        request_timeout: int = 30,
        poll_interval: int = 5,
        max_retries: int = 3,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize API provider

        Args:
            name: Provider name
            api_base_url: Base URL for API service
            api_key: API authentication key (optional)
            default_platform: Default platform to use (e.g. "wechat", "feishu")
            request_timeout: API request timeout in seconds
            poll_interval: Polling interval in seconds
            max_retries: Maximum number of retry attempts
            config: Additional configuration parameters
        """
        super().__init__(name, config)
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.default_platform = default_platform
        self.request_timeout = request_timeout
        self.poll_interval = poll_interval
        self.max_retries = max_retries

        # Store the currently running polling tasks.
        self._poll_tasks: Dict[Tuple[str, str], Future] = {}
        # Create thread pool for background service execution
        self._executor = ThreadPoolExecutor(max_workers=10)

    def __del__(self) -> None:
        """析构函数，确保线程池被正确关闭"""
        self._executor.shutdown(wait=False)

        # 取消所有邮件检查任务
        for task_key, future in list(self._poll_tasks.items()):
            future.cancel()
        self._poll_tasks.clear()

    def __str__(self) -> str:
        """Returns a string description of this instance"""
        base_str = super().__str__()
        api_info = f"- API Provider: API-based human-in-the-loop implementation, connected to {self.api_base_url}\n"
        if self.default_platform:
            api_info += f"  Default Platform: {self.default_platform}\n"
        return f"{api_info}{base_str}"

    async def _async_make_api_request(
        self,
        endpoint: str,
        method: str = "POST",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make API request

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            data: Request body data
            params: URL query parameters
            headers: Request headers

        Returns:
            Dict[str, Any]: API response data

        Raises:
            Exception: If API request fails
        """
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"

        # Prepare request headers
        request_headers = {
            "Content-Type": "application/json",
        }
        # Add authentication information
        if self.api_key:
            request_headers[
                "Authorization"
            ] = f"Bearer {self.api_key.get_secret_value()}"

        # Merge custom headers
        if headers:
            request_headers.update(headers)

        # Prepare request data
        json_data = None
        if data:
            json_data = data

        # Send request
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                        headers=request_headers,
                        timeout=self.request_timeout,
                    ) as response:
                        response_data: Dict[str, Any] = await response.json()
                        # Check response status
                        if response.status >= 400:
                            error_msg = response_data.get(
                                "error", f"API request failed: {response.status}"
                            )
                            logger.error(f"API request failed: {error_msg}")

                            # Retry if not the last attempt
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(
                                    1 * (attempt + 1)
                                )  # Exponential backoff
                                continue

                            raise Exception(error_msg)

                        return response_data
            except asyncio.TimeoutError:
                logger.warning(
                    f"API request timeout (attempt {attempt+1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                raise Exception("API request timeout")
            except Exception as e:
                logger.error(f"API request error: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))
                    continue
                raise

        return None

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
            conversation_id: Conversation ID for multi-turn dialogue
            loop_type: Type of loop interaction
            context: Context information provided to humans
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and initial status
        """
        metadata = metadata or {}

        # Generate request ID
        request_id = self._generate_request_id()
        platform = metadata.get("platform", self.default_platform)
        # Store request information
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=loop_type,
            context=context,
            metadata={**metadata, "platform": platform},
            timeout=timeout,
        )

        # Determine which platform to use
        if not platform:
            self._update_request_status_error(
                conversation_id,
                request_id,
                "Platform not specified. Please set 'platform' in metadata or set default_platform during initialization",
            )
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error="Platform not specified. Please set 'platform' in metadata or set default_platform during initialization",
            )

        # Prepare API request data
        request_data = HumanLoopRequestData(
            task_id=task_id,
            conversation_id=conversation_id,
            request_id=request_id,
            loop_type=loop_type.value,
            context=context,
            platform=platform,
            metadata=metadata,
        ).model_dump()

        try:
            # Send API request
            response = await self._async_make_api_request(
                endpoint="v1/humanloop/request", method="POST", data=request_data
            )

            # Check API response
            response_data = response or {}
            api_response = APIResponse(**response_data)
            if not api_response.success:
                error_msg = (
                    api_response.error or "API request failed without error message"
                )
                # Update request status to error
                self._update_request_status_error(
                    conversation_id, request_id, error_msg
                )

                return HumanLoopResult(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    loop_type=loop_type,
                    status=HumanLoopStatus.ERROR,
                    error=error_msg,
                )

            # Create polling task
            self._poll_tasks[(conversation_id, request_id)] = self._executor.submit(
                self._run_async_poll_request_status,
                conversation_id,
                request_id,
                platform,
                timeout,
            )

            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.PENDING,
            )

        except Exception as e:
            logger.error(f"Failed to request human-in-the-loop: {str(e)}")
            # Update request status to error
            self._update_request_status_error(conversation_id, request_id, str(e))

            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=loop_type,
                status=HumanLoopStatus.ERROR,
                error=str(e),
            )

    def _run_async_poll_request_status(
        self,
        conversation_id: str,
        request_id: str,
        platform: str,
        timeout: Optional[int],
    ) -> None:
        """Run asynchronous API interaction in a separate thread"""
        # Create new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run interaction processing in the new event loop
            loop.run_until_complete(
                self._async_poll_request_status_with_timeout(
                    conversation_id, request_id, platform, timeout
                )
            )
        finally:
            loop.close()
            # Remove from task dictionary
            if (conversation_id, request_id) in self._poll_tasks:
                del self._poll_tasks[(conversation_id, request_id)]

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

    async def async_cancel_request(self, conversation_id: str, request_id: str) -> bool:
        """Cancel human-in-the-loop request

        Args:
            conversation_id: Conversation identifier for multi-turn dialogue
            request_id: Request identifier for specific interaction request

        Returns:
            bool: Whether cancellation was successful, True for success, False for failure
        """
        # First call parent method to update local state
        result = await super().async_cancel_request(conversation_id, request_id)
        if not result:
            return False

        # Get request information
        request_info = self._get_request(conversation_id, request_id)
        if not request_info:
            return False

        # Get platform information
        platform = request_info.get("metadata", {}).get("platform")
        if not platform:
            logger.error("Cancel request failed: Platform information not found")
            return False

        try:
            # Send API request to cancel request
            cancel_data = HumanLoopCancelData(
                conversation_id=conversation_id,
                request_id=request_id,
                platform=platform,
            ).model_dump()

            response = await self._async_make_api_request(
                endpoint="v1/humanloop/cancel", method="POST", data=cancel_data
            )

            # Check API response
            response_data = response or {}
            api_response = APIResponse(**response_data)
            if not api_response.success:
                error_msg = (
                    api_response.error or "Cancel request failed without error message"
                )
                logger.error(f"Cancel request failed: {error_msg}")
                return False

            # Cancel polling task
            if (conversation_id, request_id) in self._poll_tasks:
                self._poll_tasks[(conversation_id, request_id)].cancel()
                del self._poll_tasks[(conversation_id, request_id)]

            return True

        except Exception as e:
            logger.error(f"Cancel request failed: {str(e)}")
            return False

    async def async_cancel_conversation(self, conversation_id: str) -> bool:
        """Cancel entire conversation

        Args:
            conversation_id: Conversation identifier

        Returns:
            bool: Whether cancellation was successful
        """
        # First call parent method to update local state
        result = await super().async_cancel_conversation(conversation_id)
        if not result:
            return False

        # Get all requests in the conversation
        request_ids = self._get_conversation_requests(conversation_id)
        if not request_ids:
            return True  # No requests to cancel

        # Get platform info from first request (assuming all requests use same platform)
        first_request = self._get_request(conversation_id, request_ids[0])
        if not first_request:
            return False

        platform = first_request.get("metadata", {}).get("platform")
        if not platform:
            logger.error("Cancel conversation failed: Platform information not found")
            return False

        try:
            # Send API request to cancel conversation
            cancel_data = HumanLoopCancelConversationData(
                conversation_id=conversation_id, platform=platform
            ).model_dump()

            response = await self._async_make_api_request(
                endpoint="v1/humanloop/cancel_conversation",
                method="POST",
                data=cancel_data,
            )

            # Check API response
            response_data = response or {}
            api_response = APIResponse(**response_data)
            if not api_response.success:
                error_msg = (
                    api_response.error
                    or "Cancel conversation failed without error message"
                )
                logger.error(f"Cancel conversation failed: {error_msg}")
                return False

            # Cancel all polling tasks
            for request_id in request_ids:
                if (conversation_id, request_id) in self._poll_tasks:
                    self._poll_tasks[(conversation_id, request_id)].cancel()
                    del self._poll_tasks[(conversation_id, request_id)]

            return True

        except Exception as e:
            logger.error(f"Cancel conversation failed: {str(e)}")
            return False

    async def async_continue_humanloop(
        self,
        conversation_id: str,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> HumanLoopResult:
        """Continue human-in-the-loop interaction

        Args:
            conversation_id: Conversation ID for multi-turn dialogue
            context: Context information provided to humans
            metadata: Additional metadata
            timeout: Request timeout in seconds

        Returns:
            HumanLoopResult: Result object containing request ID and status
        """
        # 检查对话是否存在
        conversation_info = self._get_conversation(conversation_id)
        if not conversation_info:
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id="",
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=f"Conversation '{conversation_id}' not found",
            )

        metadata = metadata or {}

        # Generate request ID
        request_id = self._generate_request_id()

        # Get task ID
        task_id = conversation_info.get("task_id", "unknown_task")
        # Determine which platform to use
        platform = metadata.get("platform", self.default_platform)

        # Store request information
        self._store_request(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            loop_type=HumanLoopType.CONVERSATION,
            context=context,
            metadata={**metadata, "platform": platform},
            timeout=timeout,
        )

        if not platform:
            self._update_request_status_error(
                conversation_id,
                request_id,
                "Platform not specified. Please set 'platform' in metadata or set default_platform during initialization",
            )
            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error="Platform not specified. Please set 'platform' in metadata or set default_platform during initialization",
            )

        # Prepare API request data
        continue_data = HumanLoopContinueData(
            conversation_id=conversation_id,
            request_id=request_id,
            task_id=task_id,
            context=context,
            platform=platform,
            metadata=metadata,
        ).model_dump()

        try:
            # Send API request
            response = await self._async_make_api_request(
                endpoint="v1/humanloop/continue", method="POST", data=continue_data
            )

            # Check API response
            response_data = response or {}
            api_response = APIResponse(**response_data)
            if not api_response.success:
                error_msg = (
                    api_response.error
                    or "Continue conversation failed without error message"
                )

                self._update_request_status_error(
                    conversation_id, request_id, error_msg
                )
                return HumanLoopResult(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    loop_type=HumanLoopType.CONVERSATION,
                    status=HumanLoopStatus.ERROR,
                    error=error_msg,
                )

            # Create polling task
            self._poll_tasks[(conversation_id, request_id)] = self._executor.submit(
                self._run_async_poll_request_status,
                conversation_id,
                request_id,
                platform,
                timeout,
            )

            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.PENDING,
            )

        except Exception as e:
            logger.error(f"Failed to continue human-in-the-loop: {str(e)}")
            self._update_request_status_error(conversation_id, request_id, str(e))

            return HumanLoopResult(
                conversation_id=conversation_id,
                request_id=request_id,
                loop_type=HumanLoopType.CONVERSATION,
                status=HumanLoopStatus.ERROR,
                error=str(e),
            )

    async def _async_poll_request_status_with_timeout(
        self,
        conversation_id: str,
        request_id: str,
        platform: str,
        timeout: Optional[int],
    ) -> None:
        """Poll request status with optional timeout

        Args:
            conversation_id: Conversation identifier
            request_id: Request identifier
            platform: Platform identifier
            timeout: Optional timeout in seconds. If specified, polling will stop after timeout period
        """

        try:
            if timeout:
                # 使用 wait_for 设置超时
                await asyncio.wait_for(
                    self._async_poll_request_status(
                        conversation_id, request_id, platform
                    ),
                    timeout=timeout,
                )
            else:
                # 无超时限制
                await self._async_poll_request_status(
                    conversation_id, request_id, platform
                )

        except asyncio.TimeoutError:
            # 超时处理
            request_info = self._get_request(conversation_id, request_id)
            if request_info and request_info.get("status") == HumanLoopStatus.PENDING:
                request_info["status"] = HumanLoopStatus.EXPIRED
                request_info["error"] = "Request timed out"
                logger.info(
                    f"\nRequest {request_id} has timed out after {timeout} seconds"
                )

    async def _async_poll_request_status(
        self, conversation_id: str, request_id: str, platform: str
    ) -> None:
        """Poll request status

        Args:
            conversation_id: Conversation identifier
            request_id: Request identifier
            platform: Platform identifier
        """
        try:
            while True:
                # Get request information
                request_info = self._get_request(conversation_id, request_id)
                if not request_info:
                    logger.warning(
                        f"Polling stopped: Request '{request_id}' not found in conversation '{conversation_id}'"
                    )
                    return

                # Stop polling if request is in final status
                status = request_info.get("status")
                if status not in [HumanLoopStatus.PENDING, HumanLoopStatus.INPROGRESS]:
                    return

                # Send API request to get status
                params = HumanLoopStatusParams(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    platform=platform,
                ).model_dump()

                response = await self._async_make_api_request(
                    endpoint="v1/humanloop/status", method="GET", params=params
                )

                # Parse response
                response_data = response or {}
                status_response = HumanLoopStatusResponse(**response_data)

                # Log error but continue polling if request fails
                if not status_response.success:
                    logger.warning(f"Failed to get status: {status_response.error}")
                    await asyncio.sleep(self.poll_interval)
                    continue

                # Parse status
                try:
                    new_status = HumanLoopStatus(status_response.status)
                except ValueError:
                    logger.warning(
                        f"Unknown status value: {status_response.status}, using PENDING"
                    )
                    new_status = HumanLoopStatus.PENDING

                # Update request information
                request_key = (conversation_id, request_id)
                if request_key in self._requests:
                    self._requests[request_key]["status"] = new_status

                    # Update response data
                    for field in [
                        "response",
                        "feedback",
                        "responded_by",
                        "responded_at",
                        "error",
                    ]:
                        value = getattr(status_response, field, None)
                        if value is not None:
                            self._requests[request_key][field] = value

                    # Stop polling if request is in final status
                    if new_status not in [
                        HumanLoopStatus.PENDING,
                        HumanLoopStatus.INPROGRESS,
                    ]:
                        return

                # Wait for next polling interval
                await asyncio.sleep(self.poll_interval)

        except asyncio.CancelledError:
            logger.info(
                f"Polling task cancelled: conversation '{conversation_id}', request '{request_id}'"
            )
            return
        except Exception as e:
            logger.error(f"Polling task error: {str(e)}")
            return
