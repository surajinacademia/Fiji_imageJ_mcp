"""Screenshot optimization and lightweight caching."""

from __future__ import annotations

import base64
import hashlib
import io
from collections import OrderedDict
from dataclasses import dataclass

from PIL import Image

from fiji_mcp.config.settings import load_settings


@dataclass(frozen=True)
class EncodedScreenshot:
    """Encoded screenshot payload returned by tools."""

    format: str
    width: int
    height: int
    base64_data: str
    from_cache: bool


class ScreenshotCache:
    """Small LRU cache keyed by image digest."""

    def __init__(self, max_size: int) -> None:
        self.max_size = max_size
        self._store: OrderedDict[str, EncodedScreenshot] = OrderedDict()

    def get(self, key: str) -> EncodedScreenshot | None:
        value = self._store.get(key)
        if value is None:
            return None
        self._store.move_to_end(key)
        return value

    def put(self, key: str, value: EncodedScreenshot) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self.max_size:
            self._store.popitem(last=False)


_SCREENSHOT_CACHE = ScreenshotCache(max_size=load_settings().screenshot_cache_size)


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_screenshot(image: Image.Image) -> EncodedScreenshot:
    """Resize/compress screenshot and return base64 data with LRU caching."""
    settings = load_settings()
    optimized = image.copy()
    optimized.thumbnail((settings.screenshot_max_dim, settings.screenshot_max_dim))

    raw_buffer = io.BytesIO()
    optimized.save(raw_buffer, format="PNG")
    raw_data = raw_buffer.getvalue()
    digest = _digest_bytes(raw_data)

    cached = _SCREENSHOT_CACHE.get(digest)
    if cached is not None:
        return EncodedScreenshot(
            format=cached.format,
            width=cached.width,
            height=cached.height,
            base64_data=cached.base64_data,
            from_cache=True,
        )

    encoded_buffer = io.BytesIO()
    optimized.convert("RGB").save(
        encoded_buffer,
        format="JPEG",
        quality=settings.screenshot_quality,
        optimize=True,
    )
    encoded = EncodedScreenshot(
        format="jpeg",
        width=optimized.width,
        height=optimized.height,
        base64_data=base64.b64encode(encoded_buffer.getvalue()).decode("ascii"),
        from_cache=False,
    )
    _SCREENSHOT_CACHE.put(digest, encoded)
    return encoded
