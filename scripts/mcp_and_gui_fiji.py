#!/usr/bin/env python3
"""
Combine **(A)** Fiji over MCP stdio (FastMCP client — same path as Cursor) and **(C)** desktop Fiji.app.

Plug-and-play (no subcommand) — from the repo root::

  python scripts/mcp_and_gui_fiji.py

**Behavior**

1. **FIJI_PATH** — If unset, imports ``fiji_mcp`` and uses ``detect_fiji_path()`` (same logic as the
   server), sets ``FIJI_PATH`` in the environment for the child MCP process, and prints the path.
2. **Image** — If omitted: ``demo_output/readme_ex03_img00_input.jpg`` → ``demo_images/sample_gradient.pgm``
   → first raster under ``demo_images/`` (with a clear error if none exist).
3. **MCP** — Monitor with default **4** ticks, **5** s apart; writes ``tick_*.json`` and ``tick_*.jpg``
   under ``demo_output/mcp_live/``. Each tick: ``list_open_images``, ``get_image_info``,
   ``screenshot_fiji(active_image)``. Uses **only** the MCP JVM (not your GUI Fiji).
4. **GUI** — On **macOS**, opens **Fiji.app** after MCP by default. Use ``--no-gui`` or ``--mcp-only``
   for MCP only. ``--gui-first`` starts the GUI before MCP (two JVMs).

**Useful flags** (default parser; not legacy subcommands): ``--mcp-only``, ``--gui-only``,
``--no-gui`` / ``--no-mcp``, ``--gui-first``, ``--iterations``, ``--interval``, ``--out-dir``.

**One positional argument = image path**::

  python scripts/mcp_and_gui_fiji.py path/to/cells.tif

**(C) GUI** — ``subprocess.Popen`` is **not** waited on at exit; quit Fiji or kill the PID for a clean shutdown.

**Auto-detect prerequisite:** install the package so ``fiji_mcp`` is importable (e.g.
``pip install -e .`` from this repo, or your venv with the project on ``PYTHONPATH``).

**Legacy mode** — If the **first** argument is ``mcp-monitor``, ``open-gui``, or ``both``, the old
subcommand API is used; see ``--help`` in that mode.

**Smoke test**::

  unset FIJI_PATH && python scripts/mcp_and_gui_fiji.py --mcp-only --iterations 1
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
except ImportError as exc:  # pragma: no cover
    print("Install fastmcp (pip install fastmcp).", file=sys.stderr)
    raise SystemExit(1) from exc

_REPO = Path(__file__).resolve().parents[1]
_DEFAULT_OUT = _REPO / "demo_output" / "mcp_live"
_TOOL_TIMEOUT = float(os.environ.get("FIJI_MCP_CLIENT_TOOL_TIMEOUT", "300"))
_LEGACY_SUBCOMMANDS = frozenset({"open-gui", "mcp-monitor", "both"})
_DEMO_IMAGE_EXTENSIONS = frozenset(
    {".png", ".pgm", ".pbm", ".ppm", ".tif", ".tiff", ".jpg", ".jpeg"}
)


def _server_env() -> dict[str, str]:
    env = {**os.environ}
    env.setdefault("PYTHONPATH", str(_REPO / "src"))
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("FIJI_MODE", "headless")
    return env


def _tool_result_to_dict(data: object) -> dict[str, Any]:
    if data is None:
        return {}
    if isinstance(data, dict):
        return dict(data)
    model_dump = getattr(data, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump(mode="json")
        except TypeError:
            return model_dump()
    raw = getattr(data, "__dict__", None)
    if isinstance(raw, dict) and raw:
        # FastMCP ``Root`` tool payloads (no ``model_dump``).
        return {k: v for k, v in raw.items() if not str(k).startswith("_")}
    return {"repr": repr(data)}


async def _mcp_call(
    client: Client, name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    res = await client.call_tool(name, arguments or {}, timeout=_TOOL_TIMEOUT)
    if res.is_error:
        msg = ""
        if res.content:
            c0 = res.content[0]
            if hasattr(c0, "text"):
                msg = str(c0.text)
        raise RuntimeError(f"MCP tool {name!r} failed: {msg or res}")
    return _tool_result_to_dict(res.data)


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _resolve_image(path_str: str) -> Path:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = (_REPO / p).resolve()
    if not p.is_file():
        raise SystemExit(f"Image not found: {p}")
    return p


def _ensure_repo_src_on_path() -> None:
    src = str(_REPO / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _ensure_fiji_path() -> str:
    """Set ``FIJI_PATH`` from the environment or the same auto-detection as ``fiji_mcp``."""
    existing = os.environ.get("FIJI_PATH", "").strip()
    if existing:
        return existing
    _ensure_repo_src_on_path()
    try:
        from fiji_mcp.config.settings import load_settings
        from fiji_mcp.fiji_bridge import detect_fiji_path
    except ImportError as exc:
        raise SystemExit(
            "Could not import fiji_mcp to auto-detect Fiji. Install the package "
            "(pip install -e . from this repo) or set FIJI_PATH to your Fiji root."
        ) from exc
    try:
        detected = detect_fiji_path(load_settings())
    except FileNotFoundError as exc:
        raise SystemExit(
            "FIJI_PATH is not set and Fiji was not found in the usual install locations. "
            "Set FIJI_PATH to the Fiji **root** (folder containing jars/ and Fiji.app)."
        ) from exc
    os.environ["FIJI_PATH"] = detected
    print(f"FIJI_PATH was unset; using detected Fiji: {detected}", flush=True)
    return detected


def _default_image_for_run() -> Path:
    """Prefer a visible demo JPEG, then bundled PGM, then any raster under demo_images/."""
    for rel in (
        "demo_output/readme_ex03_img00_input.jpg",
        "demo_images/sample_gradient.pgm",
    ):
        candidate = (_REPO / rel).resolve()
        if candidate.is_file():
            print(f"Using default image: {candidate.relative_to(_REPO)}", flush=True)
            return candidate
    demo_dir = _REPO / "demo_images"
    if demo_dir.is_dir():
        for path in sorted(demo_dir.iterdir()):
            if (
                path.is_file()
                and not path.name.startswith(".")
                and path.suffix.lower() in _DEMO_IMAGE_EXTENSIONS
            ):
                print(f"Using default image: {path.relative_to(_REPO)}", flush=True)
                return path
    raise SystemExit(
        "No image argument and no demo raster found under demo_output/ or demo_images/. "
        "Pass a file path, e.g. python scripts/mcp_and_gui_fiji.py path/to/sample.tif"
    )


def _find_fiji_app(fiji_root: Path | None) -> Path:
    if fiji_root is None:
        raw = os.environ.get("FIJI_PATH", "").strip()
        fiji_root = Path(raw).expanduser() if raw else Path("/Applications/Fiji")
    fiji_root = fiji_root.expanduser().resolve()
    candidates = [
        fiji_root / "Fiji.app",
        fiji_root if fiji_root.suffix.lower() == ".app" else None,
        Path("/Applications/Fiji/Fiji.app"),
        Path("/Applications/Fiji.app"),
    ]
    for c in candidates:
        if c is not None and c.is_dir():
            return c
    raise SystemExit(
        f"Could not find Fiji.app under {fiji_root}. Set FIJI_PATH to the Fiji **root** "
        "(directory containing Fiji.app), e.g. /Applications/Fiji"
    )


def open_gui_fiji(
    image: Path, *, fiji_root: Path | None = None
) -> subprocess.Popen[bytes] | None:
    """(C) Launch desktop Fiji with ``image`` (macOS only). Returns Popen or None."""
    if sys.platform != "darwin":
        print(
            "open-gui: macOS-only automation in this script. "
            "On Linux/Windows, start Fiji and use File → Open.",
            file=sys.stderr,
        )
        return None
    app = _find_fiji_app(fiji_root)
    machine = platform.machine().lower()
    exe_name = "fiji-macos-arm64" if machine == "arm64" else "fiji-macos-x64"
    launcher = app / "Contents" / "MacOS" / exe_name
    if not launcher.is_file():
        raise SystemExit(f"Missing launcher: {launcher}")
    # Trusted local Fiji launcher + one image path (user-supplied CLI).
    return subprocess.Popen(  # noqa: S603
        [str(launcher), str(image.resolve())],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def run_mcp_monitor(
    image: Path,
    *,
    out_dir: Path,
    interval: float,
    iterations: int,
) -> None:
    """(A) One stdio MCP session: open image, poll tools, save snapshots."""
    _ensure_fiji_path()

    out_dir.mkdir(parents=True, exist_ok=True)
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "fiji_mcp"],
        env=_server_env(),
        cwd=str(_REPO),
        keep_alive=False,
    )
    client = Client(transport, init_timeout=240, timeout=_TOOL_TIMEOUT)

    async with client:
        health = await _mcp_call(client, "health_check", {})
        print(
            f"MCP health_check: ok={health.get('ok')} mode={health.get('mode')}",
            flush=True,
        )
        opened = await _mcp_call(client, "open_image", {"path": str(image.resolve())})
        print(
            f"MCP open_image: ok={opened.get('ok')} title={opened.get('title')} "
            f"{opened.get('width')}x{opened.get('height')}",
            flush=True,
        )

        for tick in range(1, iterations + 1):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            opens = await _mcp_call(client, "list_open_images", {})
            info = await _mcp_call(client, "get_image_info", {})
            shot = await _mcp_call(
                client, "screenshot_fiji", {"capture_mode": "active_image"}
            )

            meta = {
                "tick": tick,
                "utc": stamp,
                "list_open_images": opens,
                "get_image_info": info,
            }
            json_path = out_dir / f"tick_{tick:04d}_{stamp}.json"
            json_path.write_text(
                json.dumps(_json_safe(meta), indent=2),
                encoding="utf-8",
            )
            b64 = shot.get("image_base64") or ""
            if b64:
                jpg_path = out_dir / f"tick_{tick:04d}_{stamp}.jpg"
                jpg_path.write_bytes(base64.standard_b64decode(b64))
                print(
                    f"tick {tick}/{iterations} windows={opens.get('count')} "
                    f"mean={info.get('mean')} → {jpg_path.name}",
                    flush=True,
                )
            else:
                print(
                    f"tick {tick}/{iterations} windows={opens.get('count')} "
                    f"(no jpeg payload)",
                    flush=True,
                )

            if tick < iterations:
                await asyncio.sleep(interval)

    print(f"Done. Artifacts under {out_dir}", flush=True)


def _run_quickstart(
    image: Path,
    *,
    out_dir: Path,
    interval: float,
    iterations: int,
    run_mcp: bool,
    run_gui: bool,
    gui_first: bool,
    fiji_root: Path | None,
) -> int:
    proc: subprocess.Popen[bytes] | None = None
    if gui_first and run_gui:
        proc = open_gui_fiji(image, fiji_root=fiji_root)
        if proc:
            print(
                f"GUI Fiji pid {proc.pid} (separate from MCP PyImageJ).",
                flush=True,
            )
    if run_mcp:
        asyncio.run(
            run_mcp_monitor(
                image,
                out_dir=out_dir,
                interval=interval,
                iterations=iterations,
            )
        )
    if not gui_first and run_gui:
        proc = open_gui_fiji(image, fiji_root=fiji_root)
        if proc:
            print(f"Started Fiji.app with {image} (pid {proc.pid}).", flush=True)
    return 0


def _legacy_main() -> int:
    parser = argparse.ArgumentParser(description="Fiji MCP (A) + desktop Fiji.app (C)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_gui = sub.add_parser("open-gui", help="(C) Open image in Fiji.app (macOS)")
    p_gui.add_argument(
        "--image",
        required=True,
        help="Path to image (absolute or relative to repo root)",
    )
    p_gui.add_argument(
        "--fiji-root",
        type=Path,
        default=None,
        help="Fiji installation root (parent of Fiji.app); default from FIJI_PATH or /Applications/Fiji",
    )

    p_mcp = sub.add_parser(
        "mcp-monitor", help="(A) MCP stdio session + periodic snapshots"
    )
    p_mcp.add_argument("--image", required=True, help="Path to image")
    p_mcp.add_argument(
        "--out-dir", type=Path, default=_DEFAULT_OUT, help="Output directory"
    )
    p_mcp.add_argument(
        "--interval", type=float, default=5.0, help="Seconds between ticks"
    )
    p_mcp.add_argument(
        "--iterations", type=int, default=6, help="Number of monitor ticks (>=1)"
    )

    p_both = sub.add_parser("both", help="Run (A) and/or (C); default A then C")
    p_both.add_argument("--image", required=True, help="Path to image")
    p_both.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    p_both.add_argument("--interval", type=float, default=5.0)
    p_both.add_argument("--iterations", type=int, default=6)
    p_both.add_argument(
        "--gui-first",
        action="store_true",
        help="Start desktop Fiji before MCP (two separate instances)",
    )
    p_both.add_argument(
        "--skip-gui",
        action="store_true",
        help="Only run MCP monitor (same as mcp-monitor)",
    )
    p_both.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Only open desktop Fiji (same as open-gui)",
    )
    p_both.add_argument("--fiji-root", type=Path, default=None)

    args = parser.parse_args()
    if getattr(args, "iterations", 1) < 1:
        raise SystemExit("--iterations must be >= 1")

    if args.cmd == "open-gui":
        img = _resolve_image(args.image)
        proc = open_gui_fiji(img, fiji_root=args.fiji_root)
        if proc:
            print(f"Started Fiji.app with {img} (pid {proc.pid}).", flush=True)
        return 0

    if args.cmd == "mcp-monitor":
        img = _resolve_image(args.image)
        asyncio.run(
            run_mcp_monitor(
                img,
                out_dir=args.out_dir,
                interval=args.interval,
                iterations=args.iterations,
            )
        )
        return 0

    if args.cmd == "both":
        img = _resolve_image(args.image)
        proc: subprocess.Popen[bytes] | None = None
        if args.gui_first and not args.skip_gui:
            proc = open_gui_fiji(img, fiji_root=args.fiji_root)
            if proc:
                print(f"GUI Fiji pid {proc.pid}; MCP uses a separate JVM.", flush=True)
        if not args.skip_mcp:
            asyncio.run(
                run_mcp_monitor(
                    img,
                    out_dir=args.out_dir,
                    interval=args.interval,
                    iterations=args.iterations,
                )
            )
        if not args.gui_first and not args.skip_gui:
            proc = open_gui_fiji(img, fiji_root=args.fiji_root)
            if proc:
                print(f"Started Fiji.app with {img} (pid {proc.pid}).", flush=True)
        return 0

    return 1


def _simple_main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fiji MCP + Fiji.app — plug-and-play: auto-detect FIJI_PATH, optional demo image, "
            "then MCP snapshots (+ Fiji.app on macOS by default)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Advanced: use subcommands mcp-monitor | open-gui | both as the first argument "
            "for explicit control (same as before)."
        ),
    )
    parser.add_argument(
        "image",
        nargs="?",
        default=None,
        help="Image path (repo-relative or absolute). If omitted, a demo file is used when present.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"MCP snapshot directory (default: {_DEFAULT_OUT.relative_to(_REPO)})",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between MCP monitor ticks",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=4,
        help="Number of MCP monitor ticks (>=1)",
    )
    parser.add_argument(
        "--fiji-root",
        type=Path,
        default=None,
        help="Fiji installation root for Fiji.app (optional; uses FIJI_PATH or auto-detect)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--mcp-only",
        action="store_true",
        help="Skip opening Fiji.app",
    )
    mode.add_argument(
        "--gui-only",
        action="store_true",
        help="Only open Fiji.app (macOS); no MCP",
    )
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Do not launch Fiji.app (MCP only)",
    )
    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Do not run MCP monitor",
    )
    parser.add_argument(
        "--gui-first",
        action="store_true",
        help="Open Fiji.app before the MCP session (two JVMs)",
    )
    args = parser.parse_args()
    if args.iterations < 1:
        raise SystemExit("--iterations must be >= 1")

    if args.gui_only:
        run_mcp, run_gui = False, True
    elif args.mcp_only:
        run_mcp, run_gui = True, False
    else:
        run_mcp = not args.no_mcp
        run_gui = (not args.no_gui) and (sys.platform == "darwin")

    if not run_mcp and not run_gui:
        raise SystemExit(
            "Nothing to do: enable MCP and/or GUI (on macOS, GUI is on by default)."
        )
    if run_gui and sys.platform != "darwin":
        print(
            "Note: Fiji.app launch is only implemented on macOS; --gui-only is a no-op here.",
            file=sys.stderr,
        )
        if not run_mcp:
            raise SystemExit("On this OS, use --mcp-only or install on macOS for GUI.")
        run_gui = False

    img = _resolve_image(args.image) if args.image else _default_image_for_run()
    if run_mcp:
        _ensure_fiji_path()

    print(
        "Quick run: MCP="
        f"{'yes' if run_mcp else 'no'}, GUI={'yes' if run_gui else 'no'}, image={img}",
        flush=True,
    )
    return _run_quickstart(
        img,
        out_dir=args.out_dir,
        interval=args.interval,
        iterations=args.iterations,
        run_mcp=run_mcp,
        run_gui=run_gui,
        gui_first=args.gui_first,
        fiji_root=args.fiji_root,
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in _LEGACY_SUBCOMMANDS:
        return _legacy_main()
    return _simple_main()


if __name__ == "__main__":
    raise SystemExit(main())
