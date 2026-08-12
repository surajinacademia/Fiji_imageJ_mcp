# Lean Repository Cleanup Design

Date: 2026-08-12
Status: Approved in conversation

## Goal

Make the v0.2 repository match its actual product: one minimal, trusted-local
Fiji MCP server with exactly nine tools. Remove vendor-specific agent guidance,
local MCP configuration, completed planning archives, redundant tooling, and
proven duplicate code/tests without weakening runtime or release safeguards.

This cleanup is local only. It must not push, publish, or stage user-owned local
agent/configuration files.

## Frozen invariants

- The public MCP surface remains exactly `get_state`, `search_commands`,
  `run_command`, `run_script`, `open_image`, `save_image`, `get_results`,
  `screenshot`, and `compare_screenshots` with unchanged schemas.
- Fiji/JVM lifecycle, serialized operations, retry boundaries, mutation outcome
  classification, Java stdout containment, and bundled-JVM selection remain
  unchanged.
- Bounded serialization, image decoding, Results rendering, comparison metrics,
  exact save-path rules, and native MCP image responses remain unchanged.
- The PyPI OIDC isolation workflow, exact release triggers, built-wheel smoke
  probe, and Python 3.10–3.12 CI matrix remain protected.
- Existing untracked `AGENTS.md`, `.agents/`, `.codex/`, `tests.md`, and other
  local files are neither read into the product nor deleted, staged, pushed, or
  published.

## Maintained repository surface

Keep the maintained user/release documentation:

- `README.md`
- `docs/tools.md`
- `CHANGELOG.md`
- `RELEASING.md`
- `LICENSE`

Delete the active vendor/local configuration and completed archives:

- `CLAUDE.md`
- `.mcp.json`
- `docs/releases/`
- the pre-existing `docs/superpowers/` specifications and plans

The cleanup specification and implementation plan are committed for the
design/implementation workflow, then removed with the completed
`docs/superpowers/` archive as part of the final cleanup. Their commits retain
the audit trail without leaving internal plans in the released tree.

Update README and release-guide links so no maintained document points to a
deleted path. Keep accurate past-tense version history in `CHANGELOG.md`; a
historical mention of a former client is not an active agent instruction.

## Local-only security boundary

Add ignore rules for:

- `AGENTS.md`
- `.agents/`
- `.codex/`
- `CLAUDE.md`
- `.mcp.json`
- `tests.md`
- `.coverage` and `.coverage.*`

Keep the general `.cursor/`, virtual-environment, cache, build, and worktree
ignores. Remove obsolete ignore comments and paths that refer only to deleted
demo/report scripts.

## Runtime simplification

`_collect_commands()` already returns a deduplicated, sorted catalog. Remove the
second `_deduplicate_commands()` call in each of its two public callers and use
the collected catalog directly. Do not otherwise restructure `tools.py`,
`bridge.py`, or `imaging.py`: their apparent verbosity protects independent
Fiji, error, memory, and protocol boundaries.

## Test simplification

Keep the in-process MCP schema tests, source stdio tests, installed-wheel smoke
probe, live-Fiji tests, and detailed bridge/command/serialization/rendering
tests because each exercises a distinct boundary.

Remove four mutation-only publish-workflow tests. The canonical workflow test
already compares the complete parsed workflow against one exact expected
structure, so an extra trigger, privileged action, install command, or artifact
upload fails that assertion without four copied synthetic workflows. Remove the
now-unused `copy` import.

Add repository-contract assertions before deletion so the test suite proves:

- local agent/config paths are ignored and not tracked;
- only the maintained documentation set remains;
- removed optional dependencies/configuration do not return;
- the source distribution excludes tests, local agent rules, local MCP config,
  and completed planning archives while retaining required package docs.

## Tooling and packaging simplification

Remove unused test/development dependencies and their configuration:

- `pytest-mock`
- `pytest-cov` and `.coveragerc`
- `black` and `[tool.black]` (Ruff is the formatter)
- `bandit` (not invoked by CI or pre-commit)

Remove unused pytest markers `slow`, `unit`, and `smoke`. Keep `integration` and
`mcp_stdio`, which are actively used. Keep pytest-asyncio, pytest-timeout,
PyYAML, the Python-3.10 `tomli` fallback, Ruff, mypy, pre-commit, build, and
Twine.

Constrain the mypy development dependency to the validated 1.x series because
fresh resolution of mypy 2.3 fails against current NumPy stubs under the
project's Python 3.10 type target; the pre-commit hook already uses mypy 1.17.

Remove the local pre-commit pytest hook because `|| true` makes it incapable of
rejecting a bad commit. Retain the real Ruff, Ruff-format, mypy, and file-format
hooks, with CI as the authoritative test gate.

Configure source-distribution contents explicitly. The sdist should contain the
runtime package, typing marker, README, license, changelog, release guide, and
tool reference. It should not ship unit/integration tests, local agent rules,
local MCP configuration, or internal completed plans.

## Verification

Before behavior edits, retain the 200-test non-integration baseline. Use
test-first repository-contract changes to capture the desired file/dependency
and artifact boundary, observe their expected failures, then apply deletions.

Final gates:

1. Repository-contract tests.
2. Command tests proving catalog behavior after redundant dedup removal.
3. Full non-integration pytest suite.
4. Ruff check and format check.
5. Mypy with the clean declared development environment.
6. Build sdist and wheel; inspect sdist members; run Twine check.
7. Install the wheel in a fresh environment and verify exactly nine stdio tools.
8. Run live Fiji integration because runtime source changed, even though the
   change is intended to be behavior-neutral.
9. Scan tracked files and built artifacts for forbidden local agent/config
   paths and stale documentation links.
10. Independent read-only review of the final diff.

The cleanup ends on its isolated branch. It is not pushed, published, or merged
without a separate explicit user instruction.
