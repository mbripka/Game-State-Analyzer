"""CLI entrypoint for the state analysis pipeline."""

from __future__ import annotations

import sys
from pathlib import Path
import json
from datetime import datetime

from ..graph.bipartite_graph import InteractionGraph
from ..loader.json_loader import load_events
from ..loader.runtime_initializer import build_initial_state
from ..simulation.runtime_event_builder import build_sequence_registry, convert_events
from ..reporting.logger import set_log_mode, is_quiet, is_debug
from ..loader.event_schema_validator import validate_event_schema_fields
from ..metrics.structural_metrics import compute_structural_metrics
from ..metrics.variable_event_density import compute_variable_event_density
from ..reporting.report_generator import build_summary
from ..reporting.logger import log, log_lines
from ..simulation.state_model import StateModel
from ..simulation.state_explorer import explore_states
from ..utils.resource_paths import get_schema_path
from ..utils.output_paths import get_reports_dir
from .cli_args import build_parser, normalize_default_command_args
from .cli_io import maybe_prepare_json


def main() -> None:
    """Parse CLI args and run the requested analysis workflow."""
    try:
        _ensure_python_version()
        _write_raw_argv_log(sys.argv)
        parser = build_parser()
        argv = normalize_default_command_args(sys.argv[1:])
        args = parser.parse_args(argv)

        _write_startup_log(argv)

        if args.command is None:
            args.command = "analyze"

        if args.json_path is None:
            json_path = _prompt_for_json_path()
        else:
            json_path = Path(args.json_path).expanduser()
        if not json_path.exists():
            print("Error: JSON file not found. Provide a valid path.")
            _pause_before_exit()
            sys.exit(1)

        if args.quiet:
            set_log_mode("quiet")
        elif args.debug:
            set_log_mode("debug")
        else:
            set_log_mode("normal")

        performance_mode = args.mode in {"fast", "dev"}
        iterable_mode = args.mode == "dev"

        json_path = maybe_prepare_json(
            json_path,
            clean=args.clean or args.json_path is None,
            quiet=args.quiet,
            debug=is_debug(),
        )

        try:
            runtime_event, events = load_events(json_path, allow_casting=False)
        except ValueError as exc:
            print(str(exc))
            _pause_before_exit()
            sys.exit(1)

        if args.command == "validate":
            schema_path = get_schema_path()
            raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
            missing_fields = validate_event_schema_fields(schema_path, raw)
            if missing_fields:
                print("Missing event schema fields:", ", ".join(missing_fields))
            else:
                print("Event schema fields validated")
            print("Loader validation complete")

        runtime_state = build_initial_state(runtime_event)
        if args.command == "runtime":
            print("Runtime state initialized")
            print(runtime_state)

        graph = InteractionGraph.from_events(events, runtime_state)
        if args.command == "graph":
            print("Graph constructed")
            metrics = compute_structural_metrics(graph)
            summary_lines = build_summary(graph, metrics, mode="graph", include_warnings=not is_quiet())
            for line in summary_lines:
                print(line)
            _write_report(summary_lines, "graph")

        exploration_result = None
        if args.command in {"explore", "analyze"}:
            read_index = graph.build_read_index()
            initial_state = StateModel(variables=dict(runtime_state))
            registry = build_sequence_registry(events)
            runtime_events = {evt.event_id: evt for evt in convert_events(events, registry)}
            if performance_mode:
                print("Performance mode enabled")
            progress_every = args.progress_every if args.progress_every > 0 else None
            max_states_limit = None if args.max_states == 0 else args.max_states
            exploration_result = explore_states(
                initial_state,
                events,
                read_index,
                runtime_events,
                sequence_registry=registry,
                performance_mode=performance_mode,
                progress_every=progress_every,
                quiet=args.quiet,
                max_states_limit=max_states_limit,
                dev_mode=iterable_mode,
                transition_log_limit=200 if iterable_mode else None,
                state_snapshot_limit=args.snapshot_limit if iterable_mode else None,
            )
            print("State exploration complete")

        metrics = None
        if args.command == "analyze" or iterable_mode:
            metrics = compute_structural_metrics(
                graph,
                exploration_result.max_depth if exploration_result else None,
                len(exploration_result.reachable_events) if exploration_result else None,
            )
            if exploration_result and not performance_mode and not iterable_mode:
                schema_path = get_schema_path()
                ved = compute_variable_event_density(schema_path, events, exploration_result.reachable_events)
                metrics["ved_value"] = ved.ved_value
                metrics["ved_category"] = ved.category
                metrics["ved_warning"] = ved.warning
                metrics["ved_affected_branching_vars"] = ved.affected_branching_vars
            if is_quiet():
                metrics["ved_warning"] = None
                metrics["nii_warning"] = None
            if iterable_mode:
                metrics["partition_estimate"] = float(metrics.get("partition_estimate", 0))
            print("Metrics computed")
            if args.raw:
                print(metrics)
            if iterable_mode:
                print(
                    "ITERABLE MODE: Results are for rapid tuning only, not production decisions."
                )
                allowed = {
                    "max_state_transition_depth",
                    "reachability",
                    "coupling_ratio",
                    "coupling_collision_variables",
                    "coupling_total_written_variables",
                    "high_collision_risk",
                    "variable_density",
                    "mutation_volatility",
                    "nii",
                    "event_count",
                    "variable_count",
                    "edge_count",
                    "read_edges",
                    "write_edges",
                    "partition_branching_variables",
                    "partition_estimate",
                }
                dev_metrics = {k: v for k, v in metrics.items() if k in allowed}
                dev_metrics["partition_estimate_note"] = "approx"
                dev_metrics["traceability"] = "reduced"
                print(dev_metrics)
                return
            print("Metrics computed")

        if args.command == "analyze":
            print("Analysis complete")
            log("Graph summary")
            summary_lines = build_summary(
                graph,
                metrics
                or compute_structural_metrics(
                    graph,
                    exploration_result.max_depth if exploration_result else None,
                    len(exploration_result.reachable_events) if exploration_result else None,
                ),
                mode="analyze",
                include_warnings=not is_quiet(),
            )
            log_lines(summary_lines)
            _write_report(summary_lines, "analysis", metrics)
            _write_completion_log("analysis")
    except Exception:
        _write_crash_log()
        raise


if __name__ == "__main__":
    main()


def _write_report(lines: list[str], prefix: str, metrics: dict | None = None) -> None:
    """Write report output to a timestamped file in analysis_reports."""
    reports_dir = get_reports_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"{prefix}_{timestamp}.txt"
    payload_lines = list(lines)
    if metrics is not None:
        payload_lines.append("")
        payload_lines.append("Raw Metrics")
        payload_lines.append("-----------")
        payload_lines.append(json.dumps(metrics, indent=2, sort_keys=True))
    report_path.write_text("\n".join(payload_lines), encoding="utf-8")


def _write_completion_log(command: str) -> None:
    """Write a completion marker to confirm analysis reached the end."""
    try:
        reports_dir = get_reports_dir()
        log_path = reports_dir / "completed.txt"
        log_path.write_text(f"completed: {command}", encoding="utf-8")
    except Exception:
        pass


def _write_crash_log() -> None:
    """Write an exception traceback for windowed runs."""
    try:
        import traceback

        reports_dir = get_reports_dir()
        log_path = reports_dir / "crash_log.txt"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


def _write_startup_log(argv: list[str]) -> None:
    """Write a startup breadcrumb for debugging drag-and-drop behavior."""
    try:
        reports_dir = get_reports_dir()
        log_path = reports_dir / "startup_log.txt"
        payload = {
            "argv": argv,
            "cwd": str(Path.cwd()),
            "stdin_tty": _stdin_is_tty(),
        }
        log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def _write_raw_argv_log(argv: list[str]) -> None:
    """Write raw argv for drag-and-drop debugging."""
    try:
        reports_dir = get_reports_dir()
        log_path = reports_dir / "startup_raw_argv.txt"
        log_path.write_text(json.dumps(argv, indent=2), encoding="utf-8")
    except Exception:
        pass


def _prompt_for_json_path() -> Path:
    """Prompt for a JSON path when none is provided."""
    prompt = "Enter path to a JSON file (or press Enter to exit): "
    while True:
        try:
            response = input(prompt).strip()
        except EOFError:
            print("No JSON file provided. Drag a JSON file onto the app or pass a path in the command line.")
            _pause_before_exit()
            sys.exit(1)
        if response == "":
            print("No JSON file provided. Exiting.")
            _pause_before_exit()
            sys.exit(1)
        candidate = Path(response).expanduser()
        if candidate.exists():
            return candidate
        print("Error: JSON file not found. Try again.")


def _pause_before_exit() -> None:
    """Pause briefly before exit when running without a TTY."""
    if not _stdin_is_tty():
        try:
            import time
            time.sleep(15)
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


def _ensure_python_version() -> None:
    """Exit with a clear message if Python version is too old."""
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or newer is required to run this tool.")
        sys.exit(1)
