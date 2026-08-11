"""Main entrypoint for the Fiji MCP server."""

from __future__ import annotations

import logging
import sys


def main() -> None:
    """Run the MCP server on stdio transport."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger(__name__).info("Starting Fiji MCP stdio server")

    from fiji_mcp.server import mcp

    mcp.run()


if __name__ == "__main__":
    main()
