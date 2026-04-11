"""Phase 4 smart screenshot: capture_mode and headless gate behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PIL import Image

from fiji_mcp.tools import screenshot
from fiji_mcp.utils.error_handler import FijiToolError
from fiji_mcp.utils.optimizer import EncodedScreenshot


def test_full_screen_headless_raises_before_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screenshot, "get_ij", lambda: MagicMock())
    monkeypatch.setattr(screenshot, "get_bridge_status", lambda: {"mode": "headless"})
    with pytest.raises(FijiToolError, match="full_screen"):
        screenshot.screenshot_fiji(capture_mode="full_screen")


def test_active_image_headless_passes_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screenshot, "get_ij", lambda: MagicMock())
    monkeypatch.setattr(screenshot, "get_bridge_status", lambda: {"mode": "headless"})

    def _fake_timeout(func, timeout_seconds=None):
        return func()

    monkeypatch.setattr(screenshot, "run_with_timeout", _fake_timeout)
    monkeypatch.setattr(screenshot, "_active_image_to_pil", lambda: Image.new("RGB", (4, 4), color=(1, 2, 3)))
    monkeypatch.setattr(
        screenshot,
        "encode_screenshot",
        lambda _img: EncodedScreenshot(
            format="jpeg",
            width=4,
            height=4,
            base64_data="qqqq",
            from_cache=False,
        ),
    )

    result = screenshot.screenshot_fiji(capture_mode="active_image")
    assert result.capture_mode == "active_image"
    assert result.width == 4


def test_results_table_headless_passes_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(screenshot, "get_ij", lambda: MagicMock())
    monkeypatch.setattr(screenshot, "get_bridge_status", lambda: {"mode": "headless"})

    def _fake_timeout(func, timeout_seconds=None):
        return func()

    monkeypatch.setattr(screenshot, "run_with_timeout", _fake_timeout)
    monkeypatch.setattr(
        screenshot,
        "_results_table_to_pil",
        lambda: Image.new("RGB", (8, 8), color=(10, 20, 30)),
    )
    monkeypatch.setattr(
        screenshot,
        "encode_screenshot",
        lambda _img: EncodedScreenshot(
            format="jpeg",
            width=8,
            height=8,
            base64_data="qqqq",
            from_cache=False,
        ),
    )

    result = screenshot.screenshot_fiji(capture_mode="results_table")
    assert result.capture_mode == "results_table"
