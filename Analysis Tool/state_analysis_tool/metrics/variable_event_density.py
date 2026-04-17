"""Variable-event density (VED) and HABV metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from ..loader.event_model import Event
from ..utils.resource_paths import get_schema_path


HABV_THRESHOLD = 0.30


@dataclass
class VEDResult:
    """Result container for VED and HABV metrics."""
    ved_value: float
    category: str
    warning: str | None
    affected_branching_vars: Dict[str, int]


def compute_variable_event_density(
    schema_path: str | Path,
    events: List[Event],
    reachable_event_ids: Set[str],
) -> VEDResult:
    """Compute VED and highly affected branching variables."""
    branching_categories = _load_branching_categories(schema_path)
    if not branching_categories:
        return VEDResult(
            ved_value=0.0,
            category="under-loaded",
            warning=None,
            affected_branching_vars={},
        )

    affected_categories: Set[str] = set()
    affected_counts: Dict[str, Set[str]] = {
        _canonical_branching_label(cat): set() for cat in branching_categories
    }

    for event in events:
        if event.event_id not in reachable_event_ids:
            continue
        if event.event_id == "runtime_state":
            continue
        touched_in_event = set()
        for binding in list(event.effects):
            name = str(binding.get("name") or "")
            matched = _match_branching_category(name, branching_categories)
            if matched:
                canonical = _canonical_branching_label(matched)
                touched_in_event.add(canonical)
        for canonical in touched_in_event:
            affected_categories.add(canonical)
            affected_counts[canonical].add(event.event_id)

    ved_value = (len(affected_categories) / len(branching_categories)) * 100.0
    category = _score_category(ved_value)
    warning = None
    if ved_value > 25:
        warning = "Warning: Higher VED may increase production and QA costs."

    counts = {k: len(v) for k, v in affected_counts.items() if len(v) > 0}
    habv = _filter_habv(counts, len(reachable_event_ids))

    return VEDResult(
        ved_value=ved_value,
        category=category,
        warning=warning,
        affected_branching_vars=habv,
    )


def _filter_habv(counts: Dict[str, int], total_reachable_events: int) -> Dict[str, int]:
    """Filter HABV entries by threshold ratio."""
    if total_reachable_events <= 0:
        return {}
    filtered: Dict[str, int] = {}
    for name, count in counts.items():
        ratio = count / total_reachable_events
        if ratio >= HABV_THRESHOLD:
            filtered[name] = count
    return filtered


def _load_branching_categories(schema_path: str | Path) -> List[str]:
    """Load branching variable category list from schema text."""
    schema_file = Path(schema_path) if schema_path else get_schema_path()
    text = schema_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]

    start = None
    end = None
    for idx, line in enumerate(lines):
        if line == "Branching Variables":
            start = idx + 1
            continue
        if start is not None and line == "Non-Branching Variables":
            end = idx
            break

    if start is None:
        return []

    section = lines[start:end] if end is not None else lines[start:]
    categories = []
    for line in section:
        if not line:
            continue
        if line.lower().startswith("only the following"):
            continue
        categories.append(line)
    return categories


def _canonical_branching_label(category: str) -> str:
    """Map schema category strings to canonical labels."""
    cat = category.lower().strip()
    if cat == "knowledge":
        return "knowledge"
    if cat == "health":
        return "health"
    if cat == "morale":
        return "morale"
    if cat == "prosperity":
        return "prosperity"
    if cat == "reputation":
        return "reputation"
    if "gateway status" in cat:
        return "gateway.status"
    if "actor encounterstatus" in cat:
        return "actor.encounterstatus"
    if "target visibility" in cat:
        return "target.visibility"
    if "faction group influence" in cat:
        return "group.influence"
    if "group membership" in cat:
        return "group.members"
    return category


def _match_branching_category(variable_name: str, categories: List[str]) -> str | None:
    """Match a variable name to a branching category."""
    var = variable_name.lower()
    for category in categories:
        cat = category.lower()
        if cat in {"knowledge", "health", "morale", "prosperity", "reputation"}:
            if var == cat or var.endswith(f".{cat}"):
                return category
        elif "gateway status" in cat:
            if var.startswith("gateway.") and var.endswith(".status"):
                return category
        elif "actor encounterstatus" in cat:
            if var.startswith("actor.") and var.endswith(".encounterstatus"):
                return category
        elif "target visibility" in cat:
            if var.startswith("target.") and var.endswith(".visibility"):
                return category
        elif "faction group influence" in cat:
            if var.startswith("group.") and var.endswith(".influence"):
                return category
        elif "group membership" in cat:
            if var.startswith("group.") and var.endswith(".members"):
                return category
        else:
            if cat in var:
                return category
    return None


def _score_category(value: float) -> str:
    """Return the VED category label for a score."""
    if value < 10:
        return "under-loaded"
    if value < 25:
        return "balanced"
    if value < 50:
        return "slightly over-loaded"
    if value < 75:
        return "moderately overloaded"
    return "emergency meeting!"
