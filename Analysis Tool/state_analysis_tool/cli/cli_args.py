"""Argument parsing helpers for the CLI."""

from __future__ import annotations

import argparse
from typing import List


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Analyze Unity narrative event JSON.",
        epilog=(
            "Non-interactive mode note: If no TTY is available, the tool will "
            "automatically cast numeric condition strings and write a separate "
            "normalized copy before analysis."
        ),
    )
    parser.add_argument("--mode", choices=["full", "fast", "dev"], default="full")
    parser.add_argument("--progress-every", type=int, default=0)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--max-states", type=int, default=200)
    parser.add_argument("--snapshot-limit", type=int, default=200)
    parser.add_argument("--raw", action="store_true")
    subparsers = parser.add_subparsers(dest="command")
    for name in ("analyze", "validate", "runtime", "graph", "explore"):
        sub = subparsers.add_parser(name)
        sub.add_argument("json_path", nargs="?", help="Path to the Unity event JSON export")
    return parser


def normalize_default_command_args(argv: List[str]) -> List[str]:
    """Insert default command after global flags when no subcommand is provided."""
    commands = {"analyze", "validate", "runtime", "graph", "explore"}
    if any(token in commands for token in argv):
        return argv

    options_with_values = {
        "--mode",
        "--progress-every",
        "--max-states",
        "--snapshot-limit",
    }
    options_flags = {"--clean", "--debug", "--quiet", "--raw"}

    global_args: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in options_with_values:
            if index + 1 < len(argv):
                global_args.extend(argv[index : index + 2])
                index += 2
                continue
            break
        if token in options_flags:
            global_args.append(token)
            index += 1
            continue
        break

    remaining = argv[index:]
    return global_args + ["analyze"] + remaining
