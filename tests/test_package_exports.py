"""Lazy package exports (avoid importing the MCP server on ``import fiji_mcp``)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib

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


def test_runtime_dependencies_are_minimal():
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["version"] == "0.2.0"
    assert project["project"]["dependencies"] == [
        "fastmcp>=2.10.3",
        "pyimagej>=1.5.0",
        "numpy>=1.26.0",
        "Pillow>=10.0.0",
    ]
    assert project["project"]["scripts"] == {
        "fiji-mcp-server": "fiji_mcp.__main__:main"
    }


def test_publish_workflow_provisions_wheel_smoke_client_dependency() -> None:
    workflow = Path(".github/workflows/publish-pypi.yml").read_text()
    validator_install = next(
        line.strip()
        for line in workflow.splitlines()
        if line.strip().startswith("run: python -m pip install --upgrade")
    )

    assert validator_install == (
        'run: python -m pip install --upgrade pip build twine "fastmcp>=2.10.3"'
    )
