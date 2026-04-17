# Game State Analysis

Game State Analysis is an event systems analysis tool for Unity-exported
event JSON. It loads event data, builds a structural interaction model,
explores reachable states, computes analysis metrics, and writes report output
for review during game development.

The current distribution model is aimed at evaluation and internal testing. The
tool is intended to help engineers, designers, and producers inspect branching
behavior, event interactions, and state-space risk before building more complex
production workflows around the same analysis backend.

## What It Does

- Loads Unity-exported narrative event JSON
- Builds a bipartite event-variable graph
- Explores reachable states from runtime state
- Computes structural and interaction metrics
- Writes analysis reports to the user's documents folder

## Running The Tool

The tool can be run from the command line or from a packaged desktop
application.

Command line example:

```bash
python3 analyze_events.py analyze /path/to/system_events.json
```

Packaged application behavior:

- If a JSON file is passed to the application, the tool analyzes that file
- In non-interactive mode, the tool uses a safe batch default and writes a
  separate normalized copy when casting is needed
- Reports are written to `~/Documents/analysis_reports/<timestamp>/`

## Report Output

Each analysis run creates a timestamped report directory containing files such
as:

- `analysis_results.txt`
- `completed.txt`
- `non_interactive_log.txt` when applicable
- `crash_log.txt` if a failure occurs before completion

## License

This project is distributed under the terms described in
[LICENSE.md].

## Disclaimer

This tool provides analytical metrics and insights based on event data.
These results are intended to support development decisions, not replace them.

Interpretation of results is the responsibility of the user.
