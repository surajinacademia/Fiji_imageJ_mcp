# Repository layout

Top-level map for contributors and release tooling.

| Path | Role |
|------|------|
| [`src/fiji_mcp/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/src/fiji_mcp) | Installable package: MCP server, tools, Fiji bridge, bundled [`data/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/src/fiji_mcp/data) (macro templates, agent skill markdown). |
| [`tests/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/tests) | Pytest suite; integration tests gated on `FIJI_PATH` / markers. |
| [`scripts/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/scripts) | Maintainer utilities: bootstrap install, README demo assets, batch report, MCP+GUI smoke client. |
| [`docs/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/docs) | Docsify site source (quickstart, tools, configuration, architecture). |
| [`docs/releases/`](releases/) | Per-version **release note** drafts for GitHub Releases. |
| [`.github/workflows/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/.github/workflows) | CI and PyPI publish. |
| [`extras/cursor-fiji-mcp-plugin/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/extras/cursor-fiji-mcp-plugin) | **Cursor** local plugin bundle (rules, skill, command). Copy to `~/.cursor/plugins/local/fiji-mcp/`. The repo **`.cursor/`** tree is gitignored—keep skills and editor JSON only on your machine. |
| [`demo_images/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/demo_images) | Sample inputs for scripts and docs. |
| [`demo_output/`](https://github.com/surajinacademia/Fiji_imageJ_mcp/tree/main/demo_output) | Generated README screenshots (regenerate via `scripts/generate_readme_demo_assets.py`). |
| Root | [`README.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/README.md), [`plan.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/plan.md), [`CHANGELOG.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/CHANGELOG.md), [`RELEASING.md`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/RELEASING.md), [`pyproject.toml`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/pyproject.toml). |

PyPI **sdists** intentionally omit most of `docs/` (see [`MANIFEST.in`](https://github.com/surajinacademia/Fiji_imageJ_mcp/blob/main/MANIFEST.in)); release-note files under `docs/releases/` are re-included explicitly for packagers.
