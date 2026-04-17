"""DTO-style event model for loader output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Event:
    """Event DTO containing conditions and effects."""
    event_id: str
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    effects: List[Dict[str, Any]] = field(default_factory=list)
    max_triggers: int | None = None
    requires_sequences: List[str] = field(default_factory=list)
    starts_sequences: List[str] = field(default_factory=list)
    ends_sequences: List[str] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Event":
        """Construct an Event from raw JSON data."""
        event_id = str(data.get("eventID") or data.get("event_id") or data.get("id") or data.get("guid") or "")

        conditions = _normalize_bindings(
            data.get("conditions")
            or data.get("reads")
            or data.get("read")
            or data.get("inputs")
        )
        effects = _normalize_bindings(
            data.get("effects")
            or data.get("mutates")
            or data.get("writes")
            or data.get("write")
            or data.get("outputs")
        )
        requires_sequences = _normalize_sequence_list(data.get("requiresSequences"))
        starts_sequences = _normalize_sequence_list(data.get("startsSequences"))
        ends_sequences = _normalize_sequence_list(data.get("endsSequences"))

        return Event(
            event_id=event_id,
            conditions=conditions,
            effects=effects,
            max_triggers=_parse_int(data.get("maxTriggers") or data.get("max_triggers")),
            requires_sequences=requires_sequences,
            starts_sequences=starts_sequences,
            ends_sequences=ends_sequences,
        )


@dataclass
class InitialState:
    """Initial world state container."""
    variables: Dict[str, Any] = field(default_factory=dict)


def _normalize_bindings(value: Any) -> List[Dict[str, Any]]:
    """Normalize condition/mutation entries into a consistent dict shape."""
    if value is None:
        return []
    if isinstance(value, dict):
        items = [{"name": k, "value": v} for k, v in value.items()]
    elif isinstance(value, list):
        items = value
    else:
        items = [value]

    normalized = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            name = item.get("name") or item.get("variable") or item.get("var")
            if name is None and len(item) == 1:
                key = next(iter(item.keys()))
                name = key
                value = item[key]
            else:
                value = item.get("value")
            if name is None:
                name = str(item)
            name_str = str(name)
            delta = item.get("delta")
            operator = item.get("operator")
            entity_type, entity_id, attribute = _parse_entity_fields(name_str)
            normalized.append(
                {
                    "name": name_str,
                    "value": value,
                    "delta": delta,
                    "operator": operator,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "attribute": attribute,
                }
            )
        else:
            name_str = str(item)
            entity_type, entity_id, attribute = _parse_entity_fields(name_str)
            normalized.append(
                {
                    "name": name_str,
                    "value": None,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "attribute": attribute,
                }
            )
    return normalized


def _parse_entity_fields(name: str) -> tuple[str | None, str | None, str | None]:
    """Split a dotted variable name into entity fields."""
    if not name:
        return None, None, None
    parts = name.split(".")
    if len(parts) >= 3:
        return parts[0], parts[1], ".".join(parts[2:])
    if len(parts) == 2:
        return parts[0], None, parts[1]
    return None, None, parts[0]


def _parse_int(value: Any) -> int | None:
    """Parse integer values from JSON fields."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _normalize_sequence_list(value: Any) -> List[str]:
    """Normalize sequence lists into strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]
