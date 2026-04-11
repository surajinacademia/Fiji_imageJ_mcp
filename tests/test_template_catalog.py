"""Bundled macro template catalog."""

from importlib import resources

import pytest

from fiji_mcp.utils import template_catalog as tc


@pytest.fixture(autouse=True)
def _clear_template_cache():
    tc._raw_catalog.cache_clear()
    yield
    tc._raw_catalog.cache_clear()


def test_list_and_filter():
    all_t = tc.list_templates()
    assert len(all_t) >= 20
    filt = tc.list_templates(category="filters")
    assert all(str(t["category"]).lower() == "filters" for t in filt)
    plug = tc.list_templates(category="plugins")
    assert any(t.get("id") == "trackmate" for t in plug)


def test_get_by_id():
    row = tc.get_template("gaussian_blur")
    assert row is not None
    assert "Gaussian" in row["macro"]
    split = tc.get_template("split_channels")
    assert split is not None
    assert "Split" in split["macro"]
    assert tc.get_template("no_such_id") is None


def test_bundled_agent_skill_packaged():
    path = resources.files("fiji_mcp.data") / "FIJI_MCP_SKILL.md"
    text = path.read_text(encoding="utf-8")
    assert path.name == "FIJI_MCP_SKILL.md"
    assert "health_check" in text
    assert "search_commands" in text
    assert "stdio" in text.lower()
