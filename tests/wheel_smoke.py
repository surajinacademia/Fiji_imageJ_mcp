from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

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


async def _probe(entrypoint: Path, stderr_path: Path) -> None:
    env = os.environ.copy()
    for key in ("FIJI_PATH", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["FIJI_MODE"] = "headless"
    transport = StdioTransport(
        command=str(entrypoint),
        args=[],
        env=env,
        keep_alive=False,
        log_file=stderr_path,
    )
    async with Client(transport, init_timeout=60, timeout=60) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == EXPECTED


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: wheel_smoke.py path/to/fiji_mcp_server.whl")
    wheel = Path(sys.argv[1]).resolve()
    if not wheel.is_file():
        raise SystemExit(f"wheel not found: {wheel}")
    with tempfile.TemporaryDirectory(prefix="fiji-mcp-wheel-smoke-") as temp:
        root = Path(temp)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        executable_dir = "Scripts" if os.name == "nt" else "bin"
        python_name = "python.exe" if os.name == "nt" else "python"
        entrypoint_name = (
            "fiji-mcp-server.exe" if os.name == "nt" else "fiji-mcp-server"
        )
        python = environment / executable_dir / python_name
        entrypoint = environment / executable_dir / entrypoint_name
        subprocess.run(  # noqa: S603 -- fixed temporary interpreter and local wheel
            [str(python), "-m", "pip", "install", str(wheel)],
            check=True,
        )
        asyncio.run(_probe(entrypoint, root / "stderr.log"))
    print("wheel install and nine-tool stdio smoke probe passed")


if __name__ == "__main__":
    main()
