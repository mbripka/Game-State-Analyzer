"""Schema validation helpers for event-level JSON keys."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def validate_event_schema_fields(schema_path: str | Path, events_json: Any) -> List[str]:
    """Return event-level keys missing from the schema text."""
    schema_text = Path(schema_path).read_text(encoding="utf-8")
    events = _extract_events(events_json)

    # Event-level keys to check if present in JSON but missing in schema
    event_level_keys: Set[str] = set()
    for event in events:
        for key in event.keys():
            if key in {"conditions", "mutates"}:
                continue
            event_level_keys.add(key)

    missing = []
    for key in sorted(event_level_keys):
        if key not in schema_text:
            missing.append(key)
    return missing


def _extract_events(data: Any) -> List[Dict[str, Any]]:
    """Extract events from supported JSON shapes."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if "events" in data and isinstance(data["events"], list):
            return [item for item in data["events"] if isinstance(item, dict)]
        for value in data.values():
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return value
    return []
