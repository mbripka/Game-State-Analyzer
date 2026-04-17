"""Resource path helpers for bundled and source-tree execution."""

from __future__ import annotations

import sys
from pathlib import Path
from importlib import resources


def get_schema_path() -> Path:
    """Resolve schema_reference.txt path for source or bundled runs."""
    # Prefer package resources when available.
    try:
        schema = resources.files("state_analysis_tool").joinpath("schema/schema_reference.txt")
        if schema.exists():
            return Path(schema)
    except Exception:
        pass

    # Fallback to PyInstaller bundle root.
    bundle_root = Path(getattr(sys, "_MEIPASS", ""))
    if bundle_root:
        bundled = bundle_root / "schema" / "schema_reference.txt"
        if bundled.exists():
            return bundled

    # Fallback to source tree.
    return Path(__file__).resolve().parents[1] / "schema" / "schema_reference.txt"
