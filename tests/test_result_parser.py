"""Tests for macro / measurement text parsing."""

from fiji_mcp.utils.result_parser import parse_macro_output


def test_auto_json_object():
    out = parse_macro_output('{"count": 3, "mean": 1.5}', "auto")
    assert out["format_detected"] == "json"
    assert out["json"] == {"count": 3, "mean": 1.5}


def test_key_value_forced():
    out = parse_macro_output("cells=47\nmean_intensity=120.5", "key_value")
    assert out["format_detected"] == "key_value"
    assert out["values"]["cells"] == 47
    assert out["values"]["mean_intensity"] == 120.5


def test_imagej_table_auto():
    text = "Area\tMean\n100\t55.2\n200\t60.0\n"
    out = parse_macro_output(text, "auto")
    assert out["format_detected"] == "imagej_table"
    assert len(out["rows"]) == 2
    assert out["rows"][0]["Area"] == 100


def test_numbers_only():
    out = parse_macro_output("The count is 42 particles (p<0.05)", "numbers_only")
    assert out["format_detected"] == "numbers_only"
    assert 42.0 in out["numbers"]
    assert 0.05 in out["numbers"]
