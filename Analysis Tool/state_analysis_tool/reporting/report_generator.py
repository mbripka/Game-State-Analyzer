"""Generate human-readable summaries for analysis results."""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..metrics.structural_metrics import find_isolated_events, find_isolated_variables
from ..graph.bipartite_graph import InteractionGraph


OVERLOADED_EDGE_THRESHOLD = 8


def build_summary(
    graph: InteractionGraph,
    metrics: Dict[str, float],
    mode: str = "analyze",
    include_warnings: bool = True,
) -> List[str]:
    """Build a summary report for graph-only or full analysis."""
    summary: List[str] = []

    summary.append("System Topology")
    summary.append("---------------")
    summary.append(f"Events = {int(metrics['event_count'])}")
    summary.append(f"Variables = {int(metrics['variable_count'])}")
    summary.append(f"Edges = {int(metrics['edge_count'])}")
    summary.append(f"Read Edges = {int(metrics['read_edges'])}")
    summary.append(f"Write Edges = {int(metrics['write_edges'])}")
    summary.append("")

    summary.append("Interaction Metrics")
    summary.append("-------------------")
    coupling_ratio = metrics.get("coupling_ratio", 0.0)
    collision_vars = int(metrics.get("coupling_collision_variables", 0))
    total_written_vars = int(metrics.get("coupling_total_written_variables", 0))
    summary.append(f"Write Coupling Ratio = {coupling_ratio:.0f}%")
    summary.append(f"({collision_vars} / {total_written_vars} variables shared across events)")
    summary.append("")

    high_collision = _high_collision_variables(graph)
    if high_collision:
        summary.append(f"High Collision Variables ({len(high_collision)}):")
        for name, writers in high_collision:
            summary.append(f"{name} (written by {writers} events)")
        if include_warnings:
            summary.append(
                "Warning: Multiple events share control of these variables, increasing integration risk."
            )
            summary.append("")

    overloaded = _overloaded_variables(graph)
    if overloaded:
        summary.append(f"Overloaded Variables ({len(overloaded)}):")
        for name, total_edges in overloaded:
            summary.append(f"{name} ({total_edges} total read/write edges)")
        if include_warnings:
            summary.append(
                "Warning: Highly connected variables may increase debugging and balancing cost."
            )
            summary.append("")

    summary.append(f"Variable Density = {metrics['variable_density']:.2f}")

    if "ved_value" in metrics:
        summary.append("")
        summary.append(
            f"Variable Event Density (VED) = {metrics['ved_value']:.2f}% ({metrics['ved_category']})"
        )
        if metrics.get("ved_warning") and include_warnings:
            summary.append(metrics["ved_warning"])

        affected = metrics.get("ved_affected_branching_vars") or {}
        if affected:
            summary.append("")
            summary.append("Highly Affected Branching Variables:")
            for name, count in sorted(affected.items(), key=lambda x: (-x[1], x[0])):
                summary.append(f"{name} (touched by {count} events)")

    summary.append("")
    summary.append(f"Narrative Interaction Index (NII) = {int(metrics['nii'])}")
    summary.append(f"Higher values indicate more branching and player influence.")
    summary.append("Compare this value across different datasets to evaluate interactivity.")
    summary.append("")

    if mode == "graph":
        return summary

    summary.append("Structural Metrics")
    summary.append("-------------------")
    summary.append(f"Max State Transition Depth = {int(metrics['max_state_transition_depth'])}")
    summary.append(f"Reachable Events = {int(metrics['reachability'])}")
    summary.append("")

    summary.append("State Space Metrics")
    summary.append("-------------------")
    summary.append(f"Branching Variables = {int(metrics['partition_branching_variables'])}")
    summary.append(f"State Space Estimate = {int(metrics['partition_estimate'])}")
    summary.append("")

    summary.append("Stability Metrics")
    summary.append("-----------------")
    summary.append(f"Mutation Volatility = {metrics['mutation_volatility']:.2f}")

    isolated_events = find_isolated_events(graph)
    isolated_vars = find_isolated_variables(graph)
    if isolated_events:
        summary.append("")
        summary.append(f"Isolated events: {', '.join(isolated_events)}")
    if isolated_vars:
        summary.append("")
        summary.append(f"Isolated variables: {', '.join(isolated_vars)}")

    warning = metrics.get("nii_warning")
    if warning and include_warnings:
        summary.append("")
        summary.append(warning)
        contributors = metrics.get("nii_contributors") or []
        if contributors:
            for name in contributors:
                summary.append(f"- {name}")

    return summary


def _high_collision_variables(graph: InteractionGraph) -> List[Tuple[str, int]]:
    """Return variables with two or more writers."""
    items = []
    for name, var in graph.variable_nodes.items():
        writers = len(var.written_by)
        if writers >= 2:
            items.append((name, writers))
    items.sort(key=lambda x: (-x[1], x[0]))
    return items


def _overloaded_variables(graph: InteractionGraph) -> List[Tuple[str, int]]:
    """Return variables with high read/write edge counts."""
    items = []
    for name, var in graph.variable_nodes.items():
        total_edges = len(var.read_by) + len(var.written_by)
        if total_edges > OVERLOADED_EDGE_THRESHOLD:
            items.append((name, total_edges))
    items.sort(key=lambda x: (-x[1], x[0]))
    return items
