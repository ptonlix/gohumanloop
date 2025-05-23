import os
from typing import Dict, Any, Optional

from gohumanloop.models.glh_model import GoHumanLoopConfig
from gohumanloop.providers.api_provider import APIProvider
from gohumanloop.utils import get_secret_from_env


class GoHumanLoopProvider(APIProvider):
    """
    GoHumanLoop platform provider class.
    This class is a concrete implementation of the `APIProvider` class.
    The `GoHumanLoopProvider` class is responsible for interacting with the GoHumanLoop platform.
    """

    def __init__(
        self,
        name: str,
        request_timeout: int = 30,
        poll_interval: int = 5,
        max_retries: int = 3,
        default_platform: Optional[str] = "GoHumanLoop",
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize GoHumanLoop provider

        Args:
            name: Provider name
            default_platform: Default platform, e.g. "wechat", "feishu" etc.
            request_timeout: API request timeout in seconds
            poll_interval: Polling interval in seconds
            max_retries: Maximum number of retries
            config: Additional configuration parameters
        """
        # Get API key from environment variables (if not provided)
        api_key = get_secret_from_env("GOHUMANLOOP_API_KEY")

        if api_key is None:
            raise ValueError("GOHUMANLOOP_API_KEY environment variable is not set!")

        # Get API base URL from environment variables (if not provided)
        api_base_url = os.environ.get(
            "GOHUMANLOOP_API_BASE_URL", "https://www.gohumanloop.com"
        )

        # Validate configuration using pydantic model
        ghl_config = GoHumanLoopConfig(api_key=api_key, api_base_url=api_base_url)

        super().__init__(
            name=name,
            api_base_url=ghl_config.api_base_url,
            api_key=ghl_config.api_key,
            default_platform=default_platform,
            request_timeout=request_timeout,
            poll_interval=poll_interval,
            max_retries=max_retries,
            config=config,
        )

    def __str__(self) -> str:
        """Returns a string description of this instance"""
        base_str = super().__str__()
        ghl_info = (
            "- GoHumanLoop Provider: Connected to GoHumanLoop Official Platform\n"
        )
        return f"{ghl_info}{base_str}"
