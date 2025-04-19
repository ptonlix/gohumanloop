from gohumanloop.core.interface import (
    HumanLoopProvider,
)

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
    "HumanLoopProvider",
    "__version__",
]