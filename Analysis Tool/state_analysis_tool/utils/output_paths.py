"""Output path helpers for report and diagnostic files."""

from __future__ import annotations

import sys
from pathlib import Path


def get_reports_dir() -> Path:
    """Return a writable reports directory.

    macOS and Linux keep the legacy location. Windows prefers a
    per-app folder under Documents to avoid permission issues in some
    environments.
    """
    if sys.platform == "win32":
        documents_dir = Path.home() / "Documents"
        candidates = [
            documents_dir / "GameStateAnalysis" / "analysis_reports",
            documents_dir / "GameStateAnalyzer" / "analysis_reports",
            documents_dir / "analysis_reports",
        ]
    else:
        candidates = [Path.home() / "Documents" / "analysis_reports"]

    for reports_dir in candidates:
        try:
            reports_dir.mkdir(parents=True, exist_ok=True)
            return reports_dir
        except Exception:
            continue

    # Last resort: return legacy path and let callers raise normally.
    return Path.home() / "Documents" / "analysis_reports"
