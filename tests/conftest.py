"""Pytest hooks for the Fiji/JPype test suite."""

from __future__ import annotations


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    """Best-effort JVM shutdown to reduce macOS exit segfaults (signal 139) after JPype tests."""
    try:
        import jpype

        if not jpype.isJVMStarted():
            return
        from scyjava import shutdown_jvm

        shutdown_jvm()
    except Exception:
        pass
