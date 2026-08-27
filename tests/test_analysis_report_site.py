from __future__ import annotations

import stat
from html.parser import HTMLParser
from pathlib import Path

from PIL import Image

REPOSITORY = Path(__file__).resolve().parents[1]
REPORT = REPOSITORY / "website" / "fiji-analysis-report"
SELECTED = ("img00", "img05", "img10", "img14", "img21")


class _ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[str] = []
        self.tbody_depth = 0
        self.tbody_rows = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tbody":
            self.tbody_depth += 1
        elif tag == "tr" and self.tbody_depth:
            self.tbody_rows += 1

        attributes = dict(attrs)
        attribute = "src" if tag in {"img", "script"} else "href"
        value = attributes.get(attribute)
        if value:
            self.paths.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tbody" and self.tbody_depth:
            self.tbody_depth -= 1


def test_page_is_self_contained_and_privacy_safe() -> None:
    index = REPORT / "index.html"
    assert index.is_file()
    parser = _ReportParser()
    parser.feed(index.read_text())

    for value in parser.paths:
        if value.startswith("#"):
            continue
        assert not value.startswith(("http://", "https://", "//", "/")), value
        target = (REPORT / value.split("#", 1)[0]).resolve()
        assert target.is_relative_to(REPORT.resolve()), value
        assert target.is_file(), value

    for path in REPORT.rglob("*"):
        if path.suffix.lower() not in {".html", ".css", ".csv", ".md", ".txt"}:
            continue
        content = path.read_text(errors="replace")
        assert "/private/tmp" not in content, path
        assert "/Users/" not in content, path
        for private_name in ("AGENTS.md", "CLAUDE.md", ".mcp.json", ".codex"):
            assert private_name not in content, path

    css = (REPORT / "assets" / "report.css").read_text().lower()
    assert "http:" not in css
    assert "https:" not in css
    assert "//" not in css


def test_page_has_exactly_five_original_and_red_boundary_pairs() -> None:
    html = (REPORT / "index.html").read_text()
    assert html.count('<figure class="comparison">') == 5

    parser = _ReportParser()
    parser.feed(html)
    image_paths = [value for value in parser.paths if value.endswith(".png")]
    expected = []
    for stem in SELECTED:
        original = f"assets/images/original/{stem}.png"
        analyzed = f"assets/images/analyzed/{stem}.png"
        expected.extend((original, analyzed))
        with (
            Image.open(REPORT / original) as source,
            Image.open(REPORT / analyzed) as result,
        ):
            assert source.size == result.size
            pixels = result.convert("RGB").tobytes()
            red_pixels = sum(
                1
                for offset in range(0, len(pixels), 3)
                if pixels[offset : offset + 3] == b"\xff\x00\x00"
            )
            assert red_pixels > 0
        assert not (REPORT / original).stat().st_mode & stat.S_IXUSR
        assert not (REPORT / analyzed).stat().st_mode & stat.S_IXUSR
    assert image_paths == expected


def test_page_is_minimal_black_cmu_and_red() -> None:
    html = (REPORT / "index.html").read_text()
    lowered_html = html.lower()
    parser = _ReportParser()
    parser.feed(html)
    assert html.count("<h1") == 1
    assert "<h2" not in html
    assert "<h3" not in html
    assert html.count("<p") == 1
    assert parser.tbody_rows == 5
    assert "cell boundaries" not in lowered_html
    assert "detected-object boundaries" in lowered_html
    assert "Thresholded pixels" in html
    assert (
        "percentage of all image pixels selected before object-size filtering" in html
    )
    assert "Foreground" not in html

    for rejected in (
        "primary evidence",
        "label-aware",
        "screenshot comparison",
        "screening plate",
        "threshold and object summary",
        "publication bundle",
        "scientific scope",
        "limitations",
        "method",
    ):
        assert rejected not in lowered_html

    css = (REPORT / "assets" / "report.css").read_text().lower()
    assert 'font-family: "cmu sans"' in css
    assert 'font-family: "cmu typewriter"' in css
    assert "background: #050505" in css
    assert "#ff2b2b" in css
    assert "#ff3bd4" not in css
    assert "#24d8e5" not in css
    for rejected in ("gradient", "box-shadow", "border-radius"):
        assert rejected not in css


def test_only_five_measurement_csv_files_remain() -> None:
    csv_paths = sorted(
        path.relative_to(REPORT).as_posix() for path in REPORT.rglob("*.csv")
    )
    assert csv_paths == [f"data/{stem}.csv" for stem in SELECTED]

    html = (REPORT / "index.html").read_text()
    for stem in SELECTED:
        assert f'href="data/{stem}.csv"' in html

    assert not list(REPORT.rglob("*.zip"))
    assert not list(REPORT.rglob("*.tif"))
    assert not list(REPORT.rglob("*.tiff"))
    assert not list(REPORT.rglob("*.json"))

    fonts = REPORT / "assets" / "fonts"
    for filename in ("cmunss.otf", "cmuntt.otf", "LICENSE.txt"):
        assert (fonts / filename).is_file()
    license_text = (fonts / "LICENSE.txt").read_text()
    assert "Computer Modern Unicode fonts" in license_text
    assert "Andrey V. Panov" in license_text
    assert "Raleway" not in license_text

    expected_files = {
        "index.html",
        "assets/favicon.svg",
        "assets/report.css",
        "assets/fonts/LICENSE.txt",
        "assets/fonts/cmunss.otf",
        "assets/fonts/cmuntt.otf",
        *(f"assets/images/original/{stem}.png" for stem in SELECTED),
        *(f"assets/images/analyzed/{stem}.png" for stem in SELECTED),
        *(f"data/{stem}.csv" for stem in SELECTED),
    }
    actual_files = {
        path.relative_to(REPORT).as_posix()
        for path in REPORT.rglob("*")
        if path.is_file()
    }
    assert actual_files == expected_files
