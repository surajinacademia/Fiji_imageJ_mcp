"""Black-box tests: spawn ``python -m fiji_mcp`` and speak MCP over stdio."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastmcp")
from fastmcp import Client  # noqa: E402  (after importorskip)
from fastmcp.client.transports import StdioTransport  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "get_state",
    "search_commands",
    "run_command",
    "run_script",
    "open_image",
    "save_image",
    "get_results",
    "screenshot",
    "compare_screenshots",
}


def _stdio_server_env() -> dict[str, str]:
    env = {**os.environ}
    env.pop("FIJI_PATH", None)
    env.setdefault("PYTHONPATH", str(_REPO_ROOT / "src"))
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _stdio_transport(stderr_log: Path) -> StdioTransport:
    return StdioTransport(
        command=sys.executable,
        args=["-m", "fiji_mcp"],
        env=_stdio_server_env(),
        cwd=str(_REPO_ROOT),
        keep_alive=False,
        log_file=stderr_log,
    )


@pytest.mark.mcp_stdio
@pytest.mark.timeout(90)
async def test_mcp_stdio_list_tools_exposes_exact_handlers(tmp_path: Path) -> None:
    """MCP initialize + ``tools/list`` only; does not require ``FIJI_PATH`` or a local Fiji."""
    stderr_log = tmp_path / "stderr.log"
    transport = _stdio_transport(stderr_log)
    client = Client(transport, init_timeout=90, timeout=90)
    async with client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == EXPECTED
    assert stderr_log.read_text().count("Starting Fiji MCP stdio server") == 1
