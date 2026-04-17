"""State-space exploration using DFS over runtime states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Set, Tuple

from .state_model import StateModel
from .event_executor import event_is_eligible, execute_event
from .sequence_gating import is_event_eligible as sequence_is_event_eligible
from .sequence_gating import apply_sequence_effects
from ..loader.event_model import Event
from .runtime_event_builder import RuntimeEvent
from ..reporting.logger import debug as log_debug, is_debug as logger_is_debug, color as log_color


MAX_DEPTH_LIMIT = 50


@dataclass
class ExplorationResult:
    """Result bundle for DFS exploration."""
    visited_states: Dict[int, StateModel]
    reachable_events: Set[str]
    max_depth: int
    transition_log: List[Tuple[int, str, int]]


def explore_states(
    initial_state: StateModel,
    events: List[Event],
    read_index: Dict[str, Set[str]],
    runtime_events: Dict[str, RuntimeEvent] | None = None,
    sequence_registry: Dict[str, int] | None = None,
    max_depth_limit: int = MAX_DEPTH_LIMIT,
    performance_mode: bool = False,
    progress_every: int | None = None,
    max_states_limit: int | None = None,
    quiet: bool = False,
    dev_mode: bool = False,
    transition_log_limit: int | None = None,
    state_snapshot_limit: int | None = None,
) -> ExplorationResult:
    """Explore reachable states using DFS and sequence gating."""
    visited_hashes: Set[int] = set()
    state_registry: Dict[int, StateModel] = {}
    state_registry_order: List[int] = []
    eligibility_cache: Dict[int, Set[str]] = {}
    reachable_events: Set[str] = set()
    transition_log: List[Tuple[int, str, int]] = []
    max_depth = 0
    transitions = 0
    next_state_index = 0
    state_index_by_hash: Dict[int, int] = {}
    last_reachable_event: str | None = None
    last_reachable_state: StateModel | None = None
    deepest_state: StateModel | None = None
    deepest_event: str | None = None

    sequence_names_by_bit = _invert_sequence_registry(sequence_registry or {})

    sorted_events = sorted(events, key=lambda e: e.event_id)
    event_by_id = {event.event_id: event for event in sorted_events}
    runtime_by_id = runtime_events or {}

    def _set_last_reachable(event_id: str, state: StateModel) -> None:
        nonlocal last_reachable_event
        nonlocal last_reachable_state
        last_reachable_event = event_id
        last_reachable_state = state.clone()

    def _visit(state: StateModel, depth: int) -> None:
        nonlocal max_depth
        nonlocal transitions
        nonlocal next_state_index
        nonlocal deepest_state
        nonlocal deepest_event
        if depth > max_depth_limit:
            return
        state_hash = state.normalized_hash()
        if state_hash in visited_hashes:
            return
        visited_hashes.add(state_hash)
        if state_hash not in state_index_by_hash:
            state_index_by_hash[state_hash] = next_state_index
            next_state_index += 1
        if not dev_mode or state_snapshot_limit:
            state_registry[state_hash] = state
            state_registry_order.append(state_hash)
            if state_snapshot_limit and len(state_registry_order) > state_snapshot_limit:
                oldest = state_registry_order.pop(0)
                state_registry.pop(oldest, None)
        if depth > max_depth:
            max_depth = depth
            deepest_state = state.clone()
            deepest_event = state.causing_event
        if max_states_limit is not None and len(visited_hashes) >= max_states_limit:
            return
        if progress_every and not quiet and len(visited_hashes) % progress_every == 0:
            print(
                f"DFS progress: visited={len(visited_hashes)} "
                f"depth={max_depth} transitions={transitions}"
            )

        cached = eligibility_cache.get(state_hash)
        if cached is not None:
            state.eligible_events = set(cached)
        eligible_ids = state.eligible_events
        if logger_is_debug():
            _log_state_header(
                state,
                state_hash,
                state_index_by_hash[state_hash],
                sequence_names_by_bit,
            )
            _log_sequence_gate_table(
                state,
                eligible_ids,
                runtime_by_id,
                sequence_names_by_bit,
            )
        def _event_priority(event_id: str) -> tuple[int, str]:
            event = event_by_id.get(event_id)
            has_conditions = 1 if event and len(event.conditions) > 0 else 0
            return (-has_conditions, event_id)

        for event_id in sorted(eligible_ids, key=_event_priority):
            event = event_by_id.get(event_id)
            if event is None:
                continue
            runtime_event = runtime_by_id.get(event.event_id)
            if runtime_event is not None:
                if not sequence_is_event_eligible(runtime_event, state.active_sequences):
                    continue
            new_state, changed_vars = execute_event(event, state)
            if runtime_event is not None:
                new_state.active_sequences = apply_sequence_effects(
                    runtime_event, state.active_sequences
                )
            if (
                new_state.variables == state.variables
                and new_state.active_sequences == state.active_sequences
            ):
                continue
            new_state.parent_state_hash = state_hash
            new_state.causing_event = event.event_id
            new_state.depth = depth + 1
            child_hash = new_state.normalized_hash()
            transition_log.append((state_hash, event.event_id, child_hash))
            if transition_log_limit is not None and len(transition_log) > transition_log_limit:
                transition_log.pop(0)
            transitions += 1
            if child_hash not in state_index_by_hash:
                state_index_by_hash[child_hash] = next_state_index
                next_state_index += 1
            if logger_is_debug():
                _log_transition(
                    state_index_by_hash[state_hash],
                    event.event_id,
                    state_index_by_hash[child_hash],
                )

            recheck_ids = set()
            for var_name in changed_vars:
                recheck_ids.update(read_index.get(var_name, set()))
            recheck_ids.add(event.event_id)

            new_state.eligible_events = _update_eligible_events(
                state.eligible_events,
                recheck_ids,
                event_by_id,
                new_state,
                reachable_events,
                runtime_by_id,
                lambda eid, st=new_state: _track_reachable(eid, st, _set_last_reachable),
            )
            eligibility_cache[new_state.normalized_hash()] = set(new_state.eligible_events)
            _visit(new_state, depth + 1)

    initial_state.depth = 0
    seed_states = _build_runtime_secondary_branches(
        initial_state,
        sorted_events,
        runtime_by_id,
        transition_log,
    )
    for seed in seed_states:
        seed.eligible_events = _compute_initial_eligible(
            sorted_events,
            seed,
            reachable_events,
            runtime_by_id,
            lambda eid, st=seed: _track_reachable(eid, st, _set_last_reachable),
        )
        eligibility_cache[seed.normalized_hash()] = set(seed.eligible_events)
        _visit(seed, 0)

    if logger_is_debug() and deepest_state is not None:
        _log_full_state_snapshot(
            deepest_state,
            events,
            sequence_names_by_bit,
            runtime_by_id,
            deepest_event,
            "DEEPEST STATE SNAPSHOT",
        )

    return ExplorationResult(
        visited_states=state_registry,
        reachable_events=reachable_events,
        max_depth=max_depth,
        transition_log=transition_log,
    )


def _build_runtime_secondary_branches(
    state: StateModel,
    events: List[Event],
    runtime_by_id: Dict[str, RuntimeEvent],
    transition_log: List[Tuple[int, str, int]],
) -> List[StateModel]:
    """Build initial DFS seed states from runtime-secondary events."""
    baseline_state = state.clone()
    candidates: List[Event] = []

    for event in events:
        if not event.conditions:
            continue
        if event.starts_sequences or event.requires_sequences:
            continue
        runtime_event = runtime_by_id.get(event.event_id)
        if runtime_event is not None:
            if not sequence_is_event_eligible(runtime_event, baseline_state.active_sequences):
                continue
        if not event_is_eligible(event, baseline_state):
            continue
        candidates.append(event)

    if not candidates:
        return [state]

    visited_hashes: Set[int] = set()
    seed_states: List[StateModel] = []

    def _branch(current: StateModel, remaining: List[Event]) -> None:
        current_hash = current.normalized_hash()
        if current_hash in visited_hashes:
            return
        visited_hashes.add(current_hash)
        seed_states.append(current)
        if not remaining:
            return
        for index, event in enumerate(remaining):
            if not event_is_eligible(event, current):
                continue
            next_state, _ = execute_event(event, current)
            next_state.depth = current.depth
            next_state.parent_state_hash = current.parent_state_hash
            next_state.causing_event = current.causing_event
            transition_log.append(
                (
                    current.normalized_hash(),
                    event.event_id,
                    next_state.normalized_hash(),
                )
            )
            _branch(next_state, remaining[:index] + remaining[index + 1 :])

    _branch(state, sorted(candidates, key=lambda e: e.event_id))
    return seed_states


def _compute_initial_eligible(
    events: List[Event],
    state: StateModel,
    reachable_events: Set[str],
    runtime_by_id: Dict[str, RuntimeEvent],
    on_reachable: Callable[[str], None] | None = None,
) -> Set[str]:
    """Compute initially eligible events for the starting state."""
    eligible_ids: Set[str] = set()
    for event in events:
        runtime_event = runtime_by_id.get(event.event_id)
        if runtime_event is not None:
            if not sequence_is_event_eligible(runtime_event, state.active_sequences):
                continue
        if event_is_eligible(event, state):
            eligible_ids.add(event.event_id)
            reachable_events.add(event.event_id)
            if on_reachable:
                on_reachable(event.event_id)
    return eligible_ids


def _update_eligible_events(
    current: Set[str],
    recheck_ids: Set[str],
    event_by_id: Dict[str, Event],
    state: StateModel,
    reachable_events: Set[str],
    runtime_by_id: Dict[str, RuntimeEvent],
    on_reachable: Callable[[str], None] | None = None,
) -> Set[str]:
    """Update eligibility for a subset of events after changes."""
    updated = set(current)
    for event_id in sorted(recheck_ids):
        event = event_by_id.get(event_id)
        if event is None:
            continue
        runtime_event = runtime_by_id.get(event.event_id)
        if runtime_event is not None:
            if not sequence_is_event_eligible(runtime_event, state.active_sequences):
                updated.discard(event_id)
                continue
        if event_is_eligible(event, state):
            updated.add(event_id)
            reachable_events.add(event_id)
            if on_reachable:
                on_reachable(event_id)
        else:
            updated.discard(event_id)
    return updated


def _invert_sequence_registry(registry: Dict[str, int]) -> Dict[int, str]:
    """Invert the sequence registry into index -> name mapping."""
    return {index: name for name, index in registry.items()}


def _resolve_active_sequence_names(
    active_sequences: int, sequence_names_by_bit: Dict[int, str]
) -> List[str]:
    """Convert active bitmask to readable sequence names."""
    if active_sequences <= 0:
        return []
    names = []
    bit_index = 0
    mask = active_sequences
    while mask:
        if mask & 1:
            names.append(sequence_names_by_bit.get(bit_index, f"seq_{bit_index}"))
        mask >>= 1
        bit_index += 1
    return sorted(names)


def _log_state_header(
    state: StateModel,
    state_hash: int,
    state_counter: int,
    sequence_names_by_bit: Dict[int, str],
) -> None:
    """Log a readable state header for debugging."""
    if not logger_is_debug():
        return
    sequences = _resolve_active_sequence_names(state.active_sequences, sequence_names_by_bit)
    sequence_label = ", ".join(sequences) if sequences else "none"
    last_event = state.causing_event or "start"
    header = log_color(
        f"[STATE {state_counter}] depth={state.depth} hash={state_hash} last_event={last_event}",
        "header",
    )
    log_debug(header)
    log_debug(log_color(f"Active Sequences: {sequence_label}", "info"))


def _log_sequence_gate_table(
    state: StateModel,
    eligible_ids: Set[str],
    runtime_by_id: Dict[str, RuntimeEvent],
    sequence_names_by_bit: Dict[int, str],
) -> None:
    """Log a compact eligibility table for sequence gating."""
    if not logger_is_debug():
        return
    allowed: List[str] = []
    blocked: List[str] = []
    for event_id in sorted(eligible_ids):
        runtime_event = runtime_by_id.get(event_id)
        if runtime_event:
            if runtime_event.requires_sequences_mask == 0:
                allowed.append(event_id)
            elif state.active_sequences == 0:
                blocked.append(event_id)
            elif (runtime_event.requires_sequences_mask & state.active_sequences) != 0:
                allowed.append(event_id)
            else:
                blocked.append(event_id)
        else:
            allowed.append(event_id)
    sequences = _resolve_active_sequence_names(state.active_sequences, sequence_names_by_bit)
    sequence_label = ", ".join(sequences) if sequences else "none"
    log_debug(log_color(f"[SEQ GATE] active={sequence_label}", "header"))
    log_debug(log_color(f"Allowed ({len(allowed)}): {', '.join(allowed) if allowed else 'none'}", "ok"))
    log_debug(log_color(f"Blocked ({len(blocked)}): {', '.join(blocked) if blocked else 'none'}", "warn"))


def _log_transition(parent_index: int, event_id: str, child_index: int) -> None:
    """Log a readable parent -> child transition line."""
    if not logger_is_debug():
        return
    log_debug(
        log_color(
            f"[TRANSITION] parent=STATE {parent_index} --{event_id}--> STATE {child_index}",
            "info",
        )
    )


def _log_full_state_snapshot(
    state: StateModel,
    events: List[Event],
    sequence_names_by_bit: Dict[int, str],
    runtime_by_id: Dict[str, RuntimeEvent],
    last_reachable_event: str | None,
    title: str,
) -> None:
    """Log a full snapshot after the last reachable event is discovered."""
    if not logger_is_debug():
        return
    log_debug("")
    log_debug(log_color(f"[{title}]", "header"))
    if last_reachable_event:
        log_debug(log_color(f"Last Event: {last_reachable_event}", "info"))
    sequences = _resolve_active_sequence_names(state.active_sequences, sequence_names_by_bit)
    sequence_label = ", ".join(sequences) if sequences else "none"
    log_debug(log_color(f"Active Sequences: {sequence_label}", "info"))
    log_debug(log_color("Variables:", "header"))
    for key in sorted(state.variables.keys()):
        log_debug(f"  {key} = {state.variables[key]}")
    log_debug(log_color("Remaining Triggers:", "header"))
    for event in sorted(events, key=lambda e: e.event_id):
        max_triggers = event.max_triggers
        used = state.trigger_counts.get(event.event_id, 0)
        if max_triggers is None or max_triggers < 0:
            remaining = "unlimited"
        else:
            remaining = max(max_triggers - used, 0)
        log_debug(f"  {event.event_id}: {remaining}")

    suggested = _suggest_next_events(state, runtime_by_id, sequence_names_by_bit)
    log_debug(log_color("Suggested Next Events (sequence-closest):", "header"))
    if suggested:
        for event_id in suggested:
            log_debug(log_color(f"  {event_id}", "ok"))
    else:
        log_debug(log_color("  none", "dim"))


def _track_reachable(
    event_id: str,
    state: StateModel,
    callback: Callable[[str, StateModel], None] | None,
) -> None:
    """Track the most recent reachable event."""
    if callback:
        callback(event_id, state)


def _suggest_next_events(
    state: StateModel,
    runtime_by_id: Dict[str, RuntimeEvent],
    sequence_names_by_bit: Dict[int, str],
) -> List[str]:
    """Suggest next closest events within the current sequence context."""
    candidates = []
    for event_id in sorted(state.eligible_events):
        runtime_event = runtime_by_id.get(event_id)
        if runtime_event:
            if runtime_event.requires_sequences_mask == 0:
                candidates.append(event_id)
            elif state.active_sequences == 0:
                continue
            elif (runtime_event.requires_sequences_mask & state.active_sequences) != 0:
                candidates.append(event_id)
        else:
            candidates.append(event_id)
    return candidates
