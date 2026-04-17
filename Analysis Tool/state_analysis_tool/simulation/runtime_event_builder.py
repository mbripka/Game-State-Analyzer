"""Build runtime event representations and sequence registries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..loader.event_model import Event
from ..reporting.logger import is_debug


@dataclass(frozen=True)
class RuntimeEvent:
    """Runtime event with sequence bitmasks."""
    event_id: str
    requires_sequences_mask: int
    starts_sequences_mask: int
    ends_sequences_mask: int


def build_mask(sequences: List[str] | None, registry: Dict[str, int]) -> int:
    """Build a bitmask from a sequence list using the registry."""
    if not sequences:
        return 0

    mask = 0
    for sequence in sequences:
        normalized = str(sequence).strip().lower()
        if normalized == "":
            continue
        if normalized not in registry:
            print(f"Warning: sequence '{sequence}' not found in registry")
            continue
        mask |= 1 << registry[normalized]

    return mask


def build_sequence_registry(events: List[Event]) -> Dict[str, int]:
    """Create a registry mapping sequence names to bit positions."""
    sequences: set[str] = set()
    for event in events:
        for seq in (event.requires_sequences + event.starts_sequences + event.ends_sequences):
            normalized = str(seq).strip().lower()
            if normalized == "":
                continue
            sequences.add(normalized)
    ordered = sorted(sequences)
    return {name: index for index, name in enumerate(ordered)}


def convert_events(dtos: List[Event], registry: Dict[str, int]) -> List[RuntimeEvent]:
    """Convert Event DTOs into RuntimeEvent objects with masks."""
    runtime_events: List[RuntimeEvent] = []
    for dto in dtos:
        event_id = getattr(dto, "event_id", None)
        if event_id is None or str(event_id).strip() == "":
            if is_debug():
                print("Warning: event with missing event_id encountered during conversion")

        requires_sequences = getattr(dto, "requires_sequences", None)
        starts_sequences = getattr(dto, "starts_sequences", None)
        ends_sequences = getattr(dto, "ends_sequences", None)

        def _normalize_list(values: List[str] | None) -> List[str]:
            if not values:
                return []
            normalized_values: List[str] = []
            for value in values:
                normalized = str(value).strip().lower()
                if normalized == "":
                    continue
                normalized_values.append(normalized)
            return normalized_values

        normalized_requires = _normalize_list(requires_sequences)
        if len(set(normalized_requires)) != len(normalized_requires):
            if is_debug():
                print(
                    f"Warning: event '{event_id}' has duplicate requiresSequences after normalization"
                )

        normalized_starts = set(_normalize_list(starts_sequences))
        normalized_ends = set(_normalize_list(ends_sequences))
        overlap = normalized_starts.intersection(normalized_ends)
        if overlap:
            if is_debug():
                print(
                    f"Warning: event '{event_id}' has sequences in both startsSequences and endsSequences: "
                    + ", ".join(sorted(overlap))
                )

        runtime_events.append(
            RuntimeEvent(
                event_id=str(event_id) if event_id is not None else "",
                requires_sequences_mask=build_mask(requires_sequences, registry),
                starts_sequences_mask=build_mask(starts_sequences, registry),
                ends_sequences_mask=build_mask(ends_sequences, registry),
            )
        )

    return runtime_events
