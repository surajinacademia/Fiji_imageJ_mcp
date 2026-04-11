"""Unit tests for discovery-layer behaviors without a live Fiji runtime."""

from __future__ import annotations

import pytest

from fiji_mcp.tools import discovery


def test_search_commands_empty_query_raises() -> None:
    with pytest.raises(Exception):
        discovery.search_commands("")


def test_search_commands_uses_keyword_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        discovery,
        "_collect_commands",
        lambda: [
            {
                "name": "Analyze Particles...",
                "class_name": "ij.plugin.filter.ParticleAnalyzer",
                "menu_path": "Analyze",
                "source": "Menus",
            },
            {
                "name": "Gaussian Blur...",
                "class_name": "ij.plugin.filter.GaussianBlur",
                "menu_path": "Process",
                "source": "Menus",
            },
        ],
    )
    result = discovery.search_commands("particles", limit=10)
    assert result.ok is True
    assert result.total_matches == 1
    assert result.matches[0].name == "Analyze Particles..."
