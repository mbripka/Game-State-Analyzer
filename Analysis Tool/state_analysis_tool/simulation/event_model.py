"""Runtime event models used by optimized execution paths."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class EventModel:
    """Runtime-optimized event container."""
    id: int
    event_id: str
    max_triggers: int
    times_triggered: int = 0
    requires_sequences_mask: int = 0
    starts_sequences_mask: int = 0
    ends_sequences_mask: int = 0
    conditions: List["ConditionModel"] = field(default_factory=list)
    mutations: List["MutationModel"] = field(default_factory=list)


@dataclass
class ConditionModel:
    """Runtime-optimized condition representation."""
    variable_id: int
    operator_type: int
    int_value: int = 0
    state_value: str = ""
    is_numeric: bool = False


@dataclass
class MutationModel:
    """Runtime-optimized mutation representation."""
    variable_id: int
    is_delta: bool
    delta: int = 0
    is_state: bool = False
    state_value: str = ""


def can_trigger(evt: EventModel) -> bool:
    """Return True if an event can still be triggered."""
    if evt.max_triggers < 0:
        return True
    return evt.times_triggered < evt.max_triggers
