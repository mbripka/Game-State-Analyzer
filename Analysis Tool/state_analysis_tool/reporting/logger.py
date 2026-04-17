"""Lightweight console logging helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable


_LOG_MODE = "normal"


def set_log_mode(mode: str) -> None:
    """Set global logging mode: normal, debug, or quiet."""
    global _LOG_MODE
    _LOG_MODE = mode


def is_debug() -> bool:
    """Return True when debug logging is enabled."""
    return _LOG_MODE == "debug"


def is_quiet() -> bool:
    """Return True when quiet logging is enabled."""
    return _LOG_MODE == "quiet"


def debug(message: str) -> None:
    """Print a debug line when debug logging is enabled."""
    if _LOG_MODE == "debug":
        print(message)


def warn(message: str) -> None:
    """Print a warning unless quiet logging is enabled."""
    if _LOG_MODE != "quiet":
        print(message)


def color(text: str, style: str) -> str:
    """Apply ANSI color styling for debug-friendly output."""
    styles = {
        "header": "\033[95m",
        "info": "\033[94m",
        "ok": "\033[92m",
        "warn": "\033[93m",
        "error": "\033[91m",
        "dim": "\033[90m",
        "bold": "\033[1m",
    }
    reset = "\033[0m"
    prefix = styles.get(style, "")
    if not prefix:
        return text
    return f"{prefix}{text}{reset}"


def log(message: str) -> None:
    """Print a timestamped log line."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def log_lines(lines: Iterable[str], title: str | None = None) -> None:
    """Print a block of lines with optional title."""
    if title:
        log(title)
    for line in lines:
        print(f"  - {line}")
