"""Lazy package exports (avoid importing the MCP server on ``import fiji_mcp``)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_import_keeps_mcp_lazy() -> None:
    env = {**os.environ, "PYTHONPATH": str(_REPO_ROOT / "src")}
    result = subprocess.run(  # noqa: S603 -- fixed interpreter and test script
        [
            sys.executable,
            "-c",
            "import sys; import fiji_mcp; assert 'fiji_mcp.server' not in sys.modules",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_mcp_is_fastmcp_after_attribute_access() -> None:
    import fiji_mcp

    mcp = fiji_mcp.mcp
    assert mcp.__class__.__name__ == "FastMCP"
