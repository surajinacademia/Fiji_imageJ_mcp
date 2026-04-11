# Configuration

---

## Fiji path

The most important setting. Point it at the **folder** containing Fiji's `jars/` and `plugins/` directories.

```bash
# Set it when running fiji-mcp-install:
fiji-mcp-install install cursor --fiji-path /Applications/Fiji

# Or set it as an environment variable:
export FIJI_PATH=/Applications/Fiji
```

Common locations:
- **macOS:** `/Applications/Fiji` or `/Applications/Fiji.app`
- **Windows:** `C:\Fiji.app`
- **Linux:** `/opt/Fiji.app` or `~/Fiji.app`

---

## Mode: headless vs GUI

| Mode | Use when | Screenshot modes available |
|------|----------|---------------------------|
| `headless` (default) | IDE / CLI MCP — most stable | `active_image`, `results_table` |
| `gui` | Local desktop, need full-screen capture | all three, including `full_screen` |

To change mode:
```bash
fiji-mcp-install install cursor --fiji-path /Applications/Fiji --mode gui
```

> On macOS with Cursor or Claude Desktop, stick with `headless` — GUI mode can hang.

---

## Manual JSON config

If you prefer to edit the config file directly, use this shape (works for all apps):

```json
{
  "mcpServers": {
    "fiji": {
      "command": "/path/to/your/python",
      "args": ["-m", "fiji_mcp"],
      "env": {
        "FIJI_PATH": "/Applications/Fiji",
        "FIJI_MODE": "headless",
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

Replace `/path/to/your/python` with the Python that has `fiji-mcp-server` installed — usually `.venv/bin/python` or your conda environment's Python.

Config file locations:

| App | Config file |
|-----|-------------|
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) |
| Cursor | `~/.cursor/mcp.json` |
| Claude Code (user) | `~/.claude.json` |
| Claude Code (project) | `<project>/.mcp.json` |
| Gemini CLI | `~/.gemini/settings.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |

---

## Environment variables

| Variable | What it does | Default |
|----------|-------------|---------|
| `FIJI_PATH` | Path to Fiji installation | Auto-detected |
| `FIJI_MODE` | `headless`, `gui`, `smart`, or `auto` | `headless` |
| `FIJI_JAVA_HOME` | Override Java home for JPype | Auto-detected |
| `FIJI_OPERATION_TIMEOUT_SECONDS` | How long each tool can run before timing out | `60` |
| `FIJI_DATA_ROOTS` | Restrict file access to specific folders (security) | Unrestricted |
| `FIJI_SCREENSHOT_MAX_DIM` | Max screenshot width/height in pixels | `1920` |
| `FIJI_SCREENSHOT_QUALITY` | JPEG quality (1–100) | `85` |
| `FIJI_MAX_MACRO_CHARS` | Max macro length in characters | `500000` |

---

## Troubleshooting

**`health_check` never responds / server won't start**
- First JVM startup takes 30–90 seconds — wait before concluding it's broken
- Verify your Fiji path: `ls /Applications/Fiji/jars` should list JAR files

**`ModuleNotFoundError: scyjava` or `pyimagej`**
- The app is using a different Python than where you installed the package
- Re-run `fiji-mcp-install` from the same terminal, or pass `--command /full/path/to/fiji-mcp-server`

**Screenshot fails with "needs a display"**
- You're in headless mode — use `capture_mode="active_image"` instead of `full_screen`

**Cursor + GUI mode hangs on macOS**
- Use `--mode headless` (the default) — `active_image` screenshots still work
