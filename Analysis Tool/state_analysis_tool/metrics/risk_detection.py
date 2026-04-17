from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Optional

from ..graph.bipartite_graph import InteractionGraph


OVERLOADED_EDGE_THRESHOLD = 8
PARTITION_WARNING_THRESHOLD = 6


def detect_risks(graph: InteractionGraph, reachable_event_ids: Optional[Set[str]] = None) -> Dict[str, List[str]]:
    risks: Dict[str, List[str]] = defaultdict(list)

    _detect_high_collision_variables(graph, risks)
    if reachable_event_ids is not None:
        _detect_unreachable_events(graph, risks, reachable_event_ids)
    _detect_overloaded_variables(graph, risks)
    _detect_partition_explosion(graph, risks)

    return dict(risks)


def _detect_high_collision_variables(graph: InteractionGraph, risks: Dict[str, List[str]]) -> None:
    for var in graph.variable_nodes.values():
        if len(var.written_by) > 1:
            risks["high_collision_variables"].append(var.variable_name)


def _detect_unreachable_events(
    graph: InteractionGraph, risks: Dict[str, List[str]], reachable_event_ids: Set[str]
) -> None:
    for event_id in graph.event_nodes.keys():
        if event_id not in reachable_event_ids:
            risks["unreachable_events"].append(event_id)


def _detect_overloaded_variables(graph: InteractionGraph, risks: Dict[str, List[str]]) -> None:
    for var in graph.variable_nodes.values():
        total = len(var.read_by) + len(var.written_by)
        if total > OVERLOADED_EDGE_THRESHOLD:
            risks["overloaded_variables"].append(var.variable_name)


def _detect_partition_explosion(graph: InteractionGraph, risks: Dict[str, List[str]]) -> None:
    branching = _branching_variables(graph)
    if len(branching) >= PARTITION_WARNING_THRESHOLD:
        risks["partition_explosion_warning"].append(
            f"branching_variables={len(branching)}"
        )


def _branching_variables(graph: InteractionGraph) -> Set[str]:
    targets = {
        "knowledge",
        "health",
        "morale",
        "prosperity",
        "reputation",
    }
    branching = set()
    for var in graph.variable_nodes.keys():
        var_lower = var.lower()
        if var_lower in targets:
            branching.add(var)
            continue
        if "influence" in var_lower and ("faction" in var_lower or var_lower.startswith("group.")):
            branching.add(var)
    return branching
