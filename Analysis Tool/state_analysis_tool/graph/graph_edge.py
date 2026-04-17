"""Graph edge representation for event-variable links."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphEdge:
    """Directed edge between event and variable nodes."""
    source: str
    target: str
    edge_type: str  # "reads" or "writes"
