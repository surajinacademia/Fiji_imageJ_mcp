"""Bridge for initializing and accessing a shared PyImageJ/Fiji runtime."""

from __future__ import annotations

import os
import platform
import shutil
import threading
from pathlib import Path
from typing import Any

from fiji_mcp.config.settings import Settings, load_settings

_INIT_LOCK = threading.Lock()
_BRIDGE_STATE: dict[str, Any] = {
    "initialized": False,
    "imagej_module": None,
    "ij": None,
    "fiji_path": None,
    "mode": None,
    "settings": None,
}


def _candidate_fiji_paths() -> list[Path]:
    system = platform.system()
    home = Path.home()
    candidates: list[Path] = []

    if system == "Darwin":
        candidates.extend(
            [
                Path("/Applications/Fiji"),
                Path("/Applications/Fiji.app"),
                home / "Applications" / "Fiji.app",
                home / "Applications" / "Fiji",
                home / "Fiji.app",
                home / "Fiji",
            ]
        )
    elif system == "Linux":
        candidates.extend(
            [
                Path("/opt/Fiji.app"),
                Path("/usr/local/Fiji.app"),
                home / "Fiji.app",
            ]
        )
    elif system == "Windows":
        candidates.extend(
            [
                Path("C:/Fiji.app"),
                Path("C:/Fiji"),
                home / "Fiji.app",
                home / "Fiji",
            ]
        )

    extra_paths = os.environ.get("FIJI_PATH_CANDIDATES", "")
    for raw_path in extra_paths.split(os.pathsep):
        if raw_path.strip():
            candidates.append(Path(raw_path).expanduser())

    return candidates


def detect_fiji_path(settings: Settings | None = None) -> str:
    """Detect Fiji installation path from environment and common install locations."""
    settings = settings or load_settings()
    if settings.fiji_path:
        path = Path(settings.fiji_path).expanduser()
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"FIJI_PATH does not exist: {path}")

    for path in _candidate_fiji_paths():
        if path.exists():
            return str(path)

    raise FileNotFoundError(
        "Could not detect Fiji installation. Set FIJI_PATH to your Fiji.app directory."
    )


def resolve_start_mode(settings: Settings | None = None) -> str:
    """Map configured mode into a PyImageJ startup mode."""
    settings = settings or load_settings()
    configured_mode = settings.fiji_mode
    if configured_mode == "gui":
        # PyImageJ refuses plain `python` on macOS without AppKit on the main thread; optional escape hatch.
        if platform.system() == "Darwin" and os.environ.get("FIJI_INTERACTIVE_FORCE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }:
            return "interactive:force"
        return "interactive"
    if configured_mode == "headless":
        return "headless"
    if _has_display():
        return "interactive"
    return "headless"


def _has_display() -> bool:
    system = platform.system()
    if system == "Linux":
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    if system in {"Darwin", "Windows"}:
        return True
    return False


def _bundled_jdk_home(fiji_root: Path) -> Path | None:
    """Return JAVA_HOME for the JDK shipped under <Fiji>/java/... (matches modern Fiji plugins)."""
    java_root = fiji_root / "java"
    if not java_root.is_dir():
        return None
    system = platform.system()
    machine = platform.machine().lower()
    platform_dirs: list[str] = []
    if system == "Darwin":
        platform_dirs.append("macos-arm64" if "arm" in machine else "macos-x64")
    elif system == "Linux":
        platform_dirs.extend(["linux-amd64", "linux-x64", "linux-arm64"])
    elif system == "Windows":
        platform_dirs.append("win64")
    for name in platform_dirs:
        base = java_root / name
        if not base.is_dir():
            continue
        try:
            for child in sorted(base.iterdir()):
                java_bin = child / "bin" / "java"
                if java_bin.is_file():
                    return child
        except OSError:
            continue
    return None


def _libjvm_path(java_home: Path) -> Path | None:
    """Return JPype-compatible libjvm path for this platform (JPype ignores JAVA_HOME alone)."""
    system = platform.system()
    if system == "Darwin":
        candidates = [java_home / "lib" / "server" / "libjvm.dylib"]
    elif system == "Linux":
        candidates = [java_home / "lib" / "server" / "libjvm.so"]
    else:
        candidates = [
            java_home / "bin" / "server" / "jvm.dll",
            java_home / "lib" / "server" / "jvm.dll",
        ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def initialize_fiji(force: bool = False) -> Any:
    """Initialize the shared Fiji runtime once and return the ImageJ gateway."""
    settings = load_settings()
    with _INIT_LOCK:
        if _BRIDGE_STATE["initialized"] and not force:
            return _BRIDGE_STATE["ij"]

        import scyjava as sj  # noqa: PLC0415 — before imagej so we can pin libjvm for JPype.

        fiji_path = detect_fiji_path(settings)
        fiji_root = Path(fiji_path).expanduser()

        java_home = settings.fiji_java_home
        if not java_home:
            bundled = _bundled_jdk_home(fiji_root)
            if bundled is not None:
                java_home = str(bundled)
        if not java_home:
            conda_prefix = os.environ.get("CONDA_PREFIX")
            if conda_prefix and Path(conda_prefix, "bin", "java").exists():
                java_home = conda_prefix
        if java_home:
            java_home_path = Path(java_home).expanduser()
            os.environ["JAVA_HOME"] = str(java_home_path)
            if not sj.jvm_started():
                libjvm = _libjvm_path(java_home_path)
                if libjvm is not None:
                    sj.config.add_kwargs(jvmpath=str(libjvm))
        if "JAVA_HOME" not in os.environ:
            java_binary = shutil.which("java")
            if java_binary:
                os.environ["JAVA_HOME"] = str(Path(java_binary).resolve().parents[1])

        import imagej  # noqa: PLC0415 — after JAVA_HOME / jvmpath for correct JVM.

        init_mode = resolve_start_mode(settings)
        ij = imagej.init(fiji_path, mode=init_mode)

        _BRIDGE_STATE["initialized"] = True
        _BRIDGE_STATE["imagej_module"] = imagej
        _BRIDGE_STATE["ij"] = ij
        _BRIDGE_STATE["fiji_path"] = fiji_path
        _BRIDGE_STATE["mode"] = init_mode
        _BRIDGE_STATE["settings"] = settings
        return ij


def get_ij() -> Any:
    """Return initialized ImageJ gateway."""
    return initialize_fiji()


def get_ij1() -> Any:
    """Return the legacy ImageJ1 IJ helper class."""
    ij = get_ij()
    return ij.IJ


def get_java_gateway() -> Any:
    """Return PyImageJ Java gateway utilities."""
    ij = get_ij()
    return ij.py


def get_bridge_status() -> dict[str, Any]:
    """Return bridge status for health checks and diagnostics."""
    return {
        "initialized": _BRIDGE_STATE["initialized"],
        "fiji_path": _BRIDGE_STATE["fiji_path"],
        "mode": _BRIDGE_STATE["mode"],
    }
