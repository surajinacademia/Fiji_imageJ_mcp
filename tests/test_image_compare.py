"""Tests for screenshot pair comparison."""

import base64
import io

import pytest
from PIL import Image

from fiji_mcp.utils.image_compare import compare_screenshot_base64_pair


def _jpeg_b64(rgb: tuple[int, int, int]) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), rgb).save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_identical_images_low_error():
    b64 = _jpeg_b64((200, 100, 50))
    stats, mime, out_b64, w, h = compare_screenshot_base64_pair(b64, b64)
    assert mime == "image/jpeg"
    assert stats.mean_abs_error < 1e-6
    assert stats.rmse < 1e-6
    assert len(out_b64) > 100
    assert w > 0 and h > 0


def test_different_images_higher_error():
    a = _jpeg_b64((10, 10, 10))
    b = _jpeg_b64((240, 240, 240))
    stats, _, _, _, _ = compare_screenshot_base64_pair(a, b)
    assert stats.mean_abs_error > 0.1


def test_rejects_extremely_large_base64_payload():
    huge = "A" * 72_000_001
    with pytest.raises(ValueError, match="too large"):
        compare_screenshot_base64_pair(huge, huge)
