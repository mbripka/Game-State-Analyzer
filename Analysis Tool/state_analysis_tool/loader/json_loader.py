"""JSON loader and validation utilities for Unity-exported events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .event_model import Event
from .value_normalizer import normalize_value


def load_events(path: str | Path, allow_casting: bool = False) -> Tuple[Optional[Event], List[Event]]:
    """Load events from JSON and optionally cast condition values in memory."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    _assert_no_floats(data)
    if allow_casting:
        _cast_condition_values_in_data(data)

    events_data = _extract_events(data)
    runtime_event_data: Optional[Dict[str, Any]] = None
    normal_events_data: List[Dict[str, Any]] = []

    for event in events_data:
        event_id = str(event.get("eventID") or event.get("event_id") or event.get("id") or event.get("guid") or "")
        if event_id == "runtime_state":
            runtime_event_data = event
        else:
            normalized = _normalize_event_values(event)
            normal_events_data.append(normalized)

    runtime_event = Event.from_dict(runtime_event_data) if runtime_event_data else None
    normal_events = [Event.from_dict(item) for item in normal_events_data]

    return runtime_event, normal_events


def _normalize_event_values(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize event fields used by downstream processing."""
    # if "conditions" in event:
    #     event["conditions"] = _normalize_conditions_list(event.get("conditions"))
    if "mutates" in event:
        event["mutates"] = _normalize_mutates_list(event.get("mutates"))
    return event


def _normalize_conditions_list(value: Any) -> Any:
    """Normalize condition values when conversion is enabled."""
    if value is None:
        return value
    if isinstance(value, list):
        normalized = []
        for item in value:
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            item = dict(item)
            if "value" in item:
                item["value"] = _normalize_conditions_value(item["value"])
            normalized.append(item)
        return normalized
    if isinstance(value, dict):
        normalized = {}
        for k, v in value.items():
            normalized[k] = _normalize_conditions_value(v)
        return normalized
    return value


def _normalize_mutates_list(value: Any) -> Any:
    """Normalize mutation values and deltas."""
    if value is None:
        return value
    if isinstance(value, list):
        normalized = []
        for item in value:
            if not isinstance(item, dict):
                normalized.append(item)
                continue
            item = dict(item)
            variable_name = item.get("variable") or item.get("name") or item.get("var")
            if "value" in item and item["value"] not in (None, ""):
                item["value"] = _normalize_selected_value(item["value"], variable_name)
            if "delta" in item and item["delta"] is not None:
                item["delta"] = _normalize_selected_value(item["delta"], variable_name)
            normalized.append(item)
        return normalized
    if isinstance(value, dict):
        normalized = {}
        for k, v in value.items():
            normalized[k] = normalize_value(v)
        return normalized
    return value


def _select_value(entry: Dict[str, Any]) -> Any:
    """Select value if present; otherwise use delta."""
    value = entry.get("value")
    if value != "":
        return value
    return entry.get("delta")


def _normalize_selected_value(value: Any, variable_name: Any) -> Any:
    """Normalize selected values."""
    normalized = normalize_value(value)
    if isinstance(normalized, float) and normalized.is_integer():
        return int(normalized)
    return normalized


def _normalize_conditions_value(value: Any) -> Any:
    """Normalize a condition value for numeric comparison."""
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
            as_float = float(text)
        except ValueError:
            return value
        if as_float.is_integer():
            return int(as_float)
        return value
    if isinstance(value, int):
        return value
    return value


def cast_condition_values_in_data(data: Any) -> List[Tuple[str, Any, Any]]:
    """Cast raw JSON condition values to int when possible."""
    events = _extract_events(data)
    warnings: List[Tuple[str, Any, Any]] = []
    for event in events:
        if "conditions" in event:
            casted, new_warnings = _cast_conditions_list(event.get("conditions"))
            event["conditions"] = casted
            warnings.extend(new_warnings)
    return warnings


def _cast_conditions_list(value: Any) -> Tuple[Any, List[Tuple[str, Any, Any]]]:
    """Cast a list/dict of condition values to int when possible."""
    warnings: List[Tuple[str, Any, Any]] = []
    if value is None:
        return value, warnings
    if isinstance(value, list):
        updated = []
        for item in value:
            if not isinstance(item, dict):
                updated.append(item)
                continue
            item = dict(item)
            if "value" in item:
                variable_name = item.get("variable") or item.get("name") or item.get("var")
                item["value"], warning = _cast_int_value(item["value"], variable_name)
                if warning:
                    warnings.append(warning)
            updated.append(item)
        return updated, warnings
    if isinstance(value, dict):
        updated = {}
        for k, v in value.items():
            updated[k], warning = _cast_int_value(v, k)
            if warning:
                warnings.append(warning)
        return updated, warnings
    return value, warnings


def _cast_int_value(value: Any, variable_name: Any) -> Tuple[Any, Tuple[str, Any, Any] | None]:
    """Cast an integer literal string to int and collect warnings on type change."""
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            try:
                int_value = int(text)
                return int_value, (str(variable_name), value, int_value)
            except ValueError:
                return value, None
    return value, None


def _extract_events(data: Any) -> List[Dict[str, Any]]:
    """Extract event dictionaries from supported JSON shapes."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if "events" in data and isinstance(data["events"], list):
            return [item for item in data["events"] if isinstance(item, dict)]
        for value in data.values():
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return value
    return []


def _assert_no_floats(data: Any) -> None:
    """Abort if any condition or mutation includes float values."""
    events = _extract_events(data)
    for event in events:
        event_id = str(event.get("eventID") or event.get("event_id") or event.get("id") or "")
        for cond in event.get("conditions", []) or []:
            if isinstance(cond, dict) and isinstance(cond.get("value"), float):
                raise ValueError(
                    "Error: float value found in condition; "
                    f"event '{event_id}', variable '{cond.get('variable') or cond.get('name')}', "
                    f"value={cond.get('value')}"
                )
        for mut in event.get("mutates", []) or []:
            if isinstance(mut, dict):
                if isinstance(mut.get("value"), float):
                    raise ValueError(
                        "Error: float value found in mutation value; "
                        f"event '{event_id}', variable '{mut.get('variable') or mut.get('name')}', "
                        f"value={mut.get('value')}"
                    )
                if isinstance(mut.get("delta"), float):
                    raise ValueError(
                        "Error: float value found in mutation delta; "
                        f"event '{event_id}', variable '{mut.get('variable') or mut.get('name')}', "
                        f"delta={mut.get('delta')}"
                    )


def _cast_condition_values_in_data(data: Any) -> None:
    """Deprecated wrapper retained for backward compatibility."""
    cast_condition_values_in_data(data)
