#!/usr/bin/env python3
"""
Regenerate README hero images: exactly three Fiji examples on bundled demo_images.

1. **Image processing** — filtering (Gaussian blur).
2. **Analysis** — threshold + Java ParticleAnalyzer; README **markdown** table from ``ResultsTable``.
3. **Feature extraction (skeleton)** — binary mask, ImageJ **Skeletonize**, then Fiji
   **Analyze Skeleton (2D/3D)** when available (branch/junction metrics); headless-safe
   where possible.

Writes JPEGs under ``demo_output/`` and refreshes **markdown tables** in ``README.md``
(between ``<!-- readme-demo-table:… -->`` markers) unless ``UPDATE_README_TABLES=0``.

Requires:
  - FIJI_PATH: Fiji installation root
  - FIJI_MODE=headless (recommended for MCP-style runs)

Usage (repo root, env with pyimagej / fiji_mcp):
  export FIJI_PATH=/Applications/Fiji
  export FIJI_MODE=headless
  python scripts/generate_readme_demo_assets.py
"""

from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

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


def _example_image_process(repo: Path, stem: str, image_rel: str, macro: str, label: str) -> None:
    """Example 1: open → single processing macro → screenshots."""
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
    _save_b64(repo / "demo_output" / f"{stem}_processed.jpg", shot_out.image_base64)

    print(f"  {stem}: {image_rel} -> {label}")
    _close_all()


def _markdown_table_from_rt(
    rt,
    *,
    max_rows: int = 4,
    keep_column_headings: frozenset[str],
) -> str:
    """GitHub-flavored markdown: slim table (index + selected numeric columns)."""
    n_rows = int(rt.getCounter())
    if n_rows < 1:
        return "_No Results rows._\n"

    n_cols = int(rt.getLastColumn()) + 1

    def _heading(col: int) -> str:
        if hasattr(rt, "getColumnHeading"):
            return str(rt.getColumnHeading(col))
        return str(rt.getHeading(col))

    headings = [_heading(c) for c in range(n_cols)]
    col_indices = list(range(n_cols))
    if keep_column_headings is not None:
        picked: list[int] = []
        for c in range(n_cols):
            if headings[c].strip() in keep_column_headings:
                picked.append(c)
        if picked:
            col_indices = picked
            headings = [headings[c] for c in col_indices]

    head_cells = ["#", *headings]
    sep_cells = ["---:"] + ["---:" for _ in headings]
    lines = [
        "| " + " | ".join(head_cells) + " |",
        "| " + " | ".join(sep_cells) + " |",
    ]
    cap = min(n_rows, max_rows)
    for row in range(cap):
        row_cells: list[str] = [str(row + 1)]
        for col in col_indices:
            try:
                v = float(rt.getValueAsDouble(col, row))
                if abs(v - round(v)) < 1e-6 and abs(v) < 1e9:
                    row_cells.append(str(int(round(v))))
                else:
                    row_cells.append(f"{v:.3f}".rstrip("0").rstrip("."))
            except Exception:
                row_cells.append("")
        lines.append("| " + " | ".join(row_cells) + " |")
    out = "\n".join(lines) + "\n"
    if n_rows > cap:
        out += f"\n*{n_rows - cap} more row(s) in the full Results table.*\n"
    return out


def _markdown_skeleton_slim(sr, *, max_trees: int = 4) -> str:
    """Short markdown: tree id, branch count, junction count."""
    n_all = int(sr.getNumOfTrees())
    if n_all < 1:
        return "_No skeleton trees._\n"

    branches = sr.getBranches()
    junctions = sr.getJunctions()
    n_show = min(n_all, max_trees)
    lines = [
        "| Tree | # Branches | # Junctions |",
        "| ---: | ---: | ---: |",
    ]
    for i in range(n_show):
        b = int(branches[i]) if branches is not None else 0
        j = int(junctions[i]) if junctions is not None else 0
        lines.append(f"| {i + 1} | {b} | {j} |")
    out = "\n".join(lines) + "\n"
    if n_all > n_show:
        out += f"\n*{n_all - n_show} more tree(s) omitted.*\n"
    return out


def _patch_readme_table(repo: Path, key: str, inner_md: str) -> None:
    """Replace content between ``readme-demo-table:key`` markers in ``README.md``."""
    path = repo / "README.md"
    text = path.read_text(encoding="utf-8")
    start_tag = f"<!-- readme-demo-table:{key} -->"
    end_tag = f"<!-- /readme-demo-table:{key} -->"
    pat = re.compile(
        re.escape(start_tag) + r"\s*\n.*?\n" + re.escape(end_tag),
        re.DOTALL,
    )
    if not pat.search(text):
        print(f"warning: README.md missing {start_tag} … {end_tag}", file=sys.stderr)
        return
    repl = start_tag + "\n" + inner_md.rstrip() + "\n" + end_tag
    path.write_text(pat.sub(repl, text, count=1), encoding="utf-8")


def _run_particle_analyzer_java() -> object:
    """Headless-safe particle analysis (avoid macro ``Analyze Particles...`` dialog)."""
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
    # README demo: keep the results table small (Area + circularity only).
    meas = int(Measurements.AREA + Measurements.CIRCULARITY)

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
            raise RuntimeError("No particles detected; change demo_images or thresholds.")

    rt.show("Results")
    return rt


def _example_analysis_particles(repo: Path, stem: str, image_rel: str) -> str:
    """Example 2: threshold → ParticleAnalyzer → overlay + measurements (markdown + optional JPEG)."""
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

    particles_md = _markdown_table_from_rt(
        rt,
        max_rows=4,
        keep_column_headings=frozenset({"Area", "Circ."}),
    )

    print(f"  {stem}: {image_rel} -> particle analysis (Area, Circ.)")
    _close_all()
    return particles_md


def _skeleton_result_to_results_table(sr) -> object:
    """Build an ImageJ ``ResultsTable`` from ``SkeletonResult`` (headless-safe)."""
    import scyjava as sj

    ResultsTable = sj.jimport("ij.measure.ResultsTable")
    rt = ResultsTable()
    n = int(sr.getNumOfTrees())
    if n < 1:
        return rt

    def _jcall(name: str):
        m = getattr(sr, name, None)
        if m is None:
            return None
        return m()

    try:
        sr.calculateNumberOfVoxels()
    except Exception:
        pass

    branches = _jcall("getBranches")
    junctions = _jcall("getJunctions")
    end_pts = _jcall("getEndPoints")
    junction_vox = _jcall("getJunctionVoxels")
    slabs = _jcall("getSlabs")
    triples = _jcall("getTriples")
    quadruples = _jcall("getQuadruples")
    n_vox = _jcall("getNumberOfVoxels")
    avg_br = _jcall("getAverageBranchLength")
    max_br = _jcall("getMaximumBranchLength")

    def _cell(arr, row: int) -> float:
        if arr is None:
            return float("nan")
        try:
            return float(arr[row])
        except Exception:
            return float("nan")

    for i in range(n):
        rt.incrementCounter()
        rt.addValue("Skeleton", float(i + 1))
        rt.addValue("# Branches", _cell(branches, i))
        rt.addValue("# Junctions", _cell(junctions, i))
        rt.addValue("# End-point voxels", _cell(end_pts, i))
        rt.addValue("# Junction voxels", _cell(junction_vox, i))
        rt.addValue("# Slab voxels", _cell(slabs, i))
        rt.addValue("# Triple points", _cell(triples, i))
        rt.addValue("# Quadruple points", _cell(quadruples, i))
        rt.addValue("# Tree voxels", _cell(n_vox, i))
        rt.addValue("Avg branch length", _cell(avg_br, i))
        rt.addValue("Max branch length", _cell(max_br, i))

    return rt


def _run_analyze_skeleton_java(imp) -> object | None:
    """Fiji **Analyze Skeleton (2D/3D)** via Java API (macro path often leaves Results empty in headless)."""
    import scyjava as sj

    try:
        AnalyzeSkeleton_ = sj.jimport("sc.fiji.analyzeSkeleton.AnalyzeSkeleton_")
    except Exception:
        return None

    plug = AnalyzeSkeleton_()
    plug.setup("", imp)
    none = int(AnalyzeSkeleton_.NONE)
    # Pass ``imp`` as ``origIP`` (not Java ``null``): JPype overload resolution treats ``None`` as ambiguous
    # between ``run(int, boolean, boolean, ImagePlus, …)`` and ``run(int, double, boolean, ImagePlus, …)``.
    return plug.run(none, False, False, imp, True, False)


def _example_skeleton(repo: Path, stem: str, image_rel: str) -> str:
    """Example 3: binary + Skeletonize; Analyze Skeleton (2D/3D) metrics via Java API."""
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
run("Gaussian Blur...", "sigma=1");
setOption("BlackBackground", true);
setAutoThreshold("Otsu dark");
run("Convert to Mask");
run("Fill Holes");
run("Skeletonize");
setBatchMode(false);
"""
    )

    shot_skel = screenshot_fiji(capture_mode="active_image")
    _save_b64(repo / "demo_output" / f"{stem}_skeleton.jpg", shot_skel.image_base64)

    import scyjava as sj

    IJ = sj.jimport("ij.IJ")
    imp = IJ.getImage()
    if imp is None:
        print(f"  {stem}: {image_rel} -> skeleton only (no active ImagePlus for Analyze Skeleton)")
        _close_all()
        return "_Skeleton image saved; Analyze Skeleton skipped (no image)._"

    sr = _run_analyze_skeleton_java(imp)
    if sr is None:
        print(f"  {stem}: {image_rel} -> skeleton only (sc.fiji.analyzeSkeleton not on classpath)")
        _close_all()
        return "_Analyze Skeleton plugin not available on this classpath._"

    n_trees = int(sr.getNumOfTrees())
    if n_trees < 1:
        print(f"  {stem}: {image_rel} -> skeleton (Analyze Skeleton: zero trees)")
        _close_all()
        return "_No skeleton trees detected._"

    sk_md = _markdown_skeleton_slim(sr, max_trees=4)

    rt = _skeleton_result_to_results_table(sr)
    if int(rt.getCounter()) < 1:
        print(f"  {stem}: {image_rel} -> skeleton (Analyze Skeleton: empty metrics table)")
        _close_all()
        return sk_md

    print(f"  {stem}: {image_rel} -> skeleton + Analyze Skeleton (2D/3D) feature table ({n_trees} tree(s))")
    _close_all()
    return sk_md


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

    # 1) Image processing
    _example_image_process(
        _REPO,
        "readme_ex01_img07",
        "demo_images/img07.png",
        'run("Gaussian Blur...", "sigma=4");',
        "Gaussian blur σ=4",
    )
    # 2) Quantitative analysis (particles)
    particles_md = _example_analysis_particles(
        _REPO,
        "readme_ex02_img10",
        "demo_images/img10.png",
    )
    # 3) Skeleton-based features (built-in Skeletonize + optional Analyze Skeleton plugin)
    skeleton_md = _example_skeleton(
        _REPO,
        "readme_ex03_img12",
        "demo_images/img12.png",
    )

    if os.environ.get("UPDATE_README_TABLES", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        _patch_readme_table(_REPO, "ex2-particles", particles_md)
        _patch_readme_table(_REPO, "ex3-skeleton", skeleton_md)
        print("Patched README.md tables (readme-demo-table markers). Set UPDATE_README_TABLES=0 to skip.")

    print("Wrote demo_output/readme_ex01_img07_{input,processed}.jpg")
    print("Wrote demo_output/readme_ex02_img10_{input,overlay}.jpg")
    print("Wrote demo_output/readme_ex03_img12_{input,skeleton}.jpg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
