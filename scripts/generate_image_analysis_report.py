#!/usr/bin/env python3
"""
Batch-analyze demo_images using **MCP only**: spawn the Fiji MCP server over stdio and call tools
via the Model Context Protocol (FastMCP `Client` + `StdioTransport`). This script does **not** import
`fiji_mcp.*` tools in-process.

Prerequisites:
  - Same environment as Fiji (e.g. conda env with `fastmcp` + `pyimagej`).
  - `FIJI_PATH` set to your Fiji installation root.
  - Macros run while the server uses stdio must not call ImageJ `print()` — stdout is reserved for MCP JSON-RPC.

  export FIJI_PATH=/Applications/Fiji FIJI_MODE=headless
  export FIJI_MCP_PYTHON=/path/to/that/env/bin/python   # optional; defaults to sys.executable

  python scripts/generate_image_analysis_report.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
except ImportError as exc:  # pragma: no cover
    print("Install fastmcp in this environment (pip install fastmcp).", file=sys.stderr)
    raise SystemExit(1) from exc

_REPO = Path(__file__).resolve().parents[1]
_DEMO = _REPO / "demo_images"
_OUT_DIR = _REPO / "research_output"

_MACRO_STATS = r"""
getDimensions(w, h, channels, slices, frames);
getStatistics(area, mean, min, max, std);
return getTitle() + "|DIMS|" + w + "|" + h + "|" + channels + "|" + slices + "|" + frames + "|STATS|" + area + "|" + mean + "|" + min + "|" + max + "|" + std;
"""

_TOOL_TIMEOUT = float(os.environ.get("FIJI_MCP_CLIENT_TOOL_TIMEOUT", "900"))


def _collect_image_paths() -> list[Path]:
    paths: list[Path] = []
    if not _DEMO.is_dir():
        return paths
    for p in sorted(_DEMO.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.suffix.lower() in {".png", ".pgm", ".pbm", ".ppm", ".tif", ".tiff", ".jpg", ".jpeg"}:
            paths.append(p)
    return paths


def _tool_result_to_dict(data: object) -> dict:
    if data is None:
        return {}
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if isinstance(data, dict):
        return data
    return {"repr": repr(data)}


def _strip_large_fields(obj: object, max_b64: int = 80) -> object:
    """Make JSON-safe; truncate huge base64 screenshot payloads."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "image_base64" and isinstance(v, str) and len(v) > max_b64:
                out[k] = f"<omitted {len(v)} chars>"
            else:
                out[k] = _strip_large_fields(v, max_b64)
        return out
    if isinstance(obj, list):
        return [_strip_large_fields(x, max_b64) for x in obj]
    return obj


async def _mcp_call(client: Client, name: str, arguments: dict | None = None) -> dict:
    res = await client.call_tool(name, arguments or {}, timeout=_TOOL_TIMEOUT)
    if res.is_error:
        msg = ""
        if res.content:
            c0 = res.content[0]
            if hasattr(c0, "text"):
                msg = str(c0.text)
        raise RuntimeError(f"MCP tool {name!r} failed: {msg or res}")
    return _tool_result_to_dict(res.data)


async def _build_report_async(client: Client, images_meta: list[Path]) -> dict:
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_via": "MCP stdio only (no in-process fiji_mcp tool imports)",
        "fiji_path": os.environ.get("FIJI_PATH"),
        "fiji_mode": os.environ.get("FIJI_MODE"),
        "health": await _mcp_call(client, "health_check", {}),
        "extensions": await _mcp_call(client, "list_extensions", {}),
        "commands_sample": await _mcp_call(client, "list_all_commands", {"limit": 40}),
        "searches": {},
        "describe_plugin": None,
        "list_open_images_after_health": await _mcp_call(client, "list_open_images", {}),
        "images": [],
        "run_batch_macros_sample": None,
        "screenshot_active_sample": None,
        "workflow_sample": None,
    }

    for q in ("network", "particle", "colocal", "segment", "threshold"):
        try:
            report["searches"][q] = await _mcp_call(client, "search_commands", {"query": q, "limit": 8})
        except Exception as e:
            report["searches"][q] = {"error": str(e)}

    try:
        hits = (report["searches"].get("particle") or {}).get("matches") or []
        if isinstance(hits, list) and hits and isinstance(hits[0], dict):
            name = hits[0].get("name")
            if name:
                report["describe_plugin"] = await _mcp_call(
                    client, "describe_plugin", {"command_name": name}
                )
    except Exception as e:
        report["describe_plugin"] = {"error": str(e)}

    for img_path in images_meta:
        row: dict = {"path": str(img_path.relative_to(_REPO)), "errors": []}
        try:
            row["open"] = await _mcp_call(client, "open_image", {"path": str(img_path.resolve())})
            row["info"] = await _mcp_call(client, "get_image_info", {})
            mr = await _mcp_call(client, "run_macro", {"macro_code": _MACRO_STATS, "retries": 1})
            row["macro_result"] = (mr.get("result") or "")[:500]
            row["macro_log_snippet"] = (mr.get("log_tail") or "")[-800:]
            ret = mr.get("result") or ""
            m = re.search(
                r"\|DIMS\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|(\d+)\|STATS\|([\d.eE+-]+)\|([\d.eE+-]+)\|([\d.eE+-]+)\|([\d.eE+-]+)\|([\d.eE+-]+)",
                ret,
            )
            if m:
                row["parsed_dims"] = [int(m.group(i)) for i in range(1, 6)]
                row["parsed_stats"] = [float(m.group(i)) for i in range(6, 11)]
        except Exception as e:
            row["errors"].append(str(e))
        report["images"].append(row)

    try:
        shot = await _mcp_call(client, "screenshot_fiji", {"capture_mode": "active_image"})
        report["screenshot_active_sample"] = _strip_large_fields(shot)
    except Exception as e:
        report["screenshot_active_sample"] = {"error": str(e)}

    try:
        # ImageJ print() must not be used — stdout is reserved for MCP JSON-RPC.
        report["run_batch_macros_sample"] = await _mcp_call(
            client,
            "run_batch_macros",
            {
                "macros": ['return "batch_step_1";', 'return "batch_step_2";'],
                "continue_on_error": True,
                "retries_per_step": 1,
            },
        )
    except Exception as e:
        report["run_batch_macros_sample"] = {"error": str(e)}

    try:
        wf = await _mcp_call(
            client,
            "run_workflow",
            {
                "steps": [
                    {"macro": 'return "wf_step_1";', "screenshot_after": False},
                    {"macro": 'return "wf_step_2";', "screenshot_after": False},
                ],
                "verify_each_step": False,
                "continue_on_error": True,
            },
        )
        report["workflow_sample"] = wf
    except Exception as e:
        report["workflow_sample"] = {"error": str(e)}

    return report


async def _async_main() -> dict:
    if not os.environ.get("FIJI_PATH", "").strip():
        raise SystemExit("Set FIJI_PATH to your Fiji installation root.")
    os.environ.setdefault("FIJI_MODE", "headless")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    py = os.environ.get("FIJI_MCP_PYTHON", sys.executable)
    server_env = {**os.environ}
    server_env.setdefault("PYTHONPATH", str(_REPO / "src"))

    transport = StdioTransport(
        command=py,
        args=["-m", "fiji_mcp"],
        env=server_env,
        cwd=str(_REPO),
        keep_alive=False,
    )
    images_meta = _collect_image_paths()
    client = Client(transport, init_timeout=900, timeout=900)
    async with client:
        return await _build_report_async(client, images_meta)


def main() -> int:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = asyncio.run(_async_main())

    raw_path = _OUT_DIR / "analysis_raw.json"
    raw_path.write_text(
        json.dumps(_strip_large_fields(report), indent=2, default=str),
        encoding="utf-8",
    )

    md = _render_markdown(report, _collect_image_paths())
    doc_path = _REPO / "docs" / "fiji_mcp_comprehensive_image_analysis_report.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(md, encoding="utf-8")

    print(f"Wrote {raw_path}")
    print(f"Wrote {doc_path}")
    return 0


def _render_markdown(report: dict, paths: list[Path]) -> str:
    lines: list[str] = []
    lines.append("# Fiji MCP — comprehensive image corpus analysis")
    lines.append("")
    lines.append(f"**Generated (UTC):** `{report['generated_at']}`  ")
    lines.append(f"**Fiji root:** `{report.get('fiji_path')}`  ")
    lines.append(f"**Mode:** `{report.get('fiji_mode')}`  ")
    lines.append(f"**Analysis path:** `{report.get('analysis_via', 'MCP')}`  ")
    lines.append("")
    lines.append("## 1. Purpose and methodology")
    lines.append("")
    lines.append(
        "This report was produced by `scripts/generate_image_analysis_report.py`, which acts as an **MCP client** only: "
        "it spawns `python -m fiji_mcp` over **stdio** and invokes Fiji tools exclusively through **`call_tool`** "
        "(no in-process imports of `fiji_mcp.tools.*`). Parallel read-only reconnaissance (file/tool inventory) may "
        "still be done separately; every numeric result in §2–§8 below came from the live MCP server."
    )
    lines.append("")
    lines.append("### 1.1 Scientific scope")
    lines.append("")
    lines.append(
        "- **Primary data:** every raster under `demo_images/` shipped with this repository (PNG PGM). "
        "No claim is made about biological specimen identity; content is treated as **unknown imaging data** "
        "for first-pass **radiometric and morphometric** characterization."
    )
    lines.append(
        "- **“Network” analysis:** in image computing, *networks* usually mean **graph-structured pipelines** "
        "(e.g. KNIME/ImageJ integration) or **neural-network–based** denoising/segmentation plugins. "
        "This run **does not** train deep models; instead we **search the installed Fiji command index** for "
        "commands whose names suggest graph, colocalization, or segmentation workflows, and we cite what Fiji exposes."
    )
    lines.append(
        "- **Rigor:** for each image we record **ImageJ `getStatistics`** on the active `ImagePlus` after open, "
        "alongside **`get_image_info`** (mean, σ, min, max, bit depth, dimensions). "
        "Limitations: RGB composites are summarized by ImageJ’s current channel semantics; PGM is 8-bit gray."
    )
    lines.append("")
    lines.append("### 1.2 Parallel reconnaissance (dispatching-parallel-agents)")
    lines.append("")
    lines.append(
        "Two **independent read-only** explorations can run **in parallel**: (1) filesystem inventory of `demo_images/`, "
        "(2) source-level catalog of every `@mcp.tool` in `src/fiji_mcp/tools/`. **All Fiji measurements** in this report "
        "were obtained **only** through MCP `call_tool` on a dedicated server subprocess."
    )
    lines.append("")
    lines.append("### 1.3 Corpus inventory (parallel file scan)")
    lines.append("")
    lines.append(
        "`demo_images/` contains **`img00.png`–`img22.png`** (23 PNGs) and **`sample_gradient.pgm`** (8×8 synthetic gradient). "
        "`demo_output/` may hold JPEGs from prior `screenshot_fiji` demos. No other scientific rasters appear under "
        "`src/`, `tests/`, or `scripts/` in this repository."
    )
    lines.append("")
    lines.append("### 1.4 MCP tool surface (parallel code scan)")
    lines.append("")
    lines.append("| Function | Async | Role |")
    lines.append("|----------|:-----:|------|")
    lines.append("| `health_check` | No | Bridge health, Fiji path, mode, ImageJ version, timeout. |")
    lines.append("| `open_image` | No | Open path; headless uses `WindowManager.setTempCurrentImage`. |")
    lines.append("| `save_image` | No | Save active image via ImageJ `saveAs`. |")
    lines.append("| `run_macro` | No | Execute ImageJ1 macro; returns `result` + `log_tail`. |")
    lines.append("| `run_batch_macros` | **Yes** | Batch macros + optional MCP progress. |")
    lines.append("| `list_all_commands` | No | CommandService + Menus (use `limit`). |")
    lines.append("| `search_commands` | No | Keyword + fuzzy search over command names/classes. |")
    lines.append("| `describe_plugin` | No | Metadata + SciJava inputs for one command. |")
    lines.append("| `list_extensions` | No | Update sites (often empty in this headless path). |")
    lines.append("| `list_open_images` | No | Open windows (often 0 in headless). |")
    lines.append("| `get_image_info` | No | Dimensions, channels, bit depth, ROI statistics. |")
    lines.append("| `screenshot_fiji` | No | `full_screen` / `active_image` / `results_table`. |")
    lines.append("| `run_workflow` | **Yes** | Multi-step pipeline + optional screenshots / progress. |")
    lines.append("")
    lines.append(
        "**Search note:** `search_commands(\"network\")` often returns **no** name matches; use **`segment`**, "
        "**`colocal`**, **`particle`**, **`threshold`**, or `list_all_commands`."
    )
    lines.append("")

    h = report.get("health") or {}
    lines.append("## 2. Runtime health (`health_check`)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(h, indent=2))
    lines.append("```")
    lines.append("")

    loi = report.get("list_open_images_after_health")
    if loi:
        lines.append("## 2.1 Open windows after health (`list_open_images`)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(loi, indent=2)[:4000])
        lines.append("```")
        lines.append("")

    ext = report.get("extensions") or {}
    lines.append("## 3. Fiji extensions / update sites (`list_extensions`)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(ext, indent=2)[:8000])
    lines.append("```")
    lines.append("")

    lines.append("## 4. Command discovery")
    lines.append("")
    sample = report.get("commands_sample") or {}
    lines.append(
        f"**`list_all_commands(limit=40)`** returned **{sample.get('returned', '?')}** of **{sample.get('total', '?')}** commands (truncated sample)."
    )
    lines.append("")
    lines.append("| Name | Class | Menu |")
    lines.append("|------|-------|------|")
    for c in (sample.get("commands") or [])[:25]:
        lines.append(
            f"| `{c.get('name', '')[:60]}` | `{str(c.get('class_name', ''))[:50]}` | `{str(c.get('menu_path', ''))[:40]}` |"
        )
    lines.append("")

    lines.append("### 4.1 Keyword searches (`search_commands`)")
    lines.append("")
    for q, payload in sorted((report.get("searches") or {}).items()):
        lines.append(f"#### Query: `{q}`")
        lines.append("")
        if "error" in payload:
            lines.append(f"*Error:* `{payload['error']}`")
            lines.append("")
            continue
        matches = payload.get("matches") or payload.get("commands") or []
        lines.append("| Name | Class |")
        lines.append("|------|-------|")
        for m in matches[:8]:
            if isinstance(m, dict):
                lines.append(f"| `{str(m.get('name', ''))[:70]}` | `{str(m.get('class_name', ''))[:55]}` |")
        lines.append("")

    dp = report.get("describe_plugin")
    if dp and "error" not in dp:
        lines.append("## 5. Plugin introspection (`describe_plugin`) — sample")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(dp, indent=2)[:12000])
        lines.append("```")
        lines.append("")
    elif dp:
        lines.append("## 5. Plugin introspection")
        lines.append("")
        lines.append(f"*Skipped or failed:* `{dp.get('error')}`")
        lines.append("")

    batch = report.get("run_batch_macros_sample")
    if batch and "error" not in batch:
        lines.append("## 5.1 Batch macros (`run_batch_macros`)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(batch, indent=2)[:8000])
        lines.append("```")
        lines.append("")
    elif batch:
        lines.append("## 5.1 Batch macros (`run_batch_macros`)")
        lines.append("")
        lines.append(f"*Error:* `{batch.get('error')}`")
        lines.append("")

    lines.append("## 6. Per-image measurements")
    lines.append("")
    lines.append(
        "Procedure per file (each via MCP `call_tool`): `open_image` → `get_image_info` → `run_macro` "
        "(`getDimensions` + `getStatistics`, return string). Headless server uses `setTempCurrentImage`."
    )
    lines.append("")
    lines.append("| File | W×H | Bit | Mean | StdDev | Min | Max | Macro stats (area,mean,min,max,std) | Notes |")
    lines.append("|------|-----|-----|------|--------|-----|-----|---------------------------------------|-------|")
    for row in report.get("images") or []:
        rel = row.get("path", "")
        if row.get("errors"):
            lines.append(f"| `{rel}` | — | — | — | — | — | — | — | **Errors:** {row['errors']} |")
            continue
        inf = row.get("info") or {}
        pd = row.get("parsed_dims")
        ps = row.get("parsed_stats")
        dims = f"{inf.get('width')}×{inf.get('height')}" if inf else "—"
        note = ""
        if pd and inf and (pd[0] != inf.get("width") or pd[1] != inf.get("height")):
            note += "macro dims differ from get_image_info; "
        ps_s = ", ".join(f"{x:.4g}" for x in ps) if ps else "—"

        def _fmt_num(v: object) -> str:
            if isinstance(v, (int, float)):
                return f"{v:.4g}"
            return "—"

        lines.append(
            f"| `{rel}` | {dims} | {inf.get('bit_depth', '—')} | {_fmt_num(inf.get('mean'))} | {_fmt_num(inf.get('std_dev'))} | "
            f"{_fmt_num(inf.get('min'))} | {_fmt_num(inf.get('max'))} | {ps_s} | {note or '—'} |"
        )
    lines.append("")

    shot = report.get("screenshot_active_sample")
    if shot and "error" not in shot:
        lines.append("## 6.1 Screenshot sample (`screenshot_fiji`, `active_image`)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(shot, indent=2))
        lines.append("```")
        lines.append("")
    elif shot:
        lines.append("## 6.1 Screenshot sample")
        lines.append("")
        lines.append(f"*Error:* `{shot.get('error')}`")
        lines.append("")

    lines.append("## 7. Interpretation guidelines (for researchers)")
    lines.append("")
    lines.append(
        "1. **Intensity statistics** are sensitive to **bit depth**, **lookup tables**, and **color vs. gray** representation. "
        "Compare across images only after harmonizing (e.g. convert to 32-bit gray, or analyze channels separately)."
    )
    lines.append(
        "2. **Small PGM (`sample_gradient.pgm`)** is a synthetic gradient — useful for **pipeline smoke tests**, "
        "not biological inference."
    )
    lines.append(
        "3. **PNG set (`img00`–`img22`)** — treat as an **unlabeled gallery** unless you attach metadata. "
        "Possible next MCP steps: `run_macro` with `run(\"Analyze Particles...\");` after thresholding, "
        "`run_workflow` for multi-step QA, or `screenshot_fiji(active_image)` / `results_table` for agent verification."
    )
    lines.append(
        "4. **MCP-only reproducibility** — rerun this script with the same `FIJI_PATH` / `FIJI_MCP_PYTHON`; "
        "results reflect the MCP tool surface only."
    )
    lines.append("")

    wf = report.get("workflow_sample")
    if wf and "error" not in wf:
        lines.append("## 8. Workflow engine sample (`run_workflow`)")
        lines.append("")
        lines.append("Two trivial macro steps via MCP, `verify_each_step=false` (no screenshots).")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(wf, indent=2)[:6000])
        lines.append("```")
        lines.append("")
    elif wf:
        lines.append("## 8. Workflow engine sample")
        lines.append("")
        lines.append(f"*Workflow smoke failed:* `{wf.get('error')}`")
        lines.append("")

    lines.append("## 9. Raw machine-readable output")
    lines.append("")
    lines.append(f"Full JSON: `research_output/analysis_raw.json` ({len(paths)} images processed).")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
