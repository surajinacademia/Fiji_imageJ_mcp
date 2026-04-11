"""Screenshot tools for GUI-mode visual verification."""

from __future__ import annotations

import io
from typing import Annotated, Literal

import scyjava as sj
from mcp.types import ToolAnnotations
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from fiji_mcp.fiji_bridge import get_bridge_status, get_ij
from fiji_mcp.mcp_instance import mcp
from fiji_mcp.schemas.tool_outputs import ScreenshotResult
from fiji_mcp.utils.error_handler import FijiToolError, run_with_timeout
from fiji_mcp.utils.optimizer import encode_screenshot

_ANN_READ = ToolAnnotations(readOnlyHint=True, idempotentHint=False)

CaptureMode = Annotated[
    Literal["full_screen", "active_image", "results_table"],
    Field(
        description=(
            "full_screen: Java Robot on the primary monitor only (needs display). "
            "active_image: rasterize the current ImagePlus. "
            "results_table: render the ImageJ Results table as a PNG (no desktop; headless-friendly when data exists)."
        ),
    ),
]

_MAX_RESULT_ROWS = 400
_MAX_LINE_CHARS = 512


def _buffered_image_to_pil(buffered: object) -> Image.Image:
    """Decode a Java BufferedImage to PIL without scyjava BufferedImage converters."""
    ByteArrayOutputStream = sj.jimport("java.io.ByteArrayOutputStream")
    ImageIO = sj.jimport("javax.imageio.ImageIO")
    baos = ByteArrayOutputStream()
    ImageIO.write(buffered, "png", baos)
    data = bytes(baos.toByteArray())
    return Image.open(io.BytesIO(data)).convert("RGBA")


def _java_capture_to_pil() -> Image.Image:
    """Capture the default screen device bounds (plan: primary monitor, not virtual multi-monitor span)."""
    _ = get_ij()

    ge = sj.jimport("java.awt.GraphicsEnvironment").getLocalGraphicsEnvironment()
    device = ge.getDefaultScreenDevice()
    bounds = device.getDefaultConfiguration().getBounds()
    rectangle = sj.jimport("java.awt.Rectangle")
    rect = rectangle(bounds.x, bounds.y, bounds.width, bounds.height)
    robot_class = sj.jimport("java.awt.Robot")
    robot = robot_class()
    capture = robot.createScreenCapture(rect)
    pil = _buffered_image_to_pil(capture)
    if pil.mode == "RGBA":
        rgb = Image.new("RGB", pil.size, (255, 255, 255))
        rgb.paste(pil, mask=pil.split()[3])
        return rgb
    return pil.convert("RGB")


def _active_image_to_pil() -> Image.Image:
    """Rasterize the front ImagePlus to a PIL image (Phase 4 smart screenshot: active window / result)."""
    _ = get_ij()
    window_manager = sj.jimport("ij.WindowManager")
    imp = window_manager.getCurrentImage()
    if imp is None:
        raise FijiToolError(
            "No active image to capture. Use open_image, run a macro that creates an image, "
            "or select an image window in Fiji, then retry with capture_mode='active_image'."
        )

    dup = imp.duplicate()
    try:
        image_converter = sj.jimport("ij.process.ImageConverter")
        image_converter(dup).convertToRGB()
    except Exception:
        pass

    buffered = None
    if hasattr(dup, "getBufferedImage"):
        try:
            buffered = dup.getBufferedImage()
        except Exception:
            buffered = None
    if buffered is None:
        ip = dup.getProcessor()
        if hasattr(ip, "createBufferedImage"):
            try:
                buffered = ip.createBufferedImage()
            except Exception:
                buffered = None

    if buffered is None:
        raise FijiToolError(
            "Could not rasterize the active image (unsupported depth or slice layout). "
            "Try converting to RGB (e.g. macro run('RGB Color');) then retry capture_mode='active_image'."
        )

    pil = _buffered_image_to_pil(buffered)
    if pil.mode == "RGBA":
        rgb = Image.new("RGB", pil.size, (255, 255, 255))
        rgb.paste(pil, mask=pil.split()[3])
        return rgb
    return pil.convert("RGB")


def _results_table_to_pil() -> Image.Image:
    """Render the ImageJ Results table as a raster image (headless-friendly)."""
    _ = get_ij()
    results_table = sj.jimport("ij.measure.ResultsTable")
    rt = results_table.getResultsTable()
    if rt is None:
        raise FijiToolError(
            "No Results table instance. Run Measure or another command that fills the Results window first."
        )
    n_rows = int(rt.getCounter())
    if n_rows < 1:
        raise FijiToolError(
            "Results table has no rows. Populate it (e.g. run('Measure');) then retry capture_mode='results_table'."
        )

    n_cols = int(rt.getLastColumn()) + 1
    if n_cols < 1:
        raise FijiToolError("Results table has no columns.")

    def _column_title(col: int) -> str:
        if hasattr(rt, "getColumnHeading"):
            return str(rt.getColumnHeading(col))
        return str(rt.getHeading(col))

    headings = [_column_title(c) for c in range(n_cols)]
    lines: list[str] = ["\t".join(headings)]
    cap = min(n_rows, _MAX_RESULT_ROWS)
    for row in range(cap):
        cells: list[str] = []
        for col in range(n_cols):
            try:
                cells.append(str(rt.getValueAsDouble(col, row)))
            except Exception:
                # Sparse ResultsTable: not every index 0..getLastColumn() is defined for all rows.
                cells.append("")
        lines.append("\t".join(cells))
    if n_rows > cap:
        lines.append(f"... ({n_rows - cap} more rows omitted)")

    lines = [ln[:_MAX_LINE_CHARS] + ("..." if len(ln) > _MAX_LINE_CHARS else "") for ln in lines]

    font = ImageFont.load_default()
    margin = 6
    line_gap = 4
    draw_probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    text_heights: list[int] = []
    text_widths: list[int] = []
    for line in lines:
        bbox = draw_probe.textbbox((0, 0), line, font=font)
        text_widths.append(bbox[2] - bbox[0])
        text_heights.append(bbox[3] - bbox[1])

    width = min(max(max(text_widths) + 2 * margin, 80), 4096)
    line_h = max(text_heights) + line_gap
    height = max(line_h * len(lines) + margin, 40)

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = margin
    for line in lines:
        draw.text((margin, y), line, fill=(0, 0, 0), font=font)
        y += line_h
    return img


@mcp.tool(
    annotations=_ANN_READ,
    description=(
        "Capture pixels for verification: full_screen (primary monitor via Robot), "
        "active_image (current ImagePlus), or results_table (render Measure/Results data). "
        "Use active_image or results_table when running headless without a display."
    ),
)
def screenshot_fiji(
    capture_mode: CaptureMode = "full_screen",
) -> ScreenshotResult:
    """Capture and return an optimized screenshot of Fiji GUI state, image, or results table."""
    get_ij()
    status = get_bridge_status()
    if capture_mode == "full_screen" and status["mode"] == "headless":
        raise FijiToolError(
            "full_screen capture needs a display. Use capture_mode='active_image' or 'results_table' "
            "in headless mode, or set FIJI_MODE=gui (or smart with DISPLAY / Xvfb) and restart."
        )

    def _capture() -> ScreenshotResult:
        if capture_mode == "full_screen":
            image = _java_capture_to_pil()
        elif capture_mode == "active_image":
            image = _active_image_to_pil()
        else:
            image = _results_table_to_pil()
        encoded = encode_screenshot(image)
        return ScreenshotResult(
            capture_mode=capture_mode,
            mime_type="image/jpeg",
            format=encoded.format,
            width=encoded.width,
            height=encoded.height,
            from_cache=encoded.from_cache,
            image_base64=encoded.base64_data,
        )

    return run_with_timeout(_capture)
