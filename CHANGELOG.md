# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-04-11

### Added

- **Bundled agent skill** `fiji_mcp/data/FIJI_MCP_SKILL.md` (Cursor/Claude-style frontmatter): discovery-first workflow, stdio rules, plugin guidance, copy path via `importlib.resources`.
- **Macro template library** expanded (channels, Z-project, colocal-style Image Calculator, MorphoLibJ / TrackMate / Coloc 2 / CLIJ2 / Cellpose entry points, extra filters).

### Changed

- **README / PyPI:** demo screenshots use absolute **`raw.githubusercontent.com`** URLs so images render on the PyPI project page (relative `./demo_output/` paths are not hosted by PyPI).

## [0.1.1] - 2026-04-11

### Added

- **PyPI packaging:** static `version` in `pyproject.toml`, `py.typed`, optional `[publish]` extras (`build`, `twine`), CI **packaging smoke** (`python -m build`), and **GitHub Actions → PyPI** workflow ([`publish-pypi.yml`](.github/workflows/publish-pypi.yml)) on **Release published**.
- **[`RELEASING.md`](RELEASING.md)** — version bump, trusted publishing, and local `twine check` steps.

### Changed

- **`__version__`** now comes from **`importlib.metadata.version("fiji-mcp-server")`** (removed generated `_version.py` / setuptools-scm for simpler releases).
- README/docs organization, demo asset cleanup, `.gitignore` for generated batch outputs and `mcp_live/` runs.

## [0.1.0] - 2026-04-11

### Added

- FastMCP stdio server for Fiji/ImageJ via PyImageJ (`fiji-mcp-server`, `python -m fiji_mcp`).
- **19 MCP tools**: macros, batch macros, open/save image, screenshots (`full_screen`, `active_image`, `results_table`), command discovery, workflows, session trace helpers, and macro templates.
- `fiji-mcp-install` for **Cursor** and **Claude Desktop** (`--fiji-path`, `--mode`, optional `--command`).
- CI workflow (pytest unit tests on Python 3.10–3.12; integration excluded in CI); **Ruff** lint job; **concurrency** group (cellpose-style).
- Documentation site under `docs/` (Docsify: Quick Start, Tools, Configuration, Architecture, batch report workflow).
- Example project MCP config in `.mcp.json` (placeholder `FIJI_PATH`; adjust for your machine).
- **Packaging / dev parity with [cellpose_mcp](https://github.com/surajinacademia/cellpose_mcp):** `LICENSE`, `MANIFEST.in`, `.python-version`, `.coveragerc`, `.pre-commit-config.yaml`, `CLAUDE.md`, `Fiji_imageJ_mcp.code-workspace`, `RELEASE_NOTES_v0.1.0.md`, `[project.optional-dependencies] dev` / `all`, Ruff / Black / Mypy, `pytest-cov` / markers, **`setuptools_scm`** + `src/fiji_mcp/_version.py`, **`[project.urls]`** and **maintainers** in `pyproject.toml`.
- Package **`__version__`** exposed from `fiji_mcp`.
