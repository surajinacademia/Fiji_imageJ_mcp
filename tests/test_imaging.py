"""Deterministic PNG rendering and stateless screenshot comparison tests."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from fiji_mcp import _minimal_tools as minimal
from fiji_mcp import imaging
from fiji_mcp.bridge import FijiError, Outcome
from fiji_mcp.imaging import (
    RenderedPNG,
    compare_paths,
    fit_within,
    render_active_image,
    render_results,
)


def _png_bytes(result: Any) -> bytes:
    """Return the sole native MCP image payload as decoded PNG bytes."""
    assert len(result.content) == 1
    content = result.content[0]
    assert content.type == "image"
    assert content.mimeType == "image/png"
    return base64.b64decode(content.data)


def _decode_png(result: Any) -> Image.Image:
    data = _png_bytes(result)
    decoded = Image.open(io.BytesIO(data))
    assert decoded.format == "PNG"
    return decoded


class FakeWindowManager:
    def __init__(self, active: object | None) -> None:
        self._active = active

    def getCurrentImage(self) -> object | None:
        return self._active


class FakeIJ:
    def __init__(
        self, active: object | None = None, results: object | None = None
    ) -> None:
        self.WindowManager = FakeWindowManager(active)
        self.ResultsTable = FakeResultsTableClass(results)


class FakeResultsTable:
    def __init__(self, headings: list[str], rows: list[list[object]]) -> None:
        self._headings = headings
        self._rows = rows
        self.requested_cells: list[tuple[int, int]] = []

    def getLastColumn(self) -> int:
        return len(self._headings) - 1

    def getColumnHeading(self, column: int) -> str:
        return self._headings[column]

    def getStringValue(self, column: int, row: int) -> str | None:
        value = self._rows[row][column]
        return value if isinstance(value, str) else None

    def getValueAsDouble(self, column: int, row: int) -> object:
        self.requested_cells.append((column, row))
        return self._rows[row][column]

    def size(self) -> int:
        return len(self._rows)


class FakeResultsTableClass:
    def __init__(self, results: object | None) -> None:
        self._results = results

    def getResultsTable(self) -> object | None:
        return self._results


class FakeImagePlus:
    def __init__(self) -> None:
        self.flatten_calls = 0

    def getC(self) -> int:
        return 2

    def getZ(self) -> int:
        return 3

    def getT(self) -> int:
        return 4

    def getOverlay(self) -> object:
        return object()

    def getRoi(self) -> object:
        return object()

    def flatten(self) -> object:
        self.flatten_calls += 1
        raise AssertionError("rendering must not flatten the source image")


class FakeCurrentPlane:
    def __init__(self) -> None:
        self.flatten_calls = 0
        self.buffered_image = object()

    def flatten(self) -> FakeCurrentPlane:
        self.flatten_calls += 1
        return self

    def getBufferedImage(self) -> object:
        return self.buffered_image


def test_fit_within_never_enlarges() -> None:
    assert fit_within(Image.new("RGB", (10, 20)), 2048).size == (10, 20)
    assert fit_within(Image.new("RGB", (4096, 2048)), 2048).size == (2048, 1024)


def test_results_render_is_deterministic_and_marks_omissions() -> None:
    first = render_results(["Area", "Mean"], [[1, 2]] * 101, total_rows=101)
    second = render_results(["Area", "Mean"], [[1, 2]] * 101, total_rows=101)

    assert first.png == second.png
    assert first.metadata["rendered_rows"] == 100
    assert first.metadata["omitted_rows"] == 1


def test_equal_images_return_zero_metrics_and_three_panels(tmp_path: Path) -> None:
    path = tmp_path / "same.png"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(path)

    result = compare_paths(path, path)

    assert result.metadata["mae"] == 0.0
    assert result.metadata["rmse"] == 0.0
    assert result.metadata["changed_pixel_fraction"] == 0.0
    assert result.metadata["panels"] == ["before", "after", "absolute_difference"]


def test_one_level_change_counts_as_changed(tmp_path: Path) -> None:
    before = np.zeros((2, 2, 3), dtype=np.uint8)
    after = before.copy()
    after[0, 0, 0] = 1
    Image.fromarray(before).save(tmp_path / "before.png")
    Image.fromarray(after).save(tmp_path / "after.png")

    result = compare_paths(tmp_path / "before.png", tmp_path / "after.png")

    assert result.metadata["mae"] == pytest.approx(1 / (2 * 2 * 3 * 255))
    assert result.metadata["rmse"] == pytest.approx(np.sqrt(1 / 12) / 255)
    assert result.metadata["changed_pixel_fraction"] == 0.25


def test_different_sizes_omit_metrics_and_difference_panel(tmp_path: Path) -> None:
    Image.new("RGB", (8, 6)).save(tmp_path / "before.png")
    Image.new("RGB", (9, 6)).save(tmp_path / "after.png")

    result = compare_paths(tmp_path / "before.png", tmp_path / "after.png")

    assert result.metadata["dimensions_match"] is False
    assert "mae" not in result.metadata
    assert "rmse" not in result.metadata
    assert "changed_pixel_fraction" not in result.metadata
    assert result.metadata["panels"] == ["before", "after"]


def test_render_active_image_flattens_only_a_current_plane_view(monkeypatch) -> None:
    source = FakeImagePlus()
    plane = FakeCurrentPlane()
    calls: list[tuple[object, int, int, int]] = []

    def duplicate_current_plane(
        image: object, c: int, z: int, t: int
    ) -> FakeCurrentPlane:
        calls.append((image, c, z, t))
        return plane

    monkeypatch.setattr(imaging, "_duplicate_current_plane", duplicate_current_plane)
    monkeypatch.setattr(
        imaging,
        "_buffered_image_to_pil",
        lambda buffered: Image.new("RGB", (4096, 2048), (10, 20, 30)),
    )

    result = render_active_image(FakeIJ(active=source))

    assert calls == [(source, 2, 3, 4)]
    assert source.flatten_calls == 0
    assert plane.flatten_calls == 1
    assert result.width == 2048
    assert result.height == 1024
    assert result.metadata["current_c"] == 2
    assert result.metadata["current_z"] == 3
    assert result.metadata["current_t"] == 4
    assert result.metadata["overlay_present"] is True
    assert result.metadata["roi_present"] is True


def test_screenshot_active_image_returns_bounded_native_png_and_saves_exact_bytes(
    monkeypatch, tmp_path: Path
) -> None:
    source = FakeImagePlus()
    plane = FakeCurrentPlane()
    output = tmp_path / "nested" / "active.png"
    monkeypatch.setattr(imaging, "_duplicate_current_plane", lambda *_args: plane)
    monkeypatch.setattr(
        imaging,
        "_buffered_image_to_pil",
        lambda buffered: Image.new("RGB", (4096, 2048), (10, 20, 30)),
    )
    monkeypatch.setattr(minimal, "run_read", lambda _name, fn: fn(FakeIJ(source)))

    result = minimal.screenshot("active_image", str(output))

    decoded = _decode_png(result)
    png = _png_bytes(result)
    assert decoded.width <= 2048
    assert decoded.height <= 2048
    assert output.read_bytes() == png
    assert result.structured_content["save_path"] == str(output.resolve())


def test_screenshot_results_reads_first_100_live_rows_in_original_order(
    monkeypatch, tmp_path: Path
) -> None:
    headings = ["Area", "", "Area"]
    rows = [[row, f"cell-{row}", row + 0.5] for row in range(101)]
    table = FakeResultsTable(headings, rows)
    output = tmp_path / "nested" / "results.png"
    monkeypatch.setattr(
        minimal, "run_read", lambda _name, fn: fn(FakeIJ(results=table))
    )

    result = minimal.screenshot("results", str(output))

    decoded = _decode_png(result)
    assert decoded.width <= 2048
    assert decoded.height <= 2048
    assert result.structured_content["columns"] == headings
    assert result.structured_content["total_rows"] == 101
    assert result.structured_content["rendered_rows"] == 100
    assert result.structured_content["omitted_rows"] == 1
    assert table.requested_cells == [
        (column, row) for row in range(100) for column in range(3)
    ]
    assert output.read_bytes() == _png_bytes(result)


def test_screenshot_results_bounds_a_wide_render(monkeypatch) -> None:
    table = FakeResultsTable(["wide" * 1_000], [["value"]])
    monkeypatch.setattr(
        minimal, "run_read", lambda _name, fn: fn(FakeIJ(results=table))
    )

    result = minimal.screenshot("results")
    decoded = _decode_png(result)

    assert decoded.width <= 2048
    assert decoded.height <= 2048


def test_compare_screenshots_is_pure_local_io_and_saves_exact_bytes(
    monkeypatch, tmp_path: Path
) -> None:
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    output = tmp_path / "nested" / "comparison.png"
    Image.new("RGB", (8, 6), (1, 2, 3)).save(before_path)
    Image.new("RGB", (8, 6), (1, 2, 4)).save(after_path)
    monkeypatch.setattr(
        minimal,
        "run_read",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Fiji was initialized")),
    )

    result = minimal.compare_screenshots(str(before_path), str(after_path), str(output))

    decoded = _decode_png(result)
    assert decoded.width <= 2048
    assert decoded.height <= 2048
    assert output.read_bytes() == _png_bytes(result)
    assert result.structured_content["save_path"] == str(output.resolve())


@pytest.mark.parametrize("target", ["full_screen", None, []])
def test_screenshot_rejects_invalid_target_before_acquiring_fiji(
    monkeypatch, target: object
) -> None:
    monkeypatch.setattr(
        minimal,
        "run_read",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Fiji was initialized")),
    )

    with pytest.raises(
        FijiError, match="target must be active_image or results"
    ) as raised:
        minimal.screenshot(target)  # type: ignore[arg-type]

    assert raised.value.code == "invalid_target"
    assert raised.value.outcome is Outcome.FAILED


def test_screenshot_rejects_a_directory_save_path_before_acquiring_fiji(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        minimal,
        "run_read",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Fiji was initialized")),
    )

    with pytest.raises(FijiError, match="Output path is a directory") as raised:
        minimal.screenshot("results", str(tmp_path))

    assert raised.value.code == "invalid_path"
    assert raised.value.outcome is Outcome.FAILED


@pytest.mark.parametrize(
    ("name", "contents", "expected_code"),
    [
        ("missing.png", None, "missing_file"),
        ("not-image.png", b"not a PNG", "unreadable_image"),
    ],
)
def test_compare_paths_rejects_invalid_inputs_before_metrics(
    monkeypatch, tmp_path: Path, name: str, contents: bytes | None, expected_code: str
) -> None:
    path = tmp_path / name
    if contents is not None:
        path.write_bytes(contents)
    monkeypatch.setattr(
        imaging.np,
        "asarray",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("metrics were computed")
        ),
    )

    with pytest.raises(FijiError) as raised:
        compare_paths(path, path)

    assert raised.value.code == expected_code
    assert raised.value.outcome is Outcome.FAILED


def test_compare_screenshots_rejects_non_image_before_metrics(
    monkeypatch, tmp_path: Path
) -> None:
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    Image.new("RGB", (2, 2)).save(before_path)
    after_path.write_bytes(b"not a PNG")
    monkeypatch.setattr(
        imaging.np,
        "asarray",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("metrics were computed")
        ),
    )

    with pytest.raises(FijiError) as raised:
        minimal.compare_screenshots(str(before_path), str(after_path))

    assert raised.value.code == "unreadable_image"
    assert raised.value.outcome is Outcome.FAILED


def test_rendered_png_is_an_immutable_value_object() -> None:
    rendered = RenderedPNG(b"png", 1, 1, {"target": "results"})

    with pytest.raises(AttributeError):
        rendered.width = 2  # type: ignore[misc]
