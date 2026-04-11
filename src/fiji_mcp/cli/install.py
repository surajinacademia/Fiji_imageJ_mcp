"""Install fiji-mcp-server into AI client MCP configs (Claude Desktop, Cursor, etc.)."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path


def _claude_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _cursor_config_path() -> Path:
    """Cursor global MCP config (same shape as Claude `mcpServers`)."""
    return Path.home() / ".cursor" / "mcp.json"


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fiji_server_entry(fiji_path: str, mode: str, command: str | None) -> dict[str, object]:
    """Prefer ``python -m fiji_mcp`` (same pattern as cellpose / napari MCP) so Cursor never picks the wrong interpreter."""
    script = command or shutil.which("fiji-mcp-server") or "fiji-mcp-server"
    script_path = Path(script).expanduser()
    if script_path.is_file():
        script_path = script_path.resolve()
    env: dict[str, str] = {
        "FIJI_PATH": fiji_path,
        "FIJI_MODE": mode,
        "PYTHONUNBUFFERED": "1",
    }
    for py_name in ("python", "python3"):
        py = script_path.parent / py_name
        if py.is_file():
            return {
                "command": str(py),
                "args": ["-m", "fiji_mcp"],
                "env": env,
            }
    return {
        "command": str(script_path) if script_path.exists() else script,
        "env": env,
    }


def install_for_claude(fiji_path: str, mode: str, command: str | None = None) -> Path:
    """Merge Fiji MCP into Claude Desktop config."""
    path = _claude_config_path()
    config = _load_json(path)
    config.setdefault("mcpServers", {})
    config["mcpServers"]["fiji"] = _fiji_server_entry(fiji_path, mode, command)
    _save_json(path, config)
    return path


def install_for_cursor(fiji_path: str, mode: str, command: str | None = None) -> Path:
    """Merge Fiji MCP into Cursor user `mcp.json` (see https://napari-hub.org/plugins/napari-mcp.html pattern)."""
    path = _cursor_config_path()
    config = _load_json(path)
    config.setdefault("mcpServers", {})
    config["mcpServers"]["fiji"] = _fiji_server_entry(fiji_path, mode, command)
    _save_json(path, config)
    return path


def _cmd_install(args: argparse.Namespace) -> None:
    fiji_path = args.fiji_path
    mode = args.mode
    command = args.command
    if args.target == "cursor":
        out = install_for_cursor(fiji_path, mode, command)
        print(f"Configured Cursor MCP at: {out}")
    else:
        out = install_for_claude(fiji_path, mode, command)
        print(f"Configured Claude Desktop MCP at: {out}")


def main() -> None:
    """CLI entrypoint: `fiji-mcp-install install cursor --fiji-path ...` or legacy `--fiji-path`."""
    argv = sys.argv[1:]
    if argv and argv[0] != "install" and any(a == "--fiji-path" for a in argv):
        argv = ["install", "claude-desktop", *argv]

    parser = argparse.ArgumentParser(
        description="Install fiji-mcp-server for Claude Desktop, Cursor, or other MCP-capable apps.",
    )
    sub = parser.add_subparsers(dest="cmd")

    inst = sub.add_parser("install", help="Write MCP server entry to a client config file")
    inst.add_argument(
        "target",
        choices=["claude-desktop", "cursor"],
        help="AI application to configure",
    )
    inst.add_argument("--fiji-path", required=True, help="Absolute path to Fiji.app (macOS) or Fiji installation")
    inst.add_argument(
        "--mode",
        default="headless",
        choices=["gui", "headless", "auto", "smart"],
        help="Fiji startup mode: use headless for Cursor MCP (stable); gui for local desktop + Robot screenshots",
    )
    inst.add_argument(
        "--command",
        default=None,
        help="Optional absolute path to fiji-mcp-server if it is not on PATH for the GUI app",
    )
    inst.set_defaults(func=_cmd_install)

    if not argv:
        parser.print_help()
        raise SystemExit(2)

    args = parser.parse_args(argv)
    if args.cmd is None or not hasattr(args, "func"):
        parser.print_help()
        raise SystemExit(2)
    args.func(args)


if __name__ == "__main__":
    main()
