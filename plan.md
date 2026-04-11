# ImageJ/Fiji MCP Server - Detailed Plan

## Current progress (tracked)

_Last updated: 2026-04-11_

| Phase | Focus | Status |
|-------|--------|--------|
| **1** — Foundation | PyImageJ init, `run_macro`, screenshots, settings | **Done** (`fiji_bridge.py`, `macro_runner.py`, `screenshot.py`, `config/settings.py`) |
| **2** — Discovery | Commands, search, `describe_plugin`, extensions | **Done** (`tools/discovery.py`) |
| **3** — Workflows | `run_workflow`, batch/async, errors | **Done** (`tools/workflow.py`, `utils/error_handler.py`, `utils/java_errors.py`) |
| **4** — Optimization | Screenshot cache/resize, smart mode, GC/timeout tuning | **Done** (`utils/optimizer.py`, settings + tests) |
| **5** — Testing | Fiji-backed integration, benchmarks, release readiness | **In progress** — unit suite green in dev env; integration gated on `FIJI_PATH` + `FIJI_TEST_IMAGE`; optional `docs/` from tree layout not yet added |

**Active work:** Phase 5 — expand integration coverage, validate against real Fiji installs, and finish packaging/docs as needed for release.

### Still missing from the plan

Open product gaps relative to the original vision (ease of use, recipe depth, and optional native Fiji UI). Priorities are ordered by impact on day-to-day agent + user workflows.

| Item | Priority | Notes |
|------|----------|--------|
| **Agent skill / SKILL.md discoverability** | **High** | Workflow guidance ships in the wheel as [`src/fiji_mcp/data/FIJI_MCP_SKILL.md`](src/fiji_mcp/data/FIJI_MCP_SKILL.md) (import path `fiji_mcp.data`), but nothing installs it as a first-class **Cursor / Claude Desktop** skill automatically. The largest ease-of-use gap remains: unless users copy or symlink that file into `.cursor/skills/…` (or equivalent), assistants tend to **re-derive** the **discovery-first → act → verify-with-screenshots** loop every session. Closing this means clearer install UX (CLI subcommand, docs tab, or client-specific skill merge) and/or publishing a companion marketplace skill. |
| **Template library depth** | **Medium** | The bundled [`macro_templates.json`](src/fiji_mcp/data/macro_templates.json) is a **curated** set (on the order of tens of entries), not an encyclopedia. Many stacks (split/merge channels, Z-project variants, Coloc 2 / TrackMate / Cellpose / CLIJ2 / MorphoLibJ) are covered at **bootstrap or single-command** level; remaining work is **depth**: multi-step, parameterized pipelines; headless-friendly patterns where possible; version-specific command strings; and more domain recipes so agents rely less on one-off macro invention. |
| **Fiji Java plugin (bidirectional GUI panel)** | **Low** | Optional native ImageJ/Fiji plugin that mirrors or drives MCP session state from the desktop UI (per earlier two-way GUI ideas). **Not started**; rough effort **2–3 weeks** once scoped (IPC, security, and update-site distribution). |

## Goals

1. **Universal Plugin Access**: Enable LLM to discover and use ANY ImageJ/Fiji plugin or extension without hardcoding
2. **Visual Feedback Loop**: Allow agent to see GUI state via screenshots for verification and decision-making
3. **Autonomous Workflows**: Execute multi-step image analysis tasks without user intervention
4. **No-Code Experience**: Users describe tasks in natural language; agent handles all technical implementation
5. **Persistent Session**: Keep Fiji GUI running for interactive, stateful operations

---

## Features

### Discovery & Introspection
- List all installed extensions/update sites
- Enumerate available commands from all plugins
- Get parameter specifications for any command
- Search for commands by capability/keyword

### Execution
- Run ImageJ macro language commands
- Execute plugin commands with parameters
- Chain multiple operations in sequence
- Handle file I/O (open/save images)

### Visual Feedback
- Capture full Fiji GUI screenshots
- Capture specific image window screenshots
- List open image windows
- Get image metadata and statistics
- **Note**: Screenshots require GUI mode and a **display** (e.g. physical monitor or Xvfb on headless servers). Pure headless environments cannot capture screenshots.

### Autonomous Operation
- Multi-step workflow execution
- Result verification via screenshots
- Error detection and recovery
- Progress reporting
 

## High-Level Design

```
SYSTEM ARCHITECTURE
├── Claude Desktop (MCP Client)
│   └── Sends JSON-RPC commands via stdio
│
├── Python 3 MCP Server Process
│   ├── Tool definitions & routing
│   ├── Response formatting
│   └── Screenshot management
│
└── Fiji/ImageJ Instance (via PyImageJ/JPype)
    ├── JVM running in-process
    ├── All plugins loaded (requires init with Fiji app path, not default ImageJ2 only)
    ├── GUI optional (chosen at startup; cannot switch headless→GUI at runtime)
    └── Java Robot for screenshots (only when GUI + display available)
```

---

## Core Algorithm

### **1. Initialization Sequence**

```
ON_SERVER_START:
    INITIALIZE PyImageJ gateway
        IF fiji_path provided THEN
            USE custom path
        ELSE
            AUTO_DETECT fiji installation (configurable list; extend as needed)
                CHECK: /Applications/Fiji.app
                CHECK: C:/Fiji, C:/Users/<user>/Fiji.app
                CHECK: ~/Fiji.app
                CHECK: /opt/Fiji.app (Linux)
        END IF
        
        # Critical: init with Fiji app path so full Fiji + update-site plugins load
        INIT PyImageJ with fiji_path (not default ImageJ2-only mode)
        
        CONFIGURE mode (chosen once at startup; no headless→GUI switch at runtime)
            IF user_wants_gui OR user_wants_screenshots THEN
                START Fiji with GUI
            ELSE
                START Fiji headless
            END IF
        
        LOAD JVM via JPype
        IMPORT Java classes:
            - ij.IJ (core functions)
            - java.awt.Robot (screenshots)
            - ij.WindowManager (window control)
    
    REGISTER all MCP tools
    WAIT for Claude connections
```

---

### **2. Tool Execution Pattern**

```
ON_TOOL_CALL(tool_name, arguments):
    CASE tool_name OF
        
        "run_macro":
            VALIDATE macro_code not empty
            TRY:
                result = IJ.runMacro(macro_code)
                log = IJ.getLog()
                RETURN success(result, log)
            CATCH error:
                RETURN failure(error_message)
        
        "list_commands":
            # Prefer ImageJ2 CommandService (covers plugins); Menus as secondary for menu structure
            commands = CommandService.getCommands()  # primary
            IF legacy_menu_structure_needed THEN
                commands.MERGE(Menus.getCommands())
            FOR each command IN commands:
                EXTRACT name, class, menu_path
            RETURN sorted_list(commands)
        
        "screenshot_fiji":
            IF gui_mode THEN
                robot = Robot()
                screen_size = Toolkit.getScreenSize()
                image = robot.captureScreen(full_screen)
                ENCODE image to base64
                RETURN image_data
            ELSE
                RETURN error("GUI mode required for screenshots")
        
        "run_workflow":
            steps = arguments.steps
            results = []
            FOR each step IN steps:
                result = EXECUTE step
                IF verify_required THEN
                    screenshot = CAPTURE_SCREEN()
                    IF not VERIFY(result, screenshot) THEN
                        RETURN failure_with_screenshot
                results.APPEND(result)
            RETURN success(results)
    END CASE
```

---

### **3. Smart Screenshot Algorithm**

```
FUNCTION smart_screenshot(context):
    IF mode == "full_gui" THEN
        RETURN capture_entire_screen()
    
    ELSE IF mode == "active_window" THEN
        window = WindowManager.getCurrentWindow()
        RETURN capture_window(window)
    
    ELSE IF mode == "result_only" THEN
        IF ResultsTable.exists() THEN
            RETURN capture_results_table()
        IF image_window.exists() THEN
            RETURN capture_active_image()
    
    OPTIMIZE:
        RESIZE if > max_dimension
        COMPRESS to reduce token cost
        CACHE recent screenshots
    
    RETURN optimized_image
```

---

### **4. Workflow Engine Algorithm**

```
FUNCTION execute_workflow(steps, verify_each=True):
    context = {
        images: [],
        results: [],
        state: {}
    }
    
    FOR i, step IN enumerate(steps):
        PRINT "Step {i+1}/{len(steps)}: {step.description}"
        
        # Execute step
        TRY:
            output = EXECUTE_COMMAND(step.command, step.params)
            context.results.APPEND(output)
        CATCH error:
            IF step.required THEN
                RETURN workflow_failure(i, error, context)
            ELSE
                CONTINUE
        
        # Visual verification if enabled
        IF verify_each AND gui_enabled THEN
            screenshot = smart_screenshot("result_only")
            context.images.APPEND(screenshot)
            
            # Optional: AI verification
            IF ai_verify_enabled THEN
                verification = ASK_CLAUDE("Does this look correct?", screenshot)
                IF not verification.passed THEN
                    RETURN verification_failure(i, screenshot, context)
        
        # State tracking
        context.state = UPDATE_STATE(context.state, output)
        
        # Delay if needed
        IF step.wait_time THEN
            SLEEP(step.wait_time)
    
    RETURN workflow_success(context)
```

---

### **5. Plugin Discovery Algorithm**

```
FUNCTION discover_plugins():
    all_commands = []
    
    # Primary: ImageJ2 CommandService (all registered commands, including Fiji plugins)
    core = CommandService.getCommands()
    all_commands.EXTEND(core)
    
    # Secondary: legacy menu structure (Menus.getCommands()) for menu path / categories
    menu_commands = Menus.getCommands()
    MERGE_WITHOUT_DUPLICATES(all_commands, menu_commands)
    
    # Optional: JAR scan only if needed for plugins not in CommandService (rare)
    # FOR each jar IN fiji_plugins_directory: ...
    
    # Categorize by menu path
    categorized = {
        "Process > Filters": [],
        "Analyze > Measure": [],
        "Plugins > Segmentation": [],
        # ... auto-build from menu structure
    }
    
    FOR command IN all_commands:
        category = EXTRACT_MENU_PATH(command)
        categorized[category].APPEND(command)
    
    # Build search index
    search_index = BUILD_FUZZY_SEARCH(all_commands)
    
    RETURN {
        commands: all_commands,
        categories: categorized,
        search: search_index
    }
```

---

### **6. Command Introspection Algorithm**

```
FUNCTION describe_plugin(plugin_name):
    # Try ImageJ2 CommandInfo first (best)
    TRY:
        command_info = CommandService.getCommand(plugin_name)
        parameters = []
        
        FOR input IN command_info.getInputs():
            param = {
                name: input.getName(),
                type: input.getType(),
                required: input.isRequired(),
                default: input.getDefaultValue(),
                description: input.getDescription(),
                choices: input.getChoices() IF is_enum(input)
            }
            parameters.APPEND(param)
        
        RETURN detailed_spec(parameters)
    
    # Fallback (best-effort only): Macro recorder may have last-run syntax for this plugin
    CATCH:
        last_run = MacroRecorder.getLastCommand()
        IF last_run.matches(plugin_name) THEN
            RETURN parse_macro_syntax(last_run)
        ELSE
            RETURN basic_info(plugin_name)  # many plugins will only get basic_info until better fallback exists
```

---

### **7. Dual-Mode Operation Algorithm**

```
FUNCTION configure_mode(user_preference):
    # Mode is chosen at startup; switching headless→GUI at runtime is not supported by PyImageJ/JVM.
    modes = {
        "auto": DETECT_ENVIRONMENT(),
        "gui": FORCE_GUI_MODE(),
        "headless": FORCE_HEADLESS_MODE(),
        "smart": CHOOSE_AT_STARTUP()  # if screenshots/verification likely needed, start with GUI; else headless
    }
    
    mode = modes[user_preference]
    
    IF mode == "smart" THEN
        # Decide once at startup: use GUI if user may request screenshots or verification
        IF user_may_request_screenshots OR verify_each_enabled THEN
            START Fiji with GUI
        ELSE
            START Fiji headless
        END IF
        # All subsequent operations run in that mode (no late START_GUI())
    
    RETURN mode
```

---

### **8. Error Recovery Algorithm**

```
FUNCTION robust_execute(command, max_retries=3):
    FOR attempt IN 1..max_retries:
        TRY:
            result = EXECUTE(command)
            RETURN success(result)
        
        CATCH error:
            # Map Java exceptions to known types; extend over time (not all failures are classifiable initially)
            error_type = CLASSIFY_ERROR(error)
            
            CASE error_type OF
                "out_of_memory":
                    GARBAGE_COLLECT()
                    CLOSE_UNUSED_IMAGES()
                    RETRY
                
                "plugin_not_found":
                    suggestions = FIND_SIMILAR_PLUGINS(command)
                    RETURN error_with_suggestions(suggestions)
                
                "invalid_parameters":
                    params = GET_VALID_PARAMETERS(command)
                    RETURN error_with_param_spec(params)
                
                "gui_required":
                    # Cannot start GUI from headless JVM; inform user to restart with GUI mode
                    RETURN error("GUI required but server started headless; restart with gui mode")
                
                ELSE:
                    IF attempt < max_retries THEN
                        WAIT exponential_backoff(attempt)
                        RETRY
                    ELSE
                        RETURN failure(error)
    
    RETURN failure("Max retries exceeded")
```

---

### **9. Optimization Strategy**

```
FUNCTION optimize_performance():
    # Memory management
    EVERY 10 operations:
        unused_images = FIND_UNUSED_IMAGES()
        CLOSE(unused_images)
        GARBAGE_COLLECT()
    
    # Screenshot caching
    screenshot_cache = LRU_CACHE(max_size=5)
    BEFORE screenshot:
        hash = COMPUTE_SCREEN_HASH()
        IF hash IN screenshot_cache THEN
            RETURN cached_screenshot
    
    # Batch operations
    IF multiple_commands_pending THEN
        GROUP similar_operations
        EXECUTE in_batch
        RETURN batch_results
    
    # No lazy GUI: GUI must be chosen at startup; screenshot requests in headless mode return error.
```

---

### **10. Smart Command Search**

```
FUNCTION search_commands(query, context=None):
    # Fuzzy matching
    fuzzy_matches = FUZZY_SEARCH(query, all_commands)
    
    # Semantic grouping
    IF query.contains("blur") THEN
        BOOST filters_category
    IF query.contains("count") THEN
        BOOST measurement_category
    IF query.contains("segment") THEN
        BOOST segmentation_category
    
    # Context-aware ranking
    IF context.has_active_image THEN
        image_type = context.active_image.type
        BOOST commands_compatible_with(image_type)
    
    # Recent usage
    recent = GET_RECENT_COMMANDS()
    FOR command IN fuzzy_matches:
        IF command IN recent THEN
            BOOST command.score
    
    # Sort and filter
    results = SORT_BY_SCORE(fuzzy_matches)
    top_results = results[0:10]
    
    RETURN {
        exact_matches: [],
        fuzzy_matches: top_results,
        suggestions: GENERATE_ALTERNATIVES(query)
    }
```

---

## System Structure

```
PROJECT_STRUCTURE:
├── fiji_mcp_server/
│   ├── __init__.py
│   ├── server.py              # Main MCP server
│   ├── fiji_bridge.py         # PyImageJ initialization
│   ├── tools/
│   │   ├── macro_runner.py    # Macro execution
│   │   ├── screenshot.py      # Screenshot capture
│   │   ├── discovery.py       # Plugin discovery
│   │   └── workflow.py        # Workflow engine
│   ├── utils/
│   │   ├── command_search.py  # Search algorithm
│   │   ├── error_handler.py   # Error recovery
│   │   └── optimizer.py       # Performance optimization
│   └── config/
│       └── settings.py        # Configuration
│
├── tests/
│   ├── test_tools.py
│   └── test_workflows.py
│
├── docs/
│   ├── command_reference.md
│   └── workflow_examples.md
│
├── pyproject.toml
└── README.md
```

---

## Advantages Summary

### **vs NicoKiaru**
```
IMPROVEMENTS:
+ Visual feedback via screenshots
+ No custom JAR dependency
+ Auto-detection of Fiji
+ Workflow engine with verification
+ Better error recovery
+ Smart screenshot optimization
+ Dual-mode operation
+ Enhanced plugin discovery
= Same plugin access
= Same performance (JPype)
```

### **vs Your Two-Process Plan**
```
IMPROVEMENTS:
+ 10x faster (in-process vs socket)
+ Simpler architecture (1 process)
+ Python 3 only (no Jython)
+ Auto-start capability
+ Headless mode supported
+ Better error handling
+ Easier deployment
= Same screenshot capability
= Same visual feedback
```

---

## Key Algorithms Prioritized

```
PRIORITY 1 (Core):
1. PyImageJ initialization with auto-detection
2. Macro runner with error handling
3. Screenshot capture via Java Robot
4. Plugin discovery system

PRIORITY 2 (Enhanced UX):
5. Workflow engine with verification
6. Smart screenshot optimization
7. Command search with fuzzy matching
8. Dual-mode operation

PRIORITY 3 (Production):
9. Error recovery mechanisms
10. Performance optimization
11. Batch processing
12. Caching strategies
```

---

## Implementation Flow

```
PHASE 1: Foundation (Days 1-2)
    SETUP PyImageJ integration
    IMPLEMENT basic tools (run_macro, list_commands)
    IMPLEMENT screenshot capture
    TEST with simple workflows

PHASE 2: Discovery (Day 3)
    IMPLEMENT plugin discovery
    BUILD search index
    ADD command introspection
    TEST extension access

PHASE 3: Workflows (Day 4)
    IMPLEMENT workflow engine
    ADD verification steps
    BUILD error recovery
    TEST multi-step analysis

PHASE 4: Optimization (Day 5)
    OPTIMIZE screenshot performance
    ADD caching
    IMPLEMENT dual-mode
    FINALIZE documentation

PHASE 5: Testing (Day 6+)
    INTEGRATION testing
    PERFORMANCE benchmarks
    USER acceptance testing
    DEPLOYMENT preparation
```

**Where we are:** Phase 5 of this flow (see **Current progress** at the top of this file).

---

## Success Metrics

```
PERFORMANCE (targets; JVM call overhead and Fiji load can exceed these on some systems):
- Command latency: < 10ms (JPype call overhead; sub-ms not realistic)
- Screenshot latency: < 100ms
- Startup time: < 10s (full Fiji + plugins; < 5s on reference hardware)
- Memory usage: < 500MB base

FUNCTIONALITY:
- All extensions accessible: ✓
- Screenshot quality: > 720p
- Workflow success rate: > 95%
- Error recovery rate: > 80%

USABILITY:
- Setup steps: ≤ 2
- Config required: Minimal
- Learning curve: < 30 min
- Documentation quality: Complete
```

---

## Plan Maturity

### Well-defined
- **Architecture**: Single-process, PyImageJ; no ambiguity.
- **Core algorithms**: Discovery (CommandService + Menus), screenshot (Robot), workflow engine—all specified.
- **Error handling**: Incremental classification, retries, known types; unclassified failures pass through.
- **Performance targets**: Realistic (10 ms / 10 s); qualified for JVM and hardware.
- **Implementation phases**: 6-day flow with clear Phase 1–5 scope.
- **Caveats**: GUI requirements, mode selection, discovery order, introspection fallback—documented.

### Needs detail (resolve during implementation)

See **Implementation Watchlist** for the same items as a quick pre-phase scan.

| Item | Where to resolve | Note / default |
|------|------------------|----------------|
| **PyImageJ API calls** | Phase 1 (fiji_bridge.py, tools) | Exact `imagej.init()`, `ij.run()`, gateway usage will come from PyImageJ docs and trial; document findings in code and optionally in `docs/`. |
| **Java Robot screenshot** | Phase 1 (screenshot.py) | Straightforward; `java.awt.Robot.createScreenCapture(Rectangle)`; examples exist. Use primary screen first. |
| **CommandService vs Menus merge** | Phase 2 (discovery.py) | Merge by command identifier (e.g. class name or command name); deduplicate before building categories; prefer CommandService metadata when both exist. |
| **Multi-monitor** | Phase 1 or 4 (screenshot) | **Default**: primary screen only (`GraphicsEnvironment.getDefaultScreenDevice()`). Optional later: env/config flag for “all screens” or “screen index” if needed. |
| **Configuration** | Phase 1 (config/settings.py) | **Recommendation**: env vars for deployment (e.g. `FIJI_PATH`, `FIJI_MODE`); optional YAML/JSON file for power users; CLI args override. Document in README. |

---

## Caveats & Design Notes

- **Screenshots**: Require GUI mode and a **display** (physical monitor or Xvfb). Pure headless servers cannot capture screenshots.
- **GUI vs headless**: Chosen **at startup** only. Runtime switch from headless to GUI is not supported; "smart" mode means "pick GUI at start if screenshots/verification are likely."
- **Full Fiji plugins**: Initialize PyImageJ with the **Fiji app path** (e.g. `/Applications/Fiji.app`), not default ImageJ2-only, so all update-site plugins load.
- **Discovery**: Prefer **CommandService** (ImageJ2) for command list; use Menus and optional JAR scan as secondary.
- **Error classification**: Implement incrementally; not every Java exception will map to a known type initially.
- **Introspection fallback**: MacroRecorder is best-effort only (session state may not match the requested plugin). Many plugins will only have `basic_info` until a better fallback (macro template, docs, or plugin annotations) is added.
- **Auto-detect paths**: List is configurable; add OS-specific paths (e.g. Linux `/opt/Fiji.app`) as needed.

This design gives you **all advantages, minimal disadvantages, optimal performance**.