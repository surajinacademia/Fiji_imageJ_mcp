# Quick start

Get Fiji MCP running in four steps.

---

## What you need first

- **Python 3.10 or newer** — check with `python3 --version`
- **[Fiji](https://fiji.sc/)** — download and install it, note the folder path
- **Java (JDK)** — required by PyImageJ; install if `pip install fiji-mcp-server` fails on `jpype1`

---

## Step 1 — Install

```bash
pip install fiji-mcp-server
```

Installs everything: FastMCP, PyImageJ, NumPy, Pillow, and two CLI commands — `fiji-mcp-server` and `fiji-mcp-install`.

> **Using a virtual environment?** That's fine — just run the commands below from inside it.

---

## Step 2 — Connect to your AI app

Run the command for whichever app you use. Replace `/Applications/Fiji` with the **folder** that contains Fiji's `jars/` and `plugins/` directories.

```bash
# Claude Desktop
fiji-mcp-install install claude-desktop --fiji-path /Applications/Fiji

# Cursor
fiji-mcp-install install cursor --fiji-path /Applications/Fiji

# Claude Code (all projects)
fiji-mcp-install install claude-code --fiji-path /Applications/Fiji

# Claude Code (one project only)
fiji-mcp-install install claude-code --fiji-path /Applications/Fiji --project /path/to/project

# Gemini CLI
fiji-mcp-install install gemini --fiji-path /Applications/Fiji

# Windsurf
fiji-mcp-install install windsurf --fiji-path /Applications/Fiji
```

**Then restart the app.** The command writes the MCP config automatically — you don't need to edit any JSON files.

> **Can't find your Fiji path?**
> - macOS: usually `/Applications/Fiji` or `/Applications/Fiji.app`
> - Windows: usually `C:\Fiji.app`
> - Linux: usually `/opt/Fiji.app` or `~/Fiji.app`

---

## Step 3 — Verify

In the chat window of your AI app, type:

```
Run the Fiji MCP health_check tool
```

You should see the Fiji version, mode (`headless`), and timeout. If it works, you're ready.

> **First startup takes 30–90 seconds** while the Java VM loads Fiji. This is normal — subsequent calls are fast.

---

## Step 4 — Try it

Some prompts to start with:

```
"Open ./demo_images/sample.tif and tell me the image dimensions."

"Search for ImageJ commands related to threshold."

"Apply a Gaussian blur with sigma 2 and show me the result."

"Count the bright objects in the image and give me their areas and circularity."
```

The assistant will discover the right Fiji plugin, run it, and optionally show a screenshot to confirm the result. You don't need to write any macro code.

---

## Troubleshooting

**The health_check times out or the server doesn't start**
- Check that `FIJI_PATH` points to the right folder — it must contain `jars/` and `plugins/`
- Make sure Java is installed (`java -version` in a terminal)
- On macOS with Cursor, use the default `headless` mode (GUI mode can hang)

**`ModuleNotFoundError: scyjava` or `pyimagej`**
- The app is using the wrong Python. Re-run `fiji-mcp-install` from the same terminal where `pip install` worked, or pass `--command /full/path/to/fiji-mcp-server`

**Screenshot returns an error in headless mode**
- Use `capture_mode="active_image"` or `capture_mode="results_table"` instead of `full_screen` — both work without a display

---

## What's next

| | |
|-|-|
| [**All tools**](tools.md) | Complete list of what the server can do |
| [**Configuration**](configuration.md) | Environment variables, advanced options |
| [**Architecture**](architecture.md) | How PyImageJ, FastMCP, and Fiji connect |
