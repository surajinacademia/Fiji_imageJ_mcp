"""Load curated macro snippets shipped with the package."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=1)
def _raw_catalog() -> dict[str, Any]:
    text = (
        resources.files("fiji_mcp.data")
        .joinpath("macro_templates.json")
        .read_text(encoding="utf-8")
    )
    return json.loads(text)


def list_templates(*, category: str | None = None) -> list[dict[str, Any]]:
    items = list(_raw_catalog().get("templates", []))
    if category:
        c = category.strip().lower()
        items = [t for t in items if str(t.get("category", "")).lower() == c]
    return items


def get_template(template_id: str) -> dict[str, Any] | None:
    tid = template_id.strip()
    for t in _raw_catalog().get("templates", []):
        if str(t.get("id", "")) == tid:
            return dict(t)
    return None
