from gohumanloop.core.interface import (
    HumanLoopProvider,
    ApprovalCallback,
    ApprovalStatus,
    ApprovalRequest,
    ApprovalResult
)
from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.providers.api_provider import APIProvider
from gohumanloop.adapters.langgraph_adapter import LanggraphAdapter, LanggraphApprovalCallback
from gohumanloop.adapters.crewai_adapter import CrewAIAdapter, CrewAIApprovalCallback
from gohumanloop.config.settings import Settings

# 创建默认设置
settings = Settings()

# 创建便捷函数
def create_api_provider(
    api_url: str | None = None,
    api_key: str | None = None,
    **kwargs
) -> APIProvider:
    """创建API提供者"""
    api_url = api_url or settings.get("api.url")
    api_key = api_key or settings.get("api.key")
    # 确保api_url和api_key不为None后再传入
    if api_url is None or api_key is None:
        raise ValueError("api_url and api_key cannot be None")
    return APIProvider(api_url=api_url, api_key=api_key, **kwargs)

def create_manager(
    provider: HumanLoopProvider | None = None,
    provider_id: str | None = None
) -> DefaultHumanLoopManager:
    """创建人机交互管理器"""
    manager = DefaultHumanLoopManager(provider)
    return manager

def create_langgraph_adapter(
    manager: DefaultHumanLoopManager | None = None,
    provider: HumanLoopProvider | None = None
) -> LanggraphAdapter:
    """创建Langgraph适配器"""
    if not manager and provider:
        manager = create_manager(provider)
    elif not manager:
        api_provider = create_api_provider()
        manager = create_manager(api_provider)

    return LanggraphAdapter(manager)

def create_crewai_adapter(
    manager: DefaultHumanLoopManager | None= None,
    provider: HumanLoopProvider | None = None
) -> CrewAIAdapter:
    """创建CrewAI适配器"""
    if not manager and provider:
        manager = create_manager(provider)
    elif not manager:
        api_provider = create_api_provider()
        manager = create_manager(api_provider)

    return CrewAIAdapter(manager)

__all__ = [
    "HumanLoopProvider",
    "ApprovalCallback",
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalResult",
    "DefaultHumanLoopManager",
    "APIProvider",
    "LanggraphAdapter",
    "LanggraphApprovalCallback",
    "CrewAIAdapter",
    "CrewAIApprovalCallback",
    "Settings",
    "settings",
    "create_api_provider",
    "create_manager",
    "create_langgraph_adapter",
    "create_crewai_adapter"
]