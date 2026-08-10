# Minimal Fiji MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current 19-tool Fiji MCP framework with a reliable nine-tool, script-first stdio server that controls one PyImageJ/Fiji runtime.

**Architecture:** Build the new runtime and handlers beside the legacy implementation so every preparatory task remains independently testable. After the bridge, tool behavior, and imaging code are complete, perform one controlled MCP registration cutover, then delete obsolete orchestration, schemas, installers, scripts, and documentation.

**Tech Stack:** Python 3.10+, FastMCP 2.x, PyImageJ 1.5+, SciJava/JPype, Pillow, NumPy, pytest, Ruff, mypy.

## Global Constraints

### Frozen invariants

- The approved specification is `docs/superpowers/specs/2026-08-10-minimal-fiji-mcp-design.md`.
- The public MCP surface is exactly: `get_state`, `search_commands`, `run_command`, `run_script`, `open_image`, `save_image`, `get_results`, `screenshot`, and `compare_screenshots`.
- `FIJI_PATH` is required when a tool first initializes Fiji; it must contain `jars/` and `plugins/`.
- `FIJI_MODE` accepts only `headless` or `gui` and defaults to `headless`.
- The only direct runtime dependencies are FastMCP, PyImageJ, Pillow, and NumPy.
- Tool handlers are synchronous. One process-wide lock remains owned by a dispatched Java worker even if its MCP request is cancelled.
- Mutating Java calls execute once. Only positively allowlisted read failures receive one retry.
- `imagej.init` and a failed or stopped JVM are never retried in-process.
- Python logging and ordinary Java `System.out` output go to `stderr`; stdio stdout is reserved for MCP JSON-RPC.
- `run_script` is trusted arbitrary local IJM/Groovy execution. Do not add a partial path sandbox that scripts can bypass.
- No workflow engine, batch API, templates, trace, plugin installation, screenshot cache, client installer, compatibility alias, or server-side scientific interpretation.

### Required workflow and outputs

- The agent can inspect live Fiji state, discover installed commands, run a command or IJM/Groovy script, open/save an image, read ordered Results rows, render active-image/Results PNGs, and compare two saved screenshots.
- The normal path is `inspect/open -> optionally capture before -> discover/execute -> inspect/results -> optionally capture after/compare -> save`; the agent sequences these calls and the server stores no workflow state.
- Headless behavior is the default. GUI mode is an explicit override, and GUI-only plugins may fail with an actionable scripting/GUI explanation.
- All public dictionaries, rows, command/script outputs, image content, errors, and screenshot metrics follow the approved specification; the simplification is allowed to break every legacy public surface explicitly listed for removal.

### Delivery discipline

- Use test-driven development for every behavior change. Run the named failing test before implementation and the named passing test afterward.
- Do not stage or modify the user's unrelated untracked `.agents/`, `.codex/`, `.coverage`, `AGENTS.md`, or `tests.md` paths.

## Final file map

| Path | Responsibility |
|---|---|
| `src/fiji_mcp/__init__.py` | Package version and lazy `mcp` export |
| `src/fiji_mcp/__main__.py` | stderr logging and stdio entry point |
| `src/fiji_mcp/server.py` | FastMCP construction and exactly nine registrations |
| `src/fiji_mcp/tools.py` | Thin public handlers and Fiji state/command/result access |
| `src/fiji_mcp/bridge.py` | Configuration, JVM lifecycle, stdout routing, locking, retries, errors, bounded Java serialization |
| `src/fiji_mcp/imaging.py` | Headless rendering, PNG encoding, and path-based screenshot comparison |
| `src/fiji_mcp/py.typed` | Typing marker |
| `tests/test_bridge.py` | Lifecycle, error, retry, lock, and cancellation semantics |
| `tests/test_serialization.py` | Bounded JSON conversion of Python/Java-like values |
| `tests/test_tools_core.py` | State, image I/O, and Results table contracts |
| `tests/test_commands.py` | Discovery, resolution, command invocation, and scripts |
| `tests/test_imaging.py` | Deterministic rendering and comparison behavior |
| `tests/test_mcp_contract.py` | Exact nine-tool FastMCP surface and schemas |
| `tests/test_mcp_stdio_client.py` | Real stdio protocol and stdout-containment tests |
| `tests/test_integration_runtime.py` | Direct local-Fiji end-to-end behavior |
| `tests/test_package_exports.py` | Lazy import and minimal packaging metadata |
| `tests/conftest.py` | Shared integration availability helpers and markers |
| `tests/wheel_smoke.py` | Clean-environment wheel install and console-entry smoke probe |
| `README.md` | Complete install, configuration, security, and usage guide |
| `docs/tools.md` | Concise nine-tool reference |

---

### Task 1: Add the isolated runtime bridge

**Files:**
- Create: `src/fiji_mcp/bridge.py`
- Create: `tests/test_bridge.py`

**Interfaces:**
- Produces: `Settings`, `Lifecycle`, `Outcome`, `FijiError`, `load_settings()`, `get_settings()`, `get_ij()`, `runtime_snapshot()`, `run_read()`, `run_mutation()`, and `_reset_runtime_for_tests()`.
- Consumes: only Python standard library, `imagej`, and `scyjava`; it must not import legacy `fiji_mcp.config` or `fiji_mcp.utils`.

- [ ] **Step 1: Write failing settings and lifecycle tests**

Create `tests/test_bridge.py` with focused tests equivalent to:

```python
from __future__ import annotations

import asyncio
import errno
import threading
from pathlib import Path

import pytest

from fiji_mcp import bridge


def _fiji_root(tmp_path: Path) -> Path:
    (tmp_path / "jars").mkdir()
    (tmp_path / "plugins").mkdir()
    return tmp_path


def test_settings_require_real_fiji_root(monkeypatch, tmp_path):
    monkeypatch.setenv("FIJI_PATH", str(tmp_path))
    monkeypatch.delenv("FIJI_MODE", raising=False)
    with pytest.raises(bridge.FijiError, match="jars/.*plugins/"):
        bridge.load_settings()


def test_settings_are_only_path_and_mode(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    monkeypatch.setenv("FIJI_PATH", str(root))
    monkeypatch.setenv("FIJI_MODE", "gui")
    assert bridge.load_settings() == bridge.Settings(root.resolve(), "gui")


def test_invalid_mode_is_rejected(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    monkeypatch.setenv("FIJI_PATH", str(root))
    monkeypatch.setenv("FIJI_MODE", "smart")
    with pytest.raises(bridge.FijiError, match="headless or gui"):
        bridge.load_settings()


def test_path_validation_retries_one_eintr_before_jvm_start(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    monkeypatch.setenv("FIJI_PATH", str(root))
    original = bridge._resolve_and_validate_root
    attempts = 0

    def interrupted_once(raw_path):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError(errno.EINTR, "interrupted")
        return original(raw_path)

    monkeypatch.setattr(bridge, "_resolve_and_validate_root", interrupted_once)
    assert bridge.load_settings().fiji_path == root.resolve()
    assert attempts == 2


def test_non_eintr_path_failure_is_not_retried(monkeypatch, tmp_path):
    monkeypatch.setenv("FIJI_PATH", str(tmp_path))
    attempts = 0

    def denied(_raw_path):
        nonlocal attempts
        attempts += 1
        raise OSError(errno.EACCES, "denied")

    monkeypatch.setattr(bridge, "_resolve_and_validate_root", denied)
    with pytest.raises(bridge.FijiError, match="validate FIJI_PATH"):
        bridge.load_settings()
    assert attempts == 1


def test_configuration_error_does_not_poison_unstarted_runtime(monkeypatch, tmp_path):
    monkeypatch.delenv("FIJI_PATH", raising=False)
    bridge._reset_runtime_for_tests()
    with pytest.raises(bridge.FijiError, match="FIJI_PATH is required"):
        bridge.get_ij()
    assert bridge.runtime_snapshot()["lifecycle"] == "NEW"

    root = _fiji_root(tmp_path)
    monkeypatch.setenv("FIJI_PATH", str(root))
    gateway = object()
    monkeypatch.setattr(bridge, "_start_fiji", lambda _settings: gateway)
    assert bridge.get_ij() is gateway


def test_failed_jvm_start_is_terminal(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    monkeypatch.setenv("FIJI_PATH", str(root))
    bridge._reset_runtime_for_tests()
    monkeypatch.setattr(bridge, "_start_fiji", lambda settings: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(bridge.FijiError, match="restart the MCP server"):
        bridge.get_ij()
    assert bridge.runtime_snapshot()["lifecycle"] == "FAILED"
    with pytest.raises(bridge.FijiError, match="restart the MCP server"):
        bridge.get_ij()


def test_java_stdout_redirect_targets_system_err(monkeypatch):
    import scyjava as sj

    class FakeSystem:
        err = object()
        received = None

        @classmethod
        def setOut(cls, stream):
            cls.received = stream

    monkeypatch.setattr(sj, "jimport", lambda name: FakeSystem)
    bridge._redirect_java_stdout()
    assert FakeSystem.received is FakeSystem.err


def test_read_retries_only_allowlisted_failure(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    attempts = 0

    def interrupted(_ij):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError(errno.EINTR, "interrupted")
        return 42

    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    assert bridge.run_read("state", interrupted) == 42
    assert attempts == 2


def test_exact_java_concurrent_modification_type_retries_once(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    concurrent_error = type(
        "ConcurrentModificationException",
        (Exception,),
        {"__module__": "java.util"},
    )
    attempts = 0

    def concurrent_once(_ij):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise concurrent_error()
        return 42

    assert bridge.run_read("state", concurrent_once) == 42
    assert attempts == 2


def test_exact_headless_exception_gets_gui_recovery(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    headless_error = type(
        "HeadlessException",
        (Exception,),
        {"__module__": "java.awt"},
    )
    with pytest.raises(bridge.FijiError) as raised:
        bridge.run_read(
            "screenshot",
            lambda _ij: (_ for _ in ()).throw(headless_error()),
        )
    assert raised.value.code == "gui_required"
    assert "FIJI_MODE=gui" in raised.value.recovery


def test_unknown_read_failure_is_not_retried(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    attempts = 0

    def fail(_ij):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("message mentions java.util.ConcurrentModificationException")

    with pytest.raises(bridge.FijiError) as raised:
        bridge.run_read("state", fail)
    assert attempts == 1
    assert raised.value.code == "java_bridge_failure"


def test_dead_jvm_disables_retry_and_requires_restart(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: False)
    with pytest.raises(bridge.FijiError, match="restart the MCP server"):
        bridge.run_read(
            "state",
            lambda _ij: (_ for _ in ()).throw(InterruptedError("interrupted")),
        )
    assert bridge.runtime_snapshot()["lifecycle"] == "FAILED"


def test_pre_dispatch_failure_is_definitely_failed(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    dispatched = False

    def prepare(_ij):
        raise RuntimeError("could not resolve command")

    def dispatch(_ij, _prepared):
        nonlocal dispatched
        dispatched = True

    with pytest.raises(bridge.FijiError) as raised:
        bridge.run_mutation("command", prepare, dispatch)
    assert raised.value.outcome is bridge.Outcome.FAILED
    assert dispatched is False


def test_allowlisted_pre_dispatch_read_retries_before_one_dispatch(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    prepare_attempts = 0
    dispatch_attempts = 0

    def prepare(_ij):
        nonlocal prepare_attempts
        prepare_attempts += 1
        if prepare_attempts == 1:
            raise OSError(errno.EINTR, "interrupted")
        return "resolved"

    def dispatch(_ij, prepared):
        nonlocal dispatch_attempts
        dispatch_attempts += 1
        return prepared

    assert bridge.run_mutation("command", prepare, dispatch) == "resolved"
    assert prepare_attempts == 2
    assert dispatch_attempts == 1


def test_dispatched_mutation_is_never_retried_and_outcome_is_unknown(monkeypatch):
    bridge._reset_runtime_for_tests(ready_ij=object())
    monkeypatch.setattr(bridge, "_jvm_is_healthy", lambda _ij: True)
    attempts = 0

    def fail(_ij, _prepared):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("bridge vanished")

    with pytest.raises(bridge.FijiError) as raised:
        bridge.run_mutation("script", lambda _ij: None, fail)
    assert attempts == 1
    assert raised.value.code == "unknown_outcome"
    assert raised.value.outcome is bridge.Outcome.UNKNOWN


def test_worker_holds_operation_lock_until_java_returns():
    bridge._reset_runtime_for_tests(ready_ij=object())
    entered = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()

    def first(_ij, _prepared):
        entered.set()
        release.wait(timeout=2)

    def second(_ij):
        second_entered.set()

    first_thread = threading.Thread(
        target=lambda: bridge.run_mutation("script", lambda _ij: None, first)
    )
    second_thread = threading.Thread(target=lambda: bridge.run_read("state", second))
    first_thread.start()
    assert entered.wait(timeout=1)
    second_thread.start()
    assert not second_entered.wait(timeout=0.05)
    release.set()
    first_thread.join(timeout=1)
    second_thread.join(timeout=1)
    assert second_entered.is_set()


@pytest.mark.asyncio
async def test_cancelled_delivery_does_not_release_running_worker_lock():
    bridge._reset_runtime_for_tests(ready_ij=object())
    entered = threading.Event()
    release = threading.Event()
    second_entered = threading.Event()

    def first(_ij, _prepared):
        entered.set()
        release.wait(timeout=2)

    first_delivery = asyncio.create_task(
        asyncio.to_thread(
            bridge.run_mutation,
            "script",
            lambda _ij: None,
            first,
        )
    )
    assert await asyncio.to_thread(entered.wait, 1)
    first_delivery.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_delivery

    second_delivery = asyncio.create_task(
        asyncio.to_thread(
            bridge.run_read,
            "state",
            lambda _ij: second_entered.set(),
        )
    )
    assert not await asyncio.to_thread(second_entered.wait, 0.05)
    release.set()
    await second_delivery
    assert second_entered.is_set()
```

- [ ] **Step 2: Run the new tests and confirm the missing module failure**

Run: `pytest tests/test_bridge.py -v`

Expected: collection fails with `ImportError` because `fiji_mcp.bridge` does not exist.

- [ ] **Step 3: Implement the runtime state machine and execution wrappers**

Create `src/fiji_mcp/bridge.py` with these concrete structures and behaviors:

```python
from __future__ import annotations

import errno
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar

P = TypeVar("P")
T = TypeVar("T")


class Lifecycle(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    FAILED = "FAILED"


class Outcome(str, Enum):
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Settings:
    fiji_path: Path
    mode: Literal["headless", "gui"]


class FijiError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool, outcome: Outcome, recovery: str):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.outcome = outcome
        self.recovery = recovery
        super().__init__(
            f"[{code}] {message} retryable={str(retryable).lower()} "
            f"outcome={outcome.value}. Next: {recovery}"
        )


_OPERATION_LOCK = threading.RLock()
_LIFECYCLE = Lifecycle.NEW
_IJ: Any | None = None
_SETTINGS: Settings | None = None


def _is_eintr(error: BaseException) -> bool:
    return isinstance(error, InterruptedError) or (
        isinstance(error, OSError) and error.errno == errno.EINTR
    )


def _resolve_and_validate_root(raw_path: str) -> Path:
    root = Path(raw_path).expanduser().resolve()
    if not (root / "jars").is_dir() or not (root / "plugins").is_dir():
        raise FijiError(
            "invalid_configuration",
            f"{root} must contain jars/ and plugins/.",
            retryable=False,
            outcome=Outcome.FAILED,
            recovery="Point FIJI_PATH at the Fiji root.",
        )
    return root


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    raw_path = env.get("FIJI_PATH", "").strip()
    if not raw_path:
        raise FijiError("invalid_configuration", "FIJI_PATH is required.", retryable=False,
                        outcome=Outcome.FAILED, recovery="Set FIJI_PATH to the Fiji root and retry.")
    root: Path | None = None
    for attempt in range(2):
        try:
            root = _resolve_and_validate_root(raw_path)
            break
        except FijiError:
            raise
        except OSError as error:
            if attempt == 0 and _is_eintr(error):
                continue
            raise FijiError(
                "invalid_configuration",
                f"Could not validate FIJI_PATH: {error}",
                retryable=False,
                outcome=Outcome.FAILED,
                recovery="Check FIJI_PATH permissions and retry.",
            ) from error
    assert root is not None
    mode = env.get("FIJI_MODE", "headless").strip().lower()
    if mode not in {"headless", "gui"}:
        raise FijiError("invalid_configuration", "FIJI_MODE must be headless or gui.", retryable=False,
                        outcome=Outcome.FAILED, recovery="Set FIJI_MODE=headless or FIJI_MODE=gui.")
    return Settings(root, mode)  # type: ignore[arg-type]


def _redirect_java_stdout() -> None:
    import scyjava as sj
    system = sj.jimport("java.lang.System")
    system.setOut(system.err)


def _start_fiji(settings: Settings) -> Any:
    import scyjava as sj
    sj.when_jvm_starts(_redirect_java_stdout)
    import imagej
    mode = "headless" if settings.mode == "headless" else "interactive"
    return imagej.init(str(settings.fiji_path), mode=mode)


def get_ij() -> Any:
    global _IJ, _LIFECYCLE, _SETTINGS
    with _OPERATION_LOCK:
        if _LIFECYCLE is Lifecycle.READY:
            assert _IJ is not None
            return _IJ
        if _LIFECYCLE is Lifecycle.FAILED:
            raise FijiError("jvm_failed", "The Fiji JVM is not reusable.", retryable=False,
                            outcome=Outcome.FAILED, recovery="Restart the MCP server.")
        # Invalid configuration occurs before STARTING and remains fixable in-process.
        settings = load_settings()
        _LIFECYCLE = Lifecycle.STARTING
        try:
            _IJ = _start_fiji(settings)
        except Exception as error:
            _LIFECYCLE = Lifecycle.FAILED
            raise FijiError("jvm_start_failed", str(error), retryable=False,
                            outcome=Outcome.FAILED, recovery="Fix the reported cause and restart the MCP server.") from error
        _SETTINGS = settings
        _LIFECYCLE = Lifecycle.READY
        return _IJ


def _exception_type_name(error: BaseException) -> str:
    error_type = type(error)
    qualified_type = f"{error_type.__module__}.{error_type.__name__}"
    java_type = str(getattr(error, "__javaclass__", ""))
    return java_type or qualified_type


def _is_allowlisted_read_retry(error: BaseException) -> bool:
    return _is_eintr(error) or (
        _exception_type_name(error) == "java.util.ConcurrentModificationException"
    )


def _jvm_is_healthy(ij: Any) -> bool:
    try:
        import scyjava as sj
        return bool(sj.jvm_started()) and bool(ij.getVersion())
    except Exception:
        return False


def _mark_jvm_failed() -> None:
    global _LIFECYCLE
    _LIFECYCLE = Lifecycle.FAILED


def _dead_jvm_error(outcome: Outcome) -> FijiError:
    return FijiError(
        "jvm_failed",
        "The Fiji JVM stopped or failed and is not reusable.",
        retryable=False,
        outcome=outcome,
        recovery="Restart the MCP server.",
    )


def _translate(error: BaseException, operation: str, outcome: Outcome) -> FijiError:
    if isinstance(error, FijiError):
        return error
    if _exception_type_name(error) == "java.awt.HeadlessException":
        return FijiError(
            "gui_required",
            f"{operation} requires a Fiji GUI.",
            retryable=False,
            outcome=outcome,
            recovery="Use a scripted/headless route or restart with FIJI_MODE=gui.",
        )
    if outcome is Outcome.UNKNOWN:
        return FijiError(
            "unknown_outcome",
            f"{operation} may have completed before the bridge failed: {error}",
            retryable=False,
            outcome=outcome,
            recovery="Inspect get_state or screenshot before deciding whether to repeat it.",
        )
    return FijiError(
        "java_bridge_failure",
        f"{operation}: {error}",
        retryable=False,
        outcome=outcome,
        recovery="Retry explicitly only if state inspection shows it is safe, or restart the server.",
    )


def _run_read_phase(operation: str, ij: Any, function: Callable[[Any], T]) -> T:
    try:
        return function(ij)
    except FijiError:
        raise
    except Exception as first:
        if _LIFECYCLE is not Lifecycle.READY or not _jvm_is_healthy(ij):
            _mark_jvm_failed()
            raise _dead_jvm_error(Outcome.FAILED) from first
        if not _is_allowlisted_read_retry(first):
            raise _translate(first, operation, Outcome.FAILED) from first
        try:
            return function(ij)
        except Exception as second:
            if not _jvm_is_healthy(ij):
                _mark_jvm_failed()
                raise _dead_jvm_error(Outcome.FAILED) from second
            raise _translate(second, operation, Outcome.FAILED) from second


def run_read(operation: str, function: Callable[[Any], T]) -> T:
    with _OPERATION_LOCK:
        return _run_read_phase(operation, get_ij(), function)


def run_mutation(
    operation: str,
    prepare: Callable[[Any], P],
    dispatch: Callable[[Any, P], T],
) -> T:
    with _OPERATION_LOCK:
        ij = get_ij()
        try:
            prepared = _run_read_phase(f"{operation}.prepare", ij, prepare)
        except FijiError:
            raise
        try:
            return dispatch(ij, prepared)
        except FijiError:
            raise
        except Exception as error:
            if not _jvm_is_healthy(ij):
                _mark_jvm_failed()
                raise _dead_jvm_error(Outcome.UNKNOWN) from error
            raise _translate(error, operation, Outcome.UNKNOWN) from error


def get_settings() -> Settings:
    get_ij()
    assert _SETTINGS is not None
    return _SETTINGS


def runtime_snapshot() -> dict[str, Any]:
    return {"lifecycle": _LIFECYCLE.value, "path": str(_SETTINGS.fiji_path) if _SETTINGS else None,
            "mode": _SETTINGS.mode if _SETTINGS else None}


def _reset_runtime_for_tests(*, ready_ij: Any | None = None) -> None:
    global _IJ, _LIFECYCLE, _SETTINGS
    _IJ = ready_ij
    _LIFECYCLE = Lifecycle.READY if ready_ij is not None else Lifecycle.NEW
    _SETTINGS = None
```

Keep the implementation synchronous. Do not use an executor timeout or release `_OPERATION_LOCK` from cancellation handling.

The two callbacks of `run_mutation` are the dispatch-phase boundary: `prepare` may inspect live Fiji state and resolve a command but may not perform the requested scientific action; `dispatch` flips the operation into the possibly-completed phase immediately before its first mutating Java call. A failure in `prepare` has `Outcome.FAILED`; an unclassified failure in `dispatch` has `Outcome.UNKNOWN`. Keep exact error codes for invalid configuration, missing file, no active image, command not found, invalid parameters, unsupported language, GUI-required behavior, Java bridge failure, and unknown post-dispatch outcome. Recognize Java failures by exception class, never by searching an arbitrary message.

- [ ] **Step 4: Run the bridge tests**

Run: `pytest tests/test_bridge.py -v`

Expected: all bridge tests pass; pre-dispatch failure is definite, dispatched failure is attempted once with `Outcome.UNKNOWN`, dead JVM state is terminal, and cancelled delivery leaves the Java worker holding the lock.

- [ ] **Step 5: Commit the isolated bridge**

```bash
git add src/fiji_mcp/bridge.py tests/test_bridge.py
git commit -m "refactor: add minimal Fiji runtime bridge"
```

---

### Task 2: Add bounded Java-result serialization

**Files:**
- Modify: `src/fiji_mcp/bridge.py`
- Create: `tests/test_serialization.py`

**Interfaces:**
- Consumes: `FijiError`, `Outcome` from Task 1.
- Produces: `to_jsonable(value: Any) -> Any` and `image_summary(image: Any) -> dict[str, Any]`.

- [ ] **Step 1: Write failing serializer tests**

```python
from __future__ import annotations

import json
import math

from fiji_mcp.bridge import to_jsonable


def test_non_finite_numbers_are_standard_json_values():
    assert to_jsonable([math.nan, math.inf, -math.inf]) == ["NaN", "Infinity", "-Infinity"]


def test_non_string_map_keys_use_ordered_entries():
    result = to_jsonable({1: "one", "1": "string one"})
    assert result == {"map_entries": [{"key": 1, "value": "one"}, {"key": "1", "value": "string one"}]}


def test_cycles_are_bounded():
    value = []
    value.append(value)
    assert to_jsonable(value) == [{"cycle": True}]


def test_collections_and_strings_are_truncated():
    result = to_jsonable({"items": list(range(101)), "text": "x" * 4001})
    assert len(result["items"]) == 101
    assert result["items"][-1] == {"truncated_items": 1}
    assert result["text"].endswith("…")


def test_oversized_payload_falls_back_to_summary():
    result = to_jsonable({str(i): "x" * 4000 for i in range(100)})
    assert result["truncated"] is True
    assert result["reason"] == "serialized result exceeds 64 KiB"
    assert len(json.dumps(result).encode("utf-8")) <= 65_536


def test_maximum_depth_is_explicit():
    result = to_jsonable([[[[["too deep"]]]]])
    assert result[0][0][0][0] == {
        "truncated": True,
        "reason": "maximum depth reached",
    }
```

Also add thin Java-like fakes with only the named methods and assert these exact cases:

- `entrySet()` yielding `getKey()`/`getValue()` pairs becomes a JSON object when every key is a string and `map_entries` when any key is not a string.
- `iterator()` yielding 101 items becomes 100 converted values plus `{"truncated_items": 1}`.
- An ImagePlus-like object and a Dataset-like object become `image_summary` dictionaries without pixel arrays.
- A ResultsTable-like object becomes a row/column-count summary rather than embedded rows.
- An unknown Java-like object whose `getClass().getName()` is `example.PluginResult` and whose string form is `plugin-result` returns `{"java_type": "example.PluginResult", "summary": "plugin-result"}`; a separate 4,001-character string-form case proves the summary cap.
- Java boxed booleans/numbers/strings become their JSON primitive equivalents, not generic object summaries.

- [ ] **Step 2: Verify the tests fail because `to_jsonable` is absent**

Run: `pytest tests/test_serialization.py -v`

Expected: import fails for `to_jsonable`.

- [ ] **Step 3: Implement explicit recursive conversion**

Add constants `_MAX_DEPTH = 4`, `_MAX_ITEMS = 100`, `_MAX_STRING = 4_000`, and `_MAX_JSON_BYTES = 65_536`. Implement a private recursive converter that:

```python
def _convert(value: Any, *, depth: int, seen: set[int]) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, str):
        return value if len(value) <= _MAX_STRING else value[: _MAX_STRING - 1] + "…"
    if depth >= _MAX_DEPTH:
        return {"truncated": True, "reason": "maximum depth reached"}
    identity = id(value)
    if identity in seen:
        return {"cycle": True}
    seen.add(identity)
    try:
        if isinstance(value, dict):
            items = list(value.items())
            if all(isinstance(key, str) for key, _ in items):
                converted = {key: _convert(item, depth=depth + 1, seen=seen) for key, item in items[:_MAX_ITEMS]}
                if len(items) > _MAX_ITEMS:
                    converted["__truncated_items__"] = len(items) - _MAX_ITEMS
                return converted
            entries = [{"key": _convert(key, depth=depth + 1, seen=seen),
                        "value": _convert(item, depth=depth + 1, seen=seen)}
                       for key, item in items[:_MAX_ITEMS]]
            if len(items) > _MAX_ITEMS:
                entries.append({"truncated_items": len(items) - _MAX_ITEMS})
            return {"map_entries": entries}
        if isinstance(value, (list, tuple, set)):
            items = list(value)
            converted = [_convert(item, depth=depth + 1, seen=seen) for item in items[:_MAX_ITEMS]]
            if len(items) > _MAX_ITEMS:
                converted.append({"truncated_items": len(items) - _MAX_ITEMS})
            return converted
        java_type = type(value).__name__
        return {"java_type": java_type, "summary": str(value)[:_MAX_STRING]}
    finally:
        seen.discard(identity)


def to_jsonable(value: Any) -> Any:
    converted = _convert(value, depth=0, seen=set())
    if len(json.dumps(converted, ensure_ascii=False).encode("utf-8")) <= _MAX_JSON_BYTES:
        return converted
    return {"truncated": True, "reason": "serialized result exceeds 64 KiB",
            "java_type": type(value).__name__, "summary": str(value)[:_MAX_STRING]}
```

Before the generic Java fallback, recognize Java primitives, Java `Map` through `entrySet`, Java `Collection` through `iterator`, ImageJ `ImagePlus`/`Dataset` by dimension methods, and Results tables by row/column methods. Convert Java maps using the same string-key versus `map_entries` rule. Preserve list/tuple order; sort Python sets by a stable string key before conversion. Resolve Java type names with `value.getClass().getName()` when available and fall back to the qualified Python proxy type. `image_summary` must return title, width, height, channels, slices, frames, and bit depth without pixel data.

- [ ] **Step 4: Run serializer and bridge tests**

Run: `pytest tests/test_serialization.py tests/test_bridge.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit serialization**

```bash
git add src/fiji_mcp/bridge.py tests/test_serialization.py
git commit -m "feat: bound Fiji tool result serialization"
```

---

### Task 3: Implement state, image I/O, and Results primitives beside the old API

**Files:**
- Create: `src/fiji_mcp/_minimal_tools.py`
- Create: `tests/test_tools_core.py`

**Interfaces:**
- Consumes: `get_settings`, `image_summary`, `run_read`, `run_mutation`, and `FijiError` from `bridge.py`.
- Produces: `get_state()`, `open_image(path)`, `save_image(path)`, `get_results(offset, limit)`, plus private `_read_results(ij, offset, limit)` used later by screenshot rendering.

- [ ] **Step 1: Write failing handler tests with a fake Fiji boundary**

Tests must monkeypatch `_minimal_tools.run_read` and `run_mutation`, not rebuild a second application state. Cover:

```python
def test_get_results_preserves_heading_and_row_order(monkeypatch):
    fake = FakeResultsTable(
        headings=["Area", "", "Area"],
        rows=[
            [1.5, None, float("nan")],
            [2.5, "cell", float("inf")],
            [3.5, "tail", float("-inf")],
        ],
    )
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    result = minimal.get_results(offset=0, limit=500)
    assert result["columns"] == ["Area", "", "Area"]
    assert result["rows"] == [
        [1.5, None, "NaN"],
        [2.5, "cell", "Infinity"],
        [3.5, "tail", "-Infinity"],
    ]
    assert result["offset"] == 0
    assert result["returned"] == 3
    assert result["total_rows"] == 3


def test_get_results_returns_a_partial_nonzero_page(monkeypatch):
    fake = FakeResultsTable(headings=["Area"], rows=[[1], [2], [3]])
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    result = minimal.get_results(offset=2, limit=2)
    assert result == {
        "columns": ["Area"],
        "rows": [[3]],
        "offset": 2,
        "returned": 1,
        "total_rows": 3,
    }


def test_get_results_empty_table_keeps_headings(monkeypatch):
    fake = FakeResultsTable(headings=["Area"], rows=[])
    monkeypatch.setattr(minimal, "_results_table", lambda _ij: fake)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    assert minimal.get_results() == {
        "columns": ["Area"],
        "rows": [],
        "offset": 0,
        "returned": 0,
        "total_rows": 0,
    }


def test_get_results_validates_page_before_java(monkeypatch):
    called = False
    monkeypatch.setattr(minimal, "run_read", lambda *_args: (_ for _ in ()).throw(AssertionError("called")))
    with pytest.raises(FijiError, match="limit must be between 1 and 5000"):
        minimal.get_results(limit=0)


def test_open_image_dispatches_once_and_returns_metadata(monkeypatch, tmp_path):
    path = tmp_path / "cells.tif"
    path.write_bytes(b"fixture")
    image = FakeImage(title="cells.tif", width=32, height=16)
    fake_ij = FakeIJ(opened=image)
    monkeypatch.setattr(minimal, "get_settings", lambda: Settings(tmp_path, "headless"))
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda _name, prepare, dispatch: dispatch(fake_ij, prepare(fake_ij)),
    )
    result = minimal.open_image(str(path))
    assert result["path"] == str(path.resolve())
    assert result["image"]["width"] == 32
    assert fake_ij.open_count == 1


def test_save_image_infers_format_from_suffix(monkeypatch, tmp_path):
    output = tmp_path / "result.png"
    fake_ij = FakeIJ(active=FakeImage("active", 4, 4))
    monkeypatch.setattr(
        minimal,
        "run_mutation",
        lambda _name, prepare, dispatch: dispatch(fake_ij, prepare(fake_ij)),
    )
    result = minimal.save_image(str(output))
    assert result["format"] == "png"
    assert fake_ij.saved_path == str(output.resolve())


def test_get_state_reports_complete_live_shape(monkeypatch):
    active = FakeImage("temporary", 32, 16, channels=2, slices=3, frames=4, bit_depth=16)
    listed = FakeImage("listed", 8, 6)
    fake_ij = FakeIJ(
        version="2.16.0/1.54p",
        active=active,
        open_images=[listed],
        results=FakeResultsTable(headings=["Area", "Mean"], rows=[[1, 2]]),
    )
    monkeypatch.setattr(minimal, "get_settings", lambda: Settings(Path("/fiji"), "headless"))
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(fake_ij))
    result = minimal.get_state()
    assert result["version"] == "2.16.0/1.54p"
    assert result["mode"] == "headless"
    assert result["active_image"]["title"] == "temporary"
    assert [image["title"] for image in result["open_images"]] == ["listed", "temporary"]
    assert result["results"] == {"columns": ["Area", "Mean"], "total_rows": 1}
```

Import `Settings` from `fiji_mcp.bridge`. The local `FakeImage`, `FakeResultsTable`, and `FakeIJ` classes should implement only methods exercised by the handler under test. Add deterministic failures for a nonexistent open path, no active image, an extensionless save path, negative offset, and limits 0 and 5,001; assert these fail before the dispatch callback. Separately assert that `IJ.openImage` returning null is called exactly once and produces a definite `missing_file`/unreadable-image failure rather than an automatic retry.

- [ ] **Step 2: Run the core handler tests and confirm import failure**

Run: `pytest tests/test_tools_core.py -v`

Expected: import fails because `_minimal_tools.py` does not exist.

- [ ] **Step 3: Implement the four core handlers**

Implement the exact signatures `get_state() -> dict[str, Any]`, `open_image(path: str) -> dict[str, Any]`, `save_image(path: str) -> dict[str, Any]`, and `get_results(offset: int = 0, limit: int = 500) -> dict[str, Any]`.

Use these concrete rules:

- `get_state` reads `ij.getVersion()`, `ij.WindowManager.getCurrentImage()`, `getIDList()`, and the live Results table in one `run_read` call. Include an active temp image in the summary even when headless `getIDList()` is empty.
- `get_state` returns exactly `lifecycle`, `version`, `mode`, `active_image`, `open_images`, and `results`; `results` contains `columns` and `total_rows`. Deduplicate the active image by ImageJ ID when it is already in the window list and append an unlisted headless temp image once.
- `open_image` resolves and checks the input file before `run_mutation`; its dispatch callback calls `ij.IJ.openImage` exactly once, then uses `WindowManager.setTempCurrentImage` in headless mode or `image.show()` in GUI mode.
- `save_image` uses the prepare callback to require an active image and a filename suffix, creates parents immediately before dispatch, calls the extension-inferring ImageJ `IJ.save(image, path)` overload exactly once, and returns the normalized suffix without a leading dot.
- `_read_results` obtains original headings by ImageJ column index. It returns `columns`, paged `rows` arrays, `offset`, `returned`, and `total_rows`. Missing cells are `None`; finite values remain numbers; NaN and infinities use the approved strings.
- Validate `offset >= 0` and `1 <= limit <= 5_000` before acquiring Fiji.
- Raise `FijiError` with `Outcome.FAILED` for missing files, missing active image, empty/invalid paths, and invalid pagination so the mutation wrapper does not change these deterministic failures to unknown.

- [ ] **Step 4: Run the new core tests plus bridge tests**

Run: `pytest tests/test_tools_core.py tests/test_bridge.py tests/test_serialization.py -v`

Expected: all tests pass while the legacy MCP server remains unchanged.

- [ ] **Step 5: Commit the core handlers**

```bash
git add src/fiji_mcp/_minimal_tools.py tests/test_tools_core.py
git commit -m "feat: add minimal Fiji state and image tools"
```

---

### Task 4: Add command discovery, invocation, and scripts

**Files:**
- Modify: `src/fiji_mcp/_minimal_tools.py`
- Create: `tests/test_commands.py`

**Interfaces:**
- Consumes: Task 3 handlers and Task 1/2 bridge APIs.
- Produces: `search_commands(query, limit)`, `run_command(name, parameters, options)`, and `run_script(language, code)`.

- [ ] **Step 1: Write failing discovery and execution tests**

Include these cases:

```python
def test_search_allows_empty_query_and_caps_limit(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    assert len(minimal.search_commands("", limit=2)["commands"]) == 2
    with pytest.raises(FijiError, match="between 1 and 100"):
        minimal.search_commands("", limit=101)


def test_discovery_reports_the_invocation_route(monkeypatch):
    monkeypatch.setattr(minimal, "_collect_commands", lambda _ij: COMMANDS)
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(object()))
    commands = minimal.search_commands("Blur")["commands"]
    assert commands[0]["invocation_route"] == "structured_parameters"


def test_scijava_record_wins_duplicate_delegate():
    merged = minimal._deduplicate_commands([
        {"name": "Blur", "class_name": "pkg.Blur", "family": "imagej1", "inputs": []},
        {"name": "Blur", "class_name": "pkg.Blur", "family": "scijava", "inputs": [{"name": "sigma"}]},
    ])
    assert merged == [{"name": "Blur", "class_name": "pkg.Blur", "family": "scijava", "inputs": [{"name": "sigma"}]}]


def test_resolution_prefers_class_then_exact_display_name():
    assert minimal._resolve_command(COMMANDS, "pkg.Blur")["class_name"] == "pkg.Blur"
    assert minimal._resolve_command(COMMANDS, "Blur")["name"] == "Blur"


def test_ambiguous_case_insensitive_name_lists_classes():
    with pytest.raises(FijiError, match="pkg.One.*pkg.Two"):
        minimal._resolve_command([
            {"name": "Measure", "class_name": "pkg.One", "family": "scijava"},
            {"name": "MEASURE", "class_name": "pkg.Two", "family": "scijava"},
        ], "measure")


def test_run_command_rejects_parameters_and_options_together():
    with pytest.raises(FijiError, match="mutually exclusive"):
        minimal.run_command("Blur", {"sigma": 2}, "sigma=2")


def test_run_command_rejects_input_for_the_wrong_route():
    with pytest.raises(FijiError, match="legacy options string.*run_script"):
        minimal._validate_route_inputs(
            {"name": "Legacy", "family": "imagej1"},
            parameters={"sigma": 2},
            options=None,
        )
    with pytest.raises(FijiError, match="structured parameters.*run_script"):
        minimal._validate_route_inputs(
            {"name": "Modern", "family": "scijava"},
            parameters=None,
            options="sigma=2",
        )
    with pytest.raises(FijiError, match="script fallback.*run_script"):
        minimal._validate_route_inputs(
            {
                "name": "Complex",
                "family": "scijava",
                "invocation_route": "script_fallback",
            },
            parameters=None,
            options=None,
        )


@pytest.mark.parametrize("language", ["python", "javascript", ""])
def test_run_script_accepts_only_ijm_and_groovy(language):
    with pytest.raises(FijiError, match="ijm or groovy"):
        minimal.run_script(language, "return 1")
```

Add fake SciJava command info/service and legacy IJ objects to assert that a SciJava command receives one Java parameter map and awaits one future, a legacy command receives one options string, IJM calls `ij.py.run_macro`, and Groovy calls `ij.py.run_script("groovy", code)`. Assert serialized outputs/results, the final 4,000 log characters, and active-image metadata. Add deterministic `command_not_found`, ambiguous-command, invalid-parameter, unsupported-language, and GUI-required failures with the approved retry/outcome/recovery fields.

- [ ] **Step 2: Run the command tests and confirm missing functions**

Run: `pytest tests/test_commands.py -v`

Expected: failures identify absent command/script functions.

- [ ] **Step 3: Implement discovery and execution**

Implement the exact signatures `search_commands(query: str, limit: int = 20) -> dict[str, Any]`, `run_command(name: str, parameters: dict[str, Any] | None = None, options: str | None = None) -> dict[str, Any]`, and `run_script(language: Literal["ijm", "groovy"], code: str) -> dict[str, Any]`. The `query` argument is required even though the supplied string may be empty.

Implementation requirements:

- `_collect_commands` merges SciJava `CommandService.getCommands()` and `ij.Menus.getCommands()`.
- SciJava entries include display name, delegate class, menu path, family, `invocation_route="structured_parameters"`, and available input name/type/required/description metadata. ImageJ1 entries use `invocation_route="legacy_options"`; if metadata proves neither route is safe, use `invocation_route="script_fallback"`.
- Deduplicate by non-empty delegate class, preferring SciJava. Retain distinct legacy entries without class metadata.
- Search case-insensitively across name, class, and menu path; empty query returns the deterministically sorted catalog.
- `_resolve_command` uses exact class, exact case-sensitive display name, then unique case-insensitive display name. Ambiguity is a deterministic `FijiError` containing candidate classes.
- Use the `run_mutation` prepare callback for registry collection, resolution, and route validation. Reject `parameters` for ImageJ1 and reject `options` for SciJava with an actionable correct-route/`run_script` message; reject every `script_fallback` record before dispatch and instruct the caller to use `run_script`. Never silently discard caller input.
- For SciJava, build `input_map = ij.py.to_java(parameters or {})`, call `service.run(command_info, True, input_map)` exactly once so JPype selects the `CommandInfo, boolean, Map` overload, wait on the returned future with `.get()`, and serialize `CommandModule.getOutputs()`.
- For ImageJ1, call `ij.IJ.run(display_name, options or "")` exactly once.
- Validate name/code/language before `run_mutation`. Do not retry either execution path.
- IJM uses `ij.py.run_macro(code)` and Groovy uses `ij.py.run_script("groovy", code)`.
- Return search records as `{"query", "returned", "total", "commands"}`. Return command `outputs` or script `result` through `to_jsonable`, read `ij.IJ.getLog()` for `log_tail` limited to its final 4,000 characters, and include post-execution `active_image` metadata.

- [ ] **Step 4: Run all new unit tests**

Run: `pytest tests/test_bridge.py tests/test_serialization.py tests/test_tools_core.py tests/test_commands.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit command and script access**

```bash
git add src/fiji_mcp/_minimal_tools.py tests/test_commands.py
git commit -m "feat: expose Fiji commands and scripts"
```

---

### Task 5: Add deterministic screenshots and comparison

**Files:**
- Create: `src/fiji_mcp/imaging.py`
- Modify: `src/fiji_mcp/_minimal_tools.py`
- Create: `tests/test_imaging.py`

**Interfaces:**
- Produces: `RenderedPNG`, `render_active_image(ij)`, `render_results(columns, rows, total_rows)`, `compare_paths(before, after)`, `screenshot(target, save_path)`, and `compare_screenshots(before_path, after_path, save_path)`.
- Consumes: `_read_results`, `run_read`, `FijiError`, and `Outcome`.

- [ ] **Step 1: Write failing pure-image tests**

```python
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from fiji_mcp.imaging import compare_paths, fit_within, render_results


def test_fit_within_never_enlarges():
    assert fit_within(Image.new("RGB", (10, 20)), 2048).size == (10, 20)
    assert fit_within(Image.new("RGB", (4096, 2048)), 2048).size == (2048, 1024)


def test_results_render_is_deterministic_and_marks_omissions():
    first = render_results(["Area", "Mean"], [[1, 2]] * 101, total_rows=101)
    second = render_results(["Area", "Mean"], [[1, 2]] * 101, total_rows=101)
    assert first.png == second.png
    assert first.metadata["rendered_rows"] == 100
    assert first.metadata["omitted_rows"] == 1


def test_equal_images_return_zero_metrics_and_three_panels(tmp_path):
    path = tmp_path / "same.png"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(path)
    result = compare_paths(path, path)
    assert result.metadata["mae"] == 0.0
    assert result.metadata["rmse"] == 0.0
    assert result.metadata["changed_pixel_fraction"] == 0.0
    assert result.metadata["panels"] == ["before", "after", "absolute_difference"]


def test_one_level_change_counts_as_changed(tmp_path):
    before = np.zeros((2, 2, 3), dtype=np.uint8)
    after = before.copy()
    after[0, 0, 0] = 1
    Image.fromarray(before).save(tmp_path / "before.png")
    Image.fromarray(after).save(tmp_path / "after.png")
    result = compare_paths(tmp_path / "before.png", tmp_path / "after.png")
    assert result.metadata["mae"] == pytest.approx(1 / (2 * 2 * 3 * 255))
    assert result.metadata["rmse"] == pytest.approx(np.sqrt(1 / 12) / 255)
    assert result.metadata["changed_pixel_fraction"] == 0.25


def test_different_sizes_omit_metrics_and_difference_panel(tmp_path):
    Image.new("RGB", (8, 6)).save(tmp_path / "before.png")
    Image.new("RGB", (9, 6)).save(tmp_path / "after.png")
    result = compare_paths(tmp_path / "before.png", tmp_path / "after.png")
    assert result.metadata["dimensions_match"] is False
    assert "mae" not in result.metadata
    assert "rmse" not in result.metadata
    assert "changed_pixel_fraction" not in result.metadata
    assert result.metadata["panels"] == ["before", "after"]
```

Add a fake `ImagePlus` test proving `render_active_image` calls `flatten()` on a nonmutating current-plane view and reports current C/Z/T plus overlay/ROI presence. Add handler tests that decode returned MCP image bytes and assert:

- `screenshot("active_image")` and `screenshot("results")` produce PNG content with neither dimension above 2,048.
- Results rendering reads the first 100 live rows in original column order and records the exact omitted-row count.
- A supplied `save_path` contains bytes identical to the returned MCP image; parent directories are created.
- `compare_screenshots` uses only its two paths, does not initialize Fiji, and saves bytes identical to its returned comparison image.
- Invalid targets, missing paths, unreadable files, and non-images produce deterministic `FijiError` values before any image metrics are computed.

- [ ] **Step 2: Run the imaging tests and confirm import failure**

Run: `pytest tests/test_imaging.py -v`

Expected: import fails because `fiji_mcp.imaging` does not exist.

- [ ] **Step 3: Implement PNG rendering and comparison**

Create:

```python
@dataclass(frozen=True)
class RenderedPNG:
    png: bytes
    width: int
    height: int
    metadata: dict[str, Any]
```

Implement these exact rules:

- `fit_within` copies and thumbnails to a maximum dimension of 2,048 without enlargement.
- Convert Java `BufferedImage` to PNG through `javax.imageio.ImageIO` and `java.io.ByteArrayOutputStream`.
- `render_active_image` duplicates/flattens only the current C/Z/T plane so the current LUT/display range, visible overlay, and ROI are represented without window chrome.
- `render_results` uses `ImageFont.load_default()`, a white background, black monospace text, original columns, at most 100 rows, and an explicit omitted-row line. Encode PNG deterministically.
- `compare_paths` opens both paths as RGB. Equal dimensions use NumPy float arrays divided by 255; calculate MAE, RMSE, and the fraction of pixels with any channel difference greater than zero. Produce labeled before/after/difference panels.
- Different dimensions produce labeled before/after panels and omit all three metric keys plus the difference panel; never crop or resample for metrics.
- Reject missing, unreadable, or non-image paths with deterministic `FijiError`.

Add handlers with the exact signatures `screenshot(target: Literal["active_image", "results"], save_path: str | None = None) -> ToolResult` and `compare_screenshots(before_path: str, after_path: str, save_path: str | None = None) -> ToolResult`. The screenshot target is required.

Each handler returns `fastmcp.tools.tool.ToolResult(content=[Image(data=rendered.png, format="png").to_image_content()], structured_content=metadata)`. When `save_path` is supplied, create parents, save exactly `rendered.png`, and add the resolved path to structured metadata. Screenshot uses `run_read`; comparison does not initialize Fiji.

- [ ] **Step 4: Run new implementation tests**

Run: `pytest tests/test_imaging.py tests/test_tools_core.py tests/test_commands.py tests/test_bridge.py tests/test_serialization.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit imaging**

```bash
git add src/fiji_mcp/imaging.py src/fiji_mcp/_minimal_tools.py tests/test_imaging.py
git commit -m "feat: add deterministic Fiji screenshots"
```

---

### Task 6: Cut the MCP server over to exactly nine tools

**Files:**
- Delete: `src/fiji_mcp/tools/__init__.py`
- Delete: `src/fiji_mcp/tools/discovery.py`
- Delete: `src/fiji_mcp/tools/macro_runner.py`
- Delete: `src/fiji_mcp/tools/screenshot.py`
- Delete: `src/fiji_mcp/tools/structured_tools.py`
- Delete: `src/fiji_mcp/tools/workflow.py`
- Rename: `src/fiji_mcp/_minimal_tools.py` to `src/fiji_mcp/tools.py`
- Rewrite: `src/fiji_mcp/server.py`
- Rewrite: `src/fiji_mcp/__main__.py`
- Delete: `src/fiji_mcp/mcp_instance.py`
- Create: `tests/test_mcp_contract.py`
- Modify: `tests/test_package_exports.py`
- Modify: `tests/test_mcp_stdio_client.py`
- Delete: `tests/test_discovery.py`
- Delete: `tests/test_macro_runner_batch.py`
- Delete: `tests/test_screenshot_phase4.py`
- Delete: `tests/test_workflow.py`

**Interfaces:**
- Consumes: all nine handlers completed in Tasks 3–5.
- Produces: `fiji_mcp.server.mcp`, the only FastMCP instance and registration point.

- [ ] **Step 1: Replace the old list-tools expectation with an exact contract test**

```python
from fastmcp import Client

from fiji_mcp.server import mcp


EXPECTED = {
    "get_state", "search_commands", "run_command", "run_script",
    "open_image", "save_image", "get_results", "screenshot",
    "compare_screenshots",
}

EXPECTED_INPUTS = {
    "get_state": (set(), set()),
    "search_commands": ({"query", "limit"}, {"query"}),
    "run_command": ({"name", "parameters", "options"}, {"name"}),
    "run_script": ({"language", "code"}, {"language", "code"}),
    "open_image": ({"path"}, {"path"}),
    "save_image": ({"path"}, {"path"}),
    "get_results": ({"offset", "limit"}, set()),
    "screenshot": ({"target", "save_path"}, {"target"}),
    "compare_screenshots": (
        {"before_path", "after_path", "save_path"},
        {"before_path", "after_path"},
    ),
}


async def test_exact_public_tool_surface():
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == EXPECTED


async def test_schema_defaults_and_limits_are_visible():
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert tools["search_commands"].inputSchema["properties"]["limit"]["default"] == 20
    assert tools["get_results"].inputSchema["properties"]["limit"]["default"] == 500
    assert set(tools["run_script"].inputSchema["properties"]["language"]["enum"]) == {"ijm", "groovy"}
    for name, (properties, required) in EXPECTED_INPUTS.items():
        schema = tools[name].inputSchema
        assert set(schema["properties"]) == properties
        assert set(schema.get("required", [])) == required
        assert tools[name].description
```

Update the non-integration stdio list-tools test to assert equality with `EXPECTED`; it must not set `FIJI_PATH`, proving registration remains lazy. Give `StdioTransport` a `tmp_path / "stderr.log"` log file, have `__main__.py` emit one `Starting Fiji MCP stdio server` diagnostic through Python logging, and assert both that the message reached the stderr log and that `tools/list` still parsed. This is the no-Fiji stdout-containment test.

- [ ] **Step 2: Run the contract test against the legacy server**

Run: `pytest tests/test_mcp_contract.py -v`

Expected: failure showing the 19 legacy tools rather than the exact nine names.

- [ ] **Step 3: Replace registration and entry-point code**

After deleting the old `tools/` package, rename `_minimal_tools.py` to `tools.py`. Rewrite `server.py` with one FastMCP instance and explicit registration:

```python
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from fiji_mcp import __version__
from fiji_mcp.tools import (
    compare_screenshots, get_results, get_state, open_image, run_command,
    run_script, save_image, screenshot, search_commands,
)

mcp = FastMCP(
    "Fiji MCP Server",
    version=__version__,
    instructions=(
        "Control one local Fiji instance. Use search_commands and run_command for registered "
        "plugins; use run_script for IJM/Groovy fallback. This trusted local server can execute "
        "arbitrary scripts. Fiji operations run sequentially."
    ),
)

READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True)
CHANGE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)

for function, annotations in (
    (get_state, READ), (search_commands, READ), (run_command, DESTRUCTIVE),
    (run_script, DESTRUCTIVE), (open_image, CHANGE), (save_image, DESTRUCTIVE),
    (get_results, READ), (screenshot, DESTRUCTIVE),
    (compare_screenshots, DESTRUCTIVE),
):
    mcp.tool(annotations=annotations, output_schema=None)(function)

__all__ = ["mcp"]
```

Keep `fiji_mcp.__getattr__("mcp")` lazy. Rewrite `__main__.py` to configure standard Python logging to `stderr`, emit the tested startup diagnostic, import `mcp`, and call `mcp.run()` without validating `FIJI_PATH` during `tools/list`.

- [ ] **Step 4: Remove tests that assert deleted tools and run the new contract**

Run: `pytest tests/test_mcp_contract.py tests/test_package_exports.py tests/test_mcp_stdio_client.py -m "not integration" -v`

Expected: the in-process and stdio clients each report exactly nine tools; no Fiji installation is required.

- [ ] **Step 5: Run every new non-integration test**

Run: `pytest tests/test_bridge.py tests/test_serialization.py tests/test_tools_core.py tests/test_commands.py tests/test_imaging.py tests/test_mcp_contract.py tests/test_package_exports.py tests/test_mcp_stdio_client.py -m "not integration" -v`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the breaking API cutover**

```bash
git add -A -- src/fiji_mcp tests/test_mcp_contract.py tests/test_package_exports.py tests/test_mcp_stdio_client.py tests/test_discovery.py tests/test_macro_runner_batch.py tests/test_screenshot_phase4.py tests/test_workflow.py
git commit -m "refactor: cut Fiji MCP to nine tools"
```

---

### Task 7: Prove real Fiji and stdio behavior

**Files:**
- Rewrite: `tests/test_integration_runtime.py`
- Modify: `tests/test_mcp_stdio_client.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: final public MCP names and local `FIJI_PATH`.
- Produces: direct and black-box integration coverage for all nine tools, including Java stdout containment.

- [ ] **Step 1: Write the direct end-to-end integration test**

Use `demo_images/sample_gradient.pgm` unless `FIJI_TEST_IMAGE` is set. In one headless session:

```python
@pytest.mark.integration
def test_minimal_fiji_end_to_end(tmp_path):
    image_path = _integration_image()
    state = tools.get_state()
    assert state["lifecycle"] == "READY"

    opened = tools.open_image(str(image_path))
    assert opened["image"]["width"] > 0

    before = tmp_path / "before.png"
    tools.screenshot("active_image", str(before))
    found_add = tools.search_commands("net.imagej.plugins.commands.assign.AddToDataValues")
    assert found_add["commands"][0]["invocation_route"] == "structured_parameters"
    tools.run_command(
        "net.imagej.plugins.commands.assign.AddToDataValues",
        parameters={"value": 1.5},
    )
    tools.run_script("ijm", 'run("Invert");')
    groovy = tools.run_script("groovy", '#@output Integer answer\nanswer = 6 * 7')
    assert groovy["result"]["answer"] == 42

    found = tools.search_commands("measure")
    assert found["commands"]
    tools.run_command("Measure", options="")
    assert tools.get_results()["total_rows"] >= 1
    results_path = tmp_path / "results.png"
    results_shot = tools.screenshot("results", str(results_path))
    assert results_shot.structured_content["rendered_rows"] >= 1
    assert results_path.is_file()

    after = tmp_path / "after.png"
    tools.screenshot("active_image", str(after))
    compared = tools.compare_screenshots(str(before), str(after))
    assert compared.structured_content["dimensions_match"] is True
    assert compared.structured_content["changed_pixel_fraction"] > 0

    saved = tools.save_image(str(tmp_path / "result.tif"))
    assert Path(saved["path"]).is_file()
```

Add `test_active_image_screenshot_preserves_plane_lut_overlay_and_source`. Through `run_script("groovy", code)`, construct a 16x16, 2C x 2Z x 2T byte hyperstack whose eight planes have distinct constant values; select C2/Z2/T2, set its display range, apply a red LUT, attach a filled green overlay ROI, and set a blue active ROI. Capture `screenshot("active_image")`, base64-decode `result.content[0].data`, and assert a background pixel is red-dominant, an overlay-interior pixel is green-dominant, and an active-ROI outline pixel is blue-dominant. Before and after capture, record all eight processors' raw `(0, 0)` values, current C/Z/T, display range, LUT RGB-table bytes, overlay size, and active ROI bounds; assert every source value/state item is unchanged. This real synthetic fixture complements the fake method-interaction test and proves the rendered pixels come from the selected plane with its display state.

Add four `@pytest.mark.integration` lifecycle probes that each run in a fresh Python subprocess and emit a final JSON assertion record:

1. `test_pre_start_eintr_probe_is_two_attempts` monkeypatches `_resolve_and_validate_root` to raise `OSError(errno.EINTR, "interrupted")` once, then delegates to the real validator; assert two attempts, lifecycle `NEW`, and no `_start_fiji` call.
2. `test_startup_failure_probe_is_terminal` points to the real Fiji root, replaces `_start_fiji` with a counter that raises `RuntimeError("injected startup failure")`, calls `get_ij()` twice, and asserts one start attempt plus lifecycle `FAILED` and restart recovery on both errors.
3. `test_ready_read_retry_probe_uses_live_health_gate` starts real Fiji, makes a `run_read` callback raise EINTR once then return `ij.getVersion()`, and asserts two callback attempts and lifecycle `READY`.
4. `test_post_dispatch_probe_is_once_and_unknown` opens the fixture in real Fiji, calls `run_mutation` with a prepare callback returning the current image and a dispatch callback that runs `ij.IJ.run(image, "Invert", "")` once before raising `RuntimeError("injected bridge loss")`; assert one dispatch, `Outcome.UNKNOWN`, error code `unknown_outcome`, changed pixels, and no automatic second inversion.

Implement one `_run_probe(source: str, fiji_path: Path) -> dict[str, Any]` test helper. Build `probe_env` from `os.environ` plus the repository `src` on `PYTHONPATH`, the supplied `FIJI_PATH`, and `FIJI_MODE=headless`; then call `subprocess.run([sys.executable, "-c", source], check=True, capture_output=True, text=True, env=probe_env)`. These disposable processes are required because a failed/stopped JPype JVM cannot safely be reused by the pytest process.

- [ ] **Step 2: Write the real stdio output-containment test**

Spawn `python -m fiji_mcp` with `FIJI_PATH` and `FIJI_MODE=headless`. Through `FastMCP Client`, execute:

```python
ijm_result = await client.call_tool(
    "run_script",
    {"language": "ijm", "code": 'print("ijm-output");'},
)
groovy_result = await client.call_tool("run_script", {
    "language": "groovy",
    "code": 'println("groovy-output")\nSystem.out.println("java-output")',
})
assert ijm_result.is_error is False
assert groovy_result.is_error is False
state = await client.call_tool("get_state", {})
assert state.is_error is False
tools = await client.list_tools()
assert {tool.name for tool in tools} == EXPECTED
```

The final `tools/list` response proves that ordinary IJM, Groovy, and Java output did not corrupt the JSON-RPC stream. Capture subprocess stderr only for assertion/debugging; do not treat expected redirected lines as protocol content.

Use `StdioTransport(log_file=tmp_path / "fiji-stderr.log")`. Assert both script calls have `is_error is False`; assert `ijm-output` is present in the IJM tool's returned `log_tail`, while `groovy-output` and `java-output` are present in the stderr log. Then call `get_state` and `tools/list` again to prove the protocol remains synchronized.

The subprocess probes cover pre-start, startup, ready-read, and post-dispatch failures without poisoning the shared test JVM. Keep the faster Task 1 unit versions as classifier/attempt-count regression tests.

- [ ] **Step 3: Run integration tests to expose real API mismatches**

Run: `FIJI_MODE=headless pytest tests/test_integration_runtime.py tests/test_mcp_stdio_client.py -m integration -v --timeout=300`

Expected before fixes: at least one failure may identify an incorrect PyImageJ command overload, Results access, headless rendering, or stdout redirection behavior. The structured fixture is the locally installed headless SciJava command `net.imagej.plugins.commands.assign.AddToDataValues` with its primitive `value: double` input; `Measure` is the Results-producing ImageJ1 fixture. If either installed command is unavailable in a different Fiji build, skip only that fixture with its missing class recorded and retain the rest of the end-to-end test. If `FIJI_PATH` is unavailable, record the skipped count and do not claim integration completion.

- [ ] **Step 4: Correct only evidence-backed integration mismatches**

Apply the smallest changes in `bridge.py`, `tools.py`, or `imaging.py` required by the failing real-Fiji assertions. Preserve all nine signatures and retry/locking rules. Add a focused regression assertion for every corrected mismatch.

- [ ] **Step 5: Run direct, stdio, and unit suites together**

Run: `FIJI_MODE=headless pytest -v --timeout=300`

Expected: all unit/contract tests pass; integration tests pass when `FIJI_PATH` exists or are explicitly skipped when it does not.

- [ ] **Step 6: Commit real-Fiji verification**

```bash
git add src/fiji_mcp tests/conftest.py tests/test_integration_runtime.py tests/test_mcp_stdio_client.py
git commit -m "test: verify minimal Fiji MCP end to end"
```

---

### Task 8: Delete legacy layers and rewrite the project around the minimal API

**Files:**
- Delete: `src/fiji_mcp/fiji_bridge.py`
- Delete: `src/fiji_mcp/cli/`
- Delete: `src/fiji_mcp/config/`
- Delete: `src/fiji_mcp/data/`
- Delete: `src/fiji_mcp/schemas/`
- Delete: `src/fiji_mcp/utils/`
- Delete: `tests/test_cli_install.py`
- Delete: `tests/test_image_compare.py`
- Delete: `tests/test_java_errors.py`
- Delete: `tests/test_path_policy.py`
- Delete: `tests/test_result_parser.py`
- Delete: `tests/test_runtime_behavior.py`
- Delete: `tests/test_session_state.py`
- Delete: `tests/test_settings.py`
- Delete: `tests/test_template_catalog.py`
- Modify: `tests/test_package_exports.py`
- Create: `tests/wheel_smoke.py`
- Modify: `pyproject.toml`
- Rewrite: `README.md`
- Rewrite: `docs/tools.md`
- Rewrite: `CLAUDE.md`
- Rewrite: `RELEASING.md`
- Modify: `CHANGELOG.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish-pypi.yml`
- Delete: `MANIFEST.in`
- Delete: `install.sh`
- Delete: `scripts/`
- Delete: `extras/cursor-fiji-mcp-plugin/`
- Delete: `plan.md`
- Delete: `Fiji_imageJ_mcp.code-workspace`
- Delete: `docs/README.md`
- Delete: `docs/_sidebar.md`
- Delete: `docs/architecture.md`
- Delete: `docs/batch_report_workflow.md`
- Delete: `docs/configuration.md`
- Delete: `docs/index.html`
- Delete: `docs/quickstart.md`
- Delete: `docs/repository_layout.md`
- Delete: `docs/superpowers/specs/2026-07-21-fiji-mcp-v0.2-design.md`
- Delete: all six `docs/superpowers/plans/2026-07-21-fiji-mcp-v0.2-*.md` files
- Delete: `demo_images/img00.png` through `demo_images/img22.png`
- Delete: `demo_output/`
- Retain: `demo_images/sample_gradient.pgm`, current `2026-08-10` spec/plan, and `docs/releases/`

**Interfaces:**
- Produces: the final source/test/documentation tree from the file map and a standard setuptools package with only `fiji-mcp-server` as a console script.

- [ ] **Step 1: Write packaging and stale-reference assertions**

Add this test to `tests/test_package_exports.py`:

```python
def test_runtime_dependencies_are_minimal():
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert project["project"]["version"] == "0.2.0"
    assert project["project"]["dependencies"] == [
        "fastmcp>=2.10.3", "pyimagej>=1.5.0", "numpy>=1.26.0", "Pillow>=10.0.0",
    ]
    assert project["project"]["scripts"] == {"fiji-mcp-server": "fiji_mcp.__main__:main"}
```

Run a stale-reference scan limited to active code/docs:

```bash
rg -n 'health_check|run_batch_macros|run_workflow|list_all_commands|describe_plugin|list_extensions|list_open_images|get_image_info|screenshot_fiji|parse_macro_output|list_macro_templates|get_macro_template|get_session_trace|clear_session_trace|fiji-mcp-install|FIJI_DATA_ROOTS|FIJI_OPERATION_TIMEOUT' src tests pyproject.toml
rg -n 'health_check|run_macro|run_batch_macros|run_workflow|list_all_commands|describe_plugin|list_extensions|list_open_images|get_image_info|screenshot_fiji|parse_macro_output|list_macro_templates|get_macro_template|get_session_trace|clear_session_trace|fiji-mcp-install|FIJI_DATA_ROOTS|FIJI_OPERATION_TIMEOUT' README.md docs/tools.md CLAUDE.md RELEASING.md
```

Expected before cleanup: multiple legacy matches.

- [ ] **Step 2: Remove unused production and test modules**

Delete every path listed above, including the four legacy test files already removed in Task 6. Preserve only the new design, this plan, and historical `docs/releases/`. This is an approved breaking simplification; do not retain compatibility imports or empty placeholder packages.

- [ ] **Step 3: Simplify package metadata and CI**

In `pyproject.toml`:

- Set the breaking-release version to `0.2.0`.
- Change the description to `Minimal MCP server for controlling Fiji/ImageJ through commands, IJM, Groovy, images, and results`.
- Remove direct `pydantic`.
- Remove `fiji-mcp-install` and data package entries.
- Keep Python `>=3.10`, test/dev extras, `fiji-mcp-server`, and `py.typed`.
- Remove Ruff exceptions for deleted files.

In CI and publishing workflows, retain checkout, Python 3.10–3.12, install, Ruff, non-integration pytest, build, and publish. Remove Cursor-plugin checks and `scripts/verify_sdist_contents.sh`; use `python -m build`, `python -m twine check dist/*`, and the exact wheel-smoke command from Step 6 for packaging validation.

- [ ] **Step 4: Rewrite documentation as one short path to success**

`README.md` must contain, in this order:

1. One-sentence purpose.
2. `pip install fiji-mcp-server` and local Fiji requirement.
3. One generic stdio JSON configuration using `fiji-mcp-server`, `FIJI_PATH`, and optional `FIJI_MODE`.
4. The exact nine-tool table.
5. Three approved end-to-end example prompts.
6. The trusted arbitrary-script warning, the fact that deliberate native file-descriptor-1 writes can bypass Java stream redirection, and the GUI-only plugin limitation.
7. A link to `docs/tools.md` and historical release notes.

`docs/tools.md` documents each exact signature, return fields, retry behavior, screenshot path workflow, Results pagination, and installed-scriptable-plugin scope. `CLAUDE.md` describes only the final files and current commands. `RELEASING.md` uses `pip install` plus manual generic MCP configuration. Add an Unreleased changelog entry naming the breaking nine-tool simplification.

- [ ] **Step 5: Run the stale-reference and file-shape checks**

Run:

```bash
rg --files src/fiji_mcp | sort
rg --files tests | sort
rg -n 'health_check|run_batch_macros|run_workflow|list_all_commands|describe_plugin|list_extensions|list_open_images|get_image_info|screenshot_fiji|parse_macro_output|list_macro_templates|get_macro_template|get_session_trace|clear_session_trace|fiji-mcp-install|FIJI_DATA_ROOTS|FIJI_OPERATION_TIMEOUT' src tests pyproject.toml
rg -n 'health_check|run_macro|run_batch_macros|run_workflow|list_all_commands|describe_plugin|list_extensions|list_open_images|get_image_info|screenshot_fiji|parse_macro_output|list_macro_templates|get_macro_template|get_session_trace|clear_session_trace|fiji-mcp-install|FIJI_DATA_ROOTS|FIJI_OPERATION_TIMEOUT' README.md docs/tools.md CLAUDE.md RELEASING.md
```

Expected: the source list matches the seven final package paths; the test list matches the final test map; the stale-reference command exits 1 with no matches.

- [ ] **Step 6: Run non-integration verification and build**

Create `tests/wheel_smoke.py` with this complete clean-environment probe:

```python
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

EXPECTED = {
    "get_state", "search_commands", "run_command", "run_script",
    "open_image", "save_image", "get_results", "screenshot",
    "compare_screenshots",
}


async def _probe(entrypoint: Path, stderr_path: Path) -> None:
    env = os.environ.copy()
    for key in ("FIJI_PATH", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(key, None)
    env["FIJI_MODE"] = "headless"
    transport = StdioTransport(
        command=str(entrypoint),
        args=[],
        env=env,
        keep_alive=False,
        log_file=stderr_path,
    )
    async with Client(transport, init_timeout=60, timeout=60) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == EXPECTED


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: wheel_smoke.py path/to/fiji_mcp_server.whl")
    wheel = Path(sys.argv[1]).resolve()
    if not wheel.is_file():
        raise SystemExit(f"wheel not found: {wheel}")
    with tempfile.TemporaryDirectory(prefix="fiji-mcp-wheel-smoke-") as temp:
        root = Path(temp)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        executable_dir = "Scripts" if os.name == "nt" else "bin"
        python_name = "python.exe" if os.name == "nt" else "python"
        entrypoint_name = (
            "fiji-mcp-server.exe" if os.name == "nt" else "fiji-mcp-server"
        )
        python = environment / executable_dir / python_name
        entrypoint = environment / executable_dir / entrypoint_name
        subprocess.run(
            [str(python), "-m", "pip", "install", str(wheel)],
            check=True,
        )
        asyncio.run(_probe(entrypoint, root / "stderr.log"))
    print("wheel install and nine-tool stdio smoke probe passed")


if __name__ == "__main__":
    main()
```

Run:

```bash
ruff check src/ tests/
mypy src/fiji_mcp --ignore-missing-imports
pytest -m "not integration" -v
python -m build
python -m twine check dist/*
python tests/wheel_smoke.py dist/fiji_mcp_server-0.2.0-py3-none-any.whl
```

Expected: all commands exit 0; the last command prints `wheel install and nine-tool stdio smoke probe passed` without `FIJI_PATH`.

- [ ] **Step 7: Commit the cleanup**

Stage only the scoped project paths; leave the five unrelated untracked paths alone.

```bash
git add -A -- src/fiji_mcp tests docs scripts extras demo_images demo_output README.md CLAUDE.md RELEASING.md CHANGELOG.md pyproject.toml MANIFEST.in install.sh plan.md Fiji_imageJ_mcp.code-workspace .github/workflows/ci.yml .github/workflows/publish-pypi.yml
git commit -m "refactor: remove legacy Fiji MCP framework"
```

---

### Task 9: Final verification against the approved specification

**Files:**
- Verify only; modify a file only when a command below provides concrete failure evidence.

**Interfaces:**
- Consumes: the completed implementation and `docs/superpowers/specs/2026-08-10-minimal-fiji-mcp-design.md`.
- Produces: fresh evidence for contract, quality, packaging, and local-Fiji acceptance.

- [ ] **Step 1: Verify the exact MCP contract without Fiji**

Run: `pytest tests/test_mcp_contract.py tests/test_mcp_stdio_client.py -m "not integration" -v`

Expected: all tests pass and both in-process and stdio surfaces contain exactly nine names.

- [ ] **Step 2: Verify all non-integration behavior**

Run: `pytest -m "not integration" -v`

Expected: zero failures and zero errors.

- [ ] **Step 3: Verify static quality**

Run:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
mypy src/fiji_mcp --ignore-missing-imports
```

Expected: all commands exit 0 without changes.

- [ ] **Step 4: Verify the distributable package**

Run:

```bash
python -m build
python -m twine check dist/*
python tests/wheel_smoke.py dist/fiji_mcp_server-0.2.0-py3-none-any.whl
```

Expected: sdist and wheel build successfully, Twine reports `PASSED` for both, a fresh temporary environment installs the wheel with its dependencies, the generated `fiji-mcp-server` console entry point starts, and its stdio client reports exactly nine tools without Fiji.

- [ ] **Step 5: Verify real Fiji when available**

Run: `FIJI_MODE=headless pytest -m integration -v --timeout=300`

Expected with `FIJI_PATH`: direct and stdio integrations pass, including IJM/Groovy/Java stdout containment. Without `FIJI_PATH`, tests must report explicit skips; the implementation cannot be declared integration-complete until this command is rerun with Fiji configured.

- [ ] **Step 6: Audit requirements and repository state**

Run:

```bash
git diff --check
git status --short
rg -n '^### 6\.[0-9]+ ' docs/superpowers/specs/2026-08-10-minimal-fiji-mcp-design.md
```

Expected: no whitespace errors; only intentionally untracked user paths remain; the specification still lists exactly nine tool sections. Compare every definition-of-done bullet in the specification to a passing command or integration result before claiming completion.
