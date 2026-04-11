#!/usr/bin/env python3
"""
Regenerate README hero images: Fiji analysis examples on bundled demo_images.

Includes filtering / morphology (Gaussian, Find Edges) and a particle-counting pipeline
(threshold, Analyze Particles with morphology measurements, Results table screenshot).

Writes JPEGs under demo_output/ (committed) for use in README.md and docs/README.md.

Requires:
  - FIJI_PATH: Fiji installation root
  - FIJI_MODE=headless (recommended; active_image screenshots work without a display)

Usage (repo root, env with pyimagej / fiji_mcp):
  export FIJI_PATH=/Applications/Fiji
  export FIJI_MODE=headless
  python scripts/generate_readme_demo_assets.py
"""

from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _save_b64(path: Path, image_base64: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.standard_b64decode(image_base64))


def _close_all() -> None:
    """Best-effort cleanup; headless WindowManager can NPE on ``selectImage``."""
    from fiji_mcp.tools.macro_runner import run_macro

    try:
        run_macro(
            """
while (nImages > 0) {
  close();
}
"""
        )
    except Exception:
        pass


def _example(repo: Path, stem: str, image_rel: str, macro: str, caption_macro: str) -> None:
    from fiji_mcp.tools.macro_runner import open_image, run_macro
    from fiji_mcp.tools.screenshot import screenshot_fiji

    img_path = (repo / image_rel).resolve()
    if not img_path.is_file():
        raise SystemExit(f"Missing demo image: {img_path}")

    open_image(str(img_path))
    shot_in = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_input.jpg", shot_in.image_base64)

    run_macro(macro)
    shot_out = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_analysis.jpg", shot_out.image_base64)

    print(f"  {stem}: {image_rel} -> {caption_macro}")
    _close_all()


def _save_results_jpeg_from_java_rt(rt, out_path: Path, *, max_rows: int = 40) -> None:
    """Rasterize a Java ``ResultsTable`` to JPEG (global Results singleton is not always updated)."""
    n_rows = int(rt.getCounter())
    if n_rows < 1:
        raise RuntimeError("ResultsTable has no rows after particle analysis.")
    n_cols = int(rt.getLastColumn()) + 1
    if n_cols < 1:
        raise RuntimeError("ResultsTable has no columns.")

    def _heading(col: int) -> str:
        if hasattr(rt, "getColumnHeading"):
            return str(rt.getColumnHeading(col))
        return str(rt.getHeading(col))

    headings = [_heading(c) for c in range(n_cols)]
    lines: list[str] = ["\t".join(headings)]
    cap = min(n_rows, max_rows)
    for row in range(cap):
        cells: list[str] = []
        for col in range(n_cols):
            try:
                cells.append(str(rt.getValueAsDouble(col, row)))
            except Exception:
                cells.append("")
        lines.append("\t".join(cells))
    if n_rows > cap:
        lines.append(f"... ({n_rows - cap} more rows omitted)")

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

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(buf.getvalue())


def _run_particle_analyzer_java() -> object:
    """Headless-safe particle analysis: macro ``run('Analyze Particles...')`` opens a GUI; use Java API."""
    import scyjava as sj

    from fiji_mcp.tools.macro_runner import run_macro

    IJ = sj.jimport("ij.IJ")
    imp = IJ.getImage()
    if imp is None:
        raise RuntimeError("No active ImagePlus after thresholding; cannot run ParticleAnalyzer.")

    ParticleAnalyzer = sj.jimport("ij.plugin.filter.ParticleAnalyzer")
    ResultsTable = sj.jimport("ij.measure.ResultsTable")
    Measurements = sj.jimport("ij.measure.Measurements")

    opts = int(ParticleAnalyzer.SHOW_OVERLAY_OUTLINES)
    meas = int(
        Measurements.AREA
        + Measurements.MEAN
        + Measurements.STD_DEV
        + Measurements.PERIMETER
        + Measurements.CIRCULARITY
        + Measurements.FERET
    )

    def _analyze(min_size: float, table: object) -> bool:
        pa = ParticleAnalyzer(opts, meas, table, min_size, 1.0e30, 0.0, 1.0)
        return bool(pa.analyze(imp))

    rt = ResultsTable()
    ok = _analyze(15.0, rt)
    if not ok:
        raise RuntimeError("ParticleAnalyzer.analyze returned false.")
    if int(rt.getCounter()) < 1:
        run_macro('run("Invert");')
        rt = ResultsTable()
        if not _analyze(1.0, rt):
            raise RuntimeError("ParticleAnalyzer retry after Invert failed.")
        if int(rt.getCounter()) < 1:
            raise RuntimeError("No particles detected after threshold + invert; pick another demo_images file.")

    rt.show("Results")
    return rt


def _example_particles_morphology(repo: Path, stem: str, image_rel: str) -> None:
    """Threshold → Java ParticleAnalyzer (counts + morphology) → overlay + Results table."""
    from fiji_mcp.tools.macro_runner import open_image, run_macro
    from fiji_mcp.tools.screenshot import screenshot_fiji

    img_path = (repo / image_rel).resolve()
    if not img_path.is_file():
        raise SystemExit(f"Missing demo image: {img_path}")

    open_image(str(img_path))
    shot_in = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_input.jpg", shot_in.image_base64)

    run_macro(
        """
setBatchMode(true);
run("8-bit");
run("Gaussian Blur...", "sigma=2");
setOption("BlackBackground", true);
setAutoThreshold("Otsu dark");
run("Convert to Mask");
run("Fill Holes");
run("Watershed");
setBatchMode(false);
"""
    )

    rt = _run_particle_analyzer_java()

    shot_overlay = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_overlay.jpg", shot_overlay.image_base64)

    _save_results_jpeg_from_java_rt(rt, repo / "demo_output" / f"{stem}_results.jpg")

    print(f"  {stem}: {image_rel} -> particle count + morphology (Java ParticleAnalyzer)")
    _close_all()


def main() -> int:
    if not os.environ.get("FIJI_PATH", "").strip():
        print("Set FIJI_PATH to your Fiji root, e.g. export FIJI_PATH=/Applications/Fiji", file=sys.stderr)
        return 1
    os.environ.setdefault("FIJI_MODE", "headless")

    from fiji_mcp.tools.macro_runner import health_check

    print("health_check …")
    h = health_check()
    if not h.ok:
        print(f"health_check failed: {h}", file=sys.stderr)
        return 1

    # Distinct demo_images + different ImageJ pipelines
    _example(
        _REPO,
        "readme_ex01_img07",
        "demo_images/img07.png",
        'run("Gaussian Blur...", "sigma=4");',
        "Gaussian blur σ=4",
    )
    _example(
        _REPO,
        "readme_ex02_img04",
        "demo_images/img04.png",
        'run("Find Edges");',
        "Find Edges",
    )
    _example_particles_morphology(
        _REPO,
        "readme_ex03_img10",
        "demo_images/img10.png",
    )

    print("Wrote demo_output/readme_ex01_img07_{input,analysis}.jpg")
    print("Wrote demo_output/readme_ex02_img04_{input,analysis}.jpg")
    print("Wrote demo_output/readme_ex03_img10_{input,overlay,results}.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
