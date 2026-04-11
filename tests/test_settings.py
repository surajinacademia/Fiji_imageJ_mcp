"""Unit tests for environment settings parsing."""

from __future__ import annotations

import os

import pytest

from fiji_mcp.config.settings import load_settings


def test_load_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FIJI_PATH", raising=False)
    monkeypatch.delenv("FIJI_MODE", raising=False)
    monkeypatch.delenv("FIJI_DATA_ROOTS", raising=False)
    monkeypatch.delenv("FIJI_MAX_MACRO_CHARS", raising=False)
    monkeypatch.delenv("FIJI_OPERATION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("FIJI_SCREENSHOT_MAX_DIM", raising=False)
    monkeypatch.delenv("FIJI_SCREENSHOT_QUALITY", raising=False)
    monkeypatch.delenv("FIJI_SCREENSHOT_CACHE_SIZE", raising=False)
    monkeypatch.delenv("FIJI_GC_EVERY_N_OPERATIONS", raising=False)
    settings = load_settings()
    assert settings.fiji_mode == "smart"
    assert settings.fiji_path is None
    assert settings.operation_timeout_seconds == 60.0
    assert settings.max_macro_chars == 500_000
    assert settings.data_roots == ()


def test_invalid_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIJI_MODE", "invalid")
    monkeypatch.delenv("FIJI_DATA_ROOTS", raising=False)
    monkeypatch.delenv("FIJI_MAX_MACRO_CHARS", raising=False)
    with pytest.raises(ValueError):
        load_settings()


def test_operation_timeout_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIJI_OPERATION_TIMEOUT_SECONDS", "0.5")
    with pytest.raises(ValueError):
        load_settings()


def test_max_macro_chars_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIJI_MAX_MACRO_CHARS", "100")
    with pytest.raises(ValueError):
        load_settings()


def test_test_image_passthrough(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    image_path = tmp_path / "test.png"
    image_path.write_text("placeholder")
    monkeypatch.setenv("FIJI_TEST_IMAGE", os.fspath(image_path))
    settings = load_settings()
    assert settings.test_image_path == os.fspath(image_path)
