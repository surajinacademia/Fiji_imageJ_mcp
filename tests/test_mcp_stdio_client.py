"""Black-box tests: spawn ``python -m fiji_mcp`` and speak MCP over stdio (FastMCP client).

These tests intentionally avoid importing ``fiji_mcp.tools.*`` so they exercise the same
JSON-RPC path as Cursor / other MCP hosts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastmcp")
from fastmcp import Client  # noqa: E402  (after importorskip)
from fastmcp.client.transports import StdioTransport  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _stdio_server_env() -> dict[str, str]:
    env = {**os.environ}
    env.setdefault("PYTHONPATH", str(_REPO_ROOT / "src"))
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _stdio_transport(*, fiji_mode: str | None = None) -> StdioTransport:
    env = _stdio_server_env()
    if fiji_mode is not None:
        env["FIJI_MODE"] = fiji_mode
    return StdioTransport(
        command=sys.executable,
        args=["-m", "fiji_mcp"],
        env=env,
        cwd=str(_REPO_ROOT),
        keep_alive=False,
    )


def _default_demo_image() -> Path | None:
    demo_dir = _REPO_ROOT / "demo_images"
    if not demo_dir.is_dir():
        return None
    preferred = demo_dir / "sample_gradient.pgm"
    if preferred.is_file():
        return preferred
    for path in sorted(demo_dir.iterdir()):
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower()
            in {
                ".pgm",
                ".pbm",
                ".ppm",
                ".tif",
                ".tiff",
                ".png",
                ".jpg",
                ".jpeg",
            }
        ):
            return path
    return None


def _fiji_stdio_ready() -> bool:
    return bool(os.environ.get("FIJI_PATH", "").strip()) and bool(_default_demo_image())


@pytest.mark.mcp_stdio
@pytest.mark.timeout(90)
async def test_mcp_stdio_list_tools_exposes_expected_handlers() -> None:
    """MCP initialize + ``tools/list`` only; does not require ``FIJI_PATH`` or a local Fiji."""
    transport = _stdio_transport()
    client = Client(transport, init_timeout=90, timeout=90)
    async with client:
        tools = await client.list_tools()
    names = {t.name for t in tools}
    expected = {
        "health_check",
        "run_macro",
        "open_image",
        "save_image",
        "run_batch_macros",
        "list_all_commands",
        "search_commands",
        "describe_plugin",
        "list_extensions",
        "list_open_images",
        "get_image_info",
        "screenshot_fiji",
        "run_workflow",
        "parse_macro_output",
        "compare_screenshots",
        "list_macro_templates",
        "get_macro_template",
        "get_session_trace",
        "clear_session_trace",
    }
    missing = expected - names
    assert not missing, (
        f"MCP tools/list missing: {sorted(missing)}; got {sorted(names)}"
    )


@pytest.mark.integration
@pytest.mark.mcp_stdio
@pytest.mark.timeout(240)
@pytest.mark.skipif(
    not _fiji_stdio_ready(),
    reason="Set FIJI_PATH and keep demo_images/ for MCP stdio integration",
)
async def test_mcp_stdio_health_check_roundtrip() -> None:
    transport = _stdio_transport(fiji_mode="headless")
    client = Client(transport, init_timeout=240, timeout=240)
    async with client:
        res = await client.call_tool("health_check", {})
    assert res.is_error is False
    data = res.data
    assert getattr(data, "ok", False) is True
    assert getattr(data, "initialized", False) is True
    assert getattr(data, "mode", "") == "headless"


@pytest.mark.integration
@pytest.mark.mcp_stdio
@pytest.mark.timeout(240)
@pytest.mark.skipif(
    not _fiji_stdio_ready(),
    reason="Set FIJI_PATH and keep demo_images/ for MCP stdio integration",
)
async def test_mcp_stdio_open_image_get_info_screenshot_active_image() -> None:
    demo = _default_demo_image()
    assert demo is not None
    image_path = str(demo.resolve())

    transport = _stdio_transport(fiji_mode="headless")
    client = Client(transport, init_timeout=240, timeout=240)
    async with client:
        h = await client.call_tool("health_check", {})
        assert h.is_error is False

        opened = await client.call_tool("open_image", {"path": image_path})
        assert opened.is_error is False
        o = opened.data
        assert getattr(o, "ok", False) is True
        w, h_ = int(getattr(o, "width", 0)), int(getattr(o, "height", 0))
        assert w > 0 and h_ > 0

        info = await client.call_tool("get_image_info", {})
        assert info.is_error is False
        inf = info.data
        assert int(getattr(inf, "width", 0)) == w
        assert int(getattr(inf, "height", 0)) == h_

        shot = await client.call_tool(
            "screenshot_fiji", {"capture_mode": "active_image"}
        )
        assert shot.is_error is False
        s = shot.data
        b64 = getattr(s, "image_base64", "") or ""
        assert len(b64) > 64
