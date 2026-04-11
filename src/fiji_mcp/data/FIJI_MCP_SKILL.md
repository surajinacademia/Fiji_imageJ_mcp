---
name: fiji-mcp-workflow
description: >-
  Drive Fiji/ImageJ through the fiji-mcp-server MCP tools—discovery-first (search_commands,
  describe_plugin), verify with screenshots, use bundled macro templates, stdio-safe macros
  without print(), health_check and env (FIJI_PATH, FIJI_MODE, FIJI_DATA_ROOTS). Use when
  the user has Fiji MCP attached or asks for ImageJ automation, batch microscopy, or
  plugin workflows from an assistant.
---

# Fiji MCP server — agent workflow

## When to use this

Apply whenever **`fiji-mcp-server`** (or `python -m fiji_mcp`) is the MCP bridge to Fiji/ImageJ: opening images, running plugins, measuring, screenshots, or multi-step workflows.

## Default loop (discovery → act → verify)

1. **`health_check`** once per session (or after long idle / Fiji errors). Cold JVM can take 30–90s.
2. **Discover before guessing:** **`search_commands`** with short queries (plugin name, task, menu text). Optionally **`list_extensions`** to see what is loaded.
3. **`describe_plugin`** when you have a concrete **`command_name`** from search—confirms options and spelling.
4. **`list_macro_templates`** / **`get_macro_template`** for curated examples; adapt **`macro`** text to the current image and task.
5. **`run_macro`** with the same **`run("Command...", "key=value ...")`** strings the **Macro Recorder** would produce—this is how Fiji invokes menu plugins; the user does not need to see macro code.
6. **Verify:** **`screenshot_fiji`** (`active_image`, **`results_table`**, or `full_screen` in GUI mode) and/or a macro that **`return`s** a short, parseable string. Use **`parse_macro_output`** on returned text when useful. **`compare_screenshots`** for before/after checks.
7. **`get_session_trace`** for an ordered audit of tool calls and open windows.

## Hard rules (stdio MCP)

- **Never use ImageJ `print()`** in macros while the server uses **stdio**—stdout is JSON-RPC; **`print()` corrupts the protocol**.
- Prefer **`return "...";`** (or structured tool payloads) for metrics. Keep returns **small** and **bounded**.
- If **`FIJI_DATA_ROOTS`** is set, **`open_image`** / **`save_image`** paths must stay under an allowed root.
- Use **`FIJI_MODE=headless`** for IDE-hosted MCP unless the user explicitly needs a visible Fiji window (**`FIJI_MODE=gui`**) for **`full_screen`** capture.

## Plugin-heavy tasks (CLIJ2, TrackMate, Coloc 2, Cellpose, MorphoLibJ)

- Confirm the command exists: **`search_commands`** (names differ by Fiji build).
- Start from **`get_macro_template`** ids in the **`plugins`** category when available; they only **open or bootstrap** the tool—finish parameters in follow-up **`run_macro`** calls or recorded option strings.
- If a plugin is missing, say so clearly and suggest install/update via Fiji’s updater rather than inventing APIs.

## Installing this skill in Cursor (optional)

The file ships inside the **`fiji-mcp-server`** wheel under **`fiji_mcp.data`**. Resolve its path:

```bash
python -c "from importlib.resources import files; print(files('fiji_mcp.data') / 'FIJI_MCP_SKILL.md')"
```

Copy (or symlink) that file into **`.cursor/skills/fiji-mcp-workflow/SKILL.md`** in a project, or merge the workflow bullets into your global rules.

## Related repo docs

Quick start, env vars, and clients: **`README.md`**, **`docs/quickstart.md`**, **`docs/configuration.md`**, **`docs/tools.md`**.
