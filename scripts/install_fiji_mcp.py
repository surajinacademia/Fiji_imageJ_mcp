#!/usr/bin/env python3
"""
Create a virtual environment and install fiji-mcp-server with all declared dependencies.

Run from the repository root (after ``git clone``):

    python scripts/install_fiji_mcp.py

This runs ``pip install -U pip setuptools wheel`` then ``pip install -e .`` so
FastMCP, PyImageJ, NumPy, Pillow, Pydantic, etc. are installed automatically.

Requirements: Python 3.10+ on PATH, network for PyPI, and a JDK compatible with
Fiji when you later ``pip install`` / first-import PyImageJ (jpype1 may need Java).

Options:
    --venv DIR          Virtualenv directory (default: .venv)
    --with-tests        Also install pytest and test extras (``.[test]``)
    --into-current      Skip venv; install into the interpreter running this script
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _venv_python(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _run(py: Path, args: list[str], *, cwd: Path) -> None:
    cmd = [str(py), *args]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def _ensure_python_version() -> None:
    if sys.version_info < (3, 10):
        print("ERROR: Python 3.10 or newer is required.", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--venv",
        type=Path,
        default=Path(".venv"),
        help="Virtual environment directory (default: .venv)",
    )
    parser.add_argument(
        "--with-tests",
        action="store_true",
        help="Install optional test dependencies (pytest, …) via .[test]",
    )
    parser.add_argument(
        "--into-current",
        action="store_true",
        help="Do not create a venv; use the current Python (installs into active env)",
    )
    args = parser.parse_args()

    _ensure_python_version()
    root = _repo_root()
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        print(f"ERROR: {pyproject} not found. Run this script from the repo (or use a full clone).", file=sys.stderr)
        raise SystemExit(1)

    if args.into_current:
        py = Path(sys.executable).resolve()
        print(f"Using current interpreter: {py}", flush=True)
    else:
        venv = args.venv
        py = _venv_python(venv)
        if not py.is_file():
            print(f"Creating virtual environment at {venv} …", flush=True)
            _run(Path(sys.executable), ["-m", "venv", str(venv)], cwd=root)
        if not py.is_file():
            print(f"ERROR: venv python not found at {py}", file=sys.stderr)
            raise SystemExit(1)

    print("Upgrading pip / setuptools / wheel …", flush=True)
    _run(py, ["-m", "pip", "install", "-U", "pip", "setuptools", "wheel"], cwd=root)

    edit = ".[test]" if args.with_tests else "."
    print(f"Installing fiji-mcp-server and dependencies (pip install -e {edit!r}) …", flush=True)
    _run(py, ["-m", "pip", "install", "-e", edit], cwd=root)

    print("\n--- Done ---", flush=True)
    print("Installed packages:", flush=True)
    _run(py, ["-m", "pip", "show", "fiji-mcp-server"], cwd=root)

    print("\nNext steps:", flush=True)
    if not args.into_current:
        if sys.platform == "win32":
            act = str(args.venv / "Scripts" / "activate")
            print(f"  1. Activate:  {act}   (PowerShell: .venv\\Scripts\\Activate.ps1)", flush=True)
        else:
            print(f"  1. Activate:  source {args.venv}/bin/activate", flush=True)
    print("  2. Point MCP at Fiji (replace path):", flush=True)
    print("       fiji-mcp-install install cursor --fiji-path /path/to/Fiji", flush=True)
    script = py.parent / ("fiji-mcp-server.exe" if sys.platform == "win32" else "fiji-mcp-server")
    if script.is_file():
        print("     If your editor does not see this venv, add:", flush=True)
        print(f"       --command {script}", flush=True)
    print("  3. Restart your editor or CLI, then ask the agent to run Fiji ``health_check``.", flush=True)


if __name__ == "__main__":
    main()
