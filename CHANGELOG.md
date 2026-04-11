# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-11

### Added

- FastMCP stdio server for Fiji/ImageJ via PyImageJ (`fiji-mcp-server`, `python -m fiji_mcp`).
- **19 MCP tools**: macros, batch macros, open/save image, screenshots (`full_screen`, `active_image`, `results_table`), command discovery, workflows, session trace helpers, and macro templates.
- `fiji-mcp-install` for **Cursor** and **Claude Desktop** (`--fiji-path`, `--mode`, optional `--command`).
- CI workflow (pytest unit tests on Python 3.10–3.12; integration excluded in CI).
- Documentation site under `docs/` (Docsify: Quick Start, Tools, Configuration, Architecture).
- Example project MCP config in `.mcp.json` (placeholder `FIJI_PATH`; adjust for your machine).
