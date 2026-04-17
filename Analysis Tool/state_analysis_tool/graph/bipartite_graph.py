"""Bipartite graph representation for events and variables."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union

from .event_node import EventNode
from .variable_node import VariableNode
from .graph_edge import GraphEdge
from ..loader.event_model import Event, InitialState


@dataclass
class InteractionGraph:
    """Bipartite graph linking events and variables."""
    event_nodes: Dict[str, EventNode] = field(default_factory=dict)
    variable_nodes: Dict[str, VariableNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    adjacency: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_event(self, event: EventNode) -> None:
        """Register an event node."""
        self.event_nodes[event.event_id] = event

    def add_variable(self, variable: VariableNode) -> None:
        """Register a variable node."""
        self.variable_nodes[variable.variable_name] = variable

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge and update adjacency."""
        self.edges.append(edge)
        self.adjacency[edge.source].add(edge.target)

    @staticmethod
    def from_events(
        events: List[Event], initial_state: Optional[Union[InitialState, Dict[str, object]]] = None
    ) -> "InteractionGraph":
        """Build a graph from events and optional initial state."""
        graph = InteractionGraph()

        if initial_state is not None:
            if isinstance(initial_state, dict):
                initial_vars = initial_state.keys()
            else:
                initial_vars = initial_state.variables.keys()
            for var_name in sorted(initial_vars):
                if var_name not in graph.variable_nodes:
                    graph.add_variable(VariableNode(variable_name=var_name))

        # Pre-register all variables referenced by events before adding edges
        for event in sorted(events, key=lambda e: e.event_id):
            for binding in event.conditions:
                var_name = str(binding.get("name"))
                if var_name not in graph.variable_nodes:
                    graph.add_variable(VariableNode(variable_name=var_name))
            for binding in event.effects:
                var_name = str(binding.get("name"))
                if var_name not in graph.variable_nodes:
                    graph.add_variable(VariableNode(variable_name=var_name))

        for event in sorted(events, key=lambda e: e.event_id):
            event_id = event.event_id
            if event_id == "runtime_state":
                continue
            event_node = EventNode(event_id=event_id)
            graph.add_event(event_node)

            for binding in sorted(event.conditions, key=lambda b: str(b.get("name"))):
                var_name = str(binding.get("name"))
                graph._add_read_edge(event_id, var_name)

            for binding in sorted(event.effects, key=lambda b: str(b.get("name"))):
                var_name = str(binding.get("name"))
                graph._add_write_edge(event_id, var_name)

        return graph

    def _get_or_create_variable(self, variable: str) -> VariableNode:
        """Fetch or create a variable node."""
        if variable not in self.variable_nodes:
            self.add_variable(VariableNode(variable_name=variable))
        return self.variable_nodes[variable]

    def _get_or_create_event(self, event_id: str) -> EventNode:
        """Fetch or create an event node."""
        if event_id not in self.event_nodes:
            self.add_event(EventNode(event_id=event_id))
        return self.event_nodes[event_id]

    def _add_read_edge(self, event_id: str, variable: str) -> None:
        """Add a read edge between an event and variable."""
        event_node = self._get_or_create_event(event_id)
        variable_node = self._get_or_create_variable(variable)

        event_node.reads.add(variable_node)
        variable_node.read_by.add(event_node)
        self.add_edge(GraphEdge(source=variable, target=event_id, edge_type="reads"))

    def _add_write_edge(self, event_id: str, variable: str) -> None:
        """Add a write edge between an event and variable."""
        event_node = self._get_or_create_event(event_id)
        variable_node = self._get_or_create_variable(variable)

        event_node.writes.add(variable_node)
        variable_node.written_by.add(event_node)
        self.add_edge(GraphEdge(source=event_id, target=variable, edge_type="writes"))

    def degree(self, node_id: str) -> int:
        """Return the degree of a node in the adjacency map."""
        return len(self.adjacency.get(node_id, set()))

    def edge_counts(self) -> Tuple[int, int]:
        """Return counts of read and write edges."""
        reads = sum(1 for e in self.edges if e.edge_type == "reads")
        writes = sum(1 for e in self.edges if e.edge_type == "writes")
        return reads, writes

    def dfs_from_event(self, start_event_id: str) -> Tuple[Set[str], Set[str], int]:
        """Depth-first traversal following Event -> Variable -> Event."""
        visited_events: Set[str] = set()
        visited_variables: Set[str] = set()
        max_depth = 0

        def _dfs_event(event_id: str, depth: int) -> None:
            nonlocal max_depth
            if event_id in visited_events:
                return
            visited_events.add(event_id)
            max_depth = max(max_depth, depth)

            event_node = self.event_nodes.get(event_id)
            if event_node is None:
                return

            for var_node in sorted(
                event_node.reads.union(event_node.writes), key=lambda v: v.variable_name
            ):
                _dfs_variable(var_node, depth + 1)

        def _dfs_variable(var_node: VariableNode, depth: int) -> None:
            nonlocal max_depth
            var_name = var_node.variable_name
            if var_name in visited_variables:
                return
            visited_variables.add(var_name)
            max_depth = max(max_depth, depth)

            for event_node in sorted(
                var_node.read_by.union(var_node.written_by), key=lambda e: e.event_id
            ):
                _dfs_event(event_node.event_id, depth + 1)

        _dfs_event(start_event_id, 0)
        return visited_events, visited_variables, max_depth

    def build_read_index(self) -> Dict[str, Set[str]]:
        """Build a variable-to-readers index."""
        index: Dict[str, Set[str]] = {}
        for var_name, var_node in self.variable_nodes.items():
            index[var_name] = {event.event_id for event in var_node.read_by}
        return index

    def build_write_index(self) -> Dict[str, Set[str]]:
        """Build a variable-to-writers index."""
        index: Dict[str, Set[str]] = {}
        for var_name, var_node in self.variable_nodes.items():
            index[var_name] = {event.event_id for event in var_node.written_by}
        return index
