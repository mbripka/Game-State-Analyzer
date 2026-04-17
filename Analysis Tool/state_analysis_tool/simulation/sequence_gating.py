"""Sequence gating utilities for runtime eligibility and updates."""

from __future__ import annotations

from typing import Any

from ..reporting.logger import debug, warn


def is_event_eligible(evt: Any, current_active_sequences: int) -> bool:
    """Check whether an event is eligible given active sequence masks."""
    if evt.requires_sequences_mask == 0:
        return True
    if current_active_sequences == 0:
        return False
    return (evt.requires_sequences_mask & current_active_sequences) != 0


def apply_sequence_effects(evt: Any, current_active_sequences: int) -> int:
    """Apply sequence start/end masks and return updated active mask."""
    event_id = getattr(evt, "event_id", "")
    starts_mask = evt.starts_sequences_mask
    ends_mask = evt.ends_sequences_mask
    if (starts_mask & ends_mask) != 0:
        warn(
            "Warning: event "
            f"'{event_id}' starts and ends the same sequence(s): {starts_mask & ends_mask}"
        )
    current_active_sequences |= evt.starts_sequences_mask
    current_active_sequences &= ~evt.ends_sequences_mask
    if current_active_sequences < 0:
        warn(
            "Error: currentActiveSequences became negative after event "
            f"'{event_id}': {current_active_sequences}"
        )
    debug(
        "Sequence gating: event "
        f"'{event_id}' startsMask={starts_mask} endsMask={ends_mask} "
        f"resultActive={current_active_sequences}"
    )
    return current_active_sequences


def process_sequence_gating(evt: Any, current_active_sequences: int) -> tuple[bool, int]:
    """Check eligibility and apply sequence effects if allowed."""
    if not is_event_eligible(evt, current_active_sequences):
        return False, current_active_sequences
    updated_sequences = apply_sequence_effects(evt, current_active_sequences)
    return True, updated_sequences
