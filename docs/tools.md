# Available tools

The server exposes **19 tools** you can ask your AI assistant to use. You never call them directly — just describe what you want and the assistant picks the right ones.

---

## Running macros and images

| Tool | What it does |
|------|-------------|
| `health_check` | Check that Fiji is running and get the version |
| `run_macro` | Run any ImageJ macro — this is how plugins get called |
| `run_batch_macros` | Run several macros in sequence |
| `open_image` | Open an image file in Fiji |
| `save_image` | Save the current image to disk |

**Example prompts:**
```
"Open ./cells.tif"
"Apply a Gaussian blur with sigma 3"
"Save the result as ./output/blurred.tif"
```

---

## Screenshots

| Tool | What it does |
|------|-------------|
| `screenshot_fiji` | Capture a screenshot for visual verification |

**Three capture modes:**
- `active_image` — rasterize the current image (works headless, best for verifying results)
- `results_table` — render the ImageJ Results table as an image (works headless)
- `full_screen` — capture the whole screen (requires GUI mode)

**Example prompts:**
```
"Show me a screenshot of the current image"
"Capture the Results table after measuring"
```

---

## Discovering plugins

Don't know which ImageJ plugin to use? The assistant can search for you.

| Tool | What it does |
|------|-------------|
| `search_commands` | Find commands by keyword |
| `list_all_commands` | List all installed commands |
| `describe_plugin` | Get details about a specific command |
| `list_extensions` | Show installed update sites and extensions |

**Example prompts:**
```
"Search for ImageJ commands related to 'segment'"
"What plugins are available for colocalization?"
"What parameters does the Analyze Particles command accept?"
```

---

## Image information

| Tool | What it does |
|------|-------------|
| `list_open_images` | Show all currently open image windows |
| `get_image_info` | Get dimensions, channels, bit depth, and pixel statistics |

**Example prompts:**
```
"What images are currently open in Fiji?"
"What are the dimensions and bit depth of the current image?"
```

---

## Multi-step workflows

| Tool | What it does |
|------|-------------|
| `run_workflow` | Chain multiple macro steps, with optional screenshot after each |

The assistant can use this to build pipelines like:
1. Subtract background
2. Apply threshold
3. Screenshot to verify
4. Count particles
5. Return results

**Example prompts:**
```
"Open the image, subtract background, threshold, count cells — show me a screenshot after each step."
"Run a full segmentation workflow and show me the results."
```

---

## Results and templates

| Tool | What it does |
|------|-------------|
| `parse_macro_output` | Parse measurement results into structured data (JSON, table, numbers) |
| `compare_screenshots` | Compare before/after screenshots with numeric diff metrics |
| `list_macro_templates` | Browse built-in workflow templates |
| `get_macro_template` | Get the macro code for a specific template |

**Built-in template categories:** `filters`, `process`, `segment`, `analyze`, `image`, `annotate`, `channels`, `stack`, `plugins`

**Example prompts:**
```
"List the available macro templates for segmentation"
"Parse the results table and give me the mean area as a number"
```

---

## Session

| Tool | What it does |
|------|-------------|
| `get_session_trace` | Show a log of recent tool calls and open images |
| `clear_session_trace` | Reset the session log |
