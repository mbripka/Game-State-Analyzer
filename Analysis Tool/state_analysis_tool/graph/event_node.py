"""Event node representation for the bipartite graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .variable_node import VariableNode


@dataclass(eq=True)
class EventNode:
    """Event node with read/write relationships."""
    event_id: str
    reads: Set[VariableNode] = field(default_factory=set)
    writes: Set[VariableNode] = field(default_factory=set)

    def __hash__(self) -> int:  # allow usage in sets while keeping mutable relations
        """Hash by event id for set membership."""
        return hash(self.event_id)
