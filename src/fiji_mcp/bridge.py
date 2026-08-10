"""Isolated, synchronous runtime bridge for a single Fiji JVM."""

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
    """The lifecycle of the process-local Fiji JVM."""

    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    FAILED = "FAILED"


class Outcome(str, Enum):
    """Whether an operation is known not to have completed."""

    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Settings:
    """The only runtime settings owned by the isolated bridge."""

    fiji_path: Path
    mode: Literal["headless", "gui"]


class FijiError(RuntimeError):
    """A structured error surfaced from the Fiji runtime boundary."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        outcome: Outcome,
        recovery: str,
    ) -> None:
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
    """Read and validate the Fiji root and execution mode."""
    env = os.environ if environ is None else environ
    raw_path = env.get("FIJI_PATH", "").strip()
    if not raw_path:
        raise FijiError(
            "invalid_configuration",
            "FIJI_PATH is required.",
            retryable=False,
            outcome=Outcome.FAILED,
            recovery="Set FIJI_PATH to the Fiji root and retry.",
        )
    root: Path | None = None
    for attempt in range(2):
        try:
            root = _resolve_and_validate_root(raw_path)
            break
        except FijiError:
            raise
        except (OSError, RuntimeError) as error:
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
        raise FijiError(
            "invalid_configuration",
            "FIJI_MODE must be headless or gui.",
            retryable=False,
            outcome=Outcome.FAILED,
            recovery="Set FIJI_MODE=headless or FIJI_MODE=gui.",
        )
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
    """Return the single JVM gateway, starting it lazily when necessary."""
    global _IJ, _LIFECYCLE, _SETTINGS
    with _OPERATION_LOCK:
        if _LIFECYCLE is Lifecycle.READY:
            assert _IJ is not None
            return _IJ
        if _LIFECYCLE is Lifecycle.FAILED:
            raise FijiError(
                "jvm_failed",
                "The Fiji JVM is not reusable.",
                retryable=False,
                outcome=Outcome.FAILED,
                recovery="restart the MCP server.",
            )
        # Invalid configuration occurs before STARTING and remains fixable in-process.
        settings = load_settings()
        _LIFECYCLE = Lifecycle.STARTING
        try:
            _IJ = _start_fiji(settings)
        except Exception as error:
            _LIFECYCLE = Lifecycle.FAILED
            raise FijiError(
                "jvm_start_failed",
                str(error),
                retryable=False,
                outcome=Outcome.FAILED,
                recovery="Fix the reported cause and restart the MCP server.",
            ) from error
        _SETTINGS = settings
        _LIFECYCLE = Lifecycle.READY
        return _IJ


def _exception_type_name(error: BaseException) -> str:
    error_type = type(error)
    module_name = error_type.__module__
    class_name = error_type.__name__
    qualified_type = (
        class_name
        if class_name.startswith(f"{module_name}.")
        else f"{module_name}.{class_name}"
    )
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
        recovery="restart the MCP server.",
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
    """Run a read-only Fiji operation with one safe retry at most."""
    with _OPERATION_LOCK:
        return _run_read_phase(operation, get_ij(), function)


def run_mutation(
    operation: str,
    prepare: Callable[[Any], P],
    dispatch: Callable[[Any, P], T],
) -> T:
    """Run a mutation with a retryable pre-dispatch phase and one dispatch."""
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
    """Return settings associated with the initialized Fiji gateway."""
    get_ij()
    assert _SETTINGS is not None
    return _SETTINGS


def runtime_snapshot() -> dict[str, Any]:
    """Return the observable runtime lifecycle and initialized settings."""
    return {
        "lifecycle": _LIFECYCLE.value,
        "path": str(_SETTINGS.fiji_path) if _SETTINGS else None,
        "mode": _SETTINGS.mode if _SETTINGS else None,
    }


def _reset_runtime_for_tests(*, ready_ij: Any | None = None) -> None:
    """Reset process state for isolated unit tests only."""
    global _IJ, _LIFECYCLE, _SETTINGS
    _IJ = ready_ij
    _LIFECYCLE = Lifecycle.READY if ready_ij is not None else Lifecycle.NEW
    _SETTINGS = None
