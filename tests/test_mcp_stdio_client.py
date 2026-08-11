"""Black-box tests: spawn ``python -m fiji_mcp`` and speak MCP over stdio."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastmcp")
from fastmcp import Client  # noqa: E402  (after importorskip)
from fastmcp.client.transports import StdioTransport  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PRECONFIGURED_ROOT_LOGGER_SERVER = "\n".join(
    (
        "import logging",
        "import sys",
        "logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)",
        "from fiji_mcp.__main__ import main",
        "main()",
    )
)

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


def _stdio_server_env(fiji_path: Path | None = None) -> dict[str, str]:
    env = {**os.environ}
    inherited_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(_REPO_ROOT / "src"), inherited_pythonpath) if value
    )
    env.setdefault("PYTHONUNBUFFERED", "1")
    if fiji_path is None:
        env.pop("FIJI_PATH", None)
        env.pop("FIJI_MODE", None)
    else:
        env["FIJI_PATH"] = str(fiji_path)
        env["FIJI_MODE"] = "headless"
    return env


def _stdio_transport(stderr_log: Path, fiji_path: Path | None = None) -> StdioTransport:
    return StdioTransport(
        command=sys.executable,
        args=["-m", "fiji_mcp"],
        env=_stdio_server_env(fiji_path),
        cwd=str(_REPO_ROOT),
        keep_alive=False,
        log_file=stderr_log,
    )


def _preconfigured_root_logger_transport(stderr_log: Path) -> StdioTransport:
    return StdioTransport(
        command=sys.executable,
        args=["-c", _PRECONFIGURED_ROOT_LOGGER_SERVER],
        env=_stdio_server_env(),
        cwd=str(_REPO_ROOT),
        keep_alive=False,
        log_file=stderr_log,
    )


def _live_fiji_root() -> Path:
    configured = os.environ.get("FIJI_PATH", "").strip()
    if not configured:
        pytest.skip("Set FIJI_PATH to run local Fiji stdio integration tests")
    root = Path(configured).expanduser().resolve()
    if not (root / "jars").is_dir() or not (root / "plugins").is_dir():
        pytest.skip(f"FIJI_PATH is not a Fiji root: {root}")
    return root


def _integration_image() -> Path:
    configured = os.environ.get("FIJI_TEST_IMAGE", "").strip()
    image_path = (
        Path(configured).expanduser()
        if configured
        else _REPO_ROOT / "demo_images" / "sample_gradient.pgm"
    )
    if not image_path.is_file():
        pytest.skip(f"Integration image is unavailable: {image_path}")
    return image_path.resolve()


def _tool_payload(result: Any) -> dict[str, Any]:
    if isinstance(result.data, dict):
        return result.data
    if isinstance(result.structured_content, dict):
        return result.structured_content
    raise AssertionError(f"Expected structured tool payload, got {result!r}")


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


@pytest.mark.mcp_stdio
@pytest.mark.timeout(90)
async def test_preconfigured_root_stdout_logger_cannot_corrupt_mcp_protocol(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A pre-existing root handler must be replaced before stdio startup logs."""
    stderr_log = tmp_path / "stderr.log"
    transport = _preconfigured_root_logger_transport(stderr_log)
    client = Client(transport, init_timeout=90, timeout=90)
    async with client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == EXPECTED
    assert not any(
        record.name == "mcp.client.stdio"
        and record.getMessage() == "Failed to parse JSONRPC message from server"
        for record in caplog.records
    )
    assert stderr_log.read_text().count("Starting Fiji MCP stdio server") == 1


@pytest.mark.integration
@pytest.mark.mcp_stdio
@pytest.mark.timeout(300)
async def test_mcp_stdio_headless_current_survives_cross_request_threads(
    tmp_path: Path,
) -> None:
    """A headless image opened in one MCP request stays usable in later requests."""
    root = _live_fiji_root()
    image_path = _integration_image()
    transport = _stdio_transport(tmp_path / "fiji-stderr.log", root)
    client = Client(transport, init_timeout=300, timeout=300)
    async with client:
        opened = await client.call_tool("open_image", {"path": str(image_path)})
        assert opened.is_error is False

        state = await client.call_tool("get_state", {})
        assert state.is_error is False
        state_payload = _tool_payload(state)
        assert state_payload["active_image"]["width"] > 0

        shot = await client.call_tool("screenshot", {"target": "active_image"})
        assert shot.is_error is False
        assert shot.content
        assert _tool_payload(shot)["target"] == "active_image"

        state_after = await client.call_tool("get_state", {})
        assert state_after.is_error is False
        assert _tool_payload(state_after)["active_image"]["width"] > 0


@pytest.mark.integration
@pytest.mark.mcp_stdio
@pytest.mark.timeout(300)
async def test_mcp_stdio_java_output_stays_off_protocol(tmp_path: Path) -> None:
    """IJM, Groovy, and Java stdout leave the JSON-RPC stream synchronized."""
    root = _live_fiji_root()
    stderr_log = tmp_path / "fiji-stderr.log"
    transport = _stdio_transport(stderr_log, root)
    client = Client(transport, init_timeout=300, timeout=300)
    async with client:
        ijm_result = await client.call_tool(
            "run_script",
            {"language": "ijm", "code": 'print("ijm-output");'},
        )
        groovy_result = await client.call_tool(
            "run_script",
            {
                "language": "groovy",
                "code": 'println("groovy-output")\nSystem.out.println("java-output")',
            },
        )
        assert ijm_result.is_error is False
        assert groovy_result.is_error is False
        assert "ijm-output" in _tool_payload(ijm_result)["log_tail"]

        state = await client.call_tool("get_state", {})
        assert state.is_error is False
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == EXPECTED

    stderr_contents = stderr_log.read_text(errors="replace")
    assert "groovy-output" in stderr_contents
    assert "java-output" in stderr_contents
