"""Tests for optional FIJI_DATA_ROOTS path policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from fiji_mcp.config.settings import Settings
from fiji_mcp.utils.error_handler import FijiToolError
from fiji_mcp.utils.path_policy import ensure_path_allowed, resolve_user_path


def _settings_with_roots(*roots: str) -> Settings:
    return Settings(
        fiji_path=None,
        fiji_java_home=None,
        fiji_mode="headless",
        operation_timeout_seconds=60.0,
        screenshot_max_dim=1920,
        screenshot_quality=85,
        screenshot_cache_size=5,
        gc_every_n_operations=10,
        test_image_path=None,
        max_macro_chars=500_000,
        data_roots=tuple(Path(r).resolve(strict=False) for r in roots),
    )


def test_resolve_user_path_expands_home(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    p = tmp_path / "img.tif"
    p.write_bytes(b"x")
    resolved = resolve_user_path("~/img.tif")
    assert resolved == p.resolve()


def test_ensure_path_allowed_no_roots_always_ok(tmp_path) -> None:
    settings = _settings_with_roots()
    target = tmp_path / "anywhere.tif"
    target.write_bytes(b"x")
    ensure_path_allowed(target.resolve(), settings, operation="open_image")


def test_ensure_path_allowed_rejects_outside_roots(tmp_path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside" / "x.tif"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    settings = _settings_with_roots(str(allowed))
    with pytest.raises(FijiToolError, match="outside allowed"):
        ensure_path_allowed(outside.resolve(), settings, operation="open_image")


def test_ensure_path_allowed_accepts_child_of_root(tmp_path) -> None:
    allowed = tmp_path / "data"
    sub = allowed / "sub" / "a.tif"
    sub.parent.mkdir(parents=True)
    sub.write_bytes(b"x")
    settings = _settings_with_roots(str(allowed))
    ensure_path_allowed(sub.resolve(), settings, operation="save_image")
