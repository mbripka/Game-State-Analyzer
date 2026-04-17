"""Value normalization helpers for JSON parsing."""

from __future__ import annotations

from typing import Any


def normalize_value(value: Any) -> Any:
    """Normalize numeric-looking values to ints/floats where possible."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return value
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            try:
                return int(text)
            except ValueError:
                return value
        try:
            return float(text)
        except ValueError:
            return value
    return value
