"""Condition evaluation helpers for runtime eligibility checks."""

from __future__ import annotations

from typing import Any, Dict


def condition_is_met(condition: Dict[str, Any], actual: Any) -> bool:
    """Evaluate a single condition against an actual value."""
    expected = condition.get("value")
    operator = condition.get("operator") or "="
    if expected is None:
        return actual is not None
    if isinstance(expected, int) and isinstance(actual, (int, float)):
        actual_num = int(actual)
        if operator == "=":
            return actual_num == expected
        if operator == "<":
            return actual_num < expected
        if operator == "<=":
            return actual_num <= expected
        if operator == ">=":
            return actual_num >= expected
        if operator == ">":
            return actual_num > expected
        return actual_num == expected
    if operator not in ("=", "=="):
        return False
    return actual == expected
