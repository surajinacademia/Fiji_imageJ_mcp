"""Fiji MCP server package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

try:
    __version__ = version("fiji-mcp-server")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ["mcp", "__version__"]


def __getattr__(name: str) -> Any:
    if name == "mcp":
        from fiji_mcp.server import mcp as _mcp

        globals()["mcp"] = _mcp
        return _mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
