# MCP tools

The server exposes **19** tools (FastMCP), grouped below.

## Fiji lifecycle and macros

| Tool | Purpose |
|------|---------|
| `health_check` | Verify Fiji / PyImageJ readiness |
| `run_macro` | Execute ImageJ macro code (with retries) |
| `run_batch_macros` | Run multiple macros in sequence |
| `open_image` | Open an image from a resolved path |
| `save_image` | Save the active image with format hint |

## Screenshots

| Tool | Purpose |
|------|---------|
| `screenshot_fiji` | `full_screen` (Robot + display), `active_image`, or `results_table` |

## Discovery and metadata

| Tool | Purpose |
|------|---------|
| `list_all_commands` | Enumerate commands (CommandService + menus) |
| `search_commands` | Search command names |
| `describe_plugin` | Details for a specific command |
| `list_extensions` | List extensions / plugins |
| `list_open_images` | Titles of open image windows |
| `get_image_info` | Dimensions, type, calibration |

## Workflows and session helpers

| Tool | Purpose |
|------|---------|
| `run_workflow` | Async multi-step workflow (MCP progress when the client supports it) |
| `parse_macro_output` | Structured parsing helpers for macro text |
| `compare_screenshots` | Compare two screenshot payloads |
| `list_macro_templates` | List curated macro templates |
| `get_macro_template` | Fetch one template by id |
| `get_session_trace` | Session diagnostics |
| `clear_session_trace` | Clear trace buffer |

## Example prompts

```text
Run health_check, then open ./demo_images/sample_gradient.pgm
Search ImageJ commands matching "Gaussian blur"
Run a macro that blurs the image and reports mean gray value
Take active_image and results_table screenshots after Measure
```
