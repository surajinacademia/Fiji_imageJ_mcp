from __future__ import annotations

import os
from pathlib import Path

import pytest

from fiji_mcp import tools

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _require_fiji() -> Path:
    configured = os.environ.get("FIJI_PATH", "").strip()
    if not configured:
        pytest.skip("Set FIJI_PATH to run real demo-image tests")
    root = Path(configured).expanduser().resolve()
    if not (root / "jars").is_dir() or not (root / "plugins").is_dir():
        pytest.skip(f"FIJI_PATH is not a Fiji root: {root}")
    return root


def _demo_image(name: str) -> Path:
    path = (_REPO_ROOT / "demo_images" / name).resolve()
    assert path.is_file(), f"Tracked demo fixture is missing: {path}"
    return path


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_groovy_sees_opened_rgb_demo_image() -> None:
    _require_fiji()
    image = _demo_image("img00.png")
    tools.open_image(str(image))

    result = tools.run_script(
        "groovy",
        """#@output String title
#@output Integer width
#@output Integer height
import ij.WindowManager
def active = WindowManager.getCurrentImage()
title = active == null ? null : active.getTitle()
width = active == null ? null : active.getWidth()
height = active == null ? null : active.getHeight()
""",
    )

    assert result["result"] == {"title": "img00.png", "width": 512, "height": 512}
