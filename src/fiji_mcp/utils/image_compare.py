"""Compare two raster images (e.g. before/after screenshots) for verification."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fiji_mcp.utils.optimizer import encode_screenshot

# Rough bound on base64 character count (~54 MiB decoded) to limit memory use on bad inputs.
_MAX_B64_CHARS = 72_000_000


@dataclass(frozen=True)
class CompareStats:
    mean_abs_error: float
    rmse: float
    width_before: int
    height_before: int
    width_after: int
    height_after: int
    compare_width: int
    compare_height: int


def _decode_b64_image(b64: str) -> Image.Image:
    raw = b64.strip()
    if len(raw) > _MAX_B64_CHARS:
        raise ValueError("base64 payload too large")
    data = base64.b64decode(raw, validate=False)
    im = Image.open(io.BytesIO(data)).convert("RGB")
    return im


def _to_gray_array(im: Image.Image, size: tuple[int, int]) -> np.ndarray:
    resized = im.resize(size, Image.Resampling.LANCZOS).convert("L")
    return np.asarray(resized, dtype=np.float64) / 255.0


def compare_screenshot_base64_pair(
    image_base64_before: str,
    image_base64_after: str,
    *,
    max_compare_side: int = 512,
    side_by_side_max_height: int = 480,
) -> tuple[CompareStats, str, str, int, int]:
    """
    Decode two base64-encoded images (same encoding as screenshot_fiji), align sizes,
    compute error metrics, build a labeled side-by-side JPEG, return stats + encoded preview.

    Returns (stats, mime_type, image_base64, composite_width, composite_height).
    """
    before = _decode_b64_image(image_base64_before)
    after = _decode_b64_image(image_base64_after)

    wb, hb = before.size
    wa, ha = after.size

    cw = min(max_compare_side, wb, wa)
    ch = min(max_compare_side, hb, ha)
    if cw < 1:
        cw = 1
    if ch < 1:
        ch = 1

    g0 = _to_gray_array(before, (cw, ch))
    g1 = _to_gray_array(after, (cw, ch))
    diff = g0 - g1
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff * diff)))

    stats = CompareStats(
        mean_abs_error=mae,
        rmse=rmse,
        width_before=wb,
        height_before=hb,
        width_after=wa,
        height_after=ha,
        compare_width=cw,
        compare_height=ch,
    )

    # Side-by-side: equalize height for layout
    target_h = min(side_by_side_max_height, hb, ha)
    if target_h < 1:
        target_h = 1
    b_r = before.copy()
    b_r.thumbnail((4096, target_h), Image.Resampling.LANCZOS)
    a_r = after.copy()
    a_r.thumbnail((4096, target_h), Image.Resampling.LANCZOS)
    gap = 8
    label_h = 22
    total_w = b_r.width + gap + a_r.width
    total_h = label_h + max(b_r.height, a_r.height)
    composite = Image.new("RGB", (total_w, total_h), (32, 32, 32))
    draw = ImageDraw.Draw(composite)
    font = ImageFont.load_default()
    draw.text((4, 2), "before", fill=(220, 220, 220), font=font)
    draw.text((b_r.width + gap + 4, 2), "after", fill=(220, 220, 220), font=font)
    composite.paste(b_r, (0, label_h))
    composite.paste(a_r, (b_r.width + gap, label_h))

    encoded = encode_screenshot(composite)
    return stats, "image/jpeg", encoded.base64_data, composite.width, composite.height
