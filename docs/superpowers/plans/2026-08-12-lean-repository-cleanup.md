# Lean Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the repository to the maintained nine-tool Fiji MCP product, its essential documentation, and its distinct safety tests without changing runtime behavior.

**Architecture:** Preserve the flat `server.py` → `tools.py` → `bridge.py`/`imaging.py` runtime and exact nine-tool schemas. Simplify only proven duplicate command-catalog work, remove unused development tooling and redundant workflow-test mutations, explicitly constrain sdist contents, then delete vendor/local configuration and completed documentation archives behind repository-contract tests.

**Tech Stack:** Python 3.10+, FastMCP, PyImageJ, pytest, Ruff, mypy 1.x, setuptools, build, Twine.

## Global Constraints

- Do not change the exact nine public MCP names, schemas, outputs, annotations, or failure contracts.
- Do not change Fiji/JVM lifecycle, retries, operation serialization, mutation outcome rules, stdout containment, serialization/rendering bounds, or save semantics.
- Do not inspect, delete, stage, commit, push, or publish the root checkout's untracked `AGENTS.md`, `.agents/`, `.codex/`, `tests.md`, or other user-owned local files.
- Delete tracked `CLAUDE.md` and `.mcp.json`; ignore local equivalents afterward.
- Keep only `README.md`, `docs/tools.md`, `CHANGELOG.md`, `RELEASING.md`, and `LICENSE` as maintained documentation.
- Do not push, publish, release, or merge this cleanup branch.

---

### Task 1: Remove unused tooling and bound source-distribution contents

**Files:**
- Modify: `tests/test_package_exports.py`
- Modify: `pyproject.toml`
- Modify: `.pre-commit-config.yaml`
- Create: `MANIFEST.in`
- Delete: `.coveragerc`

**Interfaces:**
- Consumes: current optional-dependency groups and parsed publish workflow.
- Produces: minimal test/dev dependencies, active pytest markers only, deterministic sdist manifest, unchanged exact publish-workflow assertion.

- [ ] **Step 1: Add failing tooling and manifest contracts**

Add to `tests/test_package_exports.py`:

```python
def test_test_and_dev_tooling_are_minimal() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["optional-dependencies"]["test"] == [
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "pytest-timeout>=2.2.0",
        "PyYAML>=6.0.0",
        "tomli>=2.0.1; python_version < '3.11'",
    ]
    assert project["project"]["optional-dependencies"]["dev"] == [
        "ruff>=0.12.10",
        "mypy>=1.17.0,<2.0",
        "pre-commit>=4.3.0",
    ]
    assert project["tool"]["pytest"]["ini_options"]["markers"] == [
        "integration: integration tests requiring local Fiji runtime",
        "mcp_stdio: subprocess MCP client over stdio (FastMCP Client)",
    ]
    assert "black" not in project["tool"]
    assert not Path(".coveragerc").exists()


def test_source_distribution_manifest_is_minimal() -> None:
    assert Path("MANIFEST.in").read_text().splitlines() == [
        "include README.md",
        "include LICENSE",
        "include CHANGELOG.md",
        "include RELEASING.md",
        "include docs/tools.md",
        "prune tests",
        "prune docs/releases",
        "prune docs/superpowers",
        "exclude CLAUDE.md",
        "exclude .mcp.json",
        "exclude AGENTS.md",
        "exclude tests.md",
        "global-exclude __pycache__ *.py[cod] .DS_Store",
    ]
```

- [ ] **Step 2: Run RED**

Run:

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python   -m pytest tests/test_package_exports.py   -k 'test_and_dev_tooling_are_minimal or source_distribution_manifest_is_minimal' -v
```

Expected: two failures because unused tooling remains and `MANIFEST.in` is absent.

- [ ] **Step 3: Remove redundant workflow mutation tests**

Delete `import copy`, `import pytest`, and these four tests (no remaining test in
this file uses either module):

```text
test_publish_workflow_rejects_duplicate_artifact_upload
test_publish_workflow_rejects_extra_privileged_action
test_publish_workflow_rejects_extra_install_command
test_publish_workflow_rejects_an_extra_trigger
```

Keep the canonical exact workflow equality assertion unchanged.

- [ ] **Step 4: Minimize declared tooling**

Make the optional groups exactly:

```toml
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-timeout>=2.2.0",
    "PyYAML>=6.0.0",
    "tomli>=2.0.1; python_version < '3.11'",
]
dev = [
    "ruff>=0.12.10",
    "mypy>=1.17.0,<2.0",
    "pre-commit>=4.3.0",
]
```

Remove `--cov-config=.coveragerc`, markers `slow`, `unit`, and `smoke`, the complete `[tool.black]` section, and `.coveragerc`.

- [ ] **Step 5: Remove the non-enforcing pre-commit hook**

Delete the complete `repo: local` block. Retain file-format, Ruff, Ruff-format, and mypy hooks.

- [ ] **Step 6: Create the exact sdist manifest**

Create `MANIFEST.in`:

```text
include README.md
include LICENSE
include CHANGELOG.md
include RELEASING.md
include docs/tools.md
prune tests
prune docs/releases
prune docs/superpowers
exclude CLAUDE.md
exclude .mcp.json
exclude AGENTS.md
exclude tests.md
global-exclude __pycache__ *.py[cod] .DS_Store
```

- [ ] **Step 7: Reinstall and verify GREEN**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m pip install -e '.[test,dev,publish]'
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m pytest tests/test_package_exports.py -v
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m mypy src/fiji_mcp --ignore-missing-imports
```

Expected: tests pass and mypy reports no issues using a resolved 1.x release.

- [ ] **Step 8: Commit**

```bash
git add .coveragerc .pre-commit-config.yaml MANIFEST.in pyproject.toml tests/test_package_exports.py
git commit -m "refactor: remove unused repository tooling"
```

---

### Task 2: Remove redundant command-catalog processing

**Files:**
- Modify: `tests/test_commands.py`
- Modify: `src/fiji_mcp/tools.py`

**Interfaces:**
- Consumes: `_collect_commands(ij) -> list[dict[str, Any]]`, already sorted and deduplicated.
- Produces: unchanged `search_commands()` and `run_command()` with one deduplication pass.

- [ ] **Step 1: Add failing caller-boundary regressions**

Add near the existing search/run-command tests:

```python
def test_search_consumes_the_collector_catalog_without_rededuplicating(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(
        minimal,
        "_deduplicate_commands",
        lambda _commands: pytest.fail("collector output was deduplicated twice"),
    )
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))

    assert minimal.search_commands("Blur")["returned"] == 1


def test_run_command_consumes_the_collector_catalog_without_rededuplicating(
    monkeypatch,
):
    catalog = [{
        "name": "Invert",
        "class_name": "ij.plugin.filter.Filters",
        "menu_path": "Edit > Invert",
        "family": "imagej1",
        "inputs": [],
        "invocation_route": "legacy_options",
        "_legacy_descriptor": 'ij.plugin.filter.Filters("invert")',
    }]
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: catalog)
    monkeypatch.setattr(
        minimal,
        "_deduplicate_commands",
        lambda _commands: pytest.fail("collector output was deduplicated twice"),
    )
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda _name, prepare, _dispatch: prepare(object()),
    )

    prepared = minimal.run_command("Invert")
    assert prepared[0] is catalog[0]
```

- [ ] **Step 2: Run RED**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python   -m pytest tests/test_commands.py -k 'without_rededuplicating' -v
```

Expected: both fail with `collector output was deduplicated twice`.

- [ ] **Step 3: Remove both redundant calls**

In `search_commands`, use:

```python
catalog = _collect_commands(ij)
```

In `run_command.prepare`, use:

```python
command = _resolve_command(_collect_commands(ij), target)
```

- [ ] **Step 4: Run GREEN**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m pytest tests/test_commands.py -v
```

Expected: all command tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/fiji_mcp/tools.py tests/test_commands.py
git commit -m "refactor: avoid duplicate command deduplication"
```

---

### Task 3: Enforce the lean tracked repository and verify artifacts

**Files:**
- Modify: `tests/test_package_exports.py`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `RELEASING.md`
- Delete: `CLAUDE.md`
- Delete: `.mcp.json`
- Delete: `docs/releases/`
- Delete: `docs/superpowers/`

**Interfaces:**
- Consumes: approved maintained-document list and Task 1 `MANIFEST.in`.
- Produces: no tracked/packaged local agent rules, local MCP config, or completed archives.

- [ ] **Step 1: Add failing repository-surface contract**

Add:

```python
def test_repository_surface_is_lean_and_local_rules_are_ignored() -> None:
    for required in (
        "README.md", "docs/tools.md", "CHANGELOG.md", "RELEASING.md", "LICENSE"
    ):
        assert Path(required).is_file()

    for removed in (
        "CLAUDE.md", ".mcp.json", "docs/releases", "docs/superpowers"
    ):
        assert not Path(removed).exists()

    ignored = set(Path(".gitignore").read_text().splitlines())
    assert {
        "AGENTS.md", ".agents/", ".codex/", "CLAUDE.md", ".mcp.json",
        "tests.md", ".coverage", ".coverage.*",
    } <= ignored

    readme = Path("README.md").read_text()
    releasing = Path("RELEASING.md").read_text()
    assert "docs/releases" not in readme
    assert "docs/releases" not in releasing
```

- [ ] **Step 2: Run RED**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python   -m pytest tests/test_package_exports.py -k repository_surface_is_lean -v
```

Expected: fail because the tracked files/archive directories still exist.

- [ ] **Step 3: Update local-only ignores**

Keep `.cursor/`, environment, cache, build, and worktree ignores. Add the eight exact entries asserted by the test. Remove `research_output/` and `demo_output/mcp_live*` entries and obsolete script comments.

- [ ] **Step 4: Remove obsolete maintained-document links**

Replace the README's combined history bullet with only the changelog link. Delete the optional `docs/releases/` step from `RELEASING.md` and renumber the preparation list.

- [ ] **Step 5: Delete approved tracked surfaces**

Delete exactly:

```text
CLAUDE.md
.mcp.json
docs/releases/
docs/superpowers/
```

Do not operate on similarly named untracked files in the root checkout.

- [ ] **Step 6: Verify repository GREEN**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m pytest tests/test_package_exports.py -v
git grep -nE 'docs/releases|docs/superpowers|CLAUDE\.md|\.mcp\.json' -- README.md RELEASING.md docs/tools.md pyproject.toml .github || true
```

Expected: tests pass and the maintained-reference scan is empty.

- [ ] **Step 7: Run source gates**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m pytest -m 'not integration' -v
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m ruff check src/ tests/
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m ruff format --check src/ tests/
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m mypy src/fiji_mcp --ignore-missing-imports
```

Expected: zero failures/errors; Ruff and mypy clean.

- [ ] **Step 8: Build and inspect distributions**

```bash
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m build
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python -m twine check dist/*
tar -tzf dist/fiji_mcp_server-0.2.0.tar.gz
/Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python   tests/wheel_smoke.py dist/fiji_mcp_server-0.2.0-py3-none-any.whl
```

Expected: package docs and runtime code are present; no `tests/`, local agent rules/config, or completed archive is present; Twine and the exact nine-tool wheel probe pass.

- [ ] **Step 9: Run live Fiji integration**

```bash
FIJI_PATH=/Applications/Fiji FIJI_MODE=headless   /Users/suraj/Documents/Tools/Fiji_imageJ_mcp/.venv/bin/python   -m pytest -m integration -v --timeout=300
```

Expected: all direct and stdio Fiji integration cases pass.

- [ ] **Step 10: Audit, commit, and review**

```bash
git diff --check
git status --short --untracked-files=all
git ls-files | rg '(^|/)(AGENTS\.md|CLAUDE\.md|\.mcp\.json|\.agents|\.codex)(/|$)' && exit 1 || true
git add -A -- .gitignore README.md RELEASING.md CLAUDE.md .mcp.json docs tests/test_package_exports.py
git commit -m "refactor: remove stale repository surfaces"
```

Then request an independent read-only review of the full branch. Address confirmed findings test-first and repeat affected gates. Do not push, publish, merge, or release.
