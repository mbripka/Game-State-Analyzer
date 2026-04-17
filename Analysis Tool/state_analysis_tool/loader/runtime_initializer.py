"""Initialize runtime state from the runtime_state event."""

from __future__ import annotations

from typing import Any, Dict

from .event_model import Event


def build_initial_state(runtime_event: Event | None) -> Dict[str, Any]:
    """Build initial state variables from the runtime_state event."""
    state: Dict[str, Any] = {}
    if runtime_event is None:
        return state

    for mutation in runtime_event.effects:
        name = mutation.get("name")
        if name is None:
            continue

        has_value = "value" in mutation and mutation.get("value") not in (None, "")
        has_delta = "delta" in mutation and mutation.get("delta") is not None

        if has_value:
            state[str(name)] = mutation.get("value")
        elif has_delta:
            if str(name) not in state:
                state[str(name)] = mutation.get("delta")
        else:
            print(f"Warning: runtime_state mutation missing value/delta for variable '{name}'")

    return state
