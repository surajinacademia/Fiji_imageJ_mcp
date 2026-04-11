#!/usr/bin/env python3
"""
End-to-end demo: open bundled sample image in Fiji, run a short macro, capture screenshots.

Mirrors the napari-mcp "open → analyze → screenshot" flow for Fiji (see napari-mcp on napari-hub).

Requires:
  - FIJI_PATH: absolute path to the Fiji **installation root** (folder containing `jars/`, `plugins/`, and
    usually `java/`). On macOS this is often `/Applications/Fiji`, not only `.../Fiji.app` inside it.
  - FIJI_MODE=gui (recommended) and a display for full_screen screenshots
  - On macOS, PyImageJ may require `FIJI_INTERACTIVE_FORCE=1` for local `python` runs (uses `interactive:force`).
  - Java compatible with your Fiji install

Usage (from repo root, with your conda env that has pyimagej):
  export FIJI_PATH=/Applications/Fiji
  export FIJI_MODE=gui
  FIJI_DEMO_SAVE=1 python scripts/demo_fiji_mcp_session.py   # optional: write JPEGs to demo_output/
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

# Repo root on PYTHONPATH when run as `python scripts/demo_fiji_mcp_session.py`
_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> int:
    fiji_path = os.environ.get("FIJI_PATH", "").strip()
    if not fiji_path:
        print(
            "Set FIJI_PATH to your Fiji installation root (folder with jars/), e.g.\n"
            "  export FIJI_PATH=/Applications/Fiji\n"
            "Then install the MCP for Cursor (like napari-mcp):\n"
            "  fiji-mcp-install install cursor --fiji-path \"$FIJI_PATH\" --mode gui\n"
            "Or Claude Desktop:\n"
            "  fiji-mcp-install install claude-desktop --fiji-path \"$FIJI_PATH\" --mode gui\n",
            file=sys.stderr,
        )
        return 1

    demo = _REPO / "demo_images" / "sample_gradient.pgm"
    if not demo.exists():
        print(f"Missing demo image: {demo}", file=sys.stderr)
        return 1

    os.environ.setdefault("FIJI_MODE", "gui")
    os.environ.setdefault("FIJI_TEST_IMAGE", str(demo))

    from fiji_mcp.tools.discovery import get_image_info, list_open_images
    from fiji_mcp.tools.macro_runner import health_check, open_image, run_macro
    from fiji_mcp.tools.screenshot import screenshot_fiji

    print("1) health_check …")
    h = health_check()
    print(f"   ok={h.ok} mode={h.mode} version={h.imagej_version}")

    print(f"2) open_image({demo}) …")
    opened = open_image(str(demo))
    print(f"   title={opened.title} size={opened.width}x{opened.height}")

    print("3) run_macro (Gaussian blur 2 px) …")
    macro = 'run("Gaussian Blur...", "sigma=2");'
    mr = run_macro(macro)
    print(f"   macro_ok={mr.ok} log_tail_len={len(mr.log_tail)}")

    print("4) get_image_info …")
    info = get_image_info()
    print(f"   mean={info.mean:.2f} std={info.std_dev:.2f}")

    print("5) list_open_images …")
    wins = list_open_images()
    print(f"   windows={wins.count}")

    print("6) screenshot_fiji(active_image) …")
    shot_img = screenshot_fiji(capture_mode="active_image")
    print(f"   jpeg {shot_img.width}x{shot_img.height} base64_len={len(shot_img.image_base64)} cached={shot_img.from_cache}")
    _maybe_save_screenshot("active_image", shot_img.image_base64)

    print('7) run_macro("Measure") …')
    run_macro('run("Measure");')

    print("8) screenshot_fiji(results_table) …")
    shot_rt = screenshot_fiji(capture_mode="results_table")
    print(f"   jpeg {shot_rt.width}x{shot_rt.height} base64_len={len(shot_rt.image_base64)}")
    _maybe_save_screenshot("results_table", shot_rt.image_base64)

    if os.environ.get("FIJI_MODE") == "gui":
        try:
            print("9) screenshot_fiji(full_screen) …")
            shot_fs = screenshot_fiji(capture_mode="full_screen")
            print(f"   jpeg {shot_fs.width}x{shot_fs.height} base64_len={len(shot_fs.image_base64)}")
            _maybe_save_screenshot("full_screen", shot_fs.image_base64)
        except Exception as e:
            print(f"   skipped full_screen: {e}")

    print("Demo finished OK.")
    return 0


def _maybe_save_screenshot(name: str, image_base64: str) -> None:
    if os.environ.get("FIJI_DEMO_SAVE", "").strip().lower() not in {"1", "true", "yes"}:
        return
    out_dir = _REPO / "demo_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.jpg"
    path.write_bytes(base64.standard_b64decode(image_base64))
    print(f"   saved {path}")


if __name__ == "__main__":
    raise SystemExit(main())
