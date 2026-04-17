"""Event eligibility checks and execution logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Tuple

from .state_model import StateModel
from .condition_evaluator import condition_is_met
from ..loader.event_model import Event


@dataclass
class ExecutionResult:
    """Result of applying an event to a state."""
    state: StateModel
    applied: bool


def event_is_eligible(event: Event, state: StateModel) -> bool:
    """Check whether an event is eligible in the given state."""
    if event.max_triggers is not None:
        if state.trigger_counts.get(event.event_id, 0) >= event.max_triggers:
            return False

    for condition in event.conditions:
        name = condition.get("name")
        if name is None:
            return False
        actual = state.variables.get(name)
        if not condition_is_met(condition, actual):
            return False
    return True


def execute_event(event: Event, state: StateModel) -> Tuple[StateModel, Set[str]]:
    """Execute an event and return the new state and changed variables."""
    new_state = state.clone()
    changed_vars: Set[str] = set()
    if not event_is_eligible(event, state):
        return new_state, changed_vars

    changed_any = False
    for mutation in event.effects:
        name = mutation.get("name")
        if name is None:
            continue
        before = new_state.variables.get(name)
        value = mutation.get("value")
        delta = mutation.get("delta")
        if _is_state_string(value):
            new_state.set_value(name, value)
        elif delta is not None:
            new_state.apply_delta(name, int(delta))
        elif value not in (None, ""):
            new_state.set_value(name, value)
        after = new_state.variables.get(name)
        if before != after:
            changed_vars.add(str(name))
            changed_any = True

    if changed_any:
        new_state.trigger_counts[event.event_id] = new_state.trigger_counts.get(event.event_id, 0) + 1
    return new_state, changed_vars


def apply_event(state: StateModel, event: Event) -> ExecutionResult:
    """Apply an event and return whether it produced changes."""
    new_state, _ = execute_event(event, state)
    return ExecutionResult(state=new_state, applied=new_state.variables != state.variables)


def _is_state_string(value: object) -> bool:
    """Return True when a mutation value is a non-numeric state string."""
    return isinstance(value, str) and value != "" and not value.strip().lstrip("-").replace(".", "", 1).isdigit()
