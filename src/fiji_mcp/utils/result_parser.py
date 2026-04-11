"""Parse macro return strings and log snippets into structured fields."""

from __future__ import annotations

import csv
import json
import re
from io import StringIO
from typing import Any, Literal

FormatHint = Literal["auto", "json", "csv", "key_value", "imagej_table", "numbers_only"]


def _parse_json(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _parse_key_value_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for sep in ("=", ":"):
            if sep in line:
                key, val = line.split(sep, 1)
                k = key.strip()
                v = val.strip()
                if k:
                    out[k] = v
                break
    return out


def _coerce_number(s: str) -> float | int | str:
    t = s.strip()
    if not t:
        return s
    try:
        if "." in t or "e" in t.lower():
            return float(t)
        return int(t)
    except ValueError:
        return s


def _parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        return [], []
    header = [h.strip() for h in rows[0]]
    body: list[dict[str, str]] = []
    for parts in rows[1:]:
        if not any(p.strip() for p in parts):
            continue
        row: dict[str, str] = {}
        for i, h in enumerate(header):
            if not h:
                continue
            row[h] = parts[i].strip() if i < len(parts) else ""
        body.append(row)
    return header, body


def _parse_imagej_table(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Tab-separated table (e.g. Results copy-paste). First row is headings."""
    lines = [ln for ln in (ln.strip("\r") for ln in text.splitlines()) if ln.strip()]
    if not lines:
        return [], []
    header = [c.strip() for c in lines[0].split("\t")]
    body: list[dict[str, str]] = []
    for line in lines[1:]:
        parts = line.split("\t")
        row: dict[str, str] = {}
        for i, h in enumerate(header):
            if not h:
                continue
            row[h] = parts[i].strip() if i < len(parts) else ""
        if any(row.values()):
            body.append(row)
    return header, body


_FLOAT_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _extract_numbers(text: str) -> list[float]:
    found: list[float] = []
    for m in _FLOAT_RE.finditer(text):
        try:
            found.append(float(m.group(0)))
        except ValueError:
            continue
    return found


def parse_macro_output(text: str, format_hint: FormatHint = "auto") -> dict[str, Any]:
    """
    Return a dict with keys: format_detected, json, values, rows, numbers.

    ``values`` maps string keys to int, float, or str where coercion succeeds.
    ``rows`` is a list of row dicts for tabular hints.
    """
    raw = text or ""
    fmt: str = format_hint
    payload: dict[str, Any] = {
        "format_detected": fmt,
        "json": None,
        "values": {},
        "rows": [],
        "numbers": [],
    }

    if format_hint == "json":
        data = _parse_json(raw)
        payload["json"] = data
        payload["format_detected"] = "json"
        return payload

    if format_hint == "key_value":
        kv = _parse_key_value_lines(raw)
        payload["values"] = {k: _coerce_number(v) for k, v in kv.items()}
        payload["format_detected"] = "key_value"
        return payload

    if format_hint == "csv":
        header, rows = _parse_csv(raw)
        payload["rows"] = [{k: _coerce_number(v) for k, v in r.items()} for r in rows]
        payload["format_detected"] = "csv"
        payload["values"] = {"_header": ", ".join(header)} if header else {}
        return payload

    if format_hint == "imagej_table":
        header, rows = _parse_imagej_table(raw)
        payload["rows"] = [{k: _coerce_number(v) for k, v in r.items()} for r in rows]
        payload["format_detected"] = "imagej_table"
        payload["values"] = {"_header": ", ".join(header)} if header else {}
        return payload

    if format_hint == "numbers_only":
        nums = _extract_numbers(raw)
        payload["numbers"] = nums
        payload["format_detected"] = "numbers_only"
        return payload

    # auto
    data = _parse_json(raw)
    if data is not None:
        payload["json"] = data
        payload["format_detected"] = "json"
        return payload

    if "\t" in raw and raw.count("\t") >= raw.count(","):
        header, rows = _parse_imagej_table(raw)
        if header and rows:
            payload["rows"] = [
                {k: _coerce_number(v) for k, v in r.items()} for r in rows
            ]
            payload["values"] = {"_header": ", ".join(header)}
            payload["format_detected"] = "imagej_table"
            return payload

    if "\n" in raw.strip() and "," in raw.splitlines()[0]:
        header, rows = _parse_csv(raw)
        if header and rows:
            payload["rows"] = [
                {k: _coerce_number(v) for k, v in r.items()} for r in rows
            ]
            payload["values"] = {"_header": ", ".join(header)}
            payload["format_detected"] = "csv"
            return payload

    kv = _parse_key_value_lines(raw)
    if kv:
        payload["values"] = {k: _coerce_number(v) for k, v in kv.items()}
        payload["format_detected"] = "key_value"
        return payload

    nums = _extract_numbers(raw)
    payload["numbers"] = nums
    payload["format_detected"] = "numbers_only" if nums else "empty"
    return payload
