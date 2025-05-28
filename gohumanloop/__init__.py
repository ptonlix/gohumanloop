from gohumanloop.core.interface import (
    HumanLoopProvider,
    HumanLoopManager,
    HumanLoopCallback,
    HumanLoopResult,
    HumanLoopStatus,
    HumanLoopType,
)

from gohumanloop.core.manager import DefaultHumanLoopManager
from gohumanloop.manager.ghl_manager import GoHumanLoopManager

from gohumanloop.providers.ghl_provider import GoHumanLoopProvider
from gohumanloop.providers.api_provider import APIProvider
from gohumanloop.providers.base import BaseProvider
from gohumanloop.providers.terminal_provider import TerminalProvider

from gohumanloop.utils import run_async_safely, get_secret_from_env

from gohumanloop.adapters import HumanloopAdapter, AgentOpsHumanLoopCallback

# Conditionally import EmailProvider
try:
    from gohumanloop.providers.email_provider import EmailProvider  # noqa: F401

    _has_email = True
except ImportError:
    _has_email = False

# Dynamically get version number
try:
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("gohumanloop")
    except PackageNotFoundError:
        import os
        import tomli

        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pyproject_path = os.path.join(root_dir, "pyproject.toml")

        with open(pyproject_path, "rb") as f:
            pyproject_data = tomli.load(f)
            __version__ = pyproject_data["project"]["version"]
except (ImportError, FileNotFoundError, KeyError):
    __version__ = "0.1.0"

__all__ = [
    # Core Interfaces
    "HumanLoopProvider",
    "HumanLoopManager",
    "HumanLoopCallback",
    "HumanLoopResult",
    "HumanLoopStatus",
    "HumanLoopType",
    # Manager Implementations
    "DefaultHumanLoopManager",
    "GoHumanLoopManager",
    # Provider Implementations
    "BaseProvider",
    "APIProvider",
    "GoHumanLoopProvider",
    "TerminalProvider",
    # Adapter Implementations
    "HumanloopAdapter",
    "AgentOpsHumanLoopCallback",
    # Utility Functions
    "run_async_safely",
    "get_secret_from_env",
    # Version Information
    "__version__",
]

if _has_email:
    __all__.append("EmailProvider")
