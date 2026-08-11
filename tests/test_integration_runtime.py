"""Direct integration tests against a locally installed Fiji runtime."""

from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest
import scyjava as sj
from PIL import Image

from fiji_mcp import bridge, tools

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SYNTHETIC_TITLE = "task7-selected-plane"


def _fiji_root() -> Path:
    configured = os.environ.get("FIJI_PATH", "").strip()
    if not configured:
        pytest.skip("Set FIJI_PATH to run local Fiji integration tests")
    root = Path(configured).expanduser().resolve()
    if not (root / "jars").is_dir() or not (root / "plugins").is_dir():
        pytest.skip(f"FIJI_PATH is not a Fiji root: {root}")
    return root


def _integration_image() -> Path:
    configured = os.environ.get("FIJI_TEST_IMAGE", "").strip()
    image_path = (
        Path(configured).expanduser()
        if configured
        else _REPO_ROOT / "demo_images" / "sample_gradient.pgm"
    )
    if not image_path.is_file():
        pytest.skip(f"Integration image is unavailable: {image_path}")
    return image_path.resolve()


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_minimal_fiji_end_to_end(tmp_path: Path) -> None:
    """Exercise the complete nine-tool API in one real headless Fiji session."""
    _fiji_root()
    image_path = _integration_image()
    state = tools.get_state()
    assert state["lifecycle"] == "READY"

    opened = tools.open_image(str(image_path))
    assert opened["image"]["width"] > 0

    before = tmp_path / "before.png"
    tools.screenshot("active_image", str(before))
    found_add = tools.search_commands(
        "net.imagej.plugins.commands.assign.AddToDataValues"
    )
    assert found_add["commands"][0]["invocation_route"] == "structured_parameters"
    tools.run_command(
        "net.imagej.plugins.commands.assign.AddToDataValues",
        parameters={"value": 1.5},
    )
    tools.run_script("ijm", 'run("Invert");')
    groovy = tools.run_script("groovy", "#@output Integer answer\nanswer = 6 * 7")
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

    save_path = tmp_path / "result.tiff"
    tif_sibling = tmp_path / "result.tif"
    tif_sibling.write_bytes(b"preserve .tif sibling")
    saved = tools.save_image(str(save_path))
    assert saved["path"] == str(save_path.resolve())
    assert saved["format"] == "tiff"
    assert save_path.is_file()
    assert tif_sibling.read_bytes() == b"preserve .tif sibling"


_SYNTHETIC_IMAGE_SCRIPT = """
#@output String constructed
import ij.ImagePlus
import ij.ImageStack
import ij.WindowManager
import ij.gui.Overlay
import ij.gui.Roi
import ij.process.ByteProcessor
import ij.process.LUT
import java.awt.Color
import java.util.Arrays

def stack = new ImageStack(16, 16)
for (int t = 1; t <= 2; t++) {
    for (int z = 1; z <= 2; z++) {
        for (int c = 1; c <= 2; c++) {
            int value = 10 + (t - 1) * 80 + (z - 1) * 30 + (c - 1) * 10
            byte[] pixels = new byte[16 * 16]
            Arrays.fill(pixels, (byte) value)
            stack.addSlice(new ByteProcessor(16, 16, pixels, null))
        }
    }
}

def image = new ImagePlus("task7-selected-plane", stack)
image.setDimensions(2, 2, 2)
image.setOpenAsHyperStack(true)
image.setPosition(2, 2, 2)
image.setLut(LUT.createLutFromColor(Color.RED))
image.setDisplayRange(0, 255)

def overlay = new Overlay()
def fill = new Roi(5, 5, 6, 6)
fill.setFillColor(Color.GREEN)
fill.setStrokeColor(Color.GREEN)
fill.setPosition(2, 2, 2)
overlay.add(fill)
image.setOverlay(overlay)

def active = new Roi(1, 1, 14, 14)
active.setStrokeColor(Color.BLUE)
active.setStrokeWidth(1.0)
image.setRoi(active)
def bridgeThread = Thread.getAllStackTraces().keySet().find {
    candidate -> candidate.getId() == __BRIDGE_THREAD_ID__
}
if (bridgeThread == null) {
    throw new IllegalStateException("Bridge Java thread is unavailable")
}
WindowManager.setTempCurrentImage(bridgeThread, image)
constructed = image.getTitle()
"""


def _bridge_java_thread_id() -> int:
    def current_thread_id(_ij: Any) -> int:
        thread = sj.jimport("java.lang.Thread")
        return int(thread.currentThread().getId())

    return bridge.run_read("test_bridge_java_thread", current_thread_id)


def _synthetic_snapshot() -> dict[str, Any]:
    def read_source(ij: Any) -> dict[str, Any]:
        image = ij.WindowManager.getCurrentImage()
        if image is None or str(image.getTitle()) != _SYNTHETIC_TITLE:
            raise AssertionError(
                "Synthetic ImagePlus is not bound to the bridge thread"
            )

        stack = image.getStack()
        raw_values = [
            int(stack.getProcessor(index).getPixel(0, 0))
            for index in range(1, int(image.getStackSize()) + 1)
        ]
        lut = image.getProcessor().getColorModel()
        if lut is None:
            raise AssertionError("Synthetic ImagePlus has no selected-plane LUT")

        def lut_bytes(method_name: str) -> list[int]:
            values = sj.jarray("b", 256)
            getattr(lut, method_name)(values)
            return [int(value) & 0xFF for value in values]

        roi = image.getRoi()
        overlay = image.getOverlay()
        if roi is None or overlay is None:
            raise AssertionError("Synthetic ImagePlus lost its ROI or overlay")
        bounds = roi.getBounds()
        return {
            "raw_values": raw_values,
            "position": [int(image.getC()), int(image.getZ()), int(image.getT())],
            "display_range": [
                float(image.getDisplayRangeMin()),
                float(image.getDisplayRangeMax()),
            ],
            "lut_rgb": {
                "red": lut_bytes("getReds"),
                "green": lut_bytes("getGreens"),
                "blue": lut_bytes("getBlues"),
            },
            "overlay_size": int(overlay.size()),
            "roi_bounds": {
                "x": int(bounds.x),
                "y": int(bounds.y),
                "width": int(bounds.width),
                "height": int(bounds.height),
            },
        }

    return bridge.run_read("test_synthetic_source_snapshot", read_source)


def _is_dominant(pixel: tuple[int, int, int], channel: int) -> bool:
    return pixel[channel] > max(
        component for index, component in enumerate(pixel) if index != channel
    )


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_active_image_screenshot_preserves_plane_lut_overlay_and_source() -> None:
    """Render one selected hyperstack plane without changing source state."""
    _fiji_root()
    bridge_thread_id = _bridge_java_thread_id()
    script = textwrap.dedent(_SYNTHETIC_IMAGE_SCRIPT).replace(
        "__BRIDGE_THREAD_ID__", str(bridge_thread_id)
    )
    constructed = tools.run_script("groovy", script)
    assert constructed["result"]["constructed"] == _SYNTHETIC_TITLE

    before = _synthetic_snapshot()
    assert before["raw_values"] == [10, 20, 40, 50, 90, 100, 120, 130]
    assert before["position"] == [2, 2, 2]
    assert before["overlay_size"] == 1
    assert before["roi_bounds"] == {"x": 1, "y": 1, "width": 14, "height": 14}

    rendered = tools.screenshot("active_image")
    encoded = rendered.content[0].data
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
        background = image.convert("RGB").getpixel((0, 0))
        overlay_interior = image.convert("RGB").getpixel((7, 7))
        active_outline = image.convert("RGB").getpixel((1, 1))

    assert _is_dominant(background, 0)
    assert _is_dominant(overlay_interior, 1)
    assert _is_dominant(active_outline, 2)
    assert rendered.structured_content["current_c"] == 2
    assert rendered.structured_content["current_z"] == 2
    assert rendered.structured_content["current_t"] == 2

    after = _synthetic_snapshot()
    assert after == before


def _run_probe(source: str, fiji_path: Path) -> dict[str, Any]:
    probe_env = {**os.environ}
    src_path = str(_REPO_ROOT / "src")
    inherited_pythonpath = probe_env.get("PYTHONPATH", "")
    probe_env["PYTHONPATH"] = os.pathsep.join(
        value for value in (src_path, inherited_pythonpath) if value
    )
    probe_env["FIJI_PATH"] = str(fiji_path)
    probe_env["FIJI_MODE"] = "headless"
    probe_env["PYTHONUNBUFFERED"] = "1"
    try:
        # The test module controls every probe source and invokes only sys.executable.
        completed = subprocess.run(  # noqa: S603
            [sys.executable, "-c", source],
            check=True,
            capture_output=True,
            text=True,
            env=probe_env,
            timeout=300,
        )
    except subprocess.CalledProcessError as error:
        raise AssertionError(
            "Fiji lifecycle probe failed.\n"
            f"stdout:\n{error.stdout}\n"
            f"stderr:\n{error.stderr}"
        ) from error
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            f"Fiji lifecycle probe timed out. stdout:\n{error.stdout}\n"
            f"stderr:\n{error.stderr}"
        ) from error

    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise AssertionError(
            f"Fiji lifecycle probe did not emit JSON. stderr:\n{completed.stderr}"
        )
    try:
        record = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise AssertionError(
            "Fiji lifecycle probe emitted invalid final JSON.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        ) from error
    assert isinstance(record, dict)
    return record


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_pre_start_eintr_probe_is_two_attempts() -> None:
    """A transient root-validation interruption remains pre-start and retryable."""
    root = _fiji_root()
    record = _run_probe(
        textwrap.dedent(
            """
            import errno
            import json
            from fiji_mcp import bridge

            original = bridge._resolve_and_validate_root
            attempts = 0
            starts = 0

            def interrupted_once(path):
                global attempts
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.EINTR, "interrupted")
                return original(path)

            def counted_start(settings):
                global starts
                starts += 1
                raise AssertionError("startup must not run during settings validation")

            bridge._resolve_and_validate_root = interrupted_once
            bridge._start_fiji = counted_start
            settings = bridge.load_settings()
            record = {
                "attempts": attempts,
                "starts": starts,
                "lifecycle": bridge.runtime_snapshot()["lifecycle"],
                "path": str(settings.fiji_path),
            }
            assert record["attempts"] == 2
            assert record["starts"] == 0
            assert record["lifecycle"] == "NEW"
            print(json.dumps(record, sort_keys=True))
            """
        ),
        root,
    )
    assert record["attempts"] == 2
    assert record["starts"] == 0
    assert record["lifecycle"] == "NEW"
    assert Path(record["path"]) == root


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_startup_failure_probe_is_terminal() -> None:
    """A failed first JVM start never retries in the poisoned process."""
    root = _fiji_root()
    record = _run_probe(
        textwrap.dedent(
            """
            import json
            from fiji_mcp import bridge

            starts = 0

            def fail_start(settings):
                global starts
                starts += 1
                raise RuntimeError("injected startup failure")

            bridge._start_fiji = fail_start
            errors = []
            for _ in range(2):
                try:
                    bridge.get_ij()
                except bridge.FijiError as error:
                    errors.append({
                        "code": error.code,
                        "outcome": error.outcome.value,
                        "recovery": error.recovery,
                    })
                else:
                    raise AssertionError("startup unexpectedly succeeded")

            record = {
                "starts": starts,
                "lifecycle": bridge.runtime_snapshot()["lifecycle"],
                "errors": errors,
            }
            assert record["starts"] == 1
            assert record["lifecycle"] == "FAILED"
            assert [error["code"] for error in errors] == ["jvm_start_failed", "jvm_failed"]
            assert [error["outcome"] for error in errors] == ["failed", "failed"]
            assert all("restart the MCP server" in error["recovery"] for error in errors)
            print(json.dumps(record, sort_keys=True))
            """
        ),
        root,
    )
    assert record["starts"] == 1
    assert record["lifecycle"] == "FAILED"
    assert [error["code"] for error in record["errors"]] == [
        "jvm_start_failed",
        "jvm_failed",
    ]
    assert [error["outcome"] for error in record["errors"]] == ["failed", "failed"]
    assert all(
        "restart the MCP server" in error["recovery"] for error in record["errors"]
    )


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_bundled_jvm_loads_installed_java21_trackmate() -> None:
    """Fiji starts its installed Java-21 plugin runtime rather than SciJava's JRE 11."""
    root = _fiji_root()
    record = _run_probe(
        textwrap.dedent(
            """
            import json
            import scyjava as sj
            from fiji_mcp import bridge

            bridge.get_ij()
            system = sj.jimport("java.lang.System")
            trackmate = sj.jimport("fiji.plugin.trackmate.TrackMate")
            assert trackmate is not None
            record = {
                "java_version": str(system.getProperty("java.version")),
                "trackmate_imported": trackmate is not None,
            }
            assert record["java_version"].startswith("21.")
            assert record["trackmate_imported"] is True
            print(json.dumps(record, sort_keys=True))
            """
        ),
        root,
    )
    assert record["java_version"].startswith("21.")
    assert record["trackmate_imported"] is True


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_ready_read_retry_probe_uses_live_health_gate() -> None:
    """One allowed read interruption retries only after a real JVM health check."""
    root = _fiji_root()
    record = _run_probe(
        textwrap.dedent(
            """
            import errno
            import json
            from fiji_mcp import bridge

            attempts = 0
            ij = bridge.get_ij()

            def interrupted_once(gateway):
                global attempts
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.EINTR, "interrupted")
                return str(gateway.getVersion())

            version = bridge.run_read("ready_read_probe", interrupted_once)
            record = {
                "attempts": attempts,
                "lifecycle": bridge.runtime_snapshot()["lifecycle"],
                "version": version,
                "gateway_version": str(ij.getVersion()),
            }
            assert record["attempts"] == 2
            assert record["lifecycle"] == "READY"
            assert record["version"] == record["gateway_version"]
            print(json.dumps(record, sort_keys=True))
            """
        ),
        root,
    )
    assert record["attempts"] == 2
    assert record["lifecycle"] == "READY"
    assert record["version"]


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_post_dispatch_probe_is_once_and_unknown() -> None:
    """A bridge loss after a live mutation has an unknown, never-retried outcome."""
    root = _fiji_root()
    image_path = _integration_image()
    record = _run_probe(
        textwrap.dedent(
            """
            import json
            from fiji_mcp import bridge

            image_path = __IMAGE_PATH__
            ij = bridge.get_ij()
            image = ij.IJ.openImage(image_path)
            if image is None:
                raise AssertionError("Fiji could not open lifecycle fixture")
            ij.WindowManager.setTempCurrentImage(image)
            before = [
                int(image.getProcessor().getPixel(x, y))
                for y in range(image.getHeight())
                for x in range(image.getWidth())
            ]
            dispatches = 0

            def prepare(gateway):
                return gateway.WindowManager.getCurrentImage()

            def dispatch(gateway, prepared):
                global dispatches
                dispatches += 1
                gateway.IJ.run(prepared, "Invert", "")
                raise RuntimeError("injected bridge loss")

            try:
                bridge.run_mutation("post_dispatch_probe", prepare, dispatch)
            except bridge.FijiError as error:
                observed = {
                    "code": error.code,
                    "outcome": error.outcome.value,
                    "recovery": error.recovery,
                }
            else:
                raise AssertionError("post-dispatch failure did not surface")

            after = [
                int(image.getProcessor().getPixel(x, y))
                for y in range(image.getHeight())
                for x in range(image.getWidth())
            ]
            record = {
                "dispatches": dispatches,
                "changed_pixels": sum(before_value != after_value for before_value, after_value in zip(before, after, strict=True)),
                "error": observed,
                "lifecycle": bridge.runtime_snapshot()["lifecycle"],
            }
            assert record["dispatches"] == 1
            assert record["changed_pixels"] > 0
            assert record["error"]["code"] == "unknown_outcome"
            assert record["error"]["outcome"] == bridge.Outcome.UNKNOWN.value
            print(json.dumps(record, sort_keys=True))
            """
        ).replace("__IMAGE_PATH__", json.dumps(str(image_path))),
        root,
    )
    assert record["dispatches"] == 1
    assert record["changed_pixels"] > 0
    assert record["error"]["code"] == "unknown_outcome"
    assert record["error"]["outcome"] == bridge.Outcome.UNKNOWN.value


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_results_table_probe_preserves_defined_column_semantics() -> None:
    """Use a disposable Fiji process so Results-table state cannot leak."""
    root = _fiji_root()
    record = _run_probe(
        textwrap.dedent(
            """
            import json
            from fiji_mcp import bridge, tools

            ij = bridge.get_ij()
            table = ij.ResultsTable.getResultsTable()

            def populate(nan_empty):
                table.reset()
                table.setNaNEmptyCells(nan_empty)
                table.incrementCounter()
                table.addValue("present", 1.0)
                table.addValue("asymmetric", 2.0)
                table.setValue("explicit_nan", 0, float("nan"))
                table.setValue("text", 0, "hello")
                table.setValue(6, 0, 6.0)
                table.incrementCounter()
                table.addValue("present", 3.0)
                table.setValue("text", 1, "")
                return tools.get_results()

            try:
                nan_empty = populate(True)
                zero_empty = populate(False)
                expected_columns = [
                    "present",
                    "asymmetric",
                    "explicit_nan",
                    "text",
                    "",
                    "",
                    "C7",
                ]
                assert nan_empty["columns"] == expected_columns
                assert nan_empty["rows"] == [
                    [1.0, 2.0, "NaN", "hello", None, None, 6.0],
                    [3.0, "NaN", "NaN", "", None, None, "NaN"],
                ]
                assert zero_empty["columns"] == expected_columns
                assert zero_empty["rows"] == [
                    [1.0, 2.0, "NaN", "hello", None, None, 6.0],
                    [3.0, 0.0, 0.0, "", None, None, 0.0],
                ]
                record = {"nan_empty": nan_empty, "zero_empty": zero_empty}
            finally:
                table.reset()

            print(json.dumps(record, sort_keys=True, allow_nan=False))
            """
        ),
        root,
    )

    assert record["nan_empty"]["rows"][1] == [
        3.0,
        "NaN",
        "NaN",
        "",
        None,
        None,
        "NaN",
    ]
    assert record["zero_empty"]["rows"][1] == [3.0, 0.0, 0.0, "", None, None, 0.0]
