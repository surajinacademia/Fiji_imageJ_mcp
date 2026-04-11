"""Shared MCP instance."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastmcp import FastMCP


def _package_version() -> str:
    try:
        return version("fiji-mcp-server")
    except PackageNotFoundError:
        return "0.0.0-dev"


_SERVER_INSTRUCTIONS = (
    "This server controls a local Fiji/ImageJ via PyImageJ (JPype). "
    "Use health_check before long jobs. "
    "When transport is stdio, ImageJ macros must not call print() — stdout is reserved for JSON-RPC; "
    "use macro return values or tool responses instead. "
    "For locked-down deployments set FIJI_DATA_ROOTS to restrict open_image/save_image paths."
)

mcp = FastMCP(
    "Fiji MCP Server",
    instructions=_SERVER_INSTRUCTIONS,
    version=_package_version(),
)
