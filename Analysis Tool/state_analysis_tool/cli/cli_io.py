"""CLI I/O helpers for JSON preparation and demo resolution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ..loader.json_loader import cast_condition_values_in_data
from ..utils.output_paths import get_reports_dir


def maybe_prepare_json(path: Path, clean: bool, quiet: bool, debug: bool) -> Path:
    """Optionally cast condition values into a normalized copy before loading."""
    if clean:
        return path
    if quiet:
        return path
    if not _stdin_is_tty():
        _log_non_interactive_casting()
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        warnings = cast_condition_values_in_data(raw)
        normalized_path = write_normalized_copy(path, raw)
        if debug and warnings:
            for variable_name, old_value, new_value in warnings:
                print(
                    "Warning: condition value type changed from string to int for "
                    f"variable '{variable_name}': '{old_value}' -> {new_value}"
                )
        return normalized_path
    if not prompt_for_casting(path):
        return path

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    warnings = cast_condition_values_in_data(raw)
    normalized_path = write_normalized_copy(path, raw)
    if debug and warnings:
        for variable_name, old_value, new_value in warnings:
            print(
                "Warning: condition value type changed from string to int for "
                f"variable '{variable_name}': '{old_value}' -> {new_value}"
            )
    return normalized_path


def prompt_for_casting(path: Path) -> bool:
    """Ask the user whether to skip casting numeric strings to integers."""
    rel_path = safe_relative_path(path)
    prompt = (
        "Warning: this program is attempting cast numeric strings in your "
        f"{rel_path} file, and any corrections are written to disk. "
        "Do you want to skip this step? ( Y , N ) "
    )
    attempts = 0
    while attempts < 3:
        try:
            response = input(prompt).strip().upper()
        except EOFError:
            return False
        if response == "Y":
            return False
        if response == "N":
            return True
        attempts += 1
    print(
        "Exit Program: The expected input of 'Y' or 'N' was not provided, "
        "to safeguard your game data file this program is set to terminate all operations. "
        "If you are using numeric strings and want to keep them as strings or your files does not include "
        "numeric strings, you can use the --clean flag to skip this casting step."
    )
    sys.exit(1)


def write_normalized_copy(source_path: Path, data: dict) -> Path:
    """Write a normalized copy next to the source file and return its path."""
    normalized_dir = source_path.parent / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized_path = normalized_dir / source_path.name
    normalized_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return normalized_path


def safe_relative_path(path: Path) -> str:
    """Return a cwd-relative path when possible for user-friendly output."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _log_non_interactive_casting() -> None:
    """Log non-interactive casting behavior for discoverability."""
    try:
        reports_dir = get_reports_dir()
        log_path = reports_dir / "non_interactive_log.txt"
        message = (
            "In non-interactive mode, the tool uses a safe batch default: "
            "write a separate normalized copy."
        )
        log_path.write_text(message, encoding="utf-8")
    except Exception:
        pass


def _stdin_is_tty() -> bool:
    """Safely detect whether stdin is attached to a TTY."""
    stdin = getattr(sys, "stdin", None)
    if stdin is None:
        return False
    isatty = getattr(stdin, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False
