from __future__ import annotations

import asyncio
import errno
import platform
import sys
import threading
import types
from pathlib import Path

import pytest

from fiji_mcp import bridge


def _fiji_root(tmp_path: Path) -> Path:
    (tmp_path / "jars").mkdir()
    (tmp_path / "plugins").mkdir()
    return tmp_path


def _bundled_macos_jvm(root: Path, name: str) -> Path:
    home = root / "java" / "macos-arm64" / name / "zulu-21.jdk" / "Contents" / "Home"
    executable = home / "bin" / "java"
    library = home / "lib" / "server" / "libjvm.dylib"
    executable.parent.mkdir(parents=True)
    library.parent.mkdir(parents=True)
    executable.touch()
    executable.chmod(0o755)
    library.touch()
    return library


def _bundled_linux_jvm(root: Path, bucket: str, name: str) -> Path:
    home = root / "java" / bucket / name
    executable = home / "bin" / "java"
    library = home / "lib" / "server" / "libjvm.so"
    executable.parent.mkdir(parents=True)
    library.parent.mkdir(parents=True)
    executable.touch()
    executable.chmod(0o755)
    library.touch()
    return library


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


def test_runtime_path_failure_is_invalid_configuration_without_retry(monkeypatch):
    raw_path = "~fiji_mcp_task1_nonexistent_user/Fiji"
    monkeypatch.setenv("FIJI_PATH", raw_path)
    original = bridge._resolve_and_validate_root
    attempts = 0

    def unresolved(path):
        nonlocal attempts
        attempts += 1
        return original(path)

    monkeypatch.setattr(bridge, "_resolve_and_validate_root", unresolved)
    with pytest.raises(
        bridge.FijiError, match="Could not validate FIJI_PATH"
    ) as raised:
        bridge.load_settings()
    assert attempts == 1
    assert raised.value.code == "invalid_configuration"
    assert raised.value.retryable is False


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
    monkeypatch.setattr(
        bridge,
        "_start_fiji",
        lambda settings: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(bridge.FijiError, match="restart the MCP server"):
        bridge.get_ij()
    assert bridge.runtime_snapshot()["lifecycle"] == "FAILED"
    with pytest.raises(bridge.FijiError, match="restart the MCP server"):
        bridge.get_ij()


def test_concurrent_first_callers_start_fiji_once(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    monkeypatch.setenv("FIJI_PATH", str(root))
    bridge._reset_runtime_for_tests()
    gateway = object()
    start_entered = threading.Event()
    release_start = threading.Event()
    second_attempting = threading.Event()
    start_calls = 0
    results = []
    errors = []
    results_lock = threading.Lock()

    def start(_settings):
        nonlocal start_calls
        start_calls += 1
        start_entered.set()
        release_start.wait(timeout=2)
        return gateway

    def caller(attempting=None):
        if attempting is not None:
            attempting.set()
        try:
            result = bridge.get_ij()
        except BaseException as error:
            with results_lock:
                errors.append(error)
        else:
            with results_lock:
                results.append(result)

    monkeypatch.setattr(bridge, "_start_fiji", start)
    first_thread = threading.Thread(target=caller)
    second_thread = threading.Thread(target=caller, args=(second_attempting,))
    first_thread.start()
    assert start_entered.wait(timeout=1)
    second_thread.start()
    assert second_attempting.wait(timeout=1)
    release_start.set()
    first_thread.join(timeout=1)
    second_thread.join(timeout=1)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []
    assert start_calls == 1
    assert results == [gateway, gateway]


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


def test_start_fiji_pins_one_bundled_jvm_before_imagej_init(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    jvm_path = _bundled_macos_jvm(root, "zulu21")
    events: list[tuple[object, ...]] = []
    gateway = object()

    fake_sj = types.SimpleNamespace(
        config=types.SimpleNamespace(
            get_kwargs=lambda: {"interrupt": True},
            add_kwargs=lambda **kwargs: events.append(("jvmpath", kwargs["jvmpath"])),
        ),
        jvm_started=lambda: False,
        when_jvm_starts=lambda _callback: events.append(("when_jvm_starts",)),
    )

    def init(path: str, *, mode: str) -> object:
        events.append(("imagej_init", path, mode))
        return gateway

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setitem(sys.modules, "scyjava", fake_sj)
    monkeypatch.setitem(sys.modules, "imagej", types.SimpleNamespace(init=init))

    assert bridge._start_fiji(bridge.Settings(root, "headless")) is gateway
    assert events == [
        ("jvmpath", str(jvm_path)),
        ("when_jvm_starts",),
        ("imagej_init", str(root), "headless"),
    ]


def test_bundled_jvm_path_rejects_multiple_valid_runtimes(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    _bundled_macos_jvm(root, "zulu21-a")
    _bundled_macos_jvm(root, "zulu21-b")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")

    with pytest.raises(RuntimeError, match="multiple bundled JVMs"):
        bridge._bundled_jvm_path(root)


def test_bundled_jvm_path_accepts_linux_amd64_alias(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    jvm_path = _bundled_linux_jvm(root, "linux-amd64", "zulu21")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")

    assert bridge._bundled_jvm_path(root) == jvm_path


def test_bundled_jvm_path_rejects_multiple_linux_alias_runtimes(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    _bundled_linux_jvm(root, "linux-amd64", "zulu21-a")
    _bundled_linux_jvm(root, "linux-x64", "zulu21-b")
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")

    with pytest.raises(RuntimeError, match="multiple bundled JVMs"):
        bridge._bundled_jvm_path(root)


def test_start_fiji_retains_preconfigured_jvmpath(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    _bundled_macos_jvm(root, "zulu21")
    calls: list[dict[str, object]] = []
    gateway = object()

    fake_sj = types.SimpleNamespace(
        config=types.SimpleNamespace(
            get_kwargs=lambda: {"jvmpath": "/external/libjvm.dylib"},
            add_kwargs=lambda **kwargs: calls.append(kwargs),
        ),
        jvm_started=lambda: False,
        when_jvm_starts=lambda _callback: None,
    )
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setitem(sys.modules, "scyjava", fake_sj)
    monkeypatch.setitem(
        sys.modules,
        "imagej",
        types.SimpleNamespace(init=lambda _path, *, mode: gateway),
    )

    assert bridge._start_fiji(bridge.Settings(root, "headless")) is gateway
    assert calls == []


def test_start_fiji_retains_scijava_fallback_without_bundled_jvm(monkeypatch, tmp_path):
    root = _fiji_root(tmp_path)
    calls: list[dict[str, object]] = []
    gateway = object()

    fake_sj = types.SimpleNamespace(
        config=types.SimpleNamespace(
            get_kwargs=lambda: {"interrupt": True},
            add_kwargs=lambda **kwargs: calls.append(kwargs),
        ),
        jvm_started=lambda: False,
        when_jvm_starts=lambda _callback: None,
    )
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    monkeypatch.setitem(sys.modules, "scyjava", fake_sj)
    monkeypatch.setitem(
        sys.modules,
        "imagej",
        types.SimpleNamespace(init=lambda _path, *, mode: gateway),
    )

    assert bridge._start_fiji(bridge.Settings(root, "headless")) is gateway
    assert calls == []


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
        "java.util.ConcurrentModificationException",
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
        "java.awt.HeadlessException",
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


class _JavaFacingGateway:
    def __init__(self, *, fails: bool) -> None:
        self.calls = 0
        self.fails = fails

    def inspect(self) -> None:
        self.calls += 1
        if self.fails:
            raise RuntimeError("Java bridge call failed")


def _fiji_error_after_java_failure(
    ij: _JavaFacingGateway, error: bridge.FijiError
) -> None:
    try:
        ij.inspect()
    except RuntimeError as cause:
        raise error from cause


def _business_error() -> bridge.FijiError:
    return bridge.FijiError(
        "render_failed",
        "The Fiji image could not be rendered.",
        retryable=False,
        outcome=bridge.Outcome.FAILED,
        recovery="Select a valid image and retry.",
    )


def test_dead_jvm_wrapped_fiji_error_marks_read_terminal(monkeypatch):
    gateway = _JavaFacingGateway(fails=True)
    bridge._reset_runtime_for_tests(ready_ij=gateway)
    health_probes = 0

    def unhealthy(_ij):
        nonlocal health_probes
        health_probes += 1
        return False

    monkeypatch.setattr(bridge, "_jvm_is_healthy", unhealthy)
    original = _business_error()
    try:
        assert bridge.runtime_snapshot()["lifecycle"] == "READY"
        with pytest.raises(bridge.FijiError) as raised:
            bridge.run_read(
                "render_active_image",
                lambda ij: _fiji_error_after_java_failure(ij, original),
            )
        assert raised.value.code == "jvm_failed"
        assert raised.value.outcome is bridge.Outcome.FAILED
        assert raised.value.__cause__ is original
        assert bridge.runtime_snapshot()["lifecycle"] == "FAILED"
        assert gateway.calls == 1
        assert health_probes == 1
    finally:
        bridge._reset_runtime_for_tests()


def test_dead_jvm_wrapped_fiji_error_before_dispatch_is_failed(monkeypatch):
    gateway = _JavaFacingGateway(fails=True)
    bridge._reset_runtime_for_tests(ready_ij=gateway)
    health_probes = 0
    dispatched = 0

    def unhealthy(_ij):
        nonlocal health_probes
        health_probes += 1
        return False

    def dispatch(_ij, _prepared):
        nonlocal dispatched
        dispatched += 1

    monkeypatch.setattr(bridge, "_jvm_is_healthy", unhealthy)
    try:
        with pytest.raises(bridge.FijiError) as raised:
            bridge.run_mutation(
                "save_image",
                lambda ij: _fiji_error_after_java_failure(ij, _business_error()),
                dispatch,
            )
        assert raised.value.code == "jvm_failed"
        assert raised.value.outcome is bridge.Outcome.FAILED
        assert bridge.runtime_snapshot()["lifecycle"] == "FAILED"
        assert dispatched == 0
        assert gateway.calls == 1
        assert health_probes == 1
    finally:
        bridge._reset_runtime_for_tests()


def test_dead_jvm_wrapped_fiji_error_after_dispatch_is_unknown(monkeypatch):
    gateway = _JavaFacingGateway(fails=True)
    bridge._reset_runtime_for_tests(ready_ij=gateway)
    health_probes = 0
    dispatched = 0

    def unhealthy(_ij):
        nonlocal health_probes
        health_probes += 1
        return False

    def dispatch(ij, _prepared):
        nonlocal dispatched
        dispatched += 1
        _fiji_error_after_java_failure(ij, _business_error())

    monkeypatch.setattr(bridge, "_jvm_is_healthy", unhealthy)
    try:
        with pytest.raises(bridge.FijiError) as raised:
            bridge.run_mutation("save_image", lambda _ij: None, dispatch)
        assert raised.value.code == "jvm_failed"
        assert raised.value.outcome is bridge.Outcome.UNKNOWN
        assert bridge.runtime_snapshot()["lifecycle"] == "FAILED"
        assert dispatched == 1
        assert gateway.calls == 1
        assert health_probes == 1
    finally:
        bridge._reset_runtime_for_tests()


def test_healthy_business_fiji_error_after_dispatch_is_preserved(monkeypatch):
    gateway = _JavaFacingGateway(fails=False)
    bridge._reset_runtime_for_tests(ready_ij=gateway)
    health_probes = 0
    dispatched = 0
    original = _business_error()

    def healthy(_ij):
        nonlocal health_probes
        health_probes += 1
        return True

    def business_failure_after_java_call(ij):
        ij.inspect()
        raise original

    def dispatch(ij, _prepared):
        nonlocal dispatched
        dispatched += 1
        business_failure_after_java_call(ij)

    monkeypatch.setattr(bridge, "_jvm_is_healthy", healthy)
    try:
        with pytest.raises(bridge.FijiError) as raised:
            bridge.run_mutation("save_image", lambda _ij: None, dispatch)
        assert raised.value is original
        assert bridge.runtime_snapshot()["lifecycle"] == "READY"
        assert dispatched == 1
        assert gateway.calls == 1
        assert health_probes == 1
    finally:
        bridge._reset_runtime_for_tests()


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
    second_attempting = threading.Event()
    second_entered = threading.Event()

    def first(_ij, _prepared):
        entered.set()
        release.wait(timeout=2)

    def second(_ij):
        second_entered.set()

    def run_second():
        second_attempting.set()
        bridge.run_read("state", second)

    first_thread = threading.Thread(
        target=lambda: bridge.run_mutation("script", lambda _ij: None, first)
    )
    second_thread = threading.Thread(target=run_second)
    first_thread.start()
    assert entered.wait(timeout=1)
    second_thread.start()
    assert second_attempting.wait(timeout=1)
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
    second_attempting = threading.Event()
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

    def run_second():
        second_attempting.set()
        return bridge.run_read(
            "state",
            lambda _ij: second_entered.set(),
        )

    second_delivery = asyncio.create_task(asyncio.to_thread(run_second))
    assert await asyncio.to_thread(second_attempting.wait, 1)
    assert not await asyncio.to_thread(second_entered.wait, 0.05)
    release.set()
    await second_delivery
    assert second_entered.is_set()
