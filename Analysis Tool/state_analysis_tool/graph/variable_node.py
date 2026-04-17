"""Variable node representation for the bipartite graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .event_node import EventNode


@dataclass(eq=True)
class VariableNode:
    """Variable node with read/write relationships."""
    variable_name: str
    read_by: Set[EventNode] = field(default_factory=set)
    written_by: Set[EventNode] = field(default_factory=set)

    def __hash__(self) -> int:  # allow usage in sets while keeping mutable relations
        """Hash by variable name for set membership."""
        return hash(self.variable_name)
