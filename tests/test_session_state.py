"""Session trace utilities."""

from fiji_mcp.utils import session_state as ss


def setup_function() -> None:
    ss.clear_tool_events()


def test_log_and_retrieve_order():
    ss.log_tool_event("run_macro", "run('Measure');", {"k": "v"})
    ss.log_tool_event("open_image", "/tmp/a.tif", {})
    events = ss.get_tool_events(limit=10)
    assert len(events) == 2
    assert events[0]["tool"] == "run_macro"
    assert events[1]["tool"] == "open_image"
    assert events[0]["seq"] < events[1]["seq"]


def test_clear():
    ss.log_tool_event("a", "b", {})
    n = ss.clear_tool_events()
    assert n == 1
    assert ss.get_tool_events() == []


def test_clear_resets_sequence():
    ss.log_tool_event("first", "x", {})
    assert ss.get_tool_events()[-1]["seq"] >= 1
    ss.clear_tool_events()
    ss.log_tool_event("after_clear", "y", {})
    events = ss.get_tool_events()
    assert len(events) == 1
    assert events[0]["seq"] == 1
