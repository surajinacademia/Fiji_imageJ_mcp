#!/usr/bin/env python3
"""
Regenerate README hero images: two Fiji analysis examples on bundled demo_images.

Writes JPEGs under demo_output/ (committed) for use in README.md and docs/README.md.

Requires:
  - FIJI_PATH: Fiji installation root
  - FIJI_MODE=headless (recommended; active_image screenshots work without a display)

Usage (repo root, env with pyimagej / fiji_mcp):
  export FIJI_PATH=/Applications/Fiji
  export FIJI_MODE=headless
  python scripts/generate_readme_demo_assets.py
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _save_b64(path: Path, image_base64: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.standard_b64decode(image_base64))


def _close_all() -> None:
    """Best-effort cleanup; headless WindowManager can NPE on ``selectImage``."""
    from fiji_mcp.tools.macro_runner import run_macro

    try:
        run_macro(
            """
while (nImages > 0) {
  close();
}
"""
        )
    except Exception:
        pass


def _example(repo: Path, stem: str, image_rel: str, macro: str, caption_macro: str) -> None:
    from fiji_mcp.tools.macro_runner import open_image, run_macro
    from fiji_mcp.tools.screenshot import screenshot_fiji

    img_path = (repo / image_rel).resolve()
    if not img_path.is_file():
        raise SystemExit(f"Missing demo image: {img_path}")

    open_image(str(img_path))
    shot_in = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_input.jpg", shot_in.image_base64)

    run_macro(macro)
    shot_out = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_analysis.jpg", shot_out.image_base64)

    print(f"  {stem}: {image_rel} -> {caption_macro}")
    _close_all()


def main() -> int:
    if not os.environ.get("FIJI_PATH", "").strip():
        print("Set FIJI_PATH to your Fiji root, e.g. export FIJI_PATH=/Applications/Fiji", file=sys.stderr)
        return 1
    os.environ.setdefault("FIJI_MODE", "headless")

    from fiji_mcp.tools.macro_runner import health_check

    print("health_check …")
    h = health_check()
    if not h.ok:
        print(f"health_check failed: {h}", file=sys.stderr)
        return 1

    # Two distinct demo_images + visibly different ImageJ pipelines
    _example(
        _REPO,
        "readme_ex01_img07",
        "demo_images/img07.png",
        'run("Gaussian Blur...", "sigma=4");',
        "Gaussian blur σ=4",
    )
    _example(
        _REPO,
        "readme_ex02_img04",
        "demo_images/img04.png",
        'run("Find Edges");',
        "Find Edges",
    )

    print("Wrote demo_output/readme_ex01_img07_{input,analysis}.jpg")
    print("Wrote demo_output/readme_ex02_img04_{input,analysis}.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
