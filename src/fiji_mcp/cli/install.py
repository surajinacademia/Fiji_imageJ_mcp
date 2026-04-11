"""Install fiji-mcp-server into AI client MCP configs (Cursor, Claude, Gemini CLI, Windsurf, etc.)."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path


def _claude_desktop_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    if system == "Windows":
        return (
            Path.home()
            / "AppData"
            / "Roaming"
            / "Claude"
            / "claude_desktop_config.json"
        )
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _cursor_config_path() -> Path:
    """Cursor global MCP config (same shape as Claude `mcpServers`)."""
    return Path.home() / ".cursor" / "mcp.json"


def _claude_code_user_config_path() -> Path:
    """Claude Code user-scoped MCP (all projects). See https://code.claude.com/docs/en/mcp"""
    return Path.home() / ".claude.json"


def _gemini_cli_settings_path() -> Path:
    """Google Gemini CLI user settings (includes ``mcpServers``). See https://geminicli.com/docs/tools/mcp-server/"""
    return Path.home() / ".gemini" / "settings.json"


def _windsurf_mcp_config_path() -> Path:
    """Windsurf Cascade MCP config. See https://docs.windsurf.com/windsurf/cascade/mcp"""
    return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fiji_server_entry(
    fiji_path: str, mode: str, command: str | None
) -> dict[str, object]:
    """Prefer ``python -m fiji_mcp`` (same pattern as cellpose / napari MCP) so clients never pick the wrong interpreter."""
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


def _merge_fiji_mcp_server(
    path: Path, fiji_path: str, mode: str, command: str | None
) -> Path:
    """Merge or create ``mcpServers.fiji`` in a JSON file (Cursor / Claude Desktop / Windsurf shape)."""
    config = _load_json(path)
    config.setdefault("mcpServers", {})
    config["mcpServers"]["fiji"] = _fiji_server_entry(fiji_path, mode, command)
    _save_json(path, config)
    return path


def install_for_claude_desktop(
    fiji_path: str, mode: str, command: str | None = None
) -> Path:
    path = _claude_desktop_config_path()
    return _merge_fiji_mcp_server(path, fiji_path, mode, command)


def install_for_cursor(fiji_path: str, mode: str, command: str | None = None) -> Path:
    path = _cursor_config_path()
    return _merge_fiji_mcp_server(path, fiji_path, mode, command)


def install_for_claude_code(
    fiji_path: str,
    mode: str,
    command: str | None,
    *,
    project_root: Path | None,
) -> Path:
    """Claude Code: user ``~/.claude.json`` or project ``<root>/.mcp.json`` (``mcpServers`` block)."""
    if project_root is not None:
        path = project_root.expanduser().resolve() / ".mcp.json"
    else:
        path = _claude_code_user_config_path()
    return _merge_fiji_mcp_server(path, fiji_path, mode, command)


def install_for_gemini_cli(
    fiji_path: str, mode: str, command: str | None = None
) -> Path:
    """Gemini CLI: merge into ``~/.gemini/settings.json`` → ``mcpServers``."""
    path = _gemini_cli_settings_path()
    return _merge_fiji_mcp_server(path, fiji_path, mode, command)


def install_for_windsurf(fiji_path: str, mode: str, command: str | None = None) -> Path:
    """Windsurf: merge into ``~/.codeium/windsurf/mcp_config.json``."""
    path = _windsurf_mcp_config_path()
    return _merge_fiji_mcp_server(path, fiji_path, mode, command)


def _cmd_install(args: argparse.Namespace) -> None:
    fiji_path = args.fiji_path
    mode = args.mode
    command = args.command
    project_root: Path | None = args.project

    if args.target == "cursor":
        out = install_for_cursor(fiji_path, mode, command)
        print(f"Configured Cursor MCP at: {out}")
    elif args.target == "claude-desktop":
        out = install_for_claude_desktop(fiji_path, mode, command)
        print(f"Configured Claude Desktop MCP at: {out}")
    elif args.target == "claude-code":
        out = install_for_claude_code(
            fiji_path, mode, command, project_root=project_root
        )
        print(f"Configured Claude Code MCP at: {out}")
    elif args.target == "gemini":
        out = install_for_gemini_cli(fiji_path, mode, command)
        print(f"Configured Gemini CLI MCP at: {out}")
    elif args.target == "windsurf":
        out = install_for_windsurf(fiji_path, mode, command)
        print(f"Configured Windsurf MCP at: {out}")
    else:
        raise SystemExit(f"Unknown target: {args.target}")


def main() -> None:
    """CLI entrypoint: ``fiji-mcp-install install <target> --fiji-path ...``."""
    argv = sys.argv[1:]
    if argv and argv[0] != "install" and any(a == "--fiji-path" for a in argv):
        argv = ["install", "claude-desktop", *argv]

    parser = argparse.ArgumentParser(
        description="Install fiji-mcp-server for Cursor, Claude Desktop, Claude Code, Gemini CLI, Windsurf, etc.",
    )
    sub = parser.add_subparsers(dest="cmd")

    inst = sub.add_parser(
        "install", help="Write MCP server entry to a client config file"
    )
    inst.add_argument(
        "target",
        choices=[
            "claude-desktop",
            "cursor",
            "claude-code",
            "gemini",
            "windsurf",
        ],
        help="AI application to configure",
    )
    inst.add_argument(
        "--fiji-path",
        required=True,
        help="Absolute path to Fiji installation root (folder containing jars/ and plugins/)",
    )
    inst.add_argument(
        "--mode",
        default="headless",
        choices=["gui", "headless", "auto", "smart"],
        help="Fiji startup mode: headless for IDE/CLI MCP (stable); gui for local desktop + Robot screenshots",
    )
    inst.add_argument(
        "--command",
        default=None,
        help="Optional absolute path to fiji-mcp-server if it is not on PATH for the host app",
    )
    inst.add_argument(
        "--project",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "For target claude-code only: write <DIR>/.mcp.json (project scope). "
            "If omitted, merge into ~/.claude.json (user scope)."
        ),
    )
    inst.set_defaults(func=_cmd_install)

    if not argv:
        parser.print_help()
        raise SystemExit(2)

    args = parser.parse_args(argv)
    if args.cmd is None or not hasattr(args, "func"):
        parser.print_help()
        raise SystemExit(2)
    if args.target != "claude-code" and args.project is not None:
        parser.error("--project is only valid with target claude-code")
    args.func(args)


if __name__ == "__main__":
    main()
