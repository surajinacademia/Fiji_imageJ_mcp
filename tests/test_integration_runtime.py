"""Integration smoke tests for local Fiji runtime."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fiji_mcp.tools.discovery import get_image_info
from fiji_mcp.tools.macro_runner import health_check, open_image


def _default_demo_image() -> Path | None:
    demo_dir = Path(__file__).resolve().parents[1] / "demo_images"
    if not demo_dir.is_dir():
        return None
    preferred = demo_dir / "sample_gradient.pgm"
    if preferred.is_file():
        return preferred
    for path in sorted(demo_dir.iterdir()):
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower()
            in {
                ".pgm",
                ".pbm",
                ".ppm",
                ".tif",
                ".tiff",
                ".png",
                ".jpg",
                ".jpeg",
            }
        ):
            return path
    return None


def _integration_enabled() -> bool:
    return bool(os.environ.get("FIJI_PATH")) and bool(
        os.environ.get("FIJI_TEST_IMAGE") or _default_demo_image()
    )


@pytest.fixture(autouse=True)
def _force_headless_for_fiji_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """PyImageJ rejects macOS ``interactive`` for plain pytest; integration uses headless Fiji."""
    monkeypatch.setenv("FIJI_MODE", "headless")


@pytest.mark.integration
@pytest.mark.timeout(240)
@pytest.mark.skipif(
    not _integration_enabled(), reason="Set FIJI_PATH and FIJI_TEST_IMAGE"
)
def test_fiji_runtime_smoke() -> None:
    image_path = Path(
        os.environ.get("FIJI_TEST_IMAGE") or _default_demo_image()
    ).expanduser()
    assert image_path.exists(), f"Missing test image: {image_path}"

    health = health_check()
    assert health.ok is True

    opened = open_image(str(image_path))
    assert opened.ok is True

    # Headless open uses setTempCurrentImage — window list may stay empty; current image still works.
    info = get_image_info()
    assert info.width == opened.width and info.height == opened.height
