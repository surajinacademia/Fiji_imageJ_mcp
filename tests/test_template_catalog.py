"""Bundled macro template catalog."""

import pytest

from fiji_mcp.utils import template_catalog as tc


@pytest.fixture(autouse=True)
def _clear_template_cache():
    tc._raw_catalog.cache_clear()
    yield
    tc._raw_catalog.cache_clear()


def test_list_and_filter():
    all_t = tc.list_templates()
    assert len(all_t) >= 5
    filt = tc.list_templates(category="filters")
    assert all(str(t["category"]).lower() == "filters" for t in filt)


def test_get_by_id():
    row = tc.get_template("gaussian_blur")
    assert row is not None
    assert "Gaussian" in row["macro"]
    assert tc.get_template("no_such_id") is None
