"""Server bootstrap that registers tool modules."""

from fiji_mcp.utils.server_logging import configure_server_logging

configure_server_logging()

from fiji_mcp.mcp_instance import mcp
from fiji_mcp.tools import discovery, macro_runner, screenshot, workflow  # noqa: F401

__all__ = ["mcp"]
