"""State model and hashing utilities for exploration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Set, Tuple
from copy import deepcopy


@dataclass
class StateModel:
    """Mutable world state used during exploration."""
    variables: Dict[str, Any] = field(default_factory=dict)
    trigger_counts: Dict[str, int] = field(default_factory=dict)
    active_sequences: int = 0
    parent_state_hash: int | None = None
    causing_event: str | None = None
    depth: int = 0
    eligible_events: Set[str] = field(default_factory=set)

    def apply_delta(self, variable: str, delta: int) -> None:
        """Apply a numeric delta and clamp to allowed range."""
        current = self.variables.get(variable, 0)
        if isinstance(current, (int, float)):
            updated = current + delta
        else:
            updated = delta
        self.variables[variable] = _clamp_int(updated)

    def set_value(self, variable: str, value: Any) -> None:
        """Set a variable value with numeric clamping."""
        if isinstance(value, (int, float)):
            self.variables[variable] = _clamp_int(value)
        else:
            self.variables[variable] = value

    def normalized_hash(self) -> int:
        """Compute a hash of normalized variable values and active sequences."""
        normalized_items: Tuple[Tuple[str, Any], ...] = tuple(
            (key, _normalize_value(self.variables.get(key)))
            for key in sorted(self.variables.keys())
        )
        # domain hashes are kept separate for future domains
        # future:
        # hash_resources
        # hash_flags
        variables_hash = hash(normalized_items)
        normalized_sequences = _normalize_sequences(self.active_sequences)
        hash_progressions = hash(tuple(sorted(normalized_sequences)))
        return hash((variables_hash, hash_progressions))

    def clone(self) -> "StateModel":
        """Create a deep copy of the state."""
        return StateModel(
            variables=deepcopy(self.variables),
            trigger_counts=deepcopy(self.trigger_counts),
            active_sequences=int(self.active_sequences),
            parent_state_hash=self.parent_state_hash,
            causing_event=self.causing_event,
            depth=self.depth,
            eligible_events=set(self.eligible_events),
        )


def _normalize_value(value: Any) -> Any:
    """Normalize numeric values for hashing."""
    if isinstance(value, (int, float)):
        return _clamp_int(value)
    return value


def _normalize_sequences(active_sequences: int) -> Tuple[int, ...]:
    """Normalize active sequence bitmask into a sorted tuple of indices."""
    if active_sequences <= 0:
        return tuple()
    indices = []
    bit_index = 0
    mask = active_sequences
    while mask:
        if mask & 1:
            indices.append(bit_index)
        mask >>= 1
        bit_index += 1
    return tuple(indices)


def _clamp_int(value: Any) -> int:
    """Clamp integer-like values to [0, 100]."""
    if isinstance(value, float):
        value = int(value)
    if isinstance(value, int):
        return max(0, min(100, value))
    return 0
