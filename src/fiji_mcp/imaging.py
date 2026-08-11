"""Deterministic Fiji image rendering and local screenshot comparison."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fiji_mcp.bridge import FijiError, Outcome

_MAX_DIMENSION = 2_048
_MAX_RESULT_ROWS = 100
_MAX_COMPARE_PIXELS = 16_777_216
_METRIC_CHUNK_ROWS = 256
_MARGIN = 8
_PANEL_GAP = 12


@dataclass(frozen=True)
class RenderedPNG:
    """One deterministic PNG payload and its small, JSON-safe description."""

    png: bytes
    width: int
    height: int
    metadata: dict[str, Any]


def _failed(code: str, message: str, recovery: str) -> FijiError:
    return FijiError(
        code,
        message,
        retryable=False,
        outcome=Outcome.FAILED,
        recovery=recovery,
    )


def fit_within(image: Image.Image, maximum: int = _MAX_DIMENSION) -> Image.Image:
    """Copy an image and shrink it proportionally without ever enlarging it."""
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
        raise ValueError("maximum must be a positive integer")
    fitted = image.copy()
    if fitted.width > maximum or fitted.height > maximum:
        fitted.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
    return fitted


def _encode_png(image: Image.Image) -> bytes:
    """Encode one RGB image with fixed PNG settings."""
    output = io.BytesIO()
    image.convert("RGB").save(
        output,
        format="PNG",
        optimize=False,
        compress_level=9,
    )
    return output.getvalue()


def _rendered_png(image: Image.Image, metadata: dict[str, Any]) -> RenderedPNG:
    fitted = fit_within(image, _MAX_DIMENSION).convert("RGB")
    payload = dict(metadata)
    payload["width"] = fitted.width
    payload["height"] = fitted.height
    return RenderedPNG(_encode_png(fitted), fitted.width, fitted.height, payload)


def _buffered_image_to_pil(buffered_image: Any) -> Image.Image:
    """Decode a Java BufferedImage through ImageIO into a detached RGB PIL image."""
    import scyjava as sj

    byte_array_output_stream = sj.jimport("java.io.ByteArrayOutputStream")
    image_io = sj.jimport("javax.imageio.ImageIO")
    output = byte_array_output_stream()
    try:
        if not image_io.write(buffered_image, "png", output):
            raise _failed(
                "render_failed",
                "ImageIO could not encode the rendered Fiji image.",
                "Try a standard ImageJ image type or convert the image to RGB first.",
            )
        return Image.open(io.BytesIO(bytes(output.toByteArray()))).convert("RGB")
    except FijiError:
        raise
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not convert the rendered Fiji image to PNG.",
            "Try a standard ImageJ image type or convert the image to RGB first.",
        ) from error
    finally:
        try:
            output.close()
        except Exception:
            pass


def _duplicate_current_plane(image: Any, c: int, z: int, t: int) -> Any:
    """Build a detached, full-size current plane without touching the source ROI."""
    try:
        source_processor = image.getProcessor()
        processor = source_processor.duplicate()
        color_model = source_processor.getColorModel()
        if color_model is not None:
            processor.setColorModel(color_model)
        current_plane = image.createImagePlus()
        current_plane.setProcessor(image.getTitle(), processor)
        current_plane.setDisplayRange(
            image.getDisplayRangeMin(), image.getDisplayRangeMax()
        )
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not construct a detached current C/Z/T plane for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error
    if current_plane is None:
        raise _failed(
            "render_failed",
            "Fiji did not return a detached current C/Z/T plane.",
            "Try selecting a valid active image and retry.",
        )

    _copy_current_annotations(image, current_plane, c, z, t)
    return current_plane


def _clone_roi(roi: Any) -> Any:
    if roi is None:
        return None
    try:
        clone = roi.clone()
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not clone the active ROI for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error
    if clone is None or clone is roi:
        raise _failed(
            "render_failed",
            "Fiji did not return a detached active ROI for rendering.",
            "Try selecting a valid active image and retry.",
        )
    return clone


def _reset_one_plane_position(roi: Any) -> None:
    try:
        roi.setPosition(1, 1, 1)
    except TypeError:
        try:
            roi.setPosition(1)
        except Exception as error:
            raise _failed(
                "render_failed",
                "Could not position a detached annotation for rendering.",
                "Try selecting a valid active image and retry.",
            ) from error
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not position a detached annotation for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error


def _filtered_overlay(overlay: Any, c: int, z: int, t: int) -> Any:
    if overlay is None:
        return None
    try:
        copied = overlay.duplicate()
        if copied is None or copied is overlay:
            raise _failed(
                "render_failed",
                "Fiji did not return a detached overlay for rendering.",
                "Try selecting a valid active image and retry.",
            )
        cropped = copied.crop(c, c, z, z, t, t)
        if cropped is not None:
            if cropped is overlay:
                raise _failed(
                    "render_failed",
                    "Fiji did not return a detached overlay for rendering.",
                    "Try selecting a valid active image and retry.",
                )
            copied = cropped
        for index in range(int(copied.size())):
            _reset_one_plane_position(copied.get(index))
    except FijiError:
        raise
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not clone the visible overlay for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error
    if copied is None or copied is overlay:
        raise _failed(
            "render_failed",
            "Fiji did not return a detached overlay for rendering.",
            "Try selecting a valid active image and retry.",
        )
    return copied


def _copy_current_annotations(
    image: Any, detached: Any, c: int, z: int, t: int
) -> None:
    try:
        source_overlay = None if _hide_overlay(image) else image.getOverlay()
        overlay = _filtered_overlay(source_overlay, c, z, t)
        active_roi = _clone_roi(image.getRoi())
    except FijiError:
        raise
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not read the active annotations for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error

    if active_roi is not None:
        _reset_one_plane_position(active_roi)
    try:
        if overlay is not None:
            if active_roi is not None:
                overlay.add(active_roi)
            detached.setOverlay(overlay)
        elif active_roi is not None:
            detached.setRoi(active_roi)
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not attach detached annotations for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error


def _current_position(image: Any) -> tuple[int, int, int]:
    try:
        return int(image.getC()), int(image.getZ()), int(image.getT())
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not determine the current C/Z/T position of the active image.",
            "Try selecting a valid active image and retry.",
        ) from error


def _annotation_present(image: Any, method_name: str) -> bool:
    try:
        return getattr(image, method_name)() is not None
    except Exception:
        return False


def _hide_overlay(image: Any) -> bool:
    """Return ImageJ's overlay-visibility state; absent APIs mean visible."""
    try:
        return bool(image.getHideOverlay())
    except Exception:
        return False


def _visible_overlay_present(image: Any) -> bool:
    return not _hide_overlay(image) and _annotation_present(image, "getOverlay")


def _buffered_image_from_flattened(image: Any) -> Any:
    try:
        buffered = image.getBufferedImage()
    except Exception:
        buffered = None
    if buffered is not None:
        return buffered

    try:
        buffered = image.getProcessor().createBufferedImage()
    except Exception:
        buffered = None
    if buffered is None:
        raise _failed(
            "render_failed",
            "Could not rasterize the rendered current C/Z/T plane.",
            "Try converting the active image to RGB and retry.",
        )
    return buffered


def render_active_image(ij: Any) -> RenderedPNG:
    """Render the active current plane, visible overlay, and ROI without window chrome."""
    try:
        image = ij.WindowManager.getCurrentImage()
    except Exception as error:
        raise _failed(
            "no_active_image",
            "No active image is available to screenshot.",
            "Open or select an image, then retry.",
        ) from error
    if image is None:
        raise _failed(
            "no_active_image",
            "No active image is available to screenshot.",
            "Open or select an image, then retry.",
        )

    c, z, t = _current_position(image)
    current_plane = _duplicate_current_plane(image, c, z, t)
    try:
        flattened = current_plane.flatten()
    except Exception as error:
        raise _failed(
            "render_failed",
            "Could not flatten the current C/Z/T plane for rendering.",
            "Try selecting a valid active image and retry.",
        ) from error
    if flattened is None:
        flattened = current_plane

    rendered = _buffered_image_to_pil(_buffered_image_from_flattened(flattened))
    return _rendered_png(
        rendered,
        {
            "target": "active_image",
            "current_c": c,
            "current_z": z,
            "current_t": t,
            "overlay_present": _visible_overlay_present(image),
            "roi_present": _annotation_present(image, "getRoi"),
        },
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _text_lines(
    columns: list[Any], rows: list[list[Any]], omitted_rows: int
) -> list[str]:
    column_count = len(columns)
    lines = ["\t".join(_text(column) for column in columns)]
    for row in rows:
        lines.append(
            "\t".join(
                _text(row[column]) if column < len(row) else ""
                for column in range(column_count)
            )
        )
    if omitted_rows:
        lines.append(f"... ({omitted_rows} rows omitted)")
    return lines


def _render_text(lines: list[str]) -> Image.Image:
    font = ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1), "white"))
    bounds = [probe.textbbox((0, 0), line, font=font) for line in lines]
    widths = [right - left for left, _top, right, _bottom in bounds]
    heights = [bottom - top for _left, top, _right, bottom in bounds]
    line_height = int(max(heights, default=1) + 3)
    width = max(int(max(widths, default=1) + 2 * _MARGIN), 1)
    height = max(int(len(lines) * line_height + 2 * _MARGIN), 1)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    y: int = _MARGIN
    for line in lines:
        draw.text((_MARGIN, y), line, fill="black", font=font)
        y += line_height
    return image


def render_results(
    columns: list[Any], rows: list[list[Any]], total_rows: int
) -> RenderedPNG:
    """Render the first 100 ordered Results rows to a deterministic PNG table."""
    rendered_rows = list(rows[:_MAX_RESULT_ROWS])
    total = max(int(total_rows), 0)
    omitted_rows = max(total - len(rendered_rows), 0)
    image = _render_text(_text_lines(columns, rendered_rows, omitted_rows))
    return _rendered_png(
        image,
        {
            "target": "results",
            "columns": [_text(column) for column in columns],
            "total_rows": total,
            "rendered_rows": len(rendered_rows),
            "omitted_rows": omitted_rows,
        },
    )


def _resolve_image_path(path: str | Path, label: str) -> Path:
    if not isinstance(path, (str, Path)) or not str(path).strip():
        raise _failed(
            "invalid_path",
            f"{label} path must be a non-empty local file path.",
            "Provide a non-empty local image path and retry.",
        )
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise _failed(
            "invalid_path",
            f"Could not resolve {label} image path.",
            "Provide a valid local image path and retry.",
        ) from error
    try:
        if not resolved.exists():
            raise _failed(
                "missing_file",
                f"Image file not found: {resolved}",
                "Check the local image path and retry.",
            )
        if not resolved.is_file():
            raise _failed(
                "invalid_path",
                f"Image path is not a file: {resolved}",
                "Provide a local image file path and retry.",
            )
    except FijiError:
        raise
    except OSError as error:
        raise _failed(
            "invalid_path",
            f"Could not inspect {label} image path.",
            "Check the local image path and retry.",
        ) from error
    return resolved


def _validate_image_header(path: Path, image: Image.Image) -> None:
    try:
        width, height = image.size
        if width < 1 or height < 1:
            raise ValueError("image dimensions must be positive")
    except Exception as error:
        raise _failed(
            "unreadable_image",
            f"Image has invalid dimensions: {path}",
            "Provide a readable local raster image and retry.",
        ) from error
    if width * height > _MAX_COMPARE_PIXELS:
        raise _failed(
            "image_too_large",
            f"Image exceeds the {_MAX_COMPARE_PIXELS:,}-pixel comparison limit: {path}",
            "Use an image at or below the comparison pixel limit and retry.",
        )


def _open_image_header(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            _validate_image_header(path, image)
            image.load()
            return cast("Image.Image", image.convert("RGB"))
    except FijiError:
        raise
    except Exception as error:
        raise _failed(
            "unreadable_image",
            f"Could not read image: {path}",
            "Provide a readable local raster image and retry.",
        ) from error


def _display_copy(image: Image.Image) -> Image.Image:
    """Return a bounded display copy before panel composition."""
    return fit_within(image, _MAX_DIMENSION)


def _chunk_rgb(image: Image.Image, width: int, start: int, stop: int) -> np.ndarray:
    return np.asarray(
        image.crop((0, start, width, stop)).convert("RGB"), dtype=np.int16
    )


def _comparison_metrics(before: Image.Image, after: Image.Image) -> dict[str, float]:
    width, height = before.size
    total_absolute = 0
    total_squared = 0
    changed_pixels = 0

    for start in range(0, height, _METRIC_CHUNK_ROWS):
        stop = min(start + _METRIC_CHUNK_ROWS, height)
        before_values = _chunk_rgb(before, width, start, stop)
        after_values = _chunk_rgb(after, width, start, stop)
        absolute = np.abs(before_values - after_values)
        total_absolute += int(np.sum(absolute, dtype=np.uint64))
        squared = absolute.astype(np.uint64)
        total_squared += int(np.sum(squared * squared, dtype=np.uint64))
        changed_pixels += int(np.count_nonzero(np.any(absolute > 0, axis=2)))

    channels = width * height * 3
    return {
        "mae": total_absolute / (channels * 255.0),
        "rmse": math.sqrt(total_squared / (channels * 255.0 * 255.0)),
        "changed_pixel_fraction": changed_pixels / (width * height),
    }


def _labelled_panel(label: str, image: Image.Image) -> Image.Image:
    font = ImageFont.load_default()
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1), "white"))
    left, top, right, bottom = probe.textbbox((0, 0), label, font=font)
    label_height = int(bottom - top)
    panel = Image.new(
        "RGB",
        (image.width + 2 * _MARGIN, label_height + image.height + 3 * _MARGIN),
        "white",
    )
    draw = ImageDraw.Draw(panel)
    draw.text((_MARGIN, _MARGIN), label, fill="black", font=font)
    panel.paste(image.convert("RGB"), (_MARGIN, label_height + 2 * _MARGIN))
    return panel


def _compose_panels(panels: list[tuple[str, Image.Image]]) -> Image.Image:
    rendered = [_labelled_panel(label, image) for label, image in panels]
    width = sum(panel.width for panel in rendered) + _PANEL_GAP * (len(rendered) - 1)
    height = max(panel.height for panel in rendered)
    composite = Image.new("RGB", (width, height), "white")
    x = 0
    for panel in rendered:
        composite.paste(panel, (x, 0))
        x += panel.width + _PANEL_GAP
    return composite


def _comparison_metadata(
    before: Image.Image, after: Image.Image, panels: list[str]
) -> dict[str, Any]:
    return {
        "before_dimensions": {"width": before.width, "height": before.height},
        "after_dimensions": {"width": after.width, "height": after.height},
        "dimensions_match": before.size == after.size,
        "panels": panels,
    }


def _absolute_difference(before: Image.Image, after: Image.Image) -> Image.Image:
    before_values = np.asarray(before.convert("RGB"), dtype=np.int16)
    after_values = np.asarray(after.convert("RGB"), dtype=np.int16)
    return Image.fromarray(np.abs(before_values - after_values).astype(np.uint8))


def compare_paths(before_path: str | Path, after_path: str | Path) -> RenderedPNG:
    """Compare two local raster paths without contacting or initializing Fiji."""
    before = _open_image_header(_resolve_image_path(before_path, "before"))
    try:
        after = _open_image_header(_resolve_image_path(after_path, "after"))
    except Exception:
        before.close()
        raise

    try:
        metadata = _comparison_metadata(before, after, ["before", "after"])
        before_display = _display_copy(before)
        after_display = _display_copy(after)
        panels: list[tuple[str, Image.Image]] = [
            ("Before", before_display),
            ("After", after_display),
        ]

        if before.size == after.size:
            metadata.update(_comparison_metrics(before, after))
            metadata["panels"] = ["before", "after", "absolute_difference"]
            panels.append(
                (
                    "Absolute difference",
                    _absolute_difference(before_display, after_display),
                )
            )

        return _rendered_png(_compose_panels(panels), metadata)
    finally:
        before.close()
        after.close()
