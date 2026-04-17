"""Structural metrics computed from the bipartite graph."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple, Any, Optional

from ..graph.bipartite_graph import InteractionGraph


def compute_structural_metrics(
    graph: InteractionGraph,
    max_state_transition_depth: Optional[int] = None,
    reachable_event_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute structural metrics for reporting."""
    reads, writes = graph.edge_counts()
    event_count = len(graph.event_nodes)
    variable_count = len(graph.variable_nodes)
    edge_count = len(graph.edges)

    coupling = _write_coupling_ratio(graph)
    high_collision = _high_collision_risk(graph)
    reachable_events = reachable_event_count if reachable_event_count is not None else 0
    variable_density = (variable_count / event_count) if event_count > 0 else 0.0
    partition_count, partition_estimate = _partition_explosion(graph)
    dimensional_growth = _dimensional_growth(graph)
    mutation_volatility = (writes / variable_count) if variable_count > 0 else 0.0
    nii_value, nii_contributors = _narrative_instability_index(graph)
    nii_warning = None
    if partition_estimate > 1000:
        nii_warning = (
            "Warning state explosion detected.\n\n"
            "Large state spaces can increase production costs and visual asset complexity.\n\n"
            "Primary contributing variables:"
        )

    return {
        "max_state_transition_depth": float(max_state_transition_depth or 0),
        "coupling_ratio": float(coupling["ratio"]),
        "coupling_collision_variables": float(coupling["collision_variables"]),
        "coupling_total_written_variables": float(coupling["total_written_variables"]),
        "high_collision_risk": float(high_collision),
        "reachability": float(reachable_events),
        "variable_density": float(variable_density),
        "partition_branching_variables": float(partition_count),
        "partition_estimate": float(partition_estimate),
        "dimensional_growth": float(dimensional_growth),
        "mutation_volatility": float(mutation_volatility),
        "nii": float(nii_value),
        "nii_warning": nii_warning,
        "nii_contributors": nii_contributors,
        "event_count": float(event_count),
        "variable_count": float(variable_count),
        "edge_count": float(edge_count),
        "read_edges": float(reads),
        "write_edges": float(writes),
    }


def find_isolated_events(graph: InteractionGraph) -> List[str]:
    """Return event ids with no edges."""
    return [eid for eid in graph.event_nodes if graph.degree(eid) == 0]


def find_isolated_variables(graph: InteractionGraph) -> List[str]:
    """Return variable names with no edges."""
    return [var for var in graph.variable_nodes if graph.degree(var) == 0]


def _high_collision_risk(graph: InteractionGraph) -> int:
    """Count variables written by more than two events."""
    return sum(1 for var in graph.variable_nodes.values() if len(var.written_by) > 2)


def _write_coupling_ratio(graph: InteractionGraph) -> Dict[str, float]:
    """Compute write coupling ratio and counts."""
    total_written = 0
    collision = 0

    for var in graph.variable_nodes.values():
        writers = len(set(var.written_by))
        if writers > 0:
            total_written += 1
            if writers >= 2:
                collision += 1

    if total_written == 0:
        return {
            "ratio": 0.0,
            "collision_variables": 0.0,
            "total_written_variables": 0.0,
        }

    return {
        "ratio": (collision / total_written) * 100.0,
        "collision_variables": float(collision),
        "total_written_variables": float(total_written),
    }

def _partition_explosion(graph: InteractionGraph) -> Tuple[int, int]:
    """Estimate state partition counts based on branching variables."""
    branching = _branching_variables(graph)
    count = len(branching)
    return count, 2 ** count


def _dimensional_growth(graph: InteractionGraph) -> int:
    """Count unique variables referenced by events."""
    referenced = set()
    for event in graph.event_nodes.values():
        for var_node in event.reads.union(event.writes):
            referenced.add(var_node.variable_name)
    return len(referenced)


def _branching_variables(graph: InteractionGraph) -> Set[str]:
    """Detect branching variables for partition estimation."""
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


def _narrative_instability_index(graph: InteractionGraph) -> Tuple[int, List[str]]:
    """Compute NII and return top contributors."""
    contributions: List[Tuple[str, int]] = []
    total = 0
    for var_name, var_node in graph.variable_nodes.items():
        writers = len(var_node.written_by)
        readers = len(var_node.read_by)
        contribution = writers * readers
        if contribution > 0:
            contributions.append((var_name, contribution))
            total += contribution

    contributions.sort(key=lambda x: (-x[1], x[0]))
    top_vars = [name for name, _ in contributions[:5]]
    return total, top_vars
