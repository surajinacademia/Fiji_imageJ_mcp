"""Main entrypoint for the Fiji MCP server."""

from __future__ import annotations

import sys

from fiji_mcp.config.settings import load_settings
from fiji_mcp.utils.server_logging import configure_server_logging


def main() -> None:
    """Run the MCP server on stdio transport."""
    configure_server_logging()
    try:
        load_settings()
    except ValueError as error:
        print(f"fiji-mcp-server: invalid configuration: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    from fiji_mcp.server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
