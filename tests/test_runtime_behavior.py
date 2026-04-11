"""Tests for timeout enforcement and startup mode resolution."""

from __future__ import annotations

import time

import pytest

from fiji_mcp.config.settings import Settings
from fiji_mcp.fiji_bridge import resolve_start_mode
from fiji_mcp.utils.error_handler import run_with_timeout


def _settings(mode: str) -> Settings:
    return Settings(
        fiji_path=None,
        fiji_java_home=None,
        fiji_mode=mode,
        operation_timeout_seconds=60.0,
        screenshot_max_dim=1920,
        screenshot_quality=85,
        screenshot_cache_size=5,
        gc_every_n_operations=10,
        test_image_path=None,
        max_macro_chars=500_000,
        data_roots=(),
    )


def test_run_with_timeout_runs_inline_no_thread_timeout() -> None:
    """JPype + ImageJ must run on the caller thread; timeout cannot interrupt Java."""
    assert run_with_timeout(lambda: 41 + 1, timeout_seconds=0.05) == 42
    started = time.monotonic()
    run_with_timeout(lambda: time.sleep(0.06), timeout_seconds=0.01)
    assert time.monotonic() - started >= 0.05


def test_resolve_start_mode_explicit_modes() -> None:
    assert resolve_start_mode(_settings("gui")) == "interactive"
    assert resolve_start_mode(_settings("headless")) == "headless"


def test_resolve_start_mode_auto_without_display(monkeypatch: pytest.MonkeyPatch) -> None:
    from fiji_mcp import fiji_bridge

    monkeypatch.setattr(fiji_bridge.platform, "system", lambda: "Linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert resolve_start_mode(_settings("auto")) == "headless"


def test_resolve_start_mode_smart_with_display(monkeypatch: pytest.MonkeyPatch) -> None:
    from fiji_mcp import fiji_bridge

    monkeypatch.setattr(fiji_bridge.platform, "system", lambda: "Linux")
    monkeypatch.setenv("DISPLAY", ":99")
    assert resolve_start_mode(_settings("smart")) == "interactive"
