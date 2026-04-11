"""Server bootstrap that registers tool modules."""

from fiji_mcp.utils.server_logging import configure_server_logging

configure_server_logging()

from fiji_mcp.mcp_instance import mcp
from fiji_mcp.tools import (  # noqa: F401
    discovery,
    macro_runner,
    screenshot,
    structured_tools,
    workflow,
)

__all__ = ["mcp"]
