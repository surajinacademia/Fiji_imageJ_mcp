"""Explicit registration for Fiji's public MCP tools."""

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from fiji_mcp import __version__
from fiji_mcp.tools import (
    compare_screenshots,
    get_results,
    get_state,
    open_image,
    run_command,
    run_script,
    save_image,
    screenshot,
    search_commands,
)

mcp = FastMCP(
    "Fiji MCP Server",
    version=__version__,
    instructions=(
        "Control one local Fiji instance. Use search_commands and run_command for registered "
        "plugins; use run_script for IJM/Groovy fallback. This trusted local server can execute "
        "arbitrary scripts. Fiji operations run sequentially."
    ),
)

READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True)
CHANGE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

for function, annotations in (
    (get_state, READ),
    (search_commands, READ),
    (run_command, DESTRUCTIVE),
    (run_script, DESTRUCTIVE),
    (open_image, CHANGE),
    (save_image, DESTRUCTIVE),
    (get_results, READ),
    (screenshot, DESTRUCTIVE),
    (compare_screenshots, DESTRUCTIVE),
):
    mcp.tool(annotations=annotations, output_schema=None)(function)

__all__ = ["mcp"]
