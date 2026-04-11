# Fiji MCP — comprehensive image corpus analysis

**Generated (UTC):** `2026-04-11T09:03:33.445006+00:00`  
**Fiji root:** `/Applications/Fiji`  
**Mode:** `headless`  

## 1. Purpose and methodology

This report was produced automatically by `scripts/generate_image_analysis_report.py`, which exercises the same code paths as the **Fiji MCP server** (PyImageJ + ImageJ1 macros + discovery). Parallel **read-only** reconnaissance (image inventory and tool catalog) was delegated to separate agents; all Fiji state and measurements run **sequentially** in one JVM session to avoid JPype threading issues.

### 1.1 Scientific scope

- **Primary data:** every raster under `demo_images/` shipped with this repository (PNG PGM). No claim is made about biological specimen identity; content is treated as **unknown imaging data** for first-pass **radiometric and morphometric** characterization.
- **“Network” analysis:** in image computing, *networks* usually mean **graph-structured pipelines** (e.g. KNIME/ImageJ integration) or **neural-network–based** denoising/segmentation plugins. This run **does not** train deep models; instead we **search the installed Fiji command index** for commands whose names suggest graph, colocalization, or segmentation workflows, and we cite what Fiji exposes.
- **Rigor:** for each image we record **ImageJ `getStatistics`** on the active `ImagePlus` after open, alongside **`get_image_info`** (mean, σ, min, max, bit depth, dimensions). Limitations: RGB composites are summarized by ImageJ’s current channel semantics; PGM is 8-bit gray.

### 1.2 Parallel reconnaissance (dispatching-parallel-agents)

Two **independent read-only** explorations ran **in parallel**: (1) filesystem inventory of `demo_images/`, (2) source-level catalog of every `@mcp.tool` in `src/fiji_mcp/tools/`. **All Fiji JVM work** in this report ran **sequentially** in one process (PyImageJ + ImageJ are unsafe across arbitrary helper threads).

### 1.3 Corpus inventory (parallel file scan)

`demo_images/` contains **`img00.png`–`img22.png`** (23 PNGs) and **`sample_gradient.pgm`** (8×8 synthetic gradient). `demo_output/` may hold JPEGs from prior `screenshot_fiji` demos. No other scientific rasters appear under `src/`, `tests/`, or `scripts/` in this repository.

### 1.4 MCP tool surface (parallel code scan)

| Function | Async | Role |
|----------|:-----:|------|
| `health_check` | No | Bridge health, Fiji path, mode, ImageJ version, timeout. |
| `open_image` | No | Open path; headless uses `WindowManager.setTempCurrentImage`. |
| `save_image` | No | Save active image via ImageJ `saveAs`. |
| `run_macro` | No | Execute ImageJ1 macro; returns `result` + `log_tail`. |
| `run_batch_macros` | **Yes** | Batch macros + optional MCP progress. |
| `list_all_commands` | No | CommandService + Menus (use `limit`). |
| `search_commands` | No | Keyword + fuzzy search over command names/classes. |
| `describe_plugin` | No | Metadata + SciJava inputs for one command. |
| `list_extensions` | No | Update sites (often empty in this headless path). |
| `list_open_images` | No | Open windows (often 0 in headless). |
| `get_image_info` | No | Dimensions, channels, bit depth, ROI statistics. |
| `screenshot_fiji` | No | `full_screen` / `active_image` / `results_table`. |
| `run_workflow` | **Yes** | Multi-step pipeline + optional screenshots / progress. |

**Search note:** `search_commands("network")` returned **no** name matches on this Fiji install (2073 commands). For ML / graph / pipeline plugins, try **`segment`**, **`colocal`**, **`particle`**, **`threshold`**, or widen with `list_all_commands`.

## 2. Runtime health (`health_check`)

```json
{
  "ok": true,
  "initialized": true,
  "fiji_path": "/Applications/Fiji",
  "mode": "headless",
  "imagej_version": "2.16.0/1.54p",
  "operation_timeout_seconds": 60.0
}
```

## 3. Fiji extensions / update sites (`list_extensions`)

```json
{
  "ok": true,
  "extensions": [],
  "count": 0,
  "note": "Update site introspection unavailable in this runtime."
}
```

## 4. Command discovery

**`list_all_commands(limit=40)`** returned **40** of **2073** commands (truncated sample).

| Name | Class | Menu |
|------|-------|------|
| ` Load Particles (.tif file - fast)` | `QuickPALM.Load_particles_tableFromImg` | `` |
| ` Open VirtualStack` | `QuickPALM.Run_MyMacro("Fast_VirtualStack_Opener.tx` | `` |
| ` Save Particles (.tif file - fast)` | `QuickPALM.Save_particles_table2img` | `` |
| `16-bit` | `ij.plugin.Converter("16-bit")` | `` |
| `2D Histogram` | `util.Histogram_2D` | `` |
| `2d Local Binary Pattern` | `net.imagej.ops.features.lbp2d.DefaultLBP2D` | `[]` |
| `2D Stitching` | `Stitching_2D` | `` |
| `3-3-2 RGB` | `ij.plugin.LutLoader("3-3-2 RGB")` | `` |
| `32-bit` | `ij.plugin.Converter("32-bit")` | `` |
| `3D Objects Counter` | `_3D_objects_counter` | `` |
| `3D OC Options` | `_3D_OC_Options` | `` |
| `3D Project...` | `ij.plugin.Projector` | `` |
| `3D Stitching` | `Stitching_3D` | `` |
| `3D Surface Plot` | `Interactive_3D_Surface_Plot` | `` |
| `3D Viewer` | `ij3d.ImageJ_3D_Viewer` | `` |
| `8-bit` | `ij.plugin.Converter("8-bit")` | `` |
| `8-bit Color` | `ij.plugin.Converter("8-bit Color")` | `` |
| `About bUnwarpJ...` | `bunwarpj.Credits` | `` |
| `About ImageJ...` | `net.imagej.app.AboutImageJ` | `[]` |
| `About ImageJ...` | `ij.plugin.AboutBox` | `` |
| `About This Submenu...` | `ij.plugin.SimpleCommands("about")` | `` |
| `About TrakEM2...` | `ini.trakem2.utils.Utils` | `` |
| `About...` | `QuickPALM.Run_MyMacro("About_.txt")` | `` |
| `About/Help LSMToolbox` | `LSM_Toolbox("about")` | `` |
| `Abs` | `ij.plugin.filter.ImageMath("abs")` | `` |

### 4.1 Keyword searches (`search_commands`)

#### Query: `colocal`

| Name | Class |
|------|-------|
| `Colocalization Test` | `sc.fiji.coloc.Colocalisation_Test` |
| `Colocalization Threshold` | `sc.fiji.coloc.Colocalisation_Threshold` |
| `Colocalize...` | `net.imagej.ops.commands.coloc.Colocalize` |
| `Colocalize...` | `command:net.imagej.ops.commands.coloc.Colocalize` |
| `Close All` | `org.scijava.plugins.commands.display.CloseAll` |
| `Close All` | `ij.plugin.Commands("close-all")` |
| `Coloc 2` | `sc.fiji.coloc.Coloc_2` |
| `Console` | `org.scijava.ui.swing.console.ShowConsole` |

#### Query: `network`

| Name | Class |
|------|-------|

#### Query: `particle`

| Name | Class |
|------|-------|
| ` Load Particles (.tif file - fast)` | `QuickPALM.Load_particles_tableFromImg` |
| ` Save Particles (.tif file - fast)` | `QuickPALM.Save_particles_table2img` |
| `Analyse Particles` | `QuickPALM.Analyse_Particles` |
| `Analyze Particles...` | `ij.plugin.filter.ParticleAnalyzer` |
| `Correct Particles Drift (based on ROI)` | `QuickPALM.Correct_Drift2` |
| `Load Particles (.tif file - fast)` | `QuickPALM.Load_particles_tableFromImg` |
| `Particle Analyzer (3D)` | `process3d.Particle_Analyzer_3D` |
| `Particles` | `ij.plugin.URLOpener("particles.gif")` |

#### Query: `segment`

| Name | Class |
|------|-------|
| `Advanced Weka Segmentation` | `trainableSegmentation.Weka_Segmentation` |
| `Apply saved SIOX segmentator` | `siox.Load_Segmentation` |
| `Balloon` | `sc.fiji.balloonSegmentation.BalloonSegmentation_` |
| `Color Clustering` | `trainableSegmentation.unsupervised.Color_Clustering` |
| `command:net.imagej.ops.segment.detectJunctions.DefaultDetectJunctions` | `net.imagej.ops.segment.detectJunctions.DefaultDetectJun` |
| `command:net.imagej.ops.segment.detectRidges.DefaultDetectRidges` | `net.imagej.ops.segment.detectRidges.DefaultDetectRidges` |
| `Segment blob in 3D Viewer` | `ij3d.segmentation.Blob_Segmentation_in_3D` |
| `Segment Image With Labkit` | `sc.fiji.labkit.ui.plugin.SegmentImageWithLabkitPlugin` |

#### Query: `threshold`

| Name | Class |
|------|-------|
| `Auto Local Threshold` | `fiji.threshold.Auto_Local_Threshold` |
| `Auto Threshold` | `fiji.threshold.Auto_Threshold` |
| `Colocalization Threshold` | `sc.fiji.coloc.Colocalisation_Threshold` |
| `Color Threshold...` | `ij.plugin.frame.ColorThresholder` |
| `command:net.imagej.ops.commands.threshold.GlobalThresholder` | `net.imagej.ops.commands.threshold.GlobalThresholder` |
| `command:net.imagej.ops.threshold.apply.ApplyConstantThreshold` | `net.imagej.ops.threshold.apply.ApplyConstantThreshold` |
| `command:net.imagej.ops.threshold.apply.ApplyManualThreshold` | `net.imagej.ops.threshold.apply.ApplyManualThreshold` |
| `command:net.imagej.ops.threshold.apply.ApplyThresholdComparable` | `net.imagej.ops.threshold.apply.ApplyThresholdComparable` |

## 5. Plugin introspection (`describe_plugin`) — sample

```json
{
  "ok": true,
  "command": {
    "name": "Load Particles (.tif file - fast)",
    "class_name": "QuickPALM.Load_particles_tableFromImg",
    "menu_path": "",
    "source": "Menus"
  },
  "inputs": [],
  "inputs_available": false,
  "note": "Legacy plugins may not expose complete parameter metadata; macro syntax may still be required."
}
```

## 6. Per-image measurements

Procedure per file: `open_image` → `get_image_info` → macro (`getDimensions` + `getStatistics`). Headless sessions use `WindowManager.setTempCurrentImage`; `list_open_images` may still report zero windows.

| File | W×H | Bit | Mean | StdDev | Min | Max | Macro stats (area,mean,min,max,std) | Notes |
|------|-----|-----|------|--------|-----|-----|---------------------------------------|-------|
| `demo_images/img00.png` | 512×512 | 24 | 43.56 | 31.95 | 0 | 166 | 2.621e+05, 43.56, 0, 166, 31.95 | — |
| `demo_images/img01.png` | 609×457 | 24 | 167.8 | 26.11 | 3 | 247 | 2.783e+05, 167.8, 3, 247, 26.11 | — |
| `demo_images/img02.png` | 467×349 | 24 | 12.08 | 15.19 | 0 | 117 | 1.63e+05, 12.08, 0, 117, 15.19 | — |
| `demo_images/img03.png` | 462×346 | 24 | 87.98 | 48.99 | 0 | 255 | 1.599e+05, 87.98, 0, 255, 48.99 | — |
| `demo_images/img04.png` | 302×227 | 24 | 14.36 | 20.23 | 0 | 113 | 6.855e+04, 14.36, 0, 113, 20.23 | — |
| `demo_images/img05.png` | 677×677 | 24 | 37.9 | 22.67 | 0 | 252 | 4.583e+05, 37.9, 0, 252, 22.67 | — |
| `demo_images/img06.png` | 267×231 | 24 | 31.74 | 32.78 | 0 | 167 | 6.168e+04, 31.74, 0, 167, 32.78 | — |
| `demo_images/img07.png` | 502×333 | 24 | 94.29 | 54.07 | 7 | 253 | 1.672e+05, 94.29, 7, 253, 54.07 | — |
| `demo_images/img08.png` | 210×153 | 24 | 157 | 48.04 | 3 | 240 | 3.213e+04, 157, 3, 240, 48.04 | — |
| `demo_images/img09.png` | 361×217 | 24 | 6.43 | 10.31 | 0 | 97 | 7.834e+04, 6.429, 0, 97, 10.31 | — |
| `demo_images/img10.png` | 681×511 | 24 | 41.78 | 40.13 | 0 | 241 | 3.48e+05, 41.78, 0, 241, 40.13 | — |
| `demo_images/img11.png` | 497×299 | 24 | 9.557 | 10.92 | 0 | 100 | 1.486e+05, 9.557, 0, 100, 10.92 | — |
| `demo_images/img12.png` | 295×295 | 24 | 33.5 | 35.33 | 0 | 250 | 8.702e+04, 33.5, 0, 250, 35.33 | — |
| `demo_images/img13.png` | 329×329 | 24 | 55.67 | 59.85 | 0 | 255 | 1.082e+05, 55.67, 0, 255, 59.85 | — |
| `demo_images/img14.png` | 692×460 | 24 | 188.8 | 53.61 | 7 | 255 | 3.183e+05, 188.8, 7, 255, 53.61 | — |
| `demo_images/img15.png` | 512×512 | 24 | 22.54 | 17.96 | 0 | 255 | 2.621e+05, 22.54, 0, 255, 17.96 | — |
| `demo_images/img16.png` | 255×191 | 24 | 25.51 | 17 | 6 | 120 | 4.87e+04, 25.51, 6, 120, 17 | — |
| `demo_images/img17.png` | 776×515 | 24 | 142.2 | 60.96 | 7 | 255 | 3.996e+05, 142.2, 7, 255, 60.96 | — |
| `demo_images/img18.png` | 543×406 | 24 | 7.784 | 12.34 | 0 | 139 | 2.205e+05, 7.784, 0, 139, 12.34 | — |
| `demo_images/img19.png` | 288×218 | 24 | 151.8 | 54.41 | 2 | 253 | 6.278e+04, 151.8, 2, 253, 54.41 | — |
| `demo_images/img20.png` | 322×193 | 24 | 11.26 | 14.38 | 0 | 134 | 6.215e+04, 11.26, 0, 134, 14.38 | — |
| `demo_images/img21.png` | 463×463 | 24 | 62.91 | 60.11 | 0 | 251 | 2.144e+05, 62.91, 0, 251, 60.11 | — |
| `demo_images/img22.png` | 258×172 | 24 | 119.4 | 40.86 | 5 | 250 | 4.438e+04, 119.4, 5, 250, 40.86 | — |
| `demo_images/sample_gradient.pgm` | 8×8 | 8 | 120 | 74.34 | 0 | 240 | 64, 120, 0, 240, 74.34 | — |

## 7. Interpretation guidelines (for researchers)

1. **Intensity statistics** are sensitive to **bit depth**, **lookup tables**, and **color vs. gray** representation. Compare across images only after harmonizing (e.g. convert to 32-bit gray, or analyze channels separately).
2. **Small PGM (`sample_gradient.pgm`)** is a synthetic gradient — useful for **pipeline smoke tests**, not biological inference.
3. **PNG set (`img00`–`img22`)** — treat as an **unlabeled gallery** unless you attach metadata. Possible next MCP steps: `run_macro` with `run("Analyze Particles...");` after thresholding, `run_workflow` for multi-step QA, or `screenshot_fiji(active_image)` / `results_table` for agent verification.
4. **MCP tool coverage** — all server tools are listed in §4; async tools are `run_batch_macros` and `run_workflow` (progress tokens when the client supports them). A minimal `run_workflow` sample appears in §8.

## 8. Workflow engine sample (`run_workflow`)

Two trivial macro steps, `verify_each_step=false` (no screenshots).

```json
{
  "ok": true,
  "results": [
    {
      "step": 1,
      "ok": true,
      "result": {
        "ok": true,
        "result": "",
        "log_tail": ""
      },
      "screenshot": null
    },
    {
      "step": 2,
      "ok": true,
      "result": {
        "ok": true,
        "result": "",
        "log_tail": ""
      },
      "screenshot": null
    }
  ],
  "total_steps": 2,
  "failed_steps": 0,
  "completed_steps": null,
  "failed_step": null
}
```

## 9. Raw machine-readable output

Full JSON: `research_output/analysis_raw.json` (24 images processed).
