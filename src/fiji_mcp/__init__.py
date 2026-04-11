"""Fiji MCP server package."""

from __future__ import annotations

from typing import Any

from fiji_mcp._version import __version__

__all__ = ["mcp", "__version__"]


def __getattr__(name: str) -> Any:
    if name == "mcp":
        from fiji_mcp.server import mcp as _mcp

        globals()["mcp"] = _mcp
        return _mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
